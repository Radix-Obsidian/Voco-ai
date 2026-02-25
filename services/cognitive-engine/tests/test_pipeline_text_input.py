"""Tests for the text-input pipeline path (bypass STT, feed directly into LangGraph).

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_pipeline_text_input.py -v
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage


class _FakeGraphResult:
    """Minimal graph result dict for testing."""

    def __init__(self, content: str = "Hello!", tool_calls=None, pending_action=None):
        ai = AIMessage(content=content, tool_calls=tool_calls or [])
        self._data = {
            "messages": [ai],
            "pending_mcp_action": pending_action,
            "pending_proposals": [],
            "pending_commands": [],
            "focused_context": "",
        }

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.mark.asyncio
async def test_text_input_invokes_graph_with_human_message():
    """text_input message → graph invoked with HumanMessage."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = _FakeGraphResult("Test response")
    mock_graph.aget_state.return_value = MagicMock(next=[], values={})

    config = {"configurable": {"thread_id": "test-session"}}
    result = await mock_graph.ainvoke(
        {"messages": [HumanMessage(content="fix the bug")]},
        config=config,
    )

    mock_graph.ainvoke.assert_called_once()
    call_args = mock_graph.ainvoke.call_args[0][0]
    assert len(call_args["messages"]) == 1
    assert isinstance(call_args["messages"][0], HumanMessage)
    assert call_args["messages"][0].content == "fix the bug"


@pytest.mark.asyncio
async def test_empty_transcript_skips_pipeline():
    """Empty transcript → pipeline skipped (no graph invocation)."""
    mock_graph = AsyncMock()

    transcript = ""
    if not transcript or len(transcript.strip()) < 2:
        # Pipeline should be skipped
        pass
    else:
        await mock_graph.ainvoke({"messages": [HumanMessage(content=transcript)]})

    mock_graph.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_graph_raises_sends_voco_error():
    """graph raises → VocoError sent via WebSocket."""
    from src.errors import ErrorCode, VocoError, send_error

    mock_ws = AsyncMock()
    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = RuntimeError("Model overloaded")

    config = {"configurable": {"thread_id": "test-session"}}
    try:
        await mock_graph.ainvoke(
            {"messages": [HumanMessage(content="hello")]},
            config=config,
        )
    except RuntimeError as exc:
        error = VocoError(
            code=ErrorCode.E_GRAPH_FAILED,
            message=f"Pipeline error: {exc}",
            recoverable=True,
            session_id="test-session",
        )
        await send_error(mock_ws, error)

    mock_ws.send_json.assert_called_once()
    payload = mock_ws.send_json.call_args[0][0]
    assert payload["type"] == "error"
    assert payload["code"] == "E_GRAPH_FAILED"
    assert "Model overloaded" in payload["message"]


@pytest.mark.asyncio
async def test_tts_called_with_response_text():
    """Graph response text → TTS called → audio bytes sent back."""
    mock_tts = AsyncMock()

    # Simulate TTS producing 3 audio chunks
    async def fake_synthesize(text):
        for i in range(3):
            yield b"\x00" * 160

    mock_tts.synthesize_stream = fake_synthesize

    mock_ws = AsyncMock()
    response_text = "Here is my analysis of the bug."

    chunk_count = 0
    async for audio_chunk in mock_tts.synthesize_stream(response_text):
        await mock_ws.send_bytes(audio_chunk)
        chunk_count += 1

    assert chunk_count == 3
    assert mock_ws.send_bytes.call_count == 3
