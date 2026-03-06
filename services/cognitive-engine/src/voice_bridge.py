"""Voice Bridge — process-level singleton bridging MCP tool calls to the Tauri WebSocket.

When Claude Code (or any MCP client) calls `voco_voice_input`, this module:
  1. Sends a `voice_input_request` message to Tauri over the active WebSocket.
  2. Tauri auto-starts mic capture; audio flows through the normal VAD → STT pipeline.
  3. main.py detects `in_bridge_mode` and calls `resolve_transcript()` instead of LangGraph.
  4. The asyncio.Future completes and the MCP handler returns the transcript.

`voco_speak` streams TTS audio back through the same WebSocket connection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket
    from src.audio.stt import DeepgramSTT
    from src.audio.tts import CartesiaTTS

logger = logging.getLogger(__name__)


class VoiceBridge:
    """Singleton that bridges MCP voice tool calls ↔ Tauri WebSocket audio pipeline."""

    def __init__(self) -> None:
        self._ws: WebSocket | None = None
        self._stt: DeepgramSTT | None = None
        self._tts: CartesiaTTS | None = None
        self._pending_future: asyncio.Future[str] | None = None
        self._tts_playing: bool = False
        self._barged_in: bool = False

    # ------------------------------------------------------------------
    # WebSocket lifecycle (called by main.py)
    # ------------------------------------------------------------------

    def register_ws(
        self,
        ws: WebSocket,
        stt: DeepgramSTT,
        tts: CartesiaTTS,
    ) -> None:
        """Register the active Tauri WebSocket and audio services."""
        self._ws = ws
        self._stt = stt
        self._tts = tts
        logger.info("[VoiceBridge] WebSocket registered")

    def unregister_ws(self, ws: WebSocket) -> None:
        """Unregister a WebSocket (only if it matches the current one)."""
        if self._ws is not ws:
            return
        # Cancel any pending voice input request
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_exception(
                ConnectionError("Voco app disconnected during voice capture")
            )
        self._ws = None
        self._stt = None
        self._tts = None
        self._pending_future = None
        logger.info("[VoiceBridge] WebSocket unregistered")

    # ------------------------------------------------------------------
    # MCP-facing API (called by ide_mcp_server.py)
    # ------------------------------------------------------------------

    @property
    def in_bridge_mode(self) -> bool:
        """True when an MCP voice input request is waiting for a transcript."""
        return self._pending_future is not None and not self._pending_future.done()

    async def request_voice_input(
        self,
        prompt: str = "",
        timeout: float = 30.0,
    ) -> str:
        """Activate mic via Tauri and wait for STT transcript.

        Returns the transcript string.
        Raises RuntimeError if Voco app isn't connected or already capturing.
        Raises asyncio.TimeoutError after *timeout* seconds of silence.
        """
        if self._ws is None:
            raise RuntimeError(
                "Voco app is not connected. Open the Voco desktop app first."
            )
        if self.in_bridge_mode:
            raise RuntimeError(
                "A voice input request is already in progress. Wait for it to complete."
            )

        # Wait for TTS to fully drain before activating mic (prevents echo)
        if self._tts_playing:
            logger.info("[VoiceBridge] Waiting for TTS to finish before mic activation...")
            for _ in range(60):  # up to 6s
                await asyncio.sleep(0.1)
                if not self._tts_playing:
                    break

        # Extra post-TTS silence gap — the frontend suppresses mic for 2s
        # after tts_end; we wait for that window to fully close plus margin
        # so the mic doesn't pick up speaker reverb / room echo.
        await asyncio.sleep(2.5)

        loop = asyncio.get_running_loop()
        self._pending_future = loop.create_future()

        # Tell Tauri to activate mic capture
        try:
            await self._ws.send_json({
                "type": "voice_input_request",
                "prompt": prompt,
            })
        except Exception as exc:
            self._pending_future = None
            raise RuntimeError(f"Failed to send voice_input_request: {exc}") from exc

        logger.info("[VoiceBridge] Voice input requested (timeout=%.0fs)", timeout)

        try:
            transcript = await asyncio.wait_for(
                self._pending_future, timeout=timeout
            )
        except asyncio.TimeoutError:
            self._pending_future = None
            raise
        finally:
            # Ensure cleanup even on cancellation
            if self._pending_future and not self._pending_future.done():
                self._pending_future.cancel()
            self._pending_future = None

        return transcript

    async def speak(self, text: str) -> None:
        """Synthesize text via Cartesia TTS and stream audio to Tauri.

        Supports barge-in: if the user speaks during playback, TTS is
        cancelled immediately.  The frontend keeps the mic hot (sends
        ``tts_start_bargeable`` instead of ``tts_start``) so VAD can
        detect speech and call ``trigger_barge_in()``.

        Raises RuntimeError if Voco app isn't connected or TTS unavailable.
        """
        if self._ws is None:
            raise RuntimeError(
                "Voco app is not connected. Open the Voco desktop app first."
            )
        if self._tts is None:
            raise RuntimeError("TTS service not available")

        logger.info("[VoiceBridge] Speaking: %s", text[:80])

        self._tts_playing = True
        self._barged_in = False

        # Tell frontend TTS is starting but keep mic hot for voice barge-in.
        # VAD uses stricter thresholds (higher confidence + RMS energy gate)
        # to distinguish real speech from TTS echo through speakers.
        await self._ws.send_json({"type": "control", "action": "tts_start_bargeable"})
        await self._ws.send_json({"type": "control", "action": "bridge_tts_active"})

        try:
            async for chunk in self._tts.synthesize_stream(text):
                if self._barged_in:
                    logger.info("[VoiceBridge] Barge-in — stopping TTS stream")
                    break
                await self._ws.send_bytes(chunk)
        finally:
            # Signal frontend to suppress mic during speaker drain
            await self._ws.send_json({"type": "control", "action": "tts_end"})
            if not self._barged_in:
                # Wait long enough for speaker to fully drain so mic doesn't
                # pick up our own TTS output.  The frontend also suppresses
                # sendAudioChunk for 1.5 s after tts_end, but we add extra
                # padding here to be safe against slower speakers / reverb.
                await asyncio.sleep(2.5)
            self._tts_playing = False

    def trigger_barge_in(self) -> None:
        """Called by main.py when VAD detects speech during voice bridge TTS."""
        if self._tts_playing:
            self._barged_in = True
            logger.info("[VoiceBridge] Barge-in triggered")

    # ------------------------------------------------------------------
    # Transcript routing (called by main.py after STT completes)
    # ------------------------------------------------------------------

    def resolve_transcript(self, text: str) -> None:
        """Complete the pending voice input Future with the STT transcript."""
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_result(text)
            logger.info("[VoiceBridge] Transcript resolved (%d chars)", len(text))
        else:
            logger.warning(
                "[VoiceBridge] resolve_transcript called but no pending future"
            )


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

voice_bridge = VoiceBridge()
