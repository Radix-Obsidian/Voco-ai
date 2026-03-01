"""VocoVADStreamer — Silero VAD wrapper for barge-in and end-of-turn detection.

Uses ONNX Runtime instead of PyTorch to avoid the ~800MB torch dependency.
The ONNX model file is downloaded once on first run (~2MB) and cached locally.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ONNX model URL and local cache path
_ONNX_MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
_ONNX_CACHE_DIR = Path.home() / ".cache" / "voco" / "silero-vad"
_ONNX_MODEL_PATH = _ONNX_CACHE_DIR / "silero_vad.onnx"


class _OnnxVADModel:
    """Lightweight ONNX wrapper for Silero VAD — replaces torch.hub.load().

    Mirrors the OnnxWrapper from silero-vad but without the torch dependency.
    Input: 512 float32 samples at 16kHz (32ms frame).
    Output: float probability of speech [0, 1].
    """

    def __init__(self, model_path: str | Path) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1

        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self.reset_states()

    def reset_states(self, batch_size: int = 1) -> None:
        """Reset LSTM hidden state and audio context."""
        self._state = np.zeros((2, batch_size, 128), dtype=np.float32)
        self._context = np.zeros(0, dtype=np.float32)
        self._last_sr = 0
        self._last_batch_size = 0

    def __call__(self, audio: np.ndarray, sr: int = 16000) -> float:
        """Run VAD inference on a single audio chunk.

        Parameters
        ----------
        audio : np.ndarray
            Float32 audio samples, shape (512,) for 16kHz.
        sr : int
            Sample rate (must be 16000).

        Returns
        -------
        float
            Speech probability [0, 1].
        """
        # Handle batch reset if needed
        batch_size = 1
        if self._last_batch_size != batch_size:
            self.reset_states(batch_size)
            self._last_batch_size = batch_size

        # Initialize context on first call or sample rate change
        if self._last_sr != sr or len(self._context) == 0:
            self._context = np.zeros(64, dtype=np.float32)  # 64 samples context for 16kHz
            self._last_sr = sr

        # Ensure correct shape: (1, chunk_size)
        if audio.ndim == 1:
            audio = audio[np.newaxis, :]  # (1, 512)

        # Prepend context
        context = self._context[np.newaxis, :] if self._context.ndim == 1 else self._context
        x = np.concatenate([context, audio], axis=1).astype(np.float32)

        # Run ONNX inference
        ort_inputs = {
            "input": x,
            "state": self._state,
            "sr": np.array(sr, dtype=np.int64),
        }

        out, new_state = self.session.run(None, ort_inputs)

        # Update state and context
        self._state = new_state
        self._context = audio[0, -64:]  # Last 64 samples as context for next call

        # out shape: (1, 1) — extract scalar probability
        return float(out.squeeze())


def _download_onnx_model() -> Path:
    """Download the Silero VAD ONNX model if not cached locally."""
    if _ONNX_MODEL_PATH.exists():
        logger.debug("[VAD] ONNX model cached at %s", _ONNX_MODEL_PATH)
        return _ONNX_MODEL_PATH

    logger.info("[VAD] Downloading Silero VAD ONNX model (~2MB)...")
    _ONNX_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    import urllib.request
    urllib.request.urlretrieve(_ONNX_MODEL_URL, _ONNX_MODEL_PATH)

    logger.info("[VAD] ONNX model saved to %s", _ONNX_MODEL_PATH)
    return _ONNX_MODEL_PATH


def load_silero_model() -> _OnnxVADModel:
    """Download (once) and return the Silero VAD ONNX model.

    Safe to call at process startup; subsequent calls use the local cache
    and return in milliseconds.
    """
    model_path = _download_onnx_model()
    model = _OnnxVADModel(model_path)
    logger.info("[VAD] Silero VAD (ONNX) model loaded.")
    return model


class VocoVADStreamer:
    """Streams raw PCM-16 audio through Silero VAD, firing async callbacks on
    barge-in (speech onset) and turn-end (sustained silence).

    Parameters
    ----------
    speech_threshold : float
        Silero probability above which a frame is considered speech.
    barge_in_frames : int
        Consecutive speech frames required to trigger barge-in (2 x 32ms = 64ms).
    silence_frames_for_turn_end : int
        Consecutive silence frames required to declare turn ended (25 x 32ms = 800ms).
    """

    SAMPLE_RATE = 16_000
    CHUNK_SAMPLES = 512  # 32ms at 16 kHz
    CHUNK_BYTES = CHUNK_SAMPLES * 2  # int16 -> 2 bytes per sample

    def __init__(
        self,
        model: _OnnxVADModel,
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

            # Convert int16 PCM -> float32 in [-1, 1]
            samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32)
            samples /= 32768.0

            # ONNX inference (no torch tensor needed)
            prob: float = self._model(samples, self.SAMPLE_RATE)

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
