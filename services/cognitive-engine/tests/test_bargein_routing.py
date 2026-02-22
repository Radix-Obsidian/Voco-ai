"""Barge-in routing stress test.

Validates that the LangGraph state machine correctly handles the
``barge_in_detected`` flag by re-routing to the orchestrator node
instead of proceeding to END or tool nodes.

This tests the *compiled graph's routing function* — the actual decision
logic that runs every turn. No mocks, no fake APIs.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_bargein_routing.py -v
"""

import pytest
from src.graph.router import _route_after_orchestrator
from src.graph.state import VocoState


def _make_state(**overrides) -> VocoState:
    """Build a minimal VocoState dict with sensible defaults."""
    base: dict = {
        "messages": [],
        "barge_in_detected": False,
        "pending_mcp_action": None,
        "pending_proposals": [],
        "pending_commands": [],
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


class TestBargeInRouting:
    """Ensure barge_in_detected always wins over other routing signals."""

    def test_bargein_overrides_end(self):
        """When barge-in fires during a normal (no-tool) response, re-route to orchestrator."""
        state = _make_state(barge_in_detected=True)
        assert _route_after_orchestrator(state) == "orchestrator_node"

    def test_bargein_overrides_mcp(self):
        """Barge-in takes priority even when a tool call is pending."""
        state = _make_state(
            barge_in_detected=True,
            pending_mcp_action={"name": "search_codebase", "args": {}, "id": "x"},
        )
        assert _route_after_orchestrator(state) == "orchestrator_node"

    def test_bargein_overrides_proposals(self):
        """Barge-in takes priority over pending file proposals."""
        state = _make_state(
            barge_in_detected=True,
            pending_proposals=[{"file_path": "foo.py"}],
        )
        assert _route_after_orchestrator(state) == "orchestrator_node"

    def test_bargein_overrides_commands(self):
        """Barge-in takes priority over pending command proposals."""
        state = _make_state(
            barge_in_detected=True,
            pending_commands=[{"command": "git push"}],
        )
        assert _route_after_orchestrator(state) == "orchestrator_node"

    def test_no_bargein_routes_to_end(self):
        """Without barge-in or tools, route to END."""
        from langgraph.graph import END
        state = _make_state()
        assert _route_after_orchestrator(state) == END

    def test_no_bargein_routes_to_mcp(self):
        """Without barge-in, pending MCP action routes to mcp_gateway_node."""
        state = _make_state(
            pending_mcp_action={"name": "search_codebase", "args": {}, "id": "x"},
        )
        assert _route_after_orchestrator(state) == "mcp_gateway_node"

    def test_no_bargein_routes_to_proposals(self):
        """Without barge-in, pending proposals route to proposal_review_node."""
        state = _make_state(pending_proposals=[{"file_path": "foo.py"}])
        assert _route_after_orchestrator(state) == "proposal_review_node"

    def test_no_bargein_routes_to_commands(self):
        """Without barge-in, pending commands route to command_review_node."""
        state = _make_state(pending_commands=[{"command": "npm test"}])
        assert _route_after_orchestrator(state) == "command_review_node"


class TestBargeInStress:
    """Rapid-fire barge-in toggling — ensure no state corruption."""

    @pytest.mark.parametrize("iteration", range(100))
    def test_rapid_bargein_toggle(self, iteration: int):
        """Toggle barge-in on/off 100 times — routing must stay deterministic."""
        bargein = iteration % 2 == 0
        state = _make_state(
            barge_in_detected=bargein,
            pending_mcp_action={"name": "search", "args": {}, "id": str(iteration)},
        )
        result = _route_after_orchestrator(state)
        if bargein:
            assert result == "orchestrator_node", f"Iteration {iteration}: expected orchestrator_node"
        else:
            assert result == "mcp_gateway_node", f"Iteration {iteration}: expected mcp_gateway_node"
