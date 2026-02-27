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
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from src.billing.routes import router as billing_router, report_voice_turn
from src.db import sync_ledger_to_supabase, update_ledger_node
from src.graph.background_worker import BackgroundJobQueue
from src.ide_mcp_server import attach_ide_mcp_routes

from src.debug import debug_logger
from src.audio.stt import DeepgramSTT
from src.audio.tts import CartesiaTTS
from src.audio.vad import VocoVADStreamer, load_silero_model
from src.graph.router import compile_graph
from src.graph.checkpointer import get_checkpointer, prune_checkpoints
from src.graph.tools import mcp_registry
from src.graph.nodes import set_session_token
from src.telemetry import init_telemetry, get_tracer, current_trace_id
from src.errors import ErrorCode, VocoError, send_error
from src.constants import (
    AUDIO_MIN_BUFFER_SIZE,
    SILENCE_FRAMES_FOR_TURN_END,
    WEBSOCKET_RECEIVE_TIMEOUT,
    WEBSOCKET_MESSAGE_TIMEOUT,
    WEBSOCKET_SCAN_TIMEOUT,
    HITL_PROPOSAL_TIMEOUT,
    HITL_COMMAND_TIMEOUT,
    RPC_BACKGROUND_TIMEOUT,
    RPC_FUTURE_MAX_AGE,
    TTS_GRACE_PERIOD,
    TTS_TAIL_DELAY,
    ALLOWED_ENV_KEYS,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Tauri app identifier from tauri.conf.json — used to locate config.json.
_TAURI_APP_ID = "com.voco.mcp-gateway"
_ALLOWED_ENV_KEYS = ALLOWED_ENV_KEYS


# In-memory store for the current Live Sandbox HTML (single-user desktop app).
# Populated by the generate_and_preview_mvp / update_sandbox_preview tool handlers.
_sandbox_html: dict[str, str] = {"current": ""}

_SANDBOX_EMPTY_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voco Sandbox</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-950 text-white flex items-center justify-center min-h-screen">
<div class="text-center space-y-3">
  <div class="text-4xl">🚀</div>
  <p class="text-zinc-400 text-sm">No sandbox active yet.</p>
  <p class="text-zinc-600 text-xs">Ask Voco to build an app and it will appear here.</p>
</div>
</body></html>"""


def _load_native_config() -> None:
    """Read API keys written by Rust's `save_api_keys` into os.environ.

    Path mirrors Tauri's app_config_dir per platform:
      Windows  : %APPDATA%\\com.voco.mcp-gateway\\config.json
      macOS    : ~/Library/Application Support/com.voco.mcp-gateway/config.json
      Linux    : ~/.config/com.voco.mcp-gateway/config.json

    Only sets keys that are not already in os.environ so .env values can still
    override during local development.
    """
    import sys
    from pathlib import Path

    # Assign to a plain `str` so Pyright doesn't narrow to a platform literal
    # and flag the non-Windows branches as unreachable.
    platform: str = sys.platform
    if platform == "win32":
        base = os.environ.get("APPDATA", "")
        config_path = Path(base) / _TAURI_APP_ID / "config.json"
    elif platform == "darwin":
        config_path = Path.home() / "Library" / "Application Support" / _TAURI_APP_ID / "config.json"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base_dir = Path(xdg) if xdg else Path.home() / ".config"
        config_path = base_dir / _TAURI_APP_ID / "config.json"

    if not config_path.exists():
        logger.debug("[Config] No native config at %s — using .env only.", config_path)
        return

    try:
        keys: dict = json.loads(config_path.read_text(encoding="utf-8"))
        loaded = []
        for k, v in keys.items():
            if k in _ALLOWED_ENV_KEYS and isinstance(v, str) and v:
                os.environ.setdefault(k, v)   # .env wins if already set
                loaded.append(k)
        if loaded:
            logger.info("[Config] Loaded from native config: %s", loaded)
    except Exception as exc:
        logger.warning("[Config] Failed to parse native config: %s", exc)


def _new_thread_id() -> str:
    return f"session-{uuid.uuid4().hex[:8]}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load the Silero VAD model and connect external MCP servers at startup."""
    _load_native_config()  # pre-populate os.environ from Tauri's config.json

    # Observability: OpenTelemetry + FastAPI auto-instrumentation
    init_telemetry()
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[Telemetry] FastAPI auto-instrumentation active.")
    except Exception as otel_exc:
        logger.warning("[Telemetry] FastAPI instrumentation skipped: %s", otel_exc)

    logger.info("Loading Silero VAD model…")
    app.state.silero_model = load_silero_model()
    logger.info("Silero VAD model ready.")

    logger.info("Initialising Universal MCP Registry…")
    await mcp_registry.initialize()
    logger.info("MCP Registry ready — %d external tools.", len(mcp_registry.get_tools()))

    yield

    await mcp_registry.shutdown()


app = FastAPI(title="Voco Cognitive Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

attach_ide_mcp_routes(app)
app.include_router(billing_router)


@app.get("/debug/events")
async def get_debug_events(limit: int = 100) -> dict:
    """Return recent debug events for troubleshooting."""
    return {"events": debug_logger.get_recent_events(limit)}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/sandbox", response_class=HTMLResponse)
async def sandbox_preview() -> HTMLResponse:
    """Serve the current Live Sandbox HTML generated by Voco."""
    html = _sandbox_html.get("current") or _SANDBOX_EMPTY_PAGE
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
    )


@app.websocket("/ws/voco-stream")
async def voco_stream(websocket: WebSocket) -> None:
    # A2: Validate token before accepting connection
    token = websocket.query_params.get("token", "")
    expected = os.environ.get("VOCO_WS_TOKEN", "")
    if expected and token != expected:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    try:
        await websocket.accept()
    except Exception as accept_exc:
        logger.error("[WS] Failed to accept WebSocket: %s", accept_exc)
        return
    vad = VocoVADStreamer(
        websocket.app.state.silero_model,
        silence_frames_for_turn_end=SILENCE_FRAMES_FOR_TURN_END,
    )

    stt = DeepgramSTT(api_key=os.environ.get("DEEPGRAM_API_KEY", ""))
    tts = CartesiaTTS(api_key=os.environ.get("CARTESIA_API_KEY", ""))

    audio_buffer: bytearray = bytearray()
    thread_id = _new_thread_id()
    config = {"configurable": {"thread_id": thread_id}}
    logger.info("[Session] New thread: %s", thread_id)
    debug_logger.log_ws_event("connect", thread_id, {"url": str(websocket.url)})

    # Per-session SQLite checkpointer — persists graph state across restarts (GAP #2).
    _session_checkpointer = await get_checkpointer(thread_id)
    graph = compile_graph(checkpointer=_session_checkpointer)
    tts_active = False  # Track if TTS is currently playing

    # Observability: send session_id to frontend so logs can be correlated
    tracer = get_tracer()
    await websocket.send_json({"type": "session_init", "session_id": thread_id})

    # Per-session auth state (populated by auth_sync from frontend)
    _auth_uid: str = "local"
    _auth_token: str = ""

    # Milestone 11: Instant ACK + Background Queue
    # Each pending Tauri RPC call gets an asyncio.Future keyed on the call_id.
    # The main receive loop resolves these futures when mcp_result arrives,
    # waking up the background task that's waiting on them.
    background_queue = BackgroundJobQueue()
    _pending_rpc_futures: dict[str, asyncio.Future] = {}
    _rpc_futures_timestamps: dict[str, float] = {}

    # Session-level metrics for observability (Issue #6)
    _session_metrics = {"timeout_count": 0, "rpc_count": 0, "turn_count": 0}

    async def _cleanup_stale_futures(max_age_seconds: float = RPC_FUTURE_MAX_AGE) -> None:
        """Remove stale futures that have timed out or completed."""
        import time
        now = time.monotonic()
        stale = [
            fid for fid, ts in _rpc_futures_timestamps.items()
            if now - ts > max_age_seconds or (_pending_rpc_futures.get(fid) and _pending_rpc_futures[fid].done())
        ]
        for fid in stale:
            _pending_rpc_futures.pop(fid, None)
            _rpc_futures_timestamps.pop(fid, None)
        if stale:
            logger.debug("[RPC] Cleaned up %d stale futures", len(stale))

    async def _on_barge_in() -> None:
        """Signal Tauri to halt TTS playback immediately (barge-in)."""
        nonlocal tts_active
        if tts_active:  # Only trigger barge-in when TTS is actually playing
            await websocket.send_json({"type": "control", "action": "halt_audio_playback"})

    _last_detected_domain = "general"

    async def _send_ledger_update(
        domain: str = "general",
        context_router: str = "pending",
        orchestrator: str = "pending",
        tools: str = "pending",
    ) -> None:
        """Emit a ledger_update message so the frontend can render the Visual Ledger."""
        nonlocal _last_detected_domain
        _last_detected_domain = domain

        # Map domain to appropriate icon types
        domain_icon = {
            "database": "Database",
            "ui": "FileCode2",
            "api": "Terminal",
            "devops": "Terminal",
            "git": "Terminal",
            "general": "FileCode2",
        }
        icon = domain_icon.get(domain, "FileCode2")

        await websocket.send_json({
            "type": "ledger_update",
            "payload": {
                "domain": domain.title(),
                "nodes": [
                    {"id": "1", "iconType": icon, "title": "Domain Paged", "description": f"Loaded {domain} context", "status": context_router},
                    {"id": "2", "iconType": "FileCode2", "title": "Orchestrator", "description": "Claude reasoning", "status": orchestrator},
                    {"id": "3", "iconType": "Terminal", "title": "Execute", "description": "Run actions", "status": tools},
                ],
            },
        })

    async def _send_ledger_clear() -> None:
        """Clear the Visual Ledger from the frontend."""
        await websocket.send_json({"type": "ledger_clear"})

    async def _on_turn_end(text_override: str | None = None) -> None:
        """Full pipeline: STT → LangGraph → (optional JSON-RPC) → TTS.

        When ``text_override`` is provided the STT step is skipped entirely —
        the text arrives directly from the "Type instead" input box and is fed
        straight into LangGraph.  Billing still fires at the end so typed turns
        are metered identically to spoken turns.
        """
        nonlocal audio_buffer, tts_active

        _session_metrics["turn_count"] += 1
        await websocket.send_json({"type": "control", "action": "turn_ended", "turn_count": _session_metrics["turn_count"]})

        if text_override is not None:
            # --- Text input path: skip STT ---
            transcript = text_override
            logger.info("[Pipeline] Text input: %.120s", transcript)
            await websocket.send_json({"type": "transcript", "text": transcript})
        else:
            # --- Voice path: transcribe buffered audio via Deepgram ---
            if not audio_buffer:
                logger.warning("[Pipeline] Turn ended with empty audio buffer — skipping.")
                return

            # Require a minimum buffer size to avoid transcribing noise/clicks
            if len(audio_buffer) < AUDIO_MIN_BUFFER_SIZE:
                logger.info("[Pipeline] Audio buffer too small (%d bytes) — likely noise, skipping.", len(audio_buffer))
                audio_buffer = bytearray()
                return

            transcript = await stt.transcribe_once(bytes(audio_buffer))
            audio_buffer = bytearray()

            if not transcript or len(transcript.strip()) < 2:
                logger.info("[Pipeline] Empty/trivial transcript — user may have been silent.")
                return

            logger.info("[Pipeline] Transcript: %s", transcript)
            await websocket.send_json({"type": "transcript", "text": transcript})

        # --- Step 2: Run LangGraph (Claude 3.5 Sonnet) ---
        await _send_ledger_update(domain="general", context_router="active", orchestrator="pending", tools="pending")

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=transcript)]},
            config=config,
        )
        logger.info("[Pipeline] Graph complete. Messages: %d", len(result["messages"]))

        has_tools = bool(result.get("pending_mcp_action") or result.get("pending_proposals") or result.get("pending_commands"))
        detected_domain = result.get("focused_context", "").split("Focus: ")[1].split(".")[0].lower() if "Focus: " in result.get("focused_context", "") else "general"
        await _send_ledger_update(
            domain=detected_domain,
            context_router="completed",
            orchestrator="completed",
            tools="active" if has_tools else "completed",
        )

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
                # Co-work: send an additional cowork_edit message for IDE-native display
                if p.get("cowork_ready"):
                    await websocket.send_json({
                        "type": "cowork_edit",
                        "proposal_id": p.get("proposal_id", ""),
                        "action": p.get("action", ""),
                        "file_path": p.get("file_path", ""),
                        "content": p.get("content", ""),
                        "diff": p.get("diff", ""),
                        "description": p.get("description", ""),
                        "project_root": project_path,
                    })
                    logger.info("[CoWork] IDE-native edit sent for %s", p.get("file_path", ""))

            # TTS: announce proposals
            desc_list = [p.get("description", p.get("file_path", "")) for p in proposals]
            summary_text = f"I have {len(proposals)} proposal{'s' if len(proposals) != 1 else ''} for your review. {'. '.join(desc_list)}. Say approve or reject."
            await websocket.send_json({"type": "control", "action": "tts_start", "text": summary_text, "tts_active": True})
            tts_active = True
            async for audio_chunk in tts.synthesize_stream(summary_text):
                await websocket.send_bytes(audio_chunk)
            await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
            tts_active = False
            await asyncio.sleep(TTS_GRACE_PERIOD)
            vad.reset()
            audio_buffer = bytearray()

            # Wait for proposal_decision from frontend (filtered receive)
            decisions = []
            try:
                decision_msg = await _receive_filtered("proposal_decision", timeout=HITL_PROPOSAL_TIMEOUT)
                decisions = decision_msg.get("decisions", [])
            except asyncio.TimeoutError:
                logger.warning("[Pipeline] Proposal decision timeout - user did not respond")
            except Exception as exc:
                logger.warning("[Pipeline] Proposal decision error: %s", exc)

            # For approved create_file proposals, dispatch write_file to Tauri
            decision_map = {d["proposal_id"]: d for d in decisions}
            for p in proposals:
                pid = p.get("proposal_id", "")
                decision = decision_map.get(pid, {})
                if decision.get("status") == "approved" and p.get("action") == "create_file":
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

        # --- Step 2.6: Check for command sandbox interrupt ---
        snapshot = await graph.aget_state(config)
        if snapshot.next and "command_review_node" in snapshot.next:
            commands = snapshot.values.get("pending_commands", [])
            project_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
            logger.info("[Pipeline] Command interrupt: %d commands pending approval", len(commands))

            # Send each command proposal to frontend for HITL review
            for c in commands:
                await websocket.send_json({
                    "type": "command_proposal",
                    "command_id": c.get("command_id", ""),
                    "command": c.get("command", ""),
                    "description": c.get("description", ""),
                    "project_path": c.get("project_path", project_path),
                })

            # TTS: announce commands
            cmd_descs = [c.get("description", c.get("command", "")) for c in commands]
            cmd_summary = f"I need to run {len(commands)} command{'s' if len(commands) != 1 else ''}. {'. '.join(cmd_descs)}. Approve or reject."
            await websocket.send_json({"type": "control", "action": "tts_start", "text": cmd_summary, "tts_active": True})
            tts_active = True
            async for audio_chunk in tts.synthesize_stream(cmd_summary):
                await websocket.send_bytes(audio_chunk)
            await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
            tts_active = False
            await asyncio.sleep(TTS_GRACE_PERIOD)
            vad.reset()
            audio_buffer = bytearray()

            # Wait for command_decision from frontend (filtered receive)
            cmd_decisions = []
            try:
                decision_msg = await _receive_filtered("command_decision", timeout=HITL_COMMAND_TIMEOUT)
                cmd_decisions = decision_msg.get("decisions", [])
            except asyncio.TimeoutError:
                logger.warning("[Pipeline] Command decision timeout - user did not respond")
            except Exception as exc:
                logger.warning("[Pipeline] Command decision error: %s", exc)

            # For approved commands, dispatch execute_command to Tauri
            for d in cmd_decisions:
                if d.get("status") != "approved":
                    continue
                cid = d["command_id"]
                # Find the matching command
                cmd_data = next((c for c in commands if c.get("command_id") == cid), None)
                if not cmd_data:
                    continue
                exec_rpc = {
                    "jsonrpc": "2.0",
                    "id": f"cmd_{cid}",
                    "method": "local/execute_command",
                    "params": {
                        "command": cmd_data.get("command", ""),
                        "project_path": cmd_data.get("project_path", project_path),
                    },
                }
                await websocket.send_json(exec_rpc)
                try:
                    exec_resp_raw = await websocket.receive_text()
                    exec_resp = json.loads(exec_resp_raw)
                    cmd_output = exec_resp.get("result", exec_resp.get("error", {}).get("message", ""))
                    d["output"] = str(cmd_output)
                    logger.info("[Pipeline] execute_command result for %s: %.200s", cid, cmd_output)
                except Exception as exc:
                    d["output"] = f"execution error: {exc}"
                    logger.warning("[Pipeline] execute_command response error: %s", exc)

            # Resume graph with command decisions (including output)
            result = await graph.ainvoke(
                Command(resume=None, update={"command_decisions": cmd_decisions}),
                config=config,
            )

        # --- Step 3: Instant ACK + Background Dispatch (Milestone 11) ---
        # The ACK ToolMessage instantly resolves Claude's tool_call, satisfying
        # Anthropic's strict requirement that an AIMessage with tool_calls must be
        # immediately followed by a ToolMessage.  The real Tauri RPC runs inside
        # a background asyncio.Task so the AI is free to keep talking.  When the
        # task finishes it injects a SystemMessage into the LangGraph checkpoint
        # via graph.aupdate_state(); Claude sees the result on the user's next turn.
        pending_action = result.get("pending_mcp_action")
        if pending_action:
            tool_name = pending_action.get("name", "")
            tool_args = pending_action.get("args", {})
            call_id = pending_action.get("id", f"rpc-{uuid.uuid4().hex[:8]}")
            _screen_handled = False

            # ----------------------------------------------------------------
            # Phase 3: Voco Eyes — inline screen analysis
            # Screen capture is handled synchronously (not background) because
            # Claude needs the images immediately to produce a useful response.
            # ----------------------------------------------------------------
            if tool_name == "analyze_screen":
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                logger.info("[VocoEyes] Requesting screen frames for call_id=%s", call_id)

                # 1. Ask frontend to call get_recent_frames() via Tauri invoke
                await websocket.send_json({"type": "screen_capture_request", "id": call_id})

                # 2. Wait for the frontend to respond with the frames (10 s timeout)
                frames: list[str] = []
                media_type = "image/jpeg"
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=WEBSOCKET_MESSAGE_TIMEOUT)
                    frames_msg = json.loads(raw)
                    if frames_msg.get("type") == "screen_frames":
                        frames = frames_msg.get("frames", [])
                        media_type = frames_msg.get("media_type", "image/jpeg")
                except asyncio.TimeoutError:
                    logger.warning("[VocoEyes] Timed out waiting for screen_frames")
                except Exception as exc:
                    logger.warning("[VocoEyes] Error receiving screen_frames: %s", exc)

                # 3. Build multimodal ToolMessage — images + context text
                user_desc = tool_args.get("user_description", "")
                if frames:
                    sampled = frames[-5:]  # max 5 frames (Anthropic image limit)
                    vision_content: list = [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{f}"},
                        }
                        for f in sampled
                    ]
                    vision_content.append({
                        "type": "text",
                        "text": (
                            f"These are {len(sampled)} sequential screenshots of the user's screen "
                            "captured at 500ms intervals (most recent last). "
                            + (f"User says: {user_desc}. " if user_desc else "")
                            + "Analyze the visual state and diagnose any visible bugs, errors, or UI issues."
                        ),
                    })
                    screen_tool_msg = ToolMessage(content=vision_content, tool_call_id=call_id)
                    logger.info("[VocoEyes] Sending %d frames to Claude vision.", len(sampled))
                else:
                    screen_tool_msg = ToolMessage(
                        content="Screen buffer was empty — no frames captured yet. Tell the user to try again in a moment.",
                        tool_call_id=call_id,
                    )
                    logger.warning("[VocoEyes] No frames in buffer.")

                # 4. Re-invoke graph — Claude produces a visual analysis response
                result = await graph.ainvoke({"messages": [screen_tool_msg]}, config=config)
                _screen_handled = True

            # ----------------------------------------------------------------
            # Phase 4: Voco Auto-Sec — inline security scan
            # Like screen analysis, this is synchronous: Rust scans the
            # project instantly (no network calls) and Claude analyzes the
            # JSON findings immediately.
            # ----------------------------------------------------------------
            elif tool_name == "scan_vulnerabilities":
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                project_path_arg = tool_args.get("project_path", os.environ.get("VOCO_PROJECT_PATH", ""))
                logger.info("[AutoSec] Requesting security scan for call_id=%s path=%s", call_id, project_path_arg)

                # 1. Ask frontend to invoke scan_security via Tauri
                await websocket.send_json({
                    "type": "scan_security_request",
                    "id": call_id,
                    "project_path": project_path_arg,
                })

                # 2. Await scan findings (30 s — project may have many env files)
                findings_str = ""
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=WEBSOCKET_SCAN_TIMEOUT)
                    scan_msg = json.loads(raw)
                    if scan_msg.get("type") == "scan_security_result":
                        findings_str = json.dumps(scan_msg.get("findings", {}), indent=2)
                    else:
                        findings_str = json.dumps(scan_msg, indent=2)
                except asyncio.TimeoutError:
                    logger.warning("[AutoSec] Timed out waiting for scan_security_result")
                    findings_str = '{"error": "Scan timed out after 30 seconds."}'
                except Exception as exc:
                    logger.warning("[AutoSec] Error receiving scan result: %s", exc)
                    findings_str = json.dumps({"error": str(exc)})

                # 3. Build ToolMessage with findings for Claude to analyze
                sec_tool_msg = ToolMessage(
                    content=(
                        "Security scan complete. Analyze these findings and provide a "
                        "prioritized threat summary with actionable remediation steps. "
                        "Be concise — your response will be spoken aloud.\n\n"
                        + findings_str
                    ),
                    tool_call_id=call_id,
                )
                logger.info("[AutoSec] Findings ready (%d chars), invoking Claude.", len(findings_str))

                # 4. Re-invoke graph — Claude produces spoken security analysis
                result = await graph.ainvoke({"messages": [sec_tool_msg]}, config=config)
                _screen_handled = True

            # ----------------------------------------------------------------
            # Phase 5: Live Sandbox — generate_and_preview_mvp / update_sandbox_preview
            # Claude provides the complete HTML as a tool argument; we store it
            # in _sandbox_html and serve it via GET /sandbox. The frontend opens
            # an iframe pointing at http://localhost:8001/sandbox.
            # ----------------------------------------------------------------
            elif tool_name in ("generate_and_preview_mvp", "update_sandbox_preview"):
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                html_code = tool_args.get("html_code", "")
                _sandbox_html["current"] = html_code
                is_update = tool_name == "update_sandbox_preview"
                sandbox_url = "http://localhost:8001/sandbox"

                await websocket.send_json({
                    "type": "sandbox_updated" if is_update else "sandbox_live",
                    "url": sandbox_url,
                })
                logger.info(
                    "[Sandbox] %s served at %s (%d bytes)",
                    "Updated" if is_update else "Live",
                    sandbox_url,
                    len(html_code),
                )

                sandbox_tool_msg = ToolMessage(
                    content=(
                        "Sandbox preview updated. The user can see the changes instantly."
                        if is_update else
                        "MVP sandbox is live at http://localhost:8001/sandbox. "
                        "The preview is now visible on the right side of the screen."
                    ),
                    tool_call_id=call_id,
                )
                result = await graph.ainvoke({"messages": [sandbox_tool_msg]}, config=config)
                _screen_handled = True

            # ----------------------------------------------------------------
            # Standard: Instant ACK + Background Dispatch (all non-screen tools)
            # ----------------------------------------------------------------
            if not _screen_handled:
                _fallback_path = (
                    tool_args.get("project_path", "")
                    or result.get("active_project_path")
                    or os.environ.get("VOCO_PROJECT_PATH", "")
                )
                # Route each tool to its correct JSON-RPC method + params
                def _build_rpc_params(name: str, args: dict, fallback: str) -> tuple[str, dict]:
                    if name == "read_file":
                        p: dict = {"file_path": args.get("file_path", ""), "project_root": args.get("project_path", fallback)}
                        if args.get("start_line"):
                            p["start_line"] = args["start_line"]
                        if args.get("end_line"):
                            p["end_line"] = args["end_line"]
                        return "local/read_file", p
                    if name == "list_directory":
                        return "local/list_directory", {
                            "dir_path": args.get("path", args.get("dir_path", "")),
                            "project_root": args.get("project_path", fallback),
                            "max_depth": args.get("max_depth", 3),
                        }
                    if name == "glob_find":
                        return "local/glob_find", {
                            "pattern": args.get("pattern", ""),
                            "project_path": args.get("project_path", fallback),
                            "file_type": args.get("file_type", "file"),
                            "max_results": args.get("max_results", 50),
                        }
                    # Default: search_codebase and any unrecognised tool
                    p = {
                        "pattern": args.get("pattern", args.get("query", "")),
                        "project_path": args.get("project_path", fallback),
                    }
                    if args.get("file_glob"):
                        p["file_glob"] = args["file_glob"]
                    if args.get("max_results") and args["max_results"] != 50:
                        p["max_count"] = args["max_results"]
                    if args.get("context_lines"):
                        p["context_lines"] = args["context_lines"]
                    return "local/search_project", p

                _rpc_method, _rpc_params = _build_rpc_params(tool_name, tool_args, _fallback_path)
                rpc_payload = {
                    "type": "mcp_request",
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "method": _rpc_method,
                    "params": _rpc_params,
                    "meta": {"trace_id": current_trace_id()},
                }
                job_id = uuid.uuid4().hex[:8]
                logger.info(
                    "[Pipeline] Queuing background job %s for tool '%s' (call_id=%s)",
                    job_id, tool_name, call_id,
                )

                # 1. Instant ACK ToolMessage — resolves the pending tool_call in <1ms.
                ack_message = ToolMessage(
                    content=(
                        f"Action queued in background with Job ID: {job_id}. "
                        "You may continue conversing with the user."
                    ),
                    tool_call_id=call_id,
                )
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )

                # 2. Reinvoke graph with the ACK so Claude can acknowledge aloud.
                result = await graph.ainvoke(
                    {"messages": [ack_message]},
                    config=config,
                )

                # 3. Register a Future keyed on call_id.  The main receive loop
                #    resolves it when Tauri sends back the matching mcp_result.
                rpc_future: asyncio.Future = asyncio.get_running_loop().create_future()
                _pending_rpc_futures[call_id] = rpc_future
                import time as _time
                _rpc_futures_timestamps[call_id] = _time.monotonic()

                # 4. Background coroutine: fire the RPC and await the Future.
                async def _do_tauri_dispatch(
                    _call_id: str = call_id,
                    _job_id: str = job_id,
                    _payload: dict = rpc_payload,
                    _future: asyncio.Future = rpc_future,
                ) -> str:
                    logger.info(
                        "[BackgroundJob %s] Sending Tauri RPC: %s",
                        _job_id, _payload["method"],
                    )
                    try:
                        await websocket.send_json(_payload)
                    except Exception as send_exc:
                        return f"Failed to dispatch RPC to Tauri: {send_exc}"
                    try:
                        raw = await asyncio.wait_for(asyncio.shield(_future), timeout=RPC_BACKGROUND_TIMEOUT)
                        mcp_resp = json.loads(raw)
                        has_res = "result" in mcp_resp or mcp_resp.get("type") == "mcp_result"
                        return (
                            str(mcp_resp.get("result", ""))
                            if has_res
                            else str(mcp_resp.get("error", "no result returned"))
                        )
                    except asyncio.TimeoutError:
                        _pending_rpc_futures.pop(_call_id, None)
                        await send_error(websocket, VocoError(
                            code=ErrorCode.E_RPC_TIMEOUT,
                            message=f"Tauri RPC timed out after 30s (job {_job_id})",
                            recoverable=True,
                            session_id=thread_id,
                            details={"job_id": _job_id, "call_id": _call_id},
                        ))
                        return f"Background job {_job_id} timed out after 30 seconds."

                # 5. Completion callback: inject result into LangGraph state.
                async def _on_job_complete(
                    _job_id: str,
                    result_str: str,
                    _config: dict = config,
                    _tool_name: str = tool_name,
                    _domain: str = detected_domain,
                ) -> None:
                    notification = SystemMessage(
                        content=(
                            f"[BACKGROUND JOB COMPLETE] Job {_job_id} "
                            f"({_tool_name}): {result_str[:2000]}"
                        )
                    )
                    try:
                        await graph.aupdate_state(_config, {"messages": [notification]})
                        logger.info(
                            "[BackgroundJob %s] Result injected into LangGraph state.", _job_id
                        )
                    except Exception as state_exc:
                        logger.error(
                            "[BackgroundJob %s] Failed to update state: %s", _job_id, state_exc
                        )
                    # Persist final node status to Supabase Logic Ledger.
                    await update_ledger_node(
                        session_id=thread_id,
                        node_id="3",
                        status="completed",
                        execution_output=result_str,
                    )

                    # Notify the frontend so it can update the Visual Ledger.
                    try:
                        await websocket.send_json({
                            "type": "async_job_update",
                            "job_id": _job_id,
                            "tool_name": _tool_name,
                            "ledger_node_id": "3",
                            "status": "completed",
                            "result": result_str[:500],
                        })
                    except Exception:
                        pass  # WebSocket may have closed before the job finished.

                # 6. Fire and forget — runs concurrently with TTS streaming.
                background_queue.submit(job_id, _do_tauri_dispatch(), _on_job_complete)
                await websocket.send_json({
                    "type": "background_job_start",
                    "job_id": job_id,
                    "tool_name": tool_name,
                })
                logger.info(
                    "[Pipeline] Background job %s dispatched; proceeding to TTS.", job_id
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
            await _send_ledger_clear()
            return

        logger.info("[Pipeline] Speaking: %.120s…", response_text)
        await websocket.send_json({"type": "control", "action": "tts_start", "text": response_text, "tts_active": True})

        tts_active = True
        try:
            chunk_count = 0
            async for audio_chunk in tts.synthesize_stream(response_text):
                await websocket.send_bytes(audio_chunk)
                chunk_count += 1
            logger.info("[TTS] Sent %d audio chunks to frontend.", chunk_count)
            if chunk_count == 0:
                logger.warning("[TTS] Zero audio chunks — Cartesia may have rejected the request.")
        except Exception as tts_exc:
            logger.error("[TTS] Synthesis failed: %s", tts_exc)

        await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
        tts_active = False

        # Small grace period so mic doesn't pick up tail-end of TTS audio
        await asyncio.sleep(TTS_GRACE_PERIOD)
        vad.reset()
        audio_buffer = bytearray()

        # --- Stripe Seat + Meter: report one voice turn (fire and forget) ---
        asyncio.create_task(report_voice_turn(customer_id=_auth_uid))

        # --- Supabase Logic Ledger sync ---
        domain_icon = {"database": "Database", "ui": "FileCode2", "api": "Terminal", "devops": "Terminal", "git": "Terminal", "general": "FileCode2"}
        _icon = domain_icon.get(detected_domain, "FileCode2")
        await sync_ledger_to_supabase(
            session_id=thread_id,
            user_id=_auth_uid,
            project_id=result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "unknown"),
            domain=detected_domain,
            nodes=[
                {"id": "1", "iconType": _icon,        "title": "Domain Paged",  "description": f"Loaded {detected_domain} context", "status": "completed"},
                {"id": "2", "iconType": "FileCode2",  "title": "Orchestrator",  "description": "Claude reasoning",                   "status": "completed"},
                {"id": "3", "iconType": "Terminal",   "title": "Execute",       "description": "Run actions",                         "status": "completed"},
            ],
            session_status="active",
        )

        await _send_ledger_clear()

    async def _safe_turn_end() -> None:
        """Wraps _on_turn_end with error handling so ledger always clears."""
        with tracer.start_as_current_span("voco.session.turn", attributes={"session.id": thread_id}):
            try:
                await _on_turn_end()
            except Exception as exc:
                logger.error("[Pipeline] Turn-end pipeline error: %s", exc, exc_info=True)
                await send_error(websocket, VocoError(
                    code=ErrorCode.E_GRAPH_FAILED,
                    message=f"Pipeline error: {exc}",
                    recoverable=True,
                    session_id=thread_id,
                ))
                try:
                    await _send_ledger_clear()
                except Exception:
                    pass

    async def _safe_text_input(text: str) -> None:
        """Run the full pipeline for a typed message, bypassing STT."""
        with tracer.start_as_current_span("voco.session.turn", attributes={"session.id": thread_id, "input.type": "text"}):
            try:
                await _on_turn_end(text_override=text)
            except Exception as exc:
                logger.error("[Pipeline] Text input pipeline error: %s", exc, exc_info=True)
                await send_error(websocket, VocoError(
                    code=ErrorCode.E_GRAPH_FAILED,
                    message=f"Pipeline error: {exc}",
                    recoverable=True,
                    session_id=thread_id,
                ))
                try:
                    await _send_ledger_clear()
                except Exception:
                    pass

    async def _receive_filtered(expected_type: str, timeout: float = 60.0) -> dict:
        """Receive text messages, draining non-matching ones, until expected_type arrives."""
        import time as _time
        deadline = _time.monotonic() + timeout
        while True:
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                return {}
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
            payload = json.loads(raw)
            msg_type = payload.get("type", "")
            if msg_type == expected_type:
                return payload
            # Route known message types so they aren't lost
            if msg_type == "mcp_result" or ("jsonrpc" in payload and "id" in payload and "type" not in payload):
                msg_id = payload.get("id", "")
                future = _pending_rpc_futures.get(msg_id)
                if future and not future.done():
                    future.set_result(raw)
            elif msg_type == "text_input":
                text = payload.get("text", "").strip()
                if text:
                    asyncio.create_task(_safe_text_input(text))
            elif msg_type == "auth_sync":
                nonlocal _auth_token, _auth_uid
                _auth_token = payload.get("token", "")
                _auth_uid = payload.get("uid", "local")
                _refresh_token = payload.get("refresh_token", "")
                from src.db import set_auth_jwt
                set_auth_jwt(_auth_token, _auth_uid, refresh_token=_refresh_token)
            elif msg_type == "update_env":
                env_patch = payload.get("env", {})
                for k, v in env_patch.items():
                    if k in _ALLOWED_ENV_KEYS and isinstance(v, str) and v:
                        os.environ[k] = v
            else:
                logger.debug("[WS] Draining unexpected message while waiting for %s: %s", expected_type, msg_type)

    vad.on_barge_in = _on_barge_in
    vad.on_turn_end = _safe_turn_end

    # Periodic cleanup of stale RPC futures (Issue #6)
    async def _periodic_cleanup() -> None:
        while True:
            await asyncio.sleep(60)
            await _cleanup_stale_futures()

    cleanup_task = asyncio.create_task(_periodic_cleanup())

    try:
        while True:
            try:
                # Wait for message with 30s timeout (allows pauses during barge-in)
                message = await asyncio.wait_for(websocket.receive(), timeout=WEBSOCKET_RECEIVE_TIMEOUT)
            except asyncio.TimeoutError:
                logger.debug("[Pipeline] WebSocket receive timeout (audio pause) — continuing")
                await _cleanup_stale_futures()
                continue
            except RuntimeError:
                # "Cannot call receive once a disconnect message has been received"
                logger.info("Client disconnected (runtime)")
                break

            if "bytes" in message:
                chunk = message["bytes"]
                # Skip VAD processing while TTS is active (prevents echo feedback)
                if tts_active:
                    continue
                audio_buffer.extend(chunk)
                await vad.process_chunk(chunk)
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")

                    if msg_type == "text_input":
                        # "Type instead" path — bypass STT, feed directly into LangGraph.
                        text = payload.get("text", "").strip()
                        if text:
                            logger.info("[WS] Text input received: %.120s", text)
                            asyncio.create_task(_safe_text_input(text))
                    elif msg_type == "mcp_result":
                        # Route Tauri's response to the awaiting background job.
                        msg_id = payload.get("id", "")
                        future = _pending_rpc_futures.get(msg_id)
                        if future and not future.done():
                            future.set_result(message["text"])
                            logger.info(
                                "[WS] Routed mcp_result (call_id=%s) to background job.", msg_id
                            )
                        else:
                            logger.debug(
                                "[WS] Received mcp_result with no pending future (call_id=%s).",
                                msg_id,
                            )
                    elif msg_type == "auth_sync":
                        try:
                            _auth_token = payload.get("token", "")
                            _auth_uid = payload.get("uid", "local")
                            _refresh_token = payload.get("refresh_token", "")
                            # Extract voco_session_token from Supabase user metadata
                            # (LiteLLM virtual key stored in user_metadata by admin)
                            voco_token = payload.get("voco_session_token", "")
                            if not voco_token:
                                # Fallback: check if the frontend included it
                                voco_token = os.environ.get("LITELLM_SESSION_TOKEN", "")
                            if voco_token:
                                set_session_token(voco_token)
                            # Re-initialize Supabase client with user JWT for RLS
                            from src.db import set_auth_jwt
                            set_auth_jwt(_auth_token, _auth_uid, refresh_token=_refresh_token)
                            logger.info("[WS] auth_sync: uid=%s token_len=%d", _auth_uid, len(_auth_token))
                            debug_logger.log_ws_event("auth_sync", thread_id, {"uid": _auth_uid, "token_len": len(_auth_token)})
                        except Exception as auth_exc:
                            debug_logger.log_auth_failure(thread_id, "auth_sync processing failed", auth_exc)
                            await send_error(websocket, VocoError(
                                code=ErrorCode.E_GRAPH_FAILED,
                                message=f"Auth sync failed: {auth_exc}",
                                recoverable=True,
                                session_id=thread_id,
                            ))
                    elif msg_type == "update_env":
                        env_patch = payload.get("env", {})
                        for k, v in env_patch.items():
                            if k in _ALLOWED_ENV_KEYS and isinstance(v, str) and v:
                                os.environ[k] = v
                        logger.info("[WS] Environment updated: %s", list(env_patch.keys()))
                    elif "jsonrpc" in payload and "id" in payload and "type" not in payload:
                        # JSON-RPC response from Tauri (no "type" field).
                        # Route to the awaiting background job future.
                        msg_id = payload.get("id", "")
                        future = _pending_rpc_futures.get(msg_id)
                        if future and not future.done():
                            future.set_result(message["text"])
                            logger.info(
                                "[WS] Routed JSON-RPC response (call_id=%s) to background job.", msg_id
                            )
                        else:
                            logger.debug(
                                "[WS] JSON-RPC response with no pending future (call_id=%s).",
                                msg_id,
                            )
                    else:
                        logger.debug("[WS] Control message: %s", payload)
                except json.JSONDecodeError:
                    logger.warning("[WS] Non-JSON text message ignored")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        debug_logger.log_ws_event("disconnect", thread_id, {"reason": "client_initiated"})
    except Exception as ws_exc:
        logger.error("[WS] Unhandled exception in voco_stream — code 1006 prevented: %s", ws_exc, exc_info=True)
        debug_logger.log_ws_event("error", thread_id, {"reason": str(ws_exc)})
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        cleanup_task.cancel()
        logger.info(
            "[Session] %s closed — turns=%d rpcs=%d timeouts=%d",
            thread_id,
            _session_metrics["turn_count"],
            _session_metrics["rpc_count"],
            _session_metrics["timeout_count"],
        )
        vad.reset()
        audio_buffer = bytearray()
        background_queue.cancel_all()
        # Close SQLite checkpointer and prune old checkpoints (GAP #2).
        try:
            if _session_checkpointer and hasattr(_session_checkpointer, "conn"):
                await _session_checkpointer.conn.close()
            await prune_checkpoints(thread_id)
        except Exception as cp_exc:
            logger.warning("[Checkpointer] Cleanup error for %s: %s", thread_id, cp_exc)
