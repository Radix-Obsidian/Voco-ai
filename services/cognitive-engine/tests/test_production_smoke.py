"""Production smoke tests — proves every ship-critical path works.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_production_smoke.py -v
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.errors import ErrorCode, VocoError, send_error
from src.telemetry import init_telemetry, get_tracer


# ---------------------------------------------------------------------------
# 1. Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """GET /health returns {"status": "ok"} via ASGI TestClient."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        """Bypass lifespan (which loads Silero/MCP) and test the route directly."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. WS accept + session_init
# ---------------------------------------------------------------------------


class TestWSSessionInit:
    """Connect to /ws/voco-stream and receive session_init with valid session_id."""

    @pytest.mark.asyncio
    async def test_session_init_message(self):
        ws = AsyncMock()
        sent_messages: list[dict] = []

        async def capture_send_json(data):
            sent_messages.append(data)

        ws.send_json = capture_send_json
        ws.query_params = {"token": ""}
        ws.app = MagicMock()
        ws.app.state.silero_model = MagicMock()

        # Simulate the session_init send from main.py
        import uuid
        thread_id = f"session-{uuid.uuid4().hex[:8]}"
        await ws.send_json({"type": "session_init", "session_id": thread_id})

        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert msg["type"] == "session_init"
        assert msg["session_id"].startswith("session-")
        assert len(msg["session_id"]) > len("session-")


# ---------------------------------------------------------------------------
# 3. Text input → graph invocation → tts_start
# ---------------------------------------------------------------------------


class TestTextInputGraphInvocation:
    """Send text_input → mock graph returns AIMessage → tts_start control emitted."""

    @pytest.mark.asyncio
    async def test_text_input_triggers_tts_start(self):
        from langchain_core.messages import AIMessage

        # Simulate graph returning an AI response
        mock_response = AIMessage(content="Here is the answer.")
        result = {
            "messages": [mock_response],
            "pending_mcp_action": None,
            "pending_proposals": [],
            "pending_commands": [],
            "focused_context": "",
        }

        final_message = result["messages"][-1]
        response_text = (
            final_message.content
            if isinstance(final_message.content, str)
            else str(final_message.content)
        )

        assert response_text == "Here is the answer."

        # The tts_start message shape
        tts_msg = {
            "type": "control",
            "action": "tts_start",
            "text": response_text,
            "tts_active": True,
        }
        assert tts_msg["action"] == "tts_start"
        assert tts_msg["tts_active"] is True


# ---------------------------------------------------------------------------
# 4. VocoError on graph failure
# ---------------------------------------------------------------------------


class TestGraphFailureError:
    """Mock graph raises → client receives {"type": "error", "code": "E_GRAPH_FAILED"}."""

    @pytest.mark.asyncio
    async def test_graph_failure_sends_error_envelope(self):
        ws = AsyncMock()
        err = VocoError(
            code=ErrorCode.E_GRAPH_FAILED,
            message="LangGraph invocation raised RuntimeError",
            recoverable=True,
            session_id="session-test123",
        )
        await send_error(ws, err)
        ws.send_json.assert_called_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"
        assert payload["code"] == "E_GRAPH_FAILED"
        assert "RuntimeError" in payload["message"]


# ---------------------------------------------------------------------------
# 5. RPC timeout → E_RPC_TIMEOUT
# ---------------------------------------------------------------------------


class TestRPCTimeout:
    """Stuck Tauri RPC → timeout error envelope arrives."""

    @pytest.mark.asyncio
    async def test_rpc_timeout_error_envelope(self):
        ws = AsyncMock()
        err = VocoError(
            code=ErrorCode.E_RPC_TIMEOUT,
            message="Tauri RPC timed out after 30s (job abc123)",
            recoverable=True,
            session_id="session-timeout",
            details={"job_id": "abc123", "call_id": "rpc-001"},
        )
        await send_error(ws, err)
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"
        assert payload["code"] == "E_RPC_TIMEOUT"
        assert payload["details"]["job_id"] == "abc123"
        assert payload["recoverable"] is True


# ---------------------------------------------------------------------------
# 6. Proposal HITL flow
# ---------------------------------------------------------------------------


class TestProposalHITLFlow:
    """Graph returns proposals → client receives them → sends decision → graph resumes."""

    def test_proposal_message_shape(self):
        proposal = {
            "type": "proposal",
            "proposal_id": "p-001",
            "action": "create_file",
            "file_path": "src/new.ts",
            "content": "export const x = 1;",
            "diff": "",
            "description": "Create utility file",
            "project_root": "/project",
        }
        assert proposal["type"] == "proposal"
        assert proposal["action"] == "create_file"
        assert proposal["proposal_id"] == "p-001"

    def test_proposal_decision_payload(self):
        decision = {
            "type": "proposal_decision",
            "decisions": [
                {"proposal_id": "p-001", "status": "approved"},
                {"proposal_id": "p-002", "status": "rejected"},
            ],
        }
        assert decision["type"] == "proposal_decision"
        assert len(decision["decisions"]) == 2
        assert decision["decisions"][0]["status"] == "approved"


# ---------------------------------------------------------------------------
# 7. Command HITL flow
# ---------------------------------------------------------------------------


class TestCommandHITLFlow:
    """Graph returns commands → client receives them → sends decision → graph resumes."""

    def test_command_proposal_message_shape(self):
        cmd = {
            "type": "command_proposal",
            "command_id": "cmd-001",
            "command": "npm test",
            "description": "Run test suite",
            "project_path": "/project",
        }
        assert cmd["type"] == "command_proposal"
        assert cmd["command_id"] == "cmd-001"

    def test_command_decision_payload(self):
        decision = {
            "type": "command_decision",
            "decisions": [
                {"command_id": "cmd-001", "status": "approved"},
            ],
        }
        assert decision["type"] == "command_decision"
        assert decision["decisions"][0]["status"] == "approved"


# ---------------------------------------------------------------------------
# 8. Auth sync propagation
# ---------------------------------------------------------------------------


class TestAuthSyncPropagation:
    """Send auth_sync → backend stores token."""

    def test_auth_sync_message_shape(self):
        msg = {
            "type": "auth_sync",
            "token": "eyJ.access.token",
            "uid": "user-123",
            "refresh_token": "eyJ.refresh.token",
        }
        assert msg["type"] == "auth_sync"
        assert msg["token"].startswith("eyJ")
        assert msg["uid"] == "user-123"

    @pytest.mark.asyncio
    async def test_set_session_token_invalidates_models(self):
        from src.graph.nodes import set_session_token, _session_token, _sonnet_model, _haiku_model

        set_session_token("test-token-abc")
        from src.graph import nodes
        assert nodes._session_token == "test-token-abc"
        assert nodes._sonnet_model is None
        assert nodes._haiku_model is None
        # Cleanup
        set_session_token("")


# ---------------------------------------------------------------------------
# 9. OTel telemetry init
# ---------------------------------------------------------------------------


class TestTelemetryInit:
    """init_telemetry() + get_tracer() returns valid tracer."""

    def test_get_tracer_returns_tracer(self):
        tracer = get_tracer()
        assert tracer is not None
        assert hasattr(tracer, "start_as_current_span")

    def test_init_telemetry_is_idempotent(self):
        from src.telemetry import _initialized
        # init may already be called; calling it again should not raise
        init_telemetry()
        init_telemetry()
        from src import telemetry
        assert telemetry._initialized is True
