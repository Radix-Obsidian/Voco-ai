"""FastAPI app — health check + WebSocket audio-streaming bridge."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from src.audio.vad import VocoVADStreamer, load_silero_model
from src.graph.router import graph

logger = logging.getLogger(__name__)


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

    async def _on_barge_in() -> None:
        await websocket.send_json({"type": "control", "action": "halt_audio_playback"})

    async def _on_turn_end() -> None:
        await websocket.send_json({"type": "control", "action": "turn_ended"})
        config = {"configurable": {"thread_id": "main-session"}}
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="User stopped speaking. [MOCK STT]")]},
            config=config,
        )
        print("[LangGraph] Graph output:", result)

    vad.on_barge_in = _on_barge_in
    vad.on_turn_end = _on_turn_end

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                await vad.process_chunk(message["bytes"])
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    logger.debug("Control message received: %s", payload)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON text message ignored")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        vad.reset()
