"""LangGraph StateGraph definition for the Voco cognitive engine."""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import boss_router_node, command_review_node, context_router_node, mcp_gateway_node, orchestrator_node, proposal_review_node
from .state import VocoState


def _route_after_orchestrator(state: VocoState) -> str:
    """Route based on barge-in flag, proposals, and whether Claude requested a tool call."""
    if state.get("barge_in_detected"):
        return "orchestrator_node"
    if state.get("pending_proposals"):
        return "proposal_review_node"
    if state.get("pending_commands"):
        return "command_review_node"
    if state.get("pending_mcp_action"):
        return "mcp_gateway_node"
    return END


builder = StateGraph(VocoState)

builder.add_node("context_router_node", context_router_node)
builder.add_node("boss_router_node", boss_router_node)
builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("mcp_gateway_node", mcp_gateway_node)
builder.add_node("proposal_review_node", proposal_review_node)
builder.add_node("command_review_node", command_review_node)

# Phase 2: context → boss router → orchestrator (boss selects Haiku or Sonnet)
builder.add_edge(START, "context_router_node")
builder.add_edge("context_router_node", "boss_router_node")
builder.add_edge("boss_router_node", "orchestrator_node")

builder.add_conditional_edges(
    "orchestrator_node",
    _route_after_orchestrator,
    {
        "orchestrator_node": "orchestrator_node",
        "mcp_gateway_node": "mcp_gateway_node",
        "proposal_review_node": "proposal_review_node",
        "command_review_node": "command_review_node",
        END: END,
    },
)
builder.add_edge("mcp_gateway_node", END)
builder.add_edge("proposal_review_node", "orchestrator_node")
builder.add_edge("command_review_node", "orchestrator_node")

def compile_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Compile the Voco StateGraph with the given checkpointer.

    If *checkpointer* is ``None``, falls back to ``InMemorySaver()``.
    This factory allows ``main.py`` to supply a per-session
    ``AsyncSqliteSaver`` for deterministic replay (Issue #2).
    """
    return builder.compile(
        checkpointer=checkpointer or InMemorySaver(),
        interrupt_before=["proposal_review_node", "command_review_node"],
    )


# NOTE: interrupt_before is the legacy HITL pattern (still functional).
# The modern LangGraph approach uses interrupt() inside nodes + Command(resume=value).
# Migration to modern pattern is tracked but deferred — current approach works correctly
# with InMemorySaver. See: https://docs.langchain.com/oss/python/langgraph/interrupts
graph = compile_graph()
