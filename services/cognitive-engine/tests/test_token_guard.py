"""Tests for token_guard — context-window overflow protection.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_token_guard.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.graph.token_guard import (
    _KEEP_LAST_CONV_MSGS,
    _KEEP_LAST_TOOL_MSGS,
    trim_messages_to_budget,
)


def _make_fake_counter(big_keyword: str = "BIG", big_tokens: int = 180_000, total_tokens: int = 200_000, small_tokens: int = 10):
    """Return a fake _count_tokens function that returns over-budget totals."""
    call_count = 0
    def fake(model, messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return total_tokens
        # Single-message calls for trimming estimation
        if len(messages) == 1 and big_keyword in str(messages[0].get("content", "")):
            return big_tokens
        return small_tokens
    return fake


# ---------------------------------------------------------------------------
# 1. Short list → unchanged
# ---------------------------------------------------------------------------


class TestShortListUnchanged:
    def test_short_conversation_passes_through(self):
        msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
        result = trim_messages_to_budget(
            system_prompt="You are Voco.",
            messages=msgs,
            max_tokens=500_000,
        )
        assert len(result) == 2
        assert result[0].content == "hi"
        assert result[1].content == "hello"


# ---------------------------------------------------------------------------
# 2. Over budget → trimmed
# ---------------------------------------------------------------------------


class TestOverBudgetTrimmed:
    def test_large_messages_trimmed(self):
        # BIG message at index 0, then 11 small messages so BIG falls outside last-10 protected window
        msgs = [HumanMessage(content="BIG message")]
        for i in range(11):
            msgs.append(HumanMessage(content=f"small-{i}"))

        with patch("src.graph.token_guard._count_tokens", side_effect=_make_fake_counter()):
            result = trim_messages_to_budget(
                system_prompt="Short prompt.",
                messages=msgs,
                max_tokens=160_000,
            )
        assert len(result) < len(msgs)

    def test_trimmed_result_preserves_recent(self):
        msgs = [
            HumanMessage(content="BIG old message"),
            HumanMessage(content="keep 1"),
            HumanMessage(content="keep 2"),
            AIMessage(content="keep 3"),
        ]
        with patch("src.graph.token_guard._count_tokens", side_effect=_make_fake_counter()):
            result = trim_messages_to_budget(
                system_prompt="System.",
                messages=msgs,
                max_tokens=160_000,
            )
        result_contents = [str(m.content) for m in result]
        assert "keep 1" in result_contents or "keep 2" in result_contents


# ---------------------------------------------------------------------------
# 3. Last 10 conversation messages protected
# ---------------------------------------------------------------------------


class TestLastConversationProtected:
    def test_last_10_conv_messages_preserved(self):
        msgs = [HumanMessage(content="BIG trimmable")]  # trimmable
        for i in range(12):
            msgs.append(HumanMessage(content=f"recent-{i}"))

        with patch("src.graph.token_guard._count_tokens", side_effect=_make_fake_counter("BIG")):
            result = trim_messages_to_budget(
                system_prompt="Prompt.",
                messages=msgs,
                max_tokens=160_000,
            )

        # The last 10 messages should all be preserved
        result_contents = [str(m.content) for m in result]
        for i in range(2, 12):  # last 10 of the 12 recent messages
            assert f"recent-{i}" in result_contents


# ---------------------------------------------------------------------------
# 4. Last 4 tool messages protected
# ---------------------------------------------------------------------------


class TestLastToolMessagesProtected:
    def test_last_4_tool_messages_preserved(self):
        msgs = [HumanMessage(content="BIG trimmable")]  # trimmable

        # Add 6 tool messages
        for i in range(6):
            msgs.append(ToolMessage(content=f"tool-result-{i}", tool_call_id=f"tc-{i}"))

        # Add a few recent human messages
        for i in range(3):
            msgs.append(HumanMessage(content=f"after-tool-{i}"))

        with patch("src.graph.token_guard._count_tokens", side_effect=_make_fake_counter("BIG")):
            result = trim_messages_to_budget(
                system_prompt="Prompt.",
                messages=msgs,
                max_tokens=160_000,
            )

        result_contents = [str(m.content) for m in result]
        # Last 4 tool messages (indices 2-5) should be preserved
        for i in range(2, 6):
            assert f"tool-result-{i}" in result_contents


# ---------------------------------------------------------------------------
# 5. System prompt never trimmed
# ---------------------------------------------------------------------------


class TestSystemPromptNeverTrimmed:
    def test_system_prompt_always_kept(self):
        # The system prompt is passed separately and is never in the trimmed list.
        # trim_messages_to_budget counts it but never removes it.
        msgs = [HumanMessage(content="BIG trimmable"), HumanMessage(content="last")]
        system = "You are Voco, the voice coding assistant."

        with patch("src.graph.token_guard._count_tokens", side_effect=_make_fake_counter("BIG")):
            result = trim_messages_to_budget(
                system_prompt=system,
                messages=msgs,
                max_tokens=160_000,
            )

        # The function returns messages only (system prompt is external),
        # so we just verify it didn't crash and returned something
        assert len(result) >= 1
        # The last message should always survive (it's in the protected window)
        assert result[-1].content == "last"
