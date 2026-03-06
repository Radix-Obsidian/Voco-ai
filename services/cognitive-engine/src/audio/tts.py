"""Cartesia Sonic TTS client for sub-100ms streaming audio synthesis."""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from typing import AsyncGenerator

import websockets

logger = logging.getLogger(__name__)

_DEFAULT_VOICE_ID = "ee7ea9f8-c0c1-498c-9279-764d6b56d189"  # Cartesia "Oliver - Customer Chap"


class CartesiaTTS:
    """Streams text to Cartesia Sonic and yields raw PCM-16 audio chunks.

    Parameters
    ----------
    api_key : str | None
        Cartesia API key. If ``None`` (default), reads ``CARTESIA_API_KEY``
        from ``os.environ`` at synthesis time so hot-swapped keys take effect
        immediately without reconnecting.
    voice_id : str
        Cartesia voice ID to use for synthesis.
    sample_rate : int
        Output PCM sample rate (default 16 kHz to match Tauri audio pipeline).
    """

    WS_URL = "wss://api.cartesia.ai/tts/websocket"
    API_VERSION = "2025-04-16"
    MAX_RETRIES = 2

    def __init__(
        self,
        api_key: str | None = None,
        *,
        voice_id: str = _DEFAULT_VOICE_ID,
        sample_rate: int = 16_000,
    ) -> None:
        self._explicit_key = api_key or None
        self._voice_id = voice_id
        self._sample_rate = sample_rate

    @property
    def _api_key(self) -> str:
        """Resolve API key: explicit > env var > empty."""
        return self._explicit_key or os.environ.get("CARTESIA_API_KEY", "")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize *text* and return the complete PCM-16 audio as bytes."""
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks)

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize *text* and yield PCM-16 audio chunks as they arrive.

        Uses Cartesia's WebSocket streaming endpoint for sub-100ms TTFB.
        Retries up to MAX_RETRIES times on transient failures (zero chunks,
        connection drops) before giving up.
        """
        api_key = self._api_key
        if not api_key:
            raise ValueError("CARTESIA_API_KEY is empty — cannot synthesize audio. Set it in Settings or .env.")

        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            chunk_count = 0
            try:
                async for chunk in self._do_synthesize(api_key, text):
                    chunk_count += 1
                    yield chunk

                if chunk_count > 0:
                    return  # Success
                else:
                    logger.warning(
                        "[TTS] Attempt %d/%d: zero audio chunks returned for %.50s...",
                        attempt, self.MAX_RETRIES, text,
                    )
                    last_error = RuntimeError("Cartesia returned zero audio chunks")
            except websockets.exceptions.InvalidStatusCode as exc:
                logger.error(
                    "[TTS] Attempt %d/%d: Cartesia rejected connection (HTTP %s) — key may be invalid.",
                    attempt, self.MAX_RETRIES, exc.status_code,
                )
                last_error = exc
            except Exception as exc:
                logger.error(
                    "[TTS] Attempt %d/%d: WebSocket error: %s",
                    attempt, self.MAX_RETRIES, exc,
                )
                last_error = exc

            # If we already yielded some chunks, don't retry (partial audio is worse than none)
            if chunk_count > 0:
                return

        # All retries exhausted
        if last_error:
            raise last_error

    async def _do_synthesize(self, api_key: str, text: str) -> AsyncGenerator[bytes, None]:
        """Single synthesis attempt — opens a fresh WebSocket connection."""
        ws_url = (
            f"{self.WS_URL}"
            f"?api_key={api_key}"
            f"&cartesia_version={self.API_VERSION}"
        )

        request_id = str(uuid.uuid4())
        payload = json.dumps({
            "model_id": "sonic-3",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self._voice_id,
            },
            "language": "en",
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._sample_rate,
            },
            "context_id": request_id,
            "continue": False,
        })

        async with websockets.connect(ws_url) as ws:
            await ws.send(payload)
            logger.info("[TTS] Synthesizing (req %s): %.80s...", request_id[:8], text)

            async for raw in ws:
                # Cartesia sends JSON text frames per official docs.
                # Binary frames are also accepted as a fallback.
                if isinstance(raw, bytes):
                    yield raw
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("[TTS] Non-JSON frame: %.200s", raw)
                    continue

                msg_type = msg.get("type", "")
                if msg_type == "chunk" and "data" in msg:
                    # Official format: {"type": "chunk", "data": "<base64>"}
                    yield base64.b64decode(msg["data"])
                elif msg_type == "done":
                    logger.debug("[TTS] Stream complete for request %s", request_id[:8])
                    break
                elif msg_type == "error":
                    error_detail = msg.get("error", msg.get("message", msg))
                    logger.error("[TTS] Cartesia error response: %s", error_detail)
                    raise RuntimeError(f"Cartesia API error: {error_detail}")
                elif "data" in msg:
                    # Legacy fallback: base64 data without type field
                    yield base64.b64decode(msg["data"])
                else:
                    logger.debug("[TTS] Unknown message type: %s", msg)
