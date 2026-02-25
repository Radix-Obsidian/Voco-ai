"""Tests for context_router_node, boss_router_node, orchestrator_node routing logic.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_graph_routing.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.graph.nodes import (
    _detect_domain,
    context_router_node,
)
from src.graph.token_guard import trim_messages_to_budget
from unittest.mock import call as _mock_call


# ---------------------------------------------------------------------------
# 1. context_router_node detects "database" domain
# ---------------------------------------------------------------------------


class TestContextRouterDatabase:
    @pytest.mark.asyncio
    async def test_detects_database_domain(self):
        state = {"messages": [HumanMessage(content="Show me the database schema and SQL migrations")]}
        result = await context_router_node(state)
        assert "Database" in result.get("focused_context", "")

    def test_detect_domain_database_keywords(self):
        domain, context = _detect_domain("query the postgres database for user table")
        assert domain == "database"
        assert "Database" in context


# ---------------------------------------------------------------------------
# 2. context_router_node detects "ui" domain
# ---------------------------------------------------------------------------


class TestContextRouterUI:
    @pytest.mark.asyncio
    async def test_detects_ui_domain(self):
        state = {"messages": [HumanMessage(content="Fix the React component button styling with Tailwind CSS")]}
        result = await context_router_node(state)
        assert "UI" in result.get("focused_context", "")

    def test_detect_domain_ui_keywords(self):
        domain, context = _detect_domain("create a React component with Tailwind layout")
        assert domain == "ui"
        assert "UI" in context


# ---------------------------------------------------------------------------
# 3. boss_router_node → haiku for chat
# ---------------------------------------------------------------------------


class TestBossRouterHaiku:
    @pytest.mark.asyncio
    async def test_routes_chat_to_haiku(self):
        mock_boss = AsyncMock()
        mock_boss.ainvoke.return_value = AIMessage(content="haiku")

        state = {"messages": [HumanMessage(content="Hello, how are you?")]}

        with patch("src.graph.nodes._get_boss", return_value=mock_boss):
            from src.graph.nodes import boss_router_node
            result = await boss_router_node(state)
            assert result["routed_model"] == "haiku"


# ---------------------------------------------------------------------------
# 4. boss_router_node → sonnet for code
# ---------------------------------------------------------------------------


class TestBossRouterSonnet:
    @pytest.mark.asyncio
    async def test_routes_code_to_sonnet(self):
        mock_boss = AsyncMock()
        mock_boss.ainvoke.return_value = AIMessage(content="sonnet")

        state = {"messages": [HumanMessage(content="Write a rate limiter middleware in Express")]}

        with patch("src.graph.nodes._get_boss", return_value=mock_boss):
            from src.graph.nodes import boss_router_node
            result = await boss_router_node(state)
            assert result["routed_model"] == "sonnet"

    @pytest.mark.asyncio
    async def test_defaults_to_sonnet_on_failure(self):
        mock_boss = AsyncMock()
        mock_boss.ainvoke.side_effect = RuntimeError("API down")

        state = {"messages": [HumanMessage(content="anything")]}

        with patch("src.graph.nodes._get_boss", return_value=mock_boss):
            from src.graph.nodes import boss_router_node
            result = await boss_router_node(state)
            assert result["routed_model"] == "sonnet"


# ---------------------------------------------------------------------------
# 5. orchestrator_node returns turn_metadata
# ---------------------------------------------------------------------------


class TestOrchestratorTurnMetadata:
    @pytest.mark.asyncio
    async def test_turn_metadata_present(self):
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = AIMessage(content="Done.")

        state = {
            "messages": [HumanMessage(content="Hello")],
            "routed_model": "haiku",
            "focused_context": "",
            "turn_metadata": None,
        }

        with patch("src.graph.nodes._get_haiku", return_value=mock_model), \
             patch("src.graph.nodes._get_sonnet", return_value=mock_model), \
             patch("src.graph.nodes.archive_turn", return_value="abc123"):
            from src.graph.nodes import orchestrator_node
            result = await orchestrator_node(state)

        meta = result.get("turn_metadata")
        assert meta is not None
        assert "prompt_hash" in meta
        assert "model_id" in meta
        assert "turn_number" in meta
        assert meta["turn_number"] == 1
        assert len(meta["prompt_hash"]) == 12


# ---------------------------------------------------------------------------
# 6. orchestrator_node tool_call separation
# ---------------------------------------------------------------------------


class TestOrchestratorToolCallSeparation:
    @pytest.mark.asyncio
    async def test_separates_proposals_commands_mcp(self):
        # AIMessage with multiple tool_calls
        response = AIMessage(
            content="I'll do three things.",
            tool_calls=[
                {"name": "propose_file_creation", "args": {"file_path": "a.ts", "content": "x", "description": "d"}, "id": "tc-1"},
                {"name": "propose_command", "args": {"command": "npm test", "description": "run tests", "project_path": "/p"}, "id": "tc-2"},
                {"name": "search_codebase", "args": {"pattern": "auth", "project_path": "/p"}, "id": "tc-3"},
            ],
        )

        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = response

        state = {
            "messages": [HumanMessage(content="Do multiple things")],
            "routed_model": "sonnet",
            "focused_context": "",
            "turn_metadata": None,
        }

        with patch("src.graph.nodes._get_sonnet", return_value=mock_model), \
             patch("src.graph.nodes._get_haiku", return_value=mock_model), \
             patch("src.graph.nodes.archive_turn", return_value="abc"):
            from src.graph.nodes import orchestrator_node
            result = await orchestrator_node(state)

        # File proposals go to pending_proposals
        assert len(result.get("pending_proposals", [])) == 1
        # Command proposals go to pending_commands
        assert len(result.get("pending_commands", [])) == 1
        # First non-proposal/command tool_call goes to pending_mcp_action
        assert result.get("pending_mcp_action") is not None
        assert result["pending_mcp_action"]["name"] == "search_codebase"


# ---------------------------------------------------------------------------
# 7. token_guard trims over budget
# ---------------------------------------------------------------------------


class TestTokenGuardTrims:
    def test_short_list_unchanged(self):
        msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
        result = trim_messages_to_budget(
            system_prompt="You are Voco.",
            messages=msgs,
            model="claude-sonnet-4-5-20250929",
            max_tokens=200_000,
        )
        assert len(result) == len(msgs)

    def test_over_budget_trimmed(self):
        # BIG at index 0, then 11 small msgs so BIG falls outside last-10 protected window
        msgs = [HumanMessage(content="big old message")]
        for i in range(11):
            msgs.append(HumanMessage(content=f"recent {i}"))

        call_count = 0
        def fake_count(model, messages):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 200_000
            return 180_000 if len(messages) == 1 and "big" in str(messages[0].get("content", "")) else 10

        with patch("src.graph.token_guard._count_tokens", side_effect=fake_count):
            result = trim_messages_to_budget(
                system_prompt="You are Voco.",
                messages=msgs,
                model="claude-sonnet-4-5-20250929",
                max_tokens=160_000,
            )
        assert len(result) < len(msgs)
        assert any("recent" in str(m.content) for m in result)
