"""TTS phase — synthesize response text via Cartesia and stream audio."""

from __future__ import annotations

import logging

from fastapi import WebSocket

from src.audio.tts import CartesiaTTS
from src.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer()


async def run_tts(text: str, tts_client: CartesiaTTS, websocket: WebSocket) -> int:
    """Stream TTS audio for *text* to the frontend via *websocket*.

    Returns the number of audio chunks sent.
    """
    with tracer.start_as_current_span("voco.tts", attributes={"text.len": len(text)}):
        chunk_count = 0
        async for audio_chunk in tts_client.synthesize_stream(text):
            await websocket.send_bytes(audio_chunk)
            chunk_count += 1

        logger.info("[TTS] Sent %d audio chunks to frontend.", chunk_count)
        if chunk_count == 0:
            logger.warning("[TTS] Zero audio chunks — Cartesia may have rejected the request.")

        return chunk_count
