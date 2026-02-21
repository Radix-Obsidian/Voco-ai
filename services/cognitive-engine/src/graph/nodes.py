"""LangGraph node functions for the Voco cognitive engine."""

from __future__ import annotations

import logging
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from .state import VocoState
from .tools import get_all_tools

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Voco, a voice-native coding assistant running as a local desktop agent. "
    "You have access to tools to search the user's codebase via the secure local MCP gateway. "
    "You also have a web_search tool to look up current documentation, library updates, or external knowledge. "
    "Be concise — your responses will be spoken aloud via TTS. "
    "When you need to find code, always use the search_codebase tool. "
    "When the user asks about something outside their codebase, use the web_search tool. "
    "When the user asks you to create or write a file, use propose_file_creation. "
    "When the user asks you to edit or modify a file, use propose_file_edit. "
    "Never write files directly — always use the proposal tools so the user can review changes first."
)

_model_with_tools = None


def _get_model():
    global _model_with_tools
    if _model_with_tools is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Check .env in services/cognitive-engine/"
            )
        _model_with_tools = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0,
            api_key=api_key,
        ).bind_tools(get_all_tools())
    return _model_with_tools


async def orchestrator_node(state: VocoState) -> dict:
    """Call Claude 3.5 Sonnet with the full conversation history.

    If the model decides to use a tool, the resulting AIMessage will contain
    ``tool_calls``. The conditional router will then send execution to
    ``mcp_gateway_node``. Otherwise it routes to END.
    """
    last_message = state["messages"][-1]
    logger.info("[Orchestrator 🧠] User said: %s", last_message.content)

    response: AIMessage = await _get_model().ainvoke(
        [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    )

    logger.info(
        "[Orchestrator 🧠] Claude response (tool_calls=%d): %.120s",
        len(response.tool_calls) if response.tool_calls else 0,
        response.content,
    )

    updates: dict = {
        "messages": [response],
        "barge_in_detected": False,
    }

    if response.tool_calls:
        # Separate proposal tool calls from MCP tool calls
        proposals = []
        mcp_action = None
        for tc in response.tool_calls:
            if tc["name"].startswith("propose_"):
                proposals.append(tc)
            elif mcp_action is None:
                mcp_action = tc

        if proposals:
            updates["pending_proposals"] = [tc["args"] for tc in proposals]
        updates["pending_mcp_action"] = mcp_action

    return updates


async def proposal_review_node(state: VocoState) -> dict:
    """Process HITL decisions on pending file proposals.

    This node is reached after an ``interrupt_before`` pause. The WebSocket
    handler in ``main.py`` collects user decisions and resumes the graph
    with ``proposal_decisions`` populated.
    """
    proposals = state.get("pending_proposals", [])
    decisions = state.get("proposal_decisions", [])

    logger.info(
        "[Proposal Review 📋] %d proposals, %d decisions",
        len(proposals),
        len(decisions),
    )

    # Build a summary ToolMessage so Claude knows what happened
    decision_map = {d["proposal_id"]: d["status"] for d in decisions}
    lines = []
    for p in proposals:
        pid = p.get("proposal_id", "?")
        status = decision_map.get(pid, "unknown")
        lines.append(f"- {p.get('file_path', '?')}: {status}")

    summary = "Proposal review results:\n" + "\n".join(lines) if lines else "No proposals to review."

    # Find the tool_call_id from the last AI message's tool_calls
    tool_call_id = "proposal-review"
    last_ai = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai = msg
            break
    if last_ai:
        for tc in last_ai.tool_calls:
            if tc["name"].startswith("propose_"):
                tool_call_id = tc["id"]
                break

    return {
        "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
        "pending_proposals": [],
        "proposal_decisions": [],
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
