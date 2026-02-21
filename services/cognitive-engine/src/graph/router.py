"""LangGraph StateGraph definition for the Voco cognitive engine."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import mcp_gateway_node, orchestrator_node
from .state import VocoState


def _route_after_orchestrator(state: VocoState) -> str:
    if state["barge_in_detected"]:
        return "orchestrator_node"
    return "mcp_gateway_node"


builder = StateGraph(VocoState)

builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("mcp_gateway_node", mcp_gateway_node)

builder.add_edge(START, "orchestrator_node")
builder.add_conditional_edges(
    "orchestrator_node",
    _route_after_orchestrator,
    {
        "orchestrator_node": "orchestrator_node",
        "mcp_gateway_node": "mcp_gateway_node",
    },
)
builder.add_edge("mcp_gateway_node", END)

graph = builder.compile(checkpointer=InMemorySaver())
