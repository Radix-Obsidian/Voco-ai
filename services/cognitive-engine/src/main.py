"""FastAPI app — health check + WebSocket audio-streaming bridge.

Data flow (Milestone 5 vertical slice):
  1. Tauri streams raw PCM-16 bytes → VAD detects speech/silence.
  2. On turn-end: audio buffer → Deepgram STT → transcript string.
  3. Transcript → LangGraph (Claude 3.5 Sonnet with tools).
  4. If Claude calls search_codebase → JSON-RPC 2.0 dispatched to Tauri.
  5. Tauri executes ripgrep, sends result back as "mcp_result" message.
  6. Result injected into graph as ToolMessage → Claude synthesises answer.
  7. Answer text → Cartesia TTS → PCM-16 audio streamed back to Tauri.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, ToolMessage

from src.audio.stt import DeepgramSTT
from src.audio.tts import CartesiaTTS
from src.audio.vad import VocoVADStreamer, load_silero_model
from src.graph.router import graph

load_dotenv()
logger = logging.getLogger(__name__)

_THREAD_ID = "main-session"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load the Silero VAD model once at startup; share across all connections."""
    logger.info("Loading Silero VAD model…")
    app.state.silero_model = load_silero_model()
    logger.info("Silero VAD model ready.")
    yield
    # Nothing to teardown — model is in-process memory, GC handles it


app = FastAPI(title="Voco Cognitive Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws/voco-stream")
async def voco_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    vad = VocoVADStreamer(websocket.app.state.silero_model)

    stt = DeepgramSTT(api_key=os.environ["DEEPGRAM_API_KEY"])
    tts = CartesiaTTS(api_key=os.environ.get("CARTESIA_API_KEY", ""))

    audio_buffer: bytearray = bytearray()
    config = {"configurable": {"thread_id": _THREAD_ID}}

    async def _on_barge_in() -> None:
        """Signal Tauri to halt TTS playback immediately (barge-in)."""
        await websocket.send_json({"type": "control", "action": "halt_audio_playback"})

    async def _on_turn_end() -> None:
        """Full pipeline: STT → LangGraph → (optional JSON-RPC) → TTS."""
        nonlocal audio_buffer

        await websocket.send_json({"type": "control", "action": "turn_ended"})

        # --- Step 1: Transcribe buffered audio via Deepgram ---
        if not audio_buffer:
            logger.warning("[Pipeline] Turn ended with empty audio buffer — skipping.")
            return

        transcript = await stt.transcribe_once(bytes(audio_buffer))
        audio_buffer = bytearray()

        if not transcript:
            logger.info("[Pipeline] Empty transcript — user may have been silent.")
            return

        logger.info("[Pipeline] Transcript: %s", transcript)
        await websocket.send_json({"type": "transcript", "text": transcript})

        # --- Step 2: Run LangGraph (Claude 3.5 Sonnet) ---
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=transcript)]},
            config=config,
        )
        logger.info("[Pipeline] Graph complete. Messages: %d", len(result["messages"]))

        # --- Step 3: Dispatch JSON-RPC to Tauri if tool was called ---
        pending_action = result.get("pending_mcp_action")
        if pending_action:
            rpc_payload = {
                "type": "mcp_request",
                "jsonrpc": "2.0",
                "id": pending_action.get("id", "rpc-1"),
                "method": pending_action.get("name"),
                "params": pending_action.get("args", {}),
            }
            logger.info("[Pipeline] Dispatching JSON-RPC to Tauri: %s", rpc_payload["method"])
            await websocket.send_json(rpc_payload)

            # Tauri will respond with a "mcp_result" message — we wait for it
            raw_response = await websocket.receive_text()
            try:
                mcp_response = json.loads(raw_response)
            except json.JSONDecodeError:
                mcp_response = {"result": "", "error": "malformed response"}

            if mcp_response.get("type") == "mcp_result":
                tool_result = mcp_response.get("result", "")
                tool_id = pending_action.get("id", "rpc-1")

                result = await graph.ainvoke(
                    {"messages": [ToolMessage(content=tool_result, tool_call_id=tool_id)]},
                    config=config,
                )

        # --- Step 4: Extract final text and synthesise via Cartesia TTS ---
        final_message = result["messages"][-1]
        response_text: str = (
            final_message.content
            if isinstance(final_message.content, str)
            else str(final_message.content)
        )

        if not response_text.strip():
            logger.warning("[Pipeline] Empty response text — skipping TTS.")
            return

        logger.info("[Pipeline] Speaking: %.120s…", response_text)
        await websocket.send_json({"type": "tts_start", "text": response_text})

        async for audio_chunk in tts.synthesize_stream(response_text):
            await websocket.send_bytes(audio_chunk)

        await websocket.send_json({"type": "tts_end"})

    vad.on_barge_in = _on_barge_in
    vad.on_turn_end = _on_turn_end

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                chunk = message["bytes"]
                audio_buffer.extend(chunk)
                await vad.process_chunk(chunk)
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")

                    if msg_type == "mcp_result":
                        logger.debug("[WS] Received out-of-band mcp_result: %s", payload)
                    else:
                        logger.debug("[WS] Control message: %s", payload)
                except json.JSONDecodeError:
                    logger.warning("[WS] Non-JSON text message ignored")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        vad.reset()
        audio_buffer = bytearray()
