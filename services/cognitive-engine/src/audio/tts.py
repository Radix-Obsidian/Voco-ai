"""Cartesia Sonic TTS client for sub-100ms streaming audio synthesis."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import AsyncGenerator

import websockets

logger = logging.getLogger(__name__)

_DEFAULT_VOICE_ID = "ee7ea9f8-c0c1-498c-9279-764d6b56d189"  # Cartesia "Oliver - Customer Chap"


class CartesiaTTS:
    """Streams text to Cartesia Sonic and yields raw PCM-16 audio chunks.

    Parameters
    ----------
    api_key : str
        Cartesia API key (from CARTESIA_API_KEY env var).
    voice_id : str
        Cartesia voice ID to use for synthesis.
    sample_rate : int
        Output PCM sample rate (default 16 kHz to match Tauri audio pipeline).
    """

    WS_URL = "wss://api.cartesia.ai/tts/websocket"
    API_VERSION = "2024-06-10"

    def __init__(
        self,
        api_key: str,
        *,
        voice_id: str = _DEFAULT_VOICE_ID,
        sample_rate: int = 16_000,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._sample_rate = sample_rate

    async def synthesize(self, text: str) -> bytes:
        """Synthesize *text* and return the complete PCM-16 audio as bytes."""
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks)

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize *text* and yield PCM-16 audio chunks as they arrive.

        Uses Cartesia's WebSocket streaming endpoint for sub-100ms TTFB.
        """
        if not self._api_key:
            logger.error("[TTS] CARTESIA_API_KEY is empty — cannot synthesize audio.")
            return

        ws_url = (
            f"{self.WS_URL}"
            f"?api_key={self._api_key}"
            f"&cartesia_version={self.API_VERSION}"
        )

        request_id = str(uuid.uuid4())
        payload = json.dumps({
            "model_id": "sonic-english",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self._voice_id,
            },
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._sample_rate,
            },
            "context_id": request_id,
            "continue": False,
        })

        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(payload)
                logger.info("[TTS] Synthesizing: %.80s...", text)

                async for raw in ws:
                    # Binary frame = raw PCM audio
                    if isinstance(raw, bytes):
                        yield raw
                        continue

                    # Text frame = JSON control message
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type", "")
                    if msg_type == "done":
                        logger.debug("[TTS] Stream complete for request %s", request_id)
                        break
                    elif msg_type == "error":
                        logger.error("[TTS] Cartesia error: %s", msg)
                        break
                    elif "data" in msg:
                        yield base64.b64decode(msg["data"])

        except websockets.exceptions.InvalidStatusCode as exc:
            logger.error("[TTS] Cartesia rejected connection (status %s) — check CARTESIA_API_KEY.", exc.status_code)
        except Exception as exc:
            logger.error("[TTS] WebSocket error: %s", exc)
