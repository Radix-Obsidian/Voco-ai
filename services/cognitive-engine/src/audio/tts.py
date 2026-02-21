"""Cartesia Sonic TTS client for sub-100ms streaming audio synthesis."""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

_DEFAULT_VOICE_ID = "248be419-c632-4f23-adf6-5706a7c7d403"  # Cartesia "Jessica"


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
        """Synthesize *text* and return the complete PCM-16 audio as bytes.

        Suitable for short responses where buffering is acceptable.
        """
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks)

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize *text* and yield PCM-16 audio chunks as they arrive.

        Uses Cartesia's WebSocket streaming endpoint for sub-100ms TTFB.
        """
        import httpx

        ws_url = (
            f"{self.WS_URL}"
            f"?api_key={self._api_key}"
            f"&cartesia_version={self.API_VERSION}"
        )

        async with httpx.AsyncClient() as client:
            async with client.websocket_connect(ws_url) as ws:
                request_id = str(uuid.uuid4())
                payload = {
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
                }
                await ws.send(json.dumps(payload))
                logger.info("[TTS] Synthesizing: %.80s…", text)

                while True:
                    raw = await ws.receive()
                    if isinstance(raw, bytes):
                        yield raw
                        continue

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
                        import base64
                        yield base64.b64decode(msg["data"])
