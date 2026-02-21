"""VocoVADStreamer — Silero VAD wrapper for barge-in and end-of-turn detection.

The Silero model is heavy to load (~2s, possible network download on first run).
Call ``load_silero_model()`` once at application startup and inject the returned
model into every ``VocoVADStreamer`` instance to avoid per-connection overhead.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import numpy as np
import torch


def load_silero_model() -> torch.nn.Module:
    """Download (once) and return the Silero VAD model in eval mode.

    Safe to call at process startup; subsequent calls use torch.hub's local
    cache and return in milliseconds.
    """
    model, _utils = torch.hub.load(
        "snakers4/silero-vad", "silero_vad", trust_repo=True
    )
    model.eval()
    return model


class VocoVADStreamer:
    """Streams raw PCM-16 audio through Silero VAD, firing async callbacks on
    barge-in (speech onset) and turn-end (sustained silence).

    Parameters
    ----------
    speech_threshold : float
        Silero probability above which a frame is considered speech.
    barge_in_frames : int
        Consecutive speech frames required to trigger barge-in (2 × 32ms = 64ms).
    silence_frames_for_turn_end : int
        Consecutive silence frames required to declare turn ended (25 × 32ms = 800ms).
    """

    SAMPLE_RATE = 16_000
    CHUNK_SAMPLES = 512  # 32ms at 16 kHz
    CHUNK_BYTES = CHUNK_SAMPLES * 2  # int16 → 2 bytes per sample

    def __init__(
        self,
        model: torch.nn.Module,
        *,
        speech_threshold: float = 0.5,
        barge_in_frames: int = 2,
        silence_frames_for_turn_end: int = 25,
    ) -> None:
        self._model = model

        self._speech_threshold = speech_threshold
        self._barge_in_frames = barge_in_frames
        self._silence_frames_for_turn_end = silence_frames_for_turn_end

        # Internal streaming state
        self._buffer: bytes = b""
        self._speech_frames: int = 0
        self._silence_frames: int = 0
        self._is_speaking: bool = False
        self._barge_in_fired: bool = False

        # Async callbacks — wired by the WebSocket endpoint
        self.on_barge_in: Callable[[], Awaitable[None]] | None = None
        self.on_turn_end: Callable[[], Awaitable[None]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_chunk(self, raw_bytes: bytes) -> None:
        """Append *raw_bytes* (PCM-16 LE, mono, 16 kHz) and run VAD on every
        complete 512-sample frame that can be extracted from the buffer."""
        self._buffer += raw_bytes

        while len(self._buffer) >= self.CHUNK_BYTES:
            frame_bytes = self._buffer[: self.CHUNK_BYTES]
            self._buffer = self._buffer[self.CHUNK_BYTES :]

            # Convert int16 PCM → float32 in [-1, 1]
            samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
            samples /= 32768.0
            chunk_tensor = torch.from_numpy(samples)

            # Silero inference
            prob: float = self._model(chunk_tensor, self.SAMPLE_RATE).item()

            if prob >= self._speech_threshold:
                self._speech_frames += 1
                self._silence_frames = 0

                if not self._is_speaking and self._speech_frames >= self._barge_in_frames:
                    self._is_speaking = True
                    if not self._barge_in_fired and self.on_barge_in is not None:
                        self._barge_in_fired = True
                        await self.on_barge_in()
            else:
                self._silence_frames += 1
                self._speech_frames = 0

                if self._is_speaking and self._silence_frames >= self._silence_frames_for_turn_end:
                    self._is_speaking = False
                    if self.on_turn_end is not None:
                        await self.on_turn_end()
                    self._reset_turn_state()

    def reset(self) -> None:
        """Reset all streaming state for a new turn."""
        self._buffer = b""
        self._reset_turn_state()
        self._model.reset_states()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_turn_state(self) -> None:
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._barge_in_fired = False
