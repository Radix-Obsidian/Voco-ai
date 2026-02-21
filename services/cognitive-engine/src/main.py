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

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

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
    tts_active = False  # Track if TTS is currently playing

    async def _on_barge_in() -> None:
        """Signal Tauri to halt TTS playback immediately (barge-in)."""
        nonlocal tts_active
        if tts_active:  # Only trigger barge-in when TTS is actually playing
            await websocket.send_json({"type": "control", "action": "halt_audio_playback"})

    async def _on_turn_end() -> None:
        """Full pipeline: STT → LangGraph → (optional JSON-RPC) → TTS."""
        nonlocal audio_buffer, tts_active

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

        # --- Step 2.5: Check for proposal interrupt ---
        snapshot = await graph.aget_state(config)
        if snapshot.next and "proposal_review_node" in snapshot.next:
            proposals = snapshot.values.get("pending_proposals", [])
            project_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
            logger.info("[Pipeline] Interrupt: %d proposals pending review", len(proposals))

            # Send each proposal to frontend for HITL review
            for p in proposals:
                await websocket.send_json({
                    "type": "proposal",
                    "proposal_id": p.get("proposal_id", ""),
                    "action": p.get("action", ""),
                    "file_path": p.get("file_path", ""),
                    "content": p.get("content", ""),
                    "diff": p.get("diff", ""),
                    "description": p.get("description", ""),
                    "project_root": project_path,
                })

            # TTS: announce proposals
            desc_list = [p.get("description", p.get("file_path", "")) for p in proposals]
            summary_text = f"I have {len(proposals)} proposal{'s' if len(proposals) != 1 else ''} for your review. {'. '.join(desc_list)}. Say approve or reject."
            await websocket.send_json({"type": "control", "action": "tts_start", "text": summary_text})
            tts_active = True
            async for audio_chunk in tts.synthesize_stream(summary_text):
                await websocket.send_bytes(audio_chunk)
            await websocket.send_json({"type": "control", "action": "tts_end"})
            tts_active = False

            # Wait for proposal_decision from frontend
            decisions = []
            try:
                raw = await websocket.receive_text()
                decision_msg = json.loads(raw)
                if decision_msg.get("type") == "proposal_decision":
                    decisions = decision_msg.get("decisions", [])
            except Exception as exc:
                logger.warning("[Pipeline] Proposal decision error: %s", exc)

            # For approved create_file proposals, dispatch write_file to Tauri
            decision_map = {d["proposal_id"]: d for d in decisions}
            for p in proposals:
                pid = p.get("proposal_id", "")
                decision = decision_map.get(pid, {})
                if decision.get("status") == "approved" and p.get("action") == "create_file":
                    import os.path
                    file_path = p.get("file_path", "")
                    if not os.path.isabs(file_path):
                        file_path = os.path.join(project_path, file_path)
                    write_rpc = {
                        "jsonrpc": "2.0",
                        "id": f"write_{pid}",
                        "method": "local/write_file",
                        "params": {
                            "file_path": file_path,
                            "content": p.get("content", ""),
                            "project_root": project_path,
                        },
                    }
                    await websocket.send_json(write_rpc)
                    try:
                        write_resp_raw = await websocket.receive_text()
                        write_resp = json.loads(write_resp_raw)
                        logger.info("[Pipeline] write_file result for %s: %s", pid, write_resp.get("result", write_resp.get("error", "")))
                    except Exception as exc:
                        logger.warning("[Pipeline] write_file response error: %s", exc)

            # Resume graph with decisions
            result = await graph.ainvoke(
                Command(resume=None, update={"proposal_decisions": decisions}),
                config=config,
            )

        # --- Step 3: Dispatch JSON-RPC to Tauri if tool was called ---
        pending_action = result.get("pending_mcp_action")
        if pending_action:
            tool_name = pending_action.get("name", "")
            tool_args = pending_action.get("args", {})
            call_id = pending_action.get("id", "rpc-1")

            # Map LangGraph tool names → namespaced JSON-RPC methods (§7 contract)
            # Note: web_search (Tavily) and GitHub tools execute server-side.
            # Only search_codebase and execute_local_command need JSON-RPC dispatch.
            _fallback_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
            if tool_name == "execute_local_command":
                method = "local/execute_command"
                params = {
                    "command": tool_args.get("command", ""),
                    "project_path": tool_args.get("project_path", _fallback_path),
                }
            else:
                # search_codebase — default to local ripgrep
                method = "local/search_project"
                params = {
                    "pattern": tool_args.get("pattern", tool_args.get("query", "")),
                    "project_path": _fallback_path,
                }

            rpc_payload = {
                "type": "mcp_request",
                "jsonrpc": "2.0",
                "id": call_id,
                "method": method,
                "params": params,
            }
            logger.info("[Pipeline] Dispatching JSON-RPC to Tauri: %s", rpc_payload["method"])
            await websocket.send_json(rpc_payload)

            try:
                raw_response = await websocket.receive_text()
                mcp_response = json.loads(raw_response)
            except Exception as exc:
                logger.warning("[Pipeline] MCP response missing/closed: %s", exc)
                mcp_response = {"result": "", "error": f"mcp_response_error: {exc}"}

            has_result = "result" in mcp_response or mcp_response.get("type") == "mcp_result"
            tool_result = mcp_response.get("result", "") if has_result else ""
            if not has_result:
                tool_result = mcp_response.get("error", "mcp_response_empty")

            tool_id = mcp_response.get("id", pending_action.get("id", "rpc-1"))

            messages_with_tool_result = result["messages"] + [
                ToolMessage(content=str(tool_result), tool_call_id=tool_id)
            ]
            result = await graph.ainvoke(
                {"messages": messages_with_tool_result},
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
        await websocket.send_json({"type": "control", "action": "tts_start", "text": response_text})

        tts_active = True
        async for audio_chunk in tts.synthesize_stream(response_text):
            await websocket.send_bytes(audio_chunk)

        await websocket.send_json({"type": "control", "action": "tts_end"})
        tts_active = False

    vad.on_barge_in = _on_barge_in
    vad.on_turn_end = _on_turn_end

    try:
        while True:
            try:
                # Wait for message with 30s timeout (allows pauses during barge-in)
                message = await asyncio.wait_for(websocket.receive(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.debug("[Pipeline] WebSocket receive timeout (audio pause) — continuing")
                continue

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
