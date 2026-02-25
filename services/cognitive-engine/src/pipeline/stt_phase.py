"""STT phase — transcribe buffered audio via Deepgram."""

from __future__ import annotations

import logging

from src.audio.stt import DeepgramSTT
from src.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer()


async def run_stt(audio_buffer: bytearray, stt_client: DeepgramSTT) -> str:
    """Transcribe *audio_buffer* and return the transcript string.

    Returns an empty string if the buffer is too small or the transcript
    is trivial (< 2 chars).
    """
    with tracer.start_as_current_span("voco.stt", attributes={"audio.bytes": len(audio_buffer)}):
        if not audio_buffer:
            logger.warning("[STT] Empty audio buffer — skipping.")
            return ""

        if len(audio_buffer) < 6400:  # < 200ms at 16kHz mono 16-bit
            logger.info("[STT] Buffer too small (%d bytes) — likely noise.", len(audio_buffer))
            return ""

        transcript = await stt_client.transcribe_once(bytes(audio_buffer))

        if not transcript or len(transcript.strip()) < 2:
            logger.info("[STT] Empty/trivial transcript — user may have been silent.")
            return ""

        logger.info("[STT] Transcript: %s", transcript)
        return transcript
