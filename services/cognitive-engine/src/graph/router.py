"""LangGraph StateGraph definition for the Voco cognitive engine."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import command_review_node, context_router_node, mcp_gateway_node, orchestrator_node, proposal_review_node
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
builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("mcp_gateway_node", mcp_gateway_node)
builder.add_node("proposal_review_node", proposal_review_node)
builder.add_node("command_review_node", command_review_node)

builder.add_edge(START, "context_router_node")
builder.add_edge("context_router_node", "orchestrator_node")
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

graph = builder.compile(
    checkpointer=InMemorySaver(),
    interrupt_before=["proposal_review_node", "command_review_node"],
)
