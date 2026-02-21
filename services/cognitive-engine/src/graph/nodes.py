"""LangGraph node functions for the Voco cognitive engine."""

from __future__ import annotations

import logging
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from .state import VocoState
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Voco, a voice-native coding assistant running as a local desktop agent. "
    "You have access to tools to search the user's codebase via the secure local MCP gateway. "
    "Be concise — your responses will be spoken aloud via TTS. "
    "When you need to find code, always use the search_codebase tool."
)

_model = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0,
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
)
_model_with_tools = _model.bind_tools(ALL_TOOLS)


async def orchestrator_node(state: VocoState) -> dict:
    """Call Claude 3.5 Sonnet with the full conversation history.

    If the model decides to use a tool, the resulting AIMessage will contain
    ``tool_calls``. The conditional router will then send execution to
    ``mcp_gateway_node``. Otherwise it routes to END.
    """
    last_message = state["messages"][-1]
    logger.info("[Orchestrator 🧠] User said: %s", last_message.content)

    response: AIMessage = await _model_with_tools.ainvoke(
        [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    )

    logger.info(
        "[Orchestrator 🧠] Claude response (tool_calls=%d): %.120s",
        len(response.tool_calls) if response.tool_calls else 0,
        response.content,
    )

    return {
        "messages": [response],
        "barge_in_detected": False,
        "pending_mcp_action": response.tool_calls[0] if response.tool_calls else None,
    }


async def mcp_gateway_node(state: VocoState) -> dict:
    """Dispatch the pending MCP action as a JSON-RPC 2.0 payload to Tauri.

    The WebSocket handler in ``main.py`` will intercept ``pending_mcp_action``
    after this node runs, serialize it, and send it down the wire.
    The result will arrive as a ``mcp_result`` control message and be injected
    back into the graph as a ``ToolMessage``.
    """
    action = state.get("pending_mcp_action")
    if not action:
        logger.warning("[MCP Gateway 🏗️] No pending action — nothing to dispatch.")
        return {}

    logger.info("[MCP Gateway 🏗️] Dispatching tool call: %s", action.get("name"))
    return {}
