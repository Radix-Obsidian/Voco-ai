"""Tests for the VocoError envelope and send_error utility.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_error_envelope.py -v
"""

from unittest.mock import AsyncMock

import pytest

from src.errors import ErrorCode, VocoError, send_error


class TestVocoErrorSerialization:
    """VocoError.to_dict() produces the expected JSON shape."""

    def test_basic_serialization(self):
        err = VocoError(
            code=ErrorCode.E_STT_FAILED,
            message="Deepgram returned 503",
            recoverable=True,
            session_id="session-abc123",
        )
        d = err.to_dict()
        assert d["type"] == "error"
        assert d["code"] == "E_STT_FAILED"
        assert d["message"] == "Deepgram returned 503"
        assert d["recoverable"] is True
        assert d["session_id"] == "session-abc123"
        assert "details" not in d

    def test_serialization_with_details(self):
        err = VocoError(
            code=ErrorCode.E_RPC_TIMEOUT,
            message="Timed out",
            recoverable=True,
            session_id="session-xyz",
            details={"job_id": "abc", "call_id": "rpc-1"},
        )
        d = err.to_dict()
        assert d["details"] == {"job_id": "abc", "call_id": "rpc-1"}

    def test_non_recoverable_error(self):
        err = VocoError(
            code=ErrorCode.E_AUTH_EXPIRED,
            message="Token expired",
            recoverable=False,
            session_id="session-auth",
        )
        d = err.to_dict()
        assert d["recoverable"] is False

    def test_all_error_codes_are_strings(self):
        for code in ErrorCode:
            assert isinstance(code.value, str)
            assert code.value.startswith("E_")


class TestSendError:
    """send_error() calls websocket.send_json() with the correct payload."""

    @pytest.mark.asyncio
    async def test_send_error_calls_send_json(self):
        ws = AsyncMock()
        err = VocoError(
            code=ErrorCode.E_GRAPH_FAILED,
            message="Graph raised RuntimeError",
            session_id="session-test",
        )
        await send_error(ws, err)
        ws.send_json.assert_called_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"
        assert payload["code"] == "E_GRAPH_FAILED"
        assert payload["message"] == "Graph raised RuntimeError"

    @pytest.mark.asyncio
    async def test_send_error_swallows_send_failure(self):
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("WebSocket closed")
        err = VocoError(code=ErrorCode.E_TTS_FAILED, message="TTS broke")
        # Should NOT raise
        await send_error(ws, err)
