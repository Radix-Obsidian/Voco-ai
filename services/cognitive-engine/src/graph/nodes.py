"""LangGraph node functions for the Voco cognitive engine."""

from langchain_core.messages import AIMessage

from .state import VocoState


async def orchestrator_node(state: VocoState) -> dict:
    last_message = state["messages"][-1]
    print(f"[Orchestrator 🧠] User said: {last_message.content}")

    return {
        "messages": [AIMessage(content="I hear you!")],
        "barge_in_detected": False,
    }


async def mcp_gateway_node(state: VocoState) -> dict:
    print("[MCP Gateway 🏗️] Placeholder for JSON-RPC dispatch to Tauri.")
    return {}
