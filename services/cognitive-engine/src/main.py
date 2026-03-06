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
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from src.auth.routes import router as auth_router
from src.billing.routes import router as billing_router, report_voice_turn
from src.db import sync_ledger_to_supabase, update_ledger_node
from src.graph.background_worker import BackgroundJobQueue
from src.ide_mcp_server import attach_ide_mcp_routes

from src.debug import debug_logger
from src.audio.stt import DeepgramSTT, DeepgramStreamingSession, WhisperLocalSession
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
                    # Extract text blocks from assistant message
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
                    # Final result
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
        except Exception:
            pass
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

    # Truncate collected output to avoid context bloat
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

    logger.info("Initialising Universal MCP Registry (background)…")
    asyncio.create_task(_init_mcp_registry())

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

    # Register with the voice bridge so MCP clients (Claude Code) can use mic/TTS
    from src.voice_bridge import voice_bridge
    voice_bridge.register_ws(websocket, stt=stt, tts=tts)

    audio_buffer: bytearray = bytearray()
    streaming_stt: DeepgramStreamingSession | None = None
    _interim_relay_task: asyncio.Task | None = None
    _speech_active = False  # True once VAD detects speech onset

    async def _relay_interims() -> None:
        """Background task: read interim transcripts from Deepgram, send to frontend."""
        nonlocal streaming_stt
        try:
            while streaming_stt and not streaming_stt._closed:
                text = await streaming_stt.interim_queue.get()
                if text is None:
                    break
                await websocket.send_json({"type": "interim_transcript", "text": text})
        except Exception as exc:
            logger.debug("[StreamSTT] Interim relay stopped: %s", exc)

    async def _start_streaming_stt() -> None:
        """Start a new streaming STT session for real-time interim transcripts.

        Picks provider based on STT_PROVIDER env var:
        - "deepgram" (default): Cloud streaming via Deepgram Nova-2
        - "whisper-local": Fully offline via faster-whisper (CTranslate2)
        """
        nonlocal streaming_stt, _interim_relay_task
        provider = os.environ.get("STT_PROVIDER", "deepgram").lower()

        try:
            if provider == "whisper-local":
                model_size = os.environ.get("WHISPER_MODEL", "base.en")
                streaming_stt = WhisperLocalSession(model_size=model_size)
                await streaming_stt.start()
                logger.info("[StreamSTT] Using local Whisper (%s)", model_size)
            else:
                dg_key = os.environ.get("DEEPGRAM_API_KEY", "")
                if not dg_key:
                    return
                streaming_stt = DeepgramStreamingSession(api_key=dg_key)
                await streaming_stt.start()
                logger.info("[StreamSTT] Using Deepgram cloud")
            _interim_relay_task = asyncio.create_task(_relay_interims())
        except Exception as exc:
            logger.warning("[StreamSTT] Failed to start: %s", exc)
            streaming_stt = None

    thread_id = _new_thread_id()
    config = {"configurable": {"thread_id": thread_id}}
    logger.info("[Session] New thread: %s", thread_id)
    debug_logger.log_ws_event("connect", thread_id, {"url": str(websocket.url)})

    # Per-session SQLite checkpointer — persists graph state across restarts (GAP #2).
    _session_checkpointer = await get_checkpointer(thread_id)
    graph = compile_graph(checkpointer=_session_checkpointer)
    tts_active = False  # Track if TTS is currently playing

    # Wake word gate — only process speech that starts with "voco" / "hey voco" etc.
    # Toggled via settings; defaults to ON so ambient speech is ignored.
    _WAKE_WORDS = ("hey voco", "a voco", "voco", "hey boco", "boco", "hey poco", "poco")
    _wake_word_required = True  # Can be toggled via update_env / settings

    # Observability: send session_id to frontend so logs can be correlated
    tracer = get_tracer()
    await websocket.send_json({"type": "session_init", "session_id": thread_id})

    # Per-session auth state (populated by auth_sync from frontend)
    _auth_uid = "local"
    _auth_token = ""
    _stripe_customer_id = ""
    _user_email = ""
    _is_founder = False

    FOUNDER_EMAILS = {
        "autrearchitect@gmail.com",
        "architect@viperbyproof.com",
    }

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
        """Signal Tauri to halt TTS playback immediately (barge-in).

        Also starts streaming STT session on speech onset for real-time transcripts.
        """
        nonlocal tts_active, _speech_active
        if voice_bridge._tts_playing:
            voice_bridge.trigger_barge_in()
            await websocket.send_json({"type": "control", "action": "halt_audio_playback"})
            logger.info("[Barge-in] Voice bridge TTS interrupted by user speech")
        elif tts_active:
            await websocket.send_json({"type": "control", "action": "halt_audio_playback"})

        # Start streaming STT on speech onset (first barge-in/speech detection)
        if not _speech_active and not streaming_stt:
            _speech_active = True
            await _start_streaming_stt()

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

    _turn_in_progress = False

    async def _on_turn_end(text_override: str | None = None) -> None:
        """Full pipeline: STT → LangGraph → (optional JSON-RPC) → TTS.

        When ``text_override`` is provided the STT step is skipped entirely —
        the text arrives directly from the "Type instead" input box and is fed
        straight into LangGraph.  Billing still fires at the end so typed turns
        are metered identically to spoken turns.
        """
        nonlocal audio_buffer, tts_active, _turn_in_progress, streaming_stt, _speech_active

        if _turn_in_progress:
            logger.warning("[Pipeline] Turn already in progress — ignoring duplicate trigger.")
            return
        _turn_in_progress = True
        _speech_active = False  # Reset for next turn

        _session_metrics["turn_count"] += 1
        await websocket.send_json({"type": "control", "action": "turn_ended", "turn_count": _session_metrics["turn_count"]})

        if text_override is not None:
            # --- Text input path: skip STT ---
            transcript = text_override
            logger.info("[Pipeline] Text input: %.120s", transcript)
            await websocket.send_json({"type": "transcript", "text": transcript})
            # Clean up streaming session if any
            if streaming_stt:
                await streaming_stt.stop()
                streaming_stt = None
            await websocket.send_json({"type": "interim_transcript", "text": ""})
        else:
            # --- Voice path: transcribe via streaming STT or fallback ---
            if not audio_buffer:
                logger.warning("[Pipeline] Turn ended with empty audio buffer — skipping.")
                if streaming_stt:
                    await streaming_stt.stop()
                    streaming_stt = None
                return

            # Require a minimum buffer size to avoid transcribing noise/clicks
            if len(audio_buffer) < AUDIO_MIN_BUFFER_SIZE:
                logger.info("[Pipeline] Audio buffer too small (%d bytes) — likely noise, skipping.", len(audio_buffer))
                audio_buffer = bytearray()
                if streaming_stt:
                    await streaming_stt.stop()
                    streaming_stt = None
                await websocket.send_json({"type": "interim_transcript", "text": ""})
                return

            try:
                if streaming_stt:
                    # Use streaming session's accumulated final transcript
                    transcript = await streaming_stt.finish()
                    streaming_stt = None
                    # Clear interim display
                    await websocket.send_json({"type": "interim_transcript", "text": ""})
                else:
                    # Fallback: batch transcription
                    provider = os.environ.get("STT_PROVIDER", "deepgram").lower()
                    if provider == "whisper-local":
                        model_size = os.environ.get("WHISPER_MODEL", "base.en")
                        local = WhisperLocalSession(model_size=model_size)
                        await local.start()
                        await local.feed(bytes(audio_buffer))
                        transcript = await local.finish()
                    else:
                        transcript = await stt.transcribe_once(bytes(audio_buffer))
            except (ValueError, Exception) as stt_err:
                audio_buffer = bytearray()
                if streaming_stt:
                    await streaming_stt.stop()
                    streaming_stt = None
                await websocket.send_json({"type": "interim_transcript", "text": ""})
                await send_error(websocket, VocoError(
                    code=ErrorCode.E_STT_FAILED,
                    message=str(stt_err),
                    recoverable=False,
                    session_id=thread_id,
                ))
                return
            audio_buffer = bytearray()

            if not transcript or len(transcript.strip()) < 2:
                logger.info("[Pipeline] Empty/trivial transcript — user may have been silent.")
                return

            logger.info("[Pipeline] Transcript: %s", transcript)

            # Wake word gate: ignore speech not directed at Voco (skip in bridge mode)
            if not voice_bridge.in_bridge_mode and _wake_word_required:
                transcript_lower = transcript.lower()
                if not any(w in transcript_lower for w in _WAKE_WORDS):
                    logger.info("[Pipeline] No wake word detected — ignoring ambient speech")
                    _turn_in_progress = False
                    return
                # Strip the wake word prefix so Claude gets clean input
                for w in _WAKE_WORDS:
                    idx = transcript_lower.find(w)
                    if idx != -1:
                        transcript = transcript[idx + len(w):].strip(" ,.")
                        break
                if not transcript or len(transcript.strip()) < 2:
                    logger.info("[Pipeline] Wake word only, no command — ignoring")
                    _turn_in_progress = False
                    return

            await websocket.send_json({"type": "transcript", "text": transcript})

            # Bridge mode: route transcript to MCP client instead of LangGraph
            if voice_bridge.in_bridge_mode:
                logger.info("[Pipeline] Bridge mode — routing transcript to MCP client")
                voice_bridge.resolve_transcript(transcript)
                _turn_in_progress = False
                return

        # --- Step 2: Run LangGraph (Claude 3.5 Sonnet) ---
        await _send_ledger_update(domain="general", context_router="active", orchestrator="pending", tools="pending")

        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {"messages": [HumanMessage(content=transcript)]},
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

            # TTS: announce proposals (non-fatal — HITL must proceed even if TTS fails)
            desc_list = [p.get("description", p.get("file_path", "")) for p in proposals]
            summary_text = f"I have {len(proposals)} proposal{'s' if len(proposals) != 1 else ''} for your review. {'. '.join(desc_list)}. Say approve or reject."
            try:
                await websocket.send_json({"type": "control", "action": "tts_start", "text": summary_text, "tts_active": True})
                tts_active = True
                vad.suppress(True)
                async for audio_chunk in tts.synthesize_stream(summary_text):
                    await websocket.send_bytes(audio_chunk)
            except Exception as tts_exc:
                logger.warning("[Pipeline] TTS failed during proposal announcement: %s", tts_exc)
            finally:
                try:
                    await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
                except Exception:
                    pass
                await asyncio.sleep(TTS_GRACE_PERIOD)
                tts_active = False
                vad.suppress(False)
                vad.reset()
                audio_buffer = bytearray()

            # Wait for proposal_decision from frontend (filtered receive)
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

            # TTS: announce commands (non-fatal — HITL must proceed even if TTS fails)
            cmd_descs = [c.get("description", c.get("command", "")) for c in commands]
            cmd_summary = f"I need to run {len(commands)} command{'s' if len(commands) != 1 else ''}. {'. '.join(cmd_descs)}. Approve or reject."
            try:
                await websocket.send_json({"type": "control", "action": "tts_start", "text": cmd_summary, "tts_active": True})
                tts_active = True
                vad.suppress(True)
                async for audio_chunk in tts.synthesize_stream(cmd_summary):
                    await websocket.send_bytes(audio_chunk)
            except Exception as tts_exc:
                logger.warning("[Pipeline] TTS failed during command announcement: %s", tts_exc)
            finally:
                try:
                    await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})
                except Exception:
                    pass
                await asyncio.sleep(TTS_GRACE_PERIOD)
                tts_active = False
                vad.suppress(False)
                vad.reset()
                audio_buffer = bytearray()

            # Wait for command_decision from frontend (filtered receive)
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
            # Secret Menu: delegate_to_claude_code
            # Uses Instant ACK + Background Task pattern so the WS handler
            # returns immediately (prevents keepalive ping timeout).
            # The subprocess result is injected into the checkpoint; Claude
            # sees it on the user's next turn.
            # ----------------------------------------------------------------
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

                # Instant ACK — satisfies Claude's tool_call → tool_result contract
                ack_tool_msg = ToolMessage(
                    content=(
                        "Claude Code delegation started in the background. "
                        "Tell the user: 'I've handed this off to Claude Code — "
                        "I'll let you know when it's done.' Keep it short."
                    ),
                    tool_call_id=call_id,
                )
                result = await graph.ainvoke({"messages": [ack_tool_msg]}, config=config)

                # Background task — runs the subprocess without blocking the WS handler
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

                    # Inject result into checkpoint so Claude sees it next turn
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

            # ----------------------------------------------------------------
            # Synchronous Agentic Loop — like Claude Code
            # Tool call → Tauri RPC → result → feed back to Claude → repeat
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

                # --- Synchronous tool loop (max 5 iterations to prevent infinite loops) ---
                MAX_TOOL_LOOPS = 5
                loop_count = 0

                # Heartbeat keeps WebSocket alive during long tool executions
                async def _heartbeat():
                    try:
                        while True:
                            await asyncio.sleep(15)
                            await websocket.send_json({"type": "heartbeat"})
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

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

                    # Notify frontend of the running tool
                    job_id = uuid.uuid4().hex[:8]
                    await websocket.send_json({
                        "type": "background_job_start",
                        "job_id": job_id,
                        "tool_name": tool_name,
                    })

                    # 1. Send RPC to Tauri and await the response synchronously.
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

                    # Mark job complete in frontend
                    try:
                        await websocket.send_json({
                            "type": "background_job_complete",
                            "job_id": job_id,
                            "tool_name": tool_name,
                        })
                    except Exception:
                        pass

                    # 2. Feed the real result back to Claude as a proper ToolMessage.
                    tool_result_msg = ToolMessage(
                        content=tool_result_str[:4000],  # Cap to avoid context bloat
                        tool_call_id=call_id,
                    )

                    # 3. Re-invoke the graph so Claude processes the result.
                    result = await graph.ainvoke(
                        {"messages": [tool_result_msg]},
                        config=config,
                    )

                    # 4. Check if Claude wants to call another tool (agentic loop).
                    next_msg = result["messages"][-1]
                    if isinstance(next_msg, AIMessage) and next_msg.tool_calls:
                        # Claude wants another tool — loop again
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
                        # Claude is done — break out, proceed to TTS
                        break

                _heartbeat_task.cancel()

                logger.info(
                    "[Pipeline] Agentic loop done after %d iteration(s).", loop_count,
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
        vad.suppress(True)
        try:
            chunk_count = 0
            async for audio_chunk in tts.synthesize_stream(response_text):
                await websocket.send_bytes(audio_chunk)
                chunk_count += 1
            logger.info("[TTS] Sent %d audio chunks to frontend.", chunk_count)
            if chunk_count == 0:
                logger.warning("[TTS] Zero audio chunks — Cartesia may have rejected the request.")
                await send_error(websocket, VocoError(
                    code=ErrorCode.E_TTS_FAILED,
                    message="Voice synthesis returned no audio — your Cartesia API key may be expired.",
                ))
        except Exception as tts_exc:
            logger.error("[TTS] Synthesis failed: %s", tts_exc)
            await send_error(websocket, VocoError(
                code=ErrorCode.E_TTS_FAILED,
                message=f"Voice synthesis failed: {tts_exc}",
            ))

        await websocket.send_json({"type": "control", "action": "tts_end", "tts_active": False})

        # Grace period BEFORE resuming mic — speakers may still be playing
        await asyncio.sleep(TTS_GRACE_PERIOD)
        tts_active = False
        vad.suppress(False)
        vad.reset()
        audio_buffer = bytearray()

        # --- Stripe Seat + Meter: report one voice turn (fire and forget) ---
        if _is_founder:
            logger.debug("[Billing] Skipping meter for founder %s", _user_email)
        else:
            asyncio.create_task(report_voice_turn(customer_id=_stripe_customer_id))

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
        nonlocal _turn_in_progress
        with tracer.start_as_current_span("voco.session.turn", attributes={"session.id": thread_id}):
            try:
                await _on_turn_end()
            except Exception as exc:
                logger.error("[Pipeline] Turn-end pipeline error: %s", exc, exc_info=True)
                # Parse structured error codes from orchestrator_node
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
                except Exception:
                    pass
            finally:
                _turn_in_progress = False

    async def _safe_text_input(text: str) -> None:
        """Run the full pipeline for a typed message, bypassing STT."""
        nonlocal _turn_in_progress
        with tracer.start_as_current_span("voco.session.turn", attributes={"session.id": thread_id, "input.type": "text"}):
            try:
                await _on_turn_end(text_override=text)
            except Exception as exc:
                logger.error("[Pipeline] Text input pipeline error: %s", exc, exc_info=True)
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
                except Exception:
                    pass
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
                    asyncio.create_task(_safe_text_input(text))
            elif msg_type == "auth_sync":
                nonlocal _auth_token, _auth_uid, _stripe_customer_id, _user_email, _is_founder
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
                # During voice bridge TTS: run VAD with stricter thresholds for barge-in
                if voice_bridge._tts_playing:
                    vad._bridge_barge_in_mode = True
                    await vad.process_chunk(chunk)
                    continue
                # Transition from bridge TTS → normal: reset VAD + buffer to flush echo
                if vad._bridge_barge_in_mode:
                    vad._bridge_barge_in_mode = False
                    vad.reset()
                    audio_buffer = bytearray()
                    logger.debug("[Pipeline] Bridge TTS ended — VAD reset, buffer cleared")
                # Skip VAD processing while normal TTS is active (prevents echo feedback)
                if tts_active:
                    continue
                audio_buffer.extend(chunk)
                # Feed audio to streaming STT for real-time interim transcripts
                if streaming_stt:
                    await streaming_stt.feed(chunk)
                elif not _speech_active and len(audio_buffer) > 1024:
                    # Start streaming on first substantial audio (VAD hasn't fired barge_in yet)
                    _speech_active = True
                    await _start_streaming_stt()
                    if streaming_stt:
                        # Feed buffered audio so far
                        await streaming_stt.feed(bytes(audio_buffer))
                await vad.process_chunk(chunk)
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type", "")

                    if msg_type == "bridge_barge_in":
                        # User clicked orb to interrupt voice bridge TTS
                        voice_bridge.trigger_barge_in()
                        logger.info("[WS] Bridge barge-in from user (orb click)")
                    elif msg_type == "text_input":
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
                            # Verify JWT signature (fail-open in dev when secret not set)
                            _verify_supabase_jwt(_auth_token, _auth_uid)
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

                            # Look up stripe_customer_id + email from users table
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
                                            # Send tier + founder status to frontend (avoids frontend needing direct DB access)
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
                        # Toggle wake word requirement from settings
                        if "wake_word" in env_patch:
                            _wake_word_required = str(env_patch["wake_word"]).lower() not in ("false", "0", "off", "disabled")
                            logger.info("[WS] Wake word requirement: %s", _wake_word_required)
                        logger.info("[WS] Environment updated: %s", list(env_patch.keys()))
                    elif msg_type == "cancel_job":
                        cancel_id = payload.get("job_id", "")
                        if cancel_id:
                            background_queue.cancel_job(cancel_id)
                            logger.info("[WS] Cancel requested for job %s", cancel_id)
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
        voice_bridge.unregister_ws(websocket)
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
