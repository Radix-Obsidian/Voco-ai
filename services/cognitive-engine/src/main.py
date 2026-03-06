"""FastAPI app — health check + WebSocket text-streaming bridge.

Data flow (V2.5 — text-first):
  1. User types message in chat UI → sent as JSON over WebSocket.
  2. Text → LangGraph (Claude Sonnet / Haiku with tools).
  3. If Claude calls a tool → JSON-RPC 2.0 dispatched to Tauri.
  4. Tauri executes (ripgrep, file ops, etc.), sends result back as "mcp_result".
  5. Result injected into graph as ToolMessage → Claude synthesises answer.
  6. Answer text streamed back to frontend as chat message.
  7. Optional: user clicks "Read aloud" → Cartesia TTS → audio streamed to Tauri.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from src.auth.routes import router as auth_router
from src.billing.routes import router as billing_router, report_turn
from src.db import sync_ledger_to_supabase, update_ledger_node
from src.graph.background_worker import BackgroundJobQueue
from src.ide_mcp_server import attach_ide_mcp_routes

from src.debug import debug_logger
from src.audio.tts import CartesiaTTS
from src.graph.router import compile_graph
from src.graph.checkpointer import get_checkpointer, prune_checkpoints
from src.graph.tools import mcp_registry
from src.graph.nodes import set_session_token
from src.telemetry import init_telemetry, get_tracer, current_trace_id
from src.errors import ErrorCode, VocoError, send_error
from src.constants import (
    WEBSOCKET_RECEIVE_TIMEOUT,
    WEBSOCKET_MESSAGE_TIMEOUT,
    WEBSOCKET_SCAN_TIMEOUT,
    HITL_PROPOSAL_TIMEOUT,
    HITL_COMMAND_TIMEOUT,
    RPC_FUTURE_MAX_AGE,
    TTS_TAIL_DELAY,
    ALLOWED_ENV_KEYS,
    CLAUDE_CODE_TIMEOUT,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Tauri app identifier from tauri.conf.json — used to locate config.json.
_TAURI_APP_ID = "com.voco.mcp-gateway"
_ALLOWED_ENV_KEYS = ALLOWED_ENV_KEYS


def _verify_supabase_jwt(token: str, expected_uid: str) -> bool:
    """Verify a Supabase JWT signature and check the `sub` claim.

    Fail-open if SUPABASE_JWT_SECRET is not set (dev mode).
    Returns True if verification passes or is skipped.
    Raises ValueError if verification fails.
    """
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if not jwt_secret:
        logger.debug("[Auth] SUPABASE_JWT_SECRET not set — skipping JWT verification (dev mode)")
        return True

    import jwt  # PyJWT

    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("JWT expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT: {e}")

    sub = payload.get("sub", "")
    if sub != expected_uid:
        raise ValueError(f"JWT sub '{sub}' does not match uid '{expected_uid}'")

    return True


# In-memory store for the current Live Sandbox HTML (single-user desktop app).
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


async def _run_claude_code(
    task_description: str,
    project_path: str,
    websocket: WebSocket,
    job_id: str,
) -> dict:
    """Spawn ``claude -p`` as a subprocess and stream progress to the frontend.

    Returns ``{"success": bool, "summary": str, "exit_code": int}``.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        await websocket.send_json({
            "type": "claude_code_progress",
            "job_id": job_id,
            "event": "error",
            "message": "Claude Code CLI not found. Install it with: npm install -g @anthropic-ai/claude-code",
        })
        return {"success": False, "summary": "Claude Code CLI is not installed.", "exit_code": -1}

    collected_output: list[str] = []
    exit_code = -1

    try:
        proc = await asyncio.create_subprocess_exec(
            claude_bin, "-p", task_description, "--output-format", "stream-json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
        )

        async def _read_stream():
            assert proc.stdout is not None
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    collected_output.append(line)
                    continue

                evt_type = evt.get("type", "")
                msg_text = ""

                if evt_type == "assistant" and "message" in evt:
                    content = evt["message"].get("content", [])
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            msg_text = block.get("text", "")[:200]
                elif evt_type == "tool_use":
                    tool_name = evt.get("tool", {}).get("name", "unknown")
                    msg_text = f"Using tool: {tool_name}"
                elif evt_type == "tool_result":
                    msg_text = "Tool completed"
                elif evt_type == "result":
                    result_text = evt.get("result", "")
                    if isinstance(result_text, str):
                        msg_text = result_text[:200]
                    elif isinstance(result_text, dict):
                        msg_text = json.dumps(result_text)[:200]

                if msg_text:
                    collected_output.append(msg_text)
                    await websocket.send_json({
                        "type": "claude_code_progress",
                        "job_id": job_id,
                        "event": evt_type or "output",
                        "message": msg_text,
                    })

        await asyncio.wait_for(_read_stream(), timeout=CLAUDE_CODE_TIMEOUT)
        await proc.wait()
        exit_code = proc.returncode or 0

    except asyncio.TimeoutError:
        logger.warning("[ClaudeCode] Timeout after %.0fs — killing subprocess", CLAUDE_CODE_TIMEOUT)
        try:
            proc.kill()  # type: ignore[possibly-undefined]
            await proc.wait()  # type: ignore[possibly-undefined]
        except Exception as exc:
            logger.warning("[ClaudeCode] Process cleanup failed: %s", exc)
        return {
            "success": False,
            "summary": f"Claude Code timed out after {int(CLAUDE_CODE_TIMEOUT)}s.",
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {"success": False, "summary": "Claude Code binary not found.", "exit_code": -1}
    except Exception as exc:
        logger.exception("[ClaudeCode] Unexpected error")
        return {"success": False, "summary": f"Error: {exc}", "exit_code": -1}

    full_output = "\n".join(collected_output)
    if len(full_output) > 4000:
        full_output = full_output[:4000] + "\n... (truncated)"

    return {
        "success": exit_code == 0,
        "summary": full_output or "(no output)",
        "exit_code": exit_code,
    }


async def _init_mcp_registry() -> None:
    """Initialize MCP registry in the background so it doesn't block startup."""
    try:
        await mcp_registry.initialize()
        logger.info("MCP Registry ready — %d external tools.", len(mcp_registry.get_tools()))
    except Exception as exc:
        logger.error("MCP Registry init failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect external MCP servers at startup."""
    _load_native_config()

    # Observability: OpenTelemetry + FastAPI auto-instrumentation
    init_telemetry()
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[Telemetry] FastAPI auto-instrumentation active.")
    except Exception as otel_exc:
        logger.warning("[Telemetry] FastAPI instrumentation skipped: %s", otel_exc)

    logger.info("Initialising Universal MCP Registry (background)…")
    asyncio.create_task(_init_mcp_registry())

    yield

    await mcp_registry.shutdown()


app = FastAPI(title="Voco Cognitive Engine", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:1420",
        "tauri://localhost",
        "https://tauri.localhost",
        "https://api.itsvoco.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

attach_ide_mcp_routes(app)
app.include_router(auth_router)
app.include_router(billing_router)


@app.get("/debug/events")
async def get_debug_events(limit: int = 100) -> dict:
    """Return recent debug events for troubleshooting."""
    return {"events": debug_logger.get_recent_events(limit)}


@app.get("/health")
async def health() -> dict:
    checks = {
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "cartesia_key": bool(os.environ.get("CARTESIA_API_KEY")),
        "orgo_key": bool(os.environ.get("ORGO_API_KEY")),
        "supabase_url": bool(os.environ.get("SUPABASE_URL")),
    }
    all_ok = all(checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}


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
    # Validate token before accepting connection
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

    tts = CartesiaTTS()   # reads CARTESIA_API_KEY from os.environ at call time

    thread_id = _new_thread_id()
    config = {"configurable": {"thread_id": thread_id}}
    logger.info("[Session] New thread: %s", thread_id)
    debug_logger.log_ws_event("connect", thread_id, {"url": str(websocket.url)})

    # Per-session SQLite checkpointer
    _session_checkpointer = await get_checkpointer(thread_id)
    graph = compile_graph(checkpointer=_session_checkpointer)

    # Observability: send session_id to frontend
    tracer = get_tracer()
    await websocket.send_json({"type": "session_init", "session_id": thread_id})

    # Per-session auth state
    _auth_uid = "local"
    _auth_token = ""
    _stripe_customer_id = ""
    _user_email = ""
    _is_founder = False
    _user_tier = "free"

    FOUNDER_EMAILS = {
        "autrearchitect@gmail.com",
        "architect@viperbyproof.com",
    }

    # Background job queue for async tool execution
    background_queue = BackgroundJobQueue()
    _pending_rpc_futures: dict[str, asyncio.Future] = {}
    _rpc_futures_timestamps: dict[str, float] = {}

    # Session-level metrics
    _session_metrics = {"timeout_count": 0, "rpc_count": 0, "turn_count": 0}

    # Orgo cloud sandbox manager (created lazily on first orgo_create_sandbox call)
    _orgo_manager = None

    async def _cleanup_stale_futures(max_age_seconds: float = RPC_FUTURE_MAX_AGE) -> None:
        """Remove stale futures that have timed out or completed."""
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

    _turn_in_progress = False

    async def _handle_message(text: str) -> None:
        """Full pipeline: Text → LangGraph → (optional JSON-RPC) → response text.

        Replaces the old voice pipeline. No STT or automatic TTS.
        """
        nonlocal _turn_in_progress

        if _turn_in_progress:
            logger.warning("[Pipeline] Turn already in progress — ignoring duplicate trigger.")
            return
        _turn_in_progress = True

        _session_metrics["turn_count"] += 1
        await websocket.send_json({"type": "control", "action": "turn_ended", "turn_count": _session_metrics["turn_count"]})

        transcript = text
        logger.info("[Pipeline] Text input: %.120s", transcript)
        await websocket.send_json({"type": "transcript", "text": transcript})

        # --- Step 2: Run LangGraph (Claude Sonnet / Haiku) ---
        await _send_ledger_update(domain="general", context_router="active", orchestrator="pending", tools="pending")

        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "messages": [HumanMessage(content=transcript)],
                        "user_tier": "founder" if _is_founder else _user_tier,
                    },
                    config=config,
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.error("[Pipeline] graph.ainvoke timed out after 60s")
            await send_error(websocket, VocoError(
                code=ErrorCode.E_GRAPH_FAILED,
                message="AI took too long to respond. Please try again.",
                recoverable=True,
                session_id=thread_id,
            ))
            await _send_ledger_clear()
            return
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

            # Send text summary to chat (no TTS announcement)
            desc_list = [p.get("description", p.get("file_path", "")) for p in proposals]
            summary_text = f"I have {len(proposals)} proposal{'s' if len(proposals) != 1 else ''} for your review: {'. '.join(desc_list)}. Please approve or reject."
            await websocket.send_json({"type": "ai_response", "text": summary_text})

            # Wait for proposal_decision from frontend
            decisions = []
            try:
                decision_msg = await _receive_filtered("proposal_decision", timeout=HITL_PROPOSAL_TIMEOUT)
                decisions = decision_msg.get("decisions", [])
            except asyncio.TimeoutError:
                logger.warning("[Pipeline] Proposal decision timeout — auto-rejecting all proposals")
                decisions = [{"proposal_id": p.get("proposal_id", ""), "status": "rejected"} for p in proposals]
            except Exception as exc:
                logger.warning("[Pipeline] Proposal decision error: %s", exc)
                decisions = [{"proposal_id": p.get("proposal_id", ""), "status": "rejected"} for p in proposals]

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

        # --- Step 2.6: Check for command interrupt ---
        snapshot = await graph.aget_state(config)
        if snapshot.next and "command_review_node" in snapshot.next:
            commands = snapshot.values.get("pending_commands", [])
            project_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
            logger.info("[Pipeline] Command interrupt: %d commands pending approval", len(commands))

            for c in commands:
                await websocket.send_json({
                    "type": "command_proposal",
                    "command_id": c.get("command_id", ""),
                    "command": c.get("command", ""),
                    "description": c.get("description", ""),
                    "project_path": c.get("project_path", project_path),
                })

            # Send text summary to chat (no TTS announcement)
            cmd_descs = [c.get("description", c.get("command", "")) for c in commands]
            cmd_summary = f"I need to run {len(commands)} command{'s' if len(commands) != 1 else ''}: {'. '.join(cmd_descs)}. Please approve or reject."
            await websocket.send_json({"type": "ai_response", "text": cmd_summary})

            cmd_decisions = []
            try:
                decision_msg = await _receive_filtered("command_decision", timeout=HITL_COMMAND_TIMEOUT)
                cmd_decisions = decision_msg.get("decisions", [])
            except asyncio.TimeoutError:
                logger.warning("[Pipeline] Command decision timeout — auto-rejecting all commands")
                cmd_decisions = [{"command_id": c.get("command_id", ""), "status": "rejected"} for c in commands]
            except Exception as exc:
                logger.warning("[Pipeline] Command decision error: %s", exc)
                cmd_decisions = [{"command_id": c.get("command_id", ""), "status": "rejected"} for c in commands]

            # For approved commands, dispatch execute_command to Tauri
            for d in cmd_decisions:
                if d.get("status") != "approved":
                    continue
                cid = d["command_id"]
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

            # Resume graph with command decisions
            result = await graph.ainvoke(
                Command(resume=None, update={"command_decisions": cmd_decisions}),
                config=config,
            )

        # --- Step 3: Handle pending MCP action (tool calls) ---
        pending_action = result.get("pending_mcp_action")
        if pending_action:
            tool_name = pending_action.get("name", "")
            tool_args = pending_action.get("args", {})
            call_id = pending_action.get("id", f"rpc-{uuid.uuid4().hex[:8]}")
            _screen_handled = False

            # --- Voco Eyes — inline screen analysis ---
            if tool_name == "analyze_screen":
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                logger.info("[VocoEyes] Requesting screen frames for call_id=%s", call_id)

                await websocket.send_json({"type": "screen_capture_request", "id": call_id})

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

                user_desc = tool_args.get("user_description", "")
                if frames:
                    sampled = frames[-5:]
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

                result = await graph.ainvoke({"messages": [screen_tool_msg]}, config=config)
                _screen_handled = True

            # --- Voco Auto-Sec — inline security scan ---
            elif tool_name == "scan_vulnerabilities":
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                project_path_arg = tool_args.get("project_path", os.environ.get("VOCO_PROJECT_PATH", ""))
                logger.info("[AutoSec] Requesting security scan for call_id=%s path=%s", call_id, project_path_arg)

                await websocket.send_json({
                    "type": "scan_security_request",
                    "id": call_id,
                    "project_path": project_path_arg,
                })

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

                sec_tool_msg = ToolMessage(
                    content=(
                        "Security scan complete. Analyze these findings and provide a "
                        "prioritized threat summary with actionable remediation steps.\n\n"
                        + findings_str
                    ),
                    tool_call_id=call_id,
                )
                logger.info("[AutoSec] Findings ready (%d chars), invoking Claude.", len(findings_str))

                result = await graph.ainvoke({"messages": [sec_tool_msg]}, config=config)
                _screen_handled = True

            # --- Live Sandbox — generate_and_preview_mvp / update_sandbox_preview ---
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
                _host = os.environ.get("VOCO_HOST", "localhost")
                _port = os.environ.get("VOCO_PORT", "8001")
                sandbox_url = f"http://{_host}:{_port}/sandbox"

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
                        f"MVP sandbox is live at {sandbox_url}. "
                        "The preview is now visible on the right side of the screen."
                    ),
                    tool_call_id=call_id,
                )
                result = await graph.ainvoke({"messages": [sandbox_tool_msg]}, config=config)
                _screen_handled = True

            # --- delegate_to_claude_code ---
            elif tool_name == "delegate_to_claude_code":
                cc_job_id = uuid.uuid4().hex[:8]
                cc_task = tool_args.get("task_description", "")
                cc_project = tool_args.get("project_path", os.environ.get("VOCO_PROJECT_PATH", ""))
                logger.info("[ClaudeCode] Starting delegation job=%s task=%s", cc_job_id, cc_task[:80])

                await websocket.send_json({
                    "type": "claude_code_start",
                    "job_id": cc_job_id,
                    "task_description": cc_task,
                })

                ack_tool_msg = ToolMessage(
                    content=(
                        "Claude Code delegation started in the background. "
                        "Tell the user: 'I've handed this off to Claude Code — "
                        "I'll let you know when it's done.' Keep it short."
                    ),
                    tool_call_id=call_id,
                )
                result = await graph.ainvoke({"messages": [ack_tool_msg]}, config=config)

                async def _cc_background(
                    _job_id: str, _task: str, _project: str,
                    _ws: WebSocket, _graph, _config: dict,
                ):
                    try:
                        cc_result = await _run_claude_code(_task, _project, _ws, _job_id)
                    except Exception as exc:
                        logger.exception("[ClaudeCode] Background task error")
                        cc_result = {"success": False, "summary": str(exc), "exit_code": -1}

                    try:
                        await _ws.send_json({
                            "type": "claude_code_complete",
                            "job_id": _job_id,
                            "success": cc_result["success"],
                            "summary": cc_result["summary"][:500],
                        })
                    except Exception:
                        logger.warning("[ClaudeCode] Could not send completion to frontend")

                    try:
                        result_msg = SystemMessage(
                            content=(
                                f"[Background] Claude Code finished "
                                f"(success={cc_result['success']}, exit_code={cc_result['exit_code']}).\n"
                                f"Output:\n{cc_result['summary']}"
                            )
                        )
                        await _graph.aupdate_state(
                            _config,
                            {"messages": [result_msg]},
                        )
                        logger.info("[ClaudeCode] Result injected into checkpoint for job=%s", _job_id)
                    except Exception as exc:
                        logger.warning("[ClaudeCode] Failed to inject result into checkpoint: %s", exc)

                asyncio.create_task(
                    _cc_background(cc_job_id, cc_task, cc_project, websocket, graph, config)
                )
                _screen_handled = True

            # --- Orgo Cloud Sandbox ---
            elif tool_name == "orgo_create_sandbox":
                await _send_ledger_update(
                    domain=detected_domain,
                    context_router="completed",
                    orchestrator="active",
                    tools="active",
                )
                project_name = tool_args.get("project_name", "sandbox")
                setup_cmds = tool_args.get("setup_commands", "")

                from src.orgo_client import OrgoVMManager, OrgoError
                if _orgo_manager is None:
                    _orgo_manager = OrgoVMManager()

                try:
                    vm_info = await _orgo_manager.create_vm(project_name)
                    computer_id = vm_info["computer_id"]

                    # Run setup commands if provided
                    setup_output = ""
                    if setup_cmds:
                        setup_result = await _orgo_manager.run_bash(setup_cmds, timeout=60.0)
                        setup_output = str(setup_result.get("output", setup_result.get("stdout", "")))

                    # Get VNC credentials for live desktop streaming
                    vnc_creds = await _orgo_manager.get_vnc_credentials()

                    await websocket.send_json({
                        "type": "orgo_sandbox_live",
                        "computer_id": computer_id,
                        "vnc_url": vnc_creds["vnc_url"],
                        "vnc_password": vnc_creds["vnc_password"],
                        "status": "running",
                    })

                    content_parts = [
                        f"Cloud sandbox '{project_name}' is live (VM: {computer_id}). "
                        "The user can see a live interactive desktop stream in the right panel.",
                    ]
                    if setup_output:
                        content_parts.append(f"Setup output:\n{setup_output[:500]}")

                    sandbox_tool_msg = ToolMessage(
                        content="\n".join(content_parts),
                        tool_call_id=call_id,
                    )
                    result = await graph.ainvoke({"messages": [sandbox_tool_msg]}, config=config)
                except OrgoError as exc:
                    err_msg = ToolMessage(
                        content=f"Failed to create cloud sandbox: {exc}",
                        tool_call_id=call_id,
                    )
                    result = await graph.ainvoke({"messages": [err_msg]}, config=config)
                _screen_handled = True

            elif tool_name == "orgo_run_command":
                from src.orgo_client import OrgoError
                command = tool_args.get("command", "")
                timeout = tool_args.get("timeout", 30)

                try:
                    cmd_result = await _orgo_manager.run_bash(command, timeout=float(timeout))
                    output = str(cmd_result.get("output", cmd_result.get("stdout", "")))
                    exit_code = cmd_result.get("exit_code", 0)

                    await websocket.send_json({
                        "type": "orgo_command_output",
                        "command": command,
                        "output": output[:2000],
                        "exit_code": exit_code,
                    })

                    tool_msg = ToolMessage(
                        content=f"Command: {command}\nExit code: {exit_code}\nOutput:\n{output[:1500]}",
                        tool_call_id=call_id,
                    )
                except (OrgoError, AttributeError) as exc:
                    tool_msg = ToolMessage(
                        content=f"Command failed: {exc}",
                        tool_call_id=call_id,
                    )
                result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                _screen_handled = True

            elif tool_name == "orgo_run_python":
                from src.orgo_client import OrgoError
                code = tool_args.get("code", "")
                timeout = tool_args.get("timeout", 10)

                try:
                    py_result = await _orgo_manager.run_python(code, timeout=float(timeout))
                    output = str(py_result.get("output", py_result.get("stdout", "")))

                    tool_msg = ToolMessage(
                        content=f"Python output:\n{output[:1500]}",
                        tool_call_id=call_id,
                    )
                except (OrgoError, AttributeError) as exc:
                    tool_msg = ToolMessage(
                        content=f"Python execution failed: {exc}",
                        tool_call_id=call_id,
                    )
                result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                _screen_handled = True

            elif tool_name == "orgo_screenshot":
                from src.orgo_client import OrgoError

                try:
                    screenshot_b64 = await _orgo_manager.take_screenshot()

                    await websocket.send_json({
                        "type": "orgo_screenshot",
                        "image": screenshot_b64,
                    })

                    # Send vision content to Claude
                    vision_content = [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                        },
                        {
                            "type": "text",
                            "text": "This is a screenshot of the cloud sandbox desktop. Describe what you see.",
                        },
                    ]
                    tool_msg = ToolMessage(content=vision_content, tool_call_id=call_id)
                except (OrgoError, AttributeError) as exc:
                    tool_msg = ToolMessage(
                        content=f"Screenshot failed: {exc}",
                        tool_call_id=call_id,
                    )
                result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                _screen_handled = True

            elif tool_name == "orgo_upload_file":
                from src.orgo_client import OrgoError
                file_path = tool_args.get("file_path", "")
                content = tool_args.get("content", "")

                try:
                    upload_result = await _orgo_manager.upload_file(file_path, content)
                    tool_msg = ToolMessage(
                        content=f"File uploaded to sandbox: {file_path}",
                        tool_call_id=call_id,
                    )
                except (OrgoError, AttributeError) as exc:
                    tool_msg = ToolMessage(
                        content=f"Upload failed: {exc}",
                        tool_call_id=call_id,
                    )
                result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                _screen_handled = True

            elif tool_name == "orgo_stop_sandbox":
                from src.orgo_client import OrgoError

                try:
                    if _orgo_manager:
                        await _orgo_manager.destroy_vm()
                    await websocket.send_json({"type": "orgo_sandbox_stopped"})
                    tool_msg = ToolMessage(
                        content="Cloud sandbox has been stopped and destroyed.",
                        tool_call_id=call_id,
                    )
                except (OrgoError, AttributeError) as exc:
                    tool_msg = ToolMessage(
                        content=f"Failed to stop sandbox: {exc}",
                        tool_call_id=call_id,
                    )
                result = await graph.ainvoke({"messages": [tool_msg]}, config=config)
                _screen_handled = True

            # --- Synchronous Agentic Loop — tool call → Tauri RPC → result → Claude → repeat ---
            if not _screen_handled:
                _fallback_path = (
                    tool_args.get("project_path", "")
                    or result.get("active_project_path")
                    or os.environ.get("VOCO_PROJECT_PATH", "")
                )

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

                MAX_TOOL_LOOPS = 5
                loop_count = 0

                async def _heartbeat():
                    try:
                        while True:
                            await asyncio.sleep(15)
                            await websocket.send_json({"type": "heartbeat"})
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        logger.debug("[WS] Heartbeat send failed: %s", exc)

                _heartbeat_task = asyncio.create_task(_heartbeat())

                while loop_count < MAX_TOOL_LOOPS:
                    loop_count += 1
                    _rpc_method, _rpc_params = _build_rpc_params(tool_name, tool_args, _fallback_path)
                    rpc_payload = {
                        "type": "mcp_request",
                        "jsonrpc": "2.0",
                        "id": call_id,
                        "method": _rpc_method,
                        "params": _rpc_params,
                        "meta": {"trace_id": current_trace_id()},
                    }
                    logger.info(
                        "[Pipeline] Sync tool %d/%d: %s (call_id=%s)",
                        loop_count, MAX_TOOL_LOOPS, tool_name, call_id,
                    )

                    await _send_ledger_update(
                        domain=detected_domain,
                        context_router="completed",
                        orchestrator="active",
                        tools="active",
                    )

                    job_id = uuid.uuid4().hex[:8]
                    await websocket.send_json({
                        "type": "background_job_start",
                        "job_id": job_id,
                        "tool_name": tool_name,
                    })

                    rpc_future: asyncio.Future = asyncio.get_running_loop().create_future()
                    _pending_rpc_futures[call_id] = rpc_future
                    _rpc_futures_timestamps[call_id] = time.monotonic()

                    try:
                        await websocket.send_json(rpc_payload)
                    except Exception as send_exc:
                        tool_result_str = f"Failed to dispatch RPC to Tauri: {send_exc}"
                    else:
                        try:
                            raw = await asyncio.wait_for(rpc_future, timeout=30.0)
                            mcp_resp = json.loads(raw)
                            has_res = "result" in mcp_resp or mcp_resp.get("type") == "mcp_result"
                            tool_result_str = (
                                str(mcp_resp.get("result", ""))
                                if has_res
                                else str(mcp_resp.get("error", "no result returned"))
                            )
                        except asyncio.TimeoutError:
                            _pending_rpc_futures.pop(call_id, None)
                            _rpc_futures_timestamps.pop(call_id, None)
                            tool_result_str = f"Tool {tool_name} timed out after 30 seconds."
                    finally:
                        _pending_rpc_futures.pop(call_id, None)
                        _rpc_futures_timestamps.pop(call_id, None)

                    logger.info(
                        "[Pipeline] Tool %s returned %d chars.", tool_name, len(tool_result_str),
                    )

                    try:
                        await websocket.send_json({
                            "type": "background_job_complete",
                            "job_id": job_id,
                            "tool_name": tool_name,
                        })
                    except Exception as exc:
                        logger.debug("[WS] Background job completion send failed: %s", exc)

                    tool_result_msg = ToolMessage(
                        content=tool_result_str[:4000],
                        tool_call_id=call_id,
                    )

                    result = await graph.ainvoke(
                        {"messages": [tool_result_msg]},
                        config=config,
                    )

                    next_msg = result["messages"][-1]
                    if isinstance(next_msg, AIMessage) and next_msg.tool_calls:
                        tc = next_msg.tool_calls[0]
                        tool_name = tc["name"]
                        tool_args = tc.get("args", {})
                        call_id = tc["id"]
                        _fallback_path = (
                            tool_args.get("project_path", "")
                            or result.get("active_project_path")
                            or _fallback_path
                        )
                        logger.info("[Pipeline] Claude wants another tool: %s", tool_name)
                        continue
                    else:
                        break

                _heartbeat_task.cancel()

                logger.info(
                    "[Pipeline] Agentic loop done after %d iteration(s).", loop_count,
                )

        # --- Step 4: Send AI response as text to chat ---
        final_message = result["messages"][-1]
        response_text: str = (
            final_message.content
            if isinstance(final_message.content, str)
            else str(final_message.content)
        )

        if not response_text.strip():
            logger.warning("[Pipeline] Empty response text — skipping.")
            await _send_ledger_clear()
            return

        logger.info("[Pipeline] Response: %.120s…", response_text)
        await websocket.send_json({"type": "ai_response", "text": response_text})

        # --- Stripe Seat + Meter: report one turn (fire and forget) ---
        if _is_founder:
            logger.debug("[Billing] Skipping meter for founder %s", _user_email)
        else:
            asyncio.create_task(report_turn(customer_id=_stripe_customer_id))

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

    async def _safe_handle_message(text: str) -> None:
        """Wraps _handle_message with error handling so ledger always clears."""
        nonlocal _turn_in_progress
        with tracer.start_as_current_span("voco.session.turn", attributes={"session.id": thread_id, "input.type": "text"}):
            try:
                await _handle_message(text)
            except Exception as exc:
                logger.error("[Pipeline] Message pipeline error: %s", exc, exc_info=True)
                exc_msg = str(exc)
                if exc_msg.startswith("E_MODEL_OVERLOADED:"):
                    err_code = ErrorCode.E_MODEL_OVERLOADED
                    err_msg = exc_msg.split(":", 1)[1].strip()
                elif exc_msg.startswith("E_AUTH_EXPIRED:"):
                    err_code = ErrorCode.E_AUTH_EXPIRED
                    err_msg = exc_msg.split(":", 1)[1].strip()
                else:
                    err_code = ErrorCode.E_GRAPH_FAILED
                    err_msg = f"Pipeline error: {exc}"
                await send_error(websocket, VocoError(
                    code=err_code,
                    message=err_msg,
                    recoverable=err_code != ErrorCode.E_AUTH_EXPIRED,
                    session_id=thread_id,
                ))
                try:
                    await _send_ledger_clear()
                except Exception as exc:
                    logger.debug("[WS] Ledger clear failed: %s", exc)
            finally:
                _turn_in_progress = False

    async def _receive_filtered(expected_type: str, timeout: float = 60.0) -> dict:
        """Receive text messages, draining non-matching ones, until expected_type arrives."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Timed out waiting for {expected_type}")
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
                    asyncio.create_task(_safe_handle_message(text))
            elif msg_type == "auth_sync":
                nonlocal _auth_token, _auth_uid, _stripe_customer_id, _user_email, _is_founder, _user_tier
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

    # Periodic cleanup of stale RPC futures
    async def _periodic_cleanup() -> None:
        while True:
            await asyncio.sleep(60)
            await _cleanup_stale_futures()

    cleanup_task = asyncio.create_task(_periodic_cleanup())

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=WEBSOCKET_RECEIVE_TIMEOUT)
            except asyncio.TimeoutError:
                logger.debug("[Pipeline] WebSocket receive timeout — continuing")
                await _cleanup_stale_futures()
                continue
            except RuntimeError:
                logger.info("Client disconnected (runtime)")
                break

            if "bytes" in message:
                # Binary messages are no longer expected (voice input removed).
                # Silently ignore for backwards compatibility.
                continue
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")

                    if msg_type == "text_input":
                        text = payload.get("text", "").strip()
                        if text:
                            logger.info("[WS] Text input received: %.120s", text)
                            asyncio.create_task(_safe_handle_message(text))
                    elif msg_type == "tts_request":
                        # On-demand TTS playback — user clicked "Read aloud"
                        tts_text = payload.get("text", "").strip()
                        if tts_text:
                            logger.info("[TTS] Read-aloud request: %.80s…", tts_text)
                            try:
                                await websocket.send_json({"type": "control", "action": "tts_start", "text": tts_text, "tts_active": True})
                                chunk_count = 0
                                async for audio_chunk in tts.synthesize_stream(tts_text):
                                    await websocket.send_bytes(audio_chunk)
                                    chunk_count += 1
                                logger.info("[TTS] Sent %d audio chunks.", chunk_count)
                                if chunk_count == 0:
                                    await send_error(websocket, VocoError(
                                        code=ErrorCode.E_TTS_FAILED,
                                        message="Voice synthesis returned no audio — check your Cartesia API key in Settings.",
                                    ))
                            except Exception as tts_exc:
                                logger.error("[TTS] Synthesis failed: %s", tts_exc)
                                await send_error(websocket, VocoError(
                                    code=ErrorCode.E_TTS_FAILED,
                                    message=f"Voice synthesis failed: {tts_exc}",
                                ))
                            finally:
                                try:
                                    await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
                                except Exception as exc:
                                    logger.debug("[WS] TTS end control message failed: %s", exc)
                    elif msg_type == "tts_stop":
                        # User clicked "Stop" on TTS playback
                        await websocket.send_json({"type": "control", "action": "halt_audio_playback"})
                    elif msg_type == "mcp_result":
                        msg_id = payload.get("id", "")
                        future = _pending_rpc_futures.get(msg_id)
                        if future and not future.done():
                            future.set_result(message["text"])
                            logger.info("[WS] Routed mcp_result (call_id=%s) to job.", msg_id)
                        else:
                            logger.debug("[WS] mcp_result with no pending future (call_id=%s).", msg_id)
                    elif msg_type == "auth_sync":
                        try:
                            _auth_token = payload.get("token", "")
                            _auth_uid = payload.get("uid", "local")
                            _refresh_token = payload.get("refresh_token", "")
                            _verify_supabase_jwt(_auth_token, _auth_uid)
                            voco_token = payload.get("voco_session_token", "")
                            if not voco_token:
                                voco_token = os.environ.get("LITELLM_SESSION_TOKEN", "")
                            if voco_token:
                                set_session_token(voco_token)
                            from src.db import set_auth_jwt
                            set_auth_jwt(_auth_token, _auth_uid, refresh_token=_refresh_token)
                            logger.info("[WS] auth_sync: uid=%s token_len=%d", _auth_uid, len(_auth_token))
                            debug_logger.log_ws_event("auth_sync", thread_id, {"uid": _auth_uid, "token_len": len(_auth_token)})

                            try:
                                _sb_url = os.environ.get("SUPABASE_URL", "")
                                _sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
                                if _sb_url and _sb_key:
                                    async with httpx.AsyncClient() as _http:
                                        resp = await _http.get(
                                            f"{_sb_url}/rest/v1/users",
                                            params={"id": f"eq.{_auth_uid}", "select": "stripe_customer_id,email,tier"},
                                            headers={
                                                "apikey": _sb_key,
                                                "Authorization": f"Bearer {_sb_key}",
                                            },
                                            timeout=5.0,
                                        )
                                        rows = resp.json()
                                        if rows and isinstance(rows, list) and len(rows) > 0:
                                            _stripe_customer_id = rows[0].get("stripe_customer_id", "") or ""
                                            _user_email = rows[0].get("email", "") or ""
                                            _user_tier = rows[0].get("tier", "") or "free"
                                            _is_founder = _user_email in FOUNDER_EMAILS
                                            logger.info(
                                                "[WS] auth_sync: stripe_cid=%s email=%s founder=%s tier=%s",
                                                _stripe_customer_id[:12] + "..." if _stripe_customer_id else "(none)",
                                                _user_email,
                                                _is_founder,
                                                _user_tier,
                                            )
                                            await websocket.send_json({
                                                "type": "user_info",
                                                "tier": _user_tier,
                                                "is_founder": _is_founder,
                                            })
                            except Exception as lookup_exc:
                                logger.warning("[WS] Supabase user lookup failed (non-fatal): %s", lookup_exc)
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
                    elif msg_type == "cancel_job":
                        cancel_id = payload.get("job_id", "")
                        if cancel_id:
                            background_queue.cancel_job(cancel_id)
                            logger.info("[WS] Cancel requested for job %s", cancel_id)
                    elif "jsonrpc" in payload and "id" in payload and "type" not in payload:
                        msg_id = payload.get("id", "")
                        future = _pending_rpc_futures.get(msg_id)
                        if future and not future.done():
                            future.set_result(message["text"])
                            logger.info("[WS] Routed JSON-RPC response (call_id=%s) to job.", msg_id)
                        else:
                            logger.debug("[WS] JSON-RPC response with no pending future (call_id=%s).", msg_id)
                    else:
                        logger.debug("[WS] Control message: %s", payload)
                except json.JSONDecodeError:
                    logger.warning("[WS] Non-JSON text message ignored")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
        debug_logger.log_ws_event("disconnect", thread_id, {"reason": "client_initiated"})
    except Exception as ws_exc:
        logger.error("[WS] Unhandled exception in voco_stream: %s", ws_exc, exc_info=True)
        debug_logger.log_ws_event("error", thread_id, {"reason": str(ws_exc)})
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception as exc:
            logger.debug("[WS] Close after error failed: %s", exc)
    finally:
        cleanup_task.cancel()
        logger.info(
            "[Session] %s closed — turns=%d rpcs=%d timeouts=%d",
            thread_id,
            _session_metrics["turn_count"],
            _session_metrics["rpc_count"],
            _session_metrics["timeout_count"],
        )
        background_queue.cancel_all()
        # Destroy Orgo VM if active (prevent VM leaks)
        if _orgo_manager is not None:
            try:
                await _orgo_manager.destroy_vm()
                await _orgo_manager.close()
                logger.info("[Orgo] Session VM cleaned up for %s", thread_id)
            except Exception as orgo_exc:
                logger.warning("[Orgo] Cleanup error for %s: %s", thread_id, orgo_exc)
        # Cancel pending RPC futures
        for fid, fut in _pending_rpc_futures.items():
            if not fut.done():
                fut.cancel()
        _pending_rpc_futures.clear()
        try:
            if _session_checkpointer and hasattr(_session_checkpointer, "conn"):
                await _session_checkpointer.conn.close()
            await prune_checkpoints(thread_id)
        except Exception as cp_exc:
            logger.warning("[Checkpointer] Cleanup error for %s: %s", thread_id, cp_exc)
