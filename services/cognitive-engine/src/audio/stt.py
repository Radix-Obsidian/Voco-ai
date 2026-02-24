"""Deepgram streaming STT client for real-time PCM-16 transcription."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class DeepgramSTT:
    """Streams raw PCM-16 audio to Deepgram and yields transcript segments.

    Parameters
    ----------
    api_key : str
        Deepgram API key (from DEEPGRAM_API_KEY env var).
    sample_rate : int
        Sample rate of the incoming PCM stream (default 16 kHz).
    """

    WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, *, sample_rate: int = 16_000) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate

    async def transcribe_once(self, audio_bytes: bytes) -> str:
        """Send a complete audio buffer to Deepgram and return the transcript.

        Uses the pre-recorded endpoint for simplicity when a full turn's
        audio is available after VAD fires ``on_turn_end``.
        """
        import httpx

        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?encoding=linear16&sample_rate={self._sample_rate}"
            f"&channels=1&model=nova-2&smart_format=true"
        )
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "audio/raw",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, content=audio_bytes)
            response.raise_for_status()
            data = response.json()

        try:
            transcript: str = (
                data["results"]["channels"][0]["alternatives"][0]["transcript"]
            )
            logger.info("[STT] Transcript: %s", transcript)
            return transcript.strip()
        except (KeyError, IndexError):
            logger.warning("[STT] Empty or malformed Deepgram response: %s", data)
            return ""

    async def transcribe_stream(
        self, audio_chunks: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[str, None]:
        """Stream PCM-16 chunks to Deepgram, yielding interim transcripts.

        Uses Deepgram's streaming WebSocket endpoint with ``interim_results``.
        """
        import websockets

        ws_url = (
            f"{self.WS_URL}"
            f"?encoding=linear16&sample_rate={self._sample_rate}"
            f"&channels=1&model=nova-2&interim_results=true"
        )
        extra_headers = {"Authorization": f"Token {self._api_key}"}
        async with websockets.connect(ws_url, extra_headers=extra_headers) as ws:
            async for chunk in audio_chunks:
                await ws.send(chunk)
                raw = await ws.recv()
                text = raw if isinstance(raw, str) else raw.decode()
                try:
                    payload = json.loads(text)
                    transcript = (
                        payload.get("channel", {})
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    if transcript:
                        yield transcript
                except (json.JSONDecodeError, IndexError):
                    continue
