"""LangGraph node functions for the Voco cognitive engine."""

from __future__ import annotations

import logging
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from .state import VocoState
from .tools import get_all_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain-aware context routing
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, tuple[list[str], str]] = {
    "ui": (
        ["component", "button", "css", "style", "layout", "tailwind", "react", "html", "frontend", "ui", "modal", "form", "page"],
        "Focus: UI/Frontend. Prioritize component structure, styling, and user-facing code.",
    ),
    "database": (
        ["database", "sql", "query", "migration", "schema", "table", "postgres", "sqlite", "prisma", "drizzle", "supabase", "db"],
        "Focus: Database. Prioritize schema design, queries, migrations, and data integrity.",
    ),
    "api": (
        ["api", "endpoint", "route", "rest", "graphql", "fetch", "request", "response", "middleware", "controller", "handler", "server"],
        "Focus: API/Backend. Prioritize endpoint design, request handling, and server logic.",
    ),
    "devops": (
        ["docker", "deploy", "ci", "cd", "pipeline", "kubernetes", "k8s", "nginx", "env", "build", "dockerfile", "yaml", "terraform", "aws", "cloud"],
        "Focus: DevOps/Infrastructure. Prioritize deployment, configuration, and infrastructure.",
    ),
    "git": (
        ["git", "commit", "branch", "merge", "rebase", "pull request", "pr", "push", "diff", "stash", "checkout"],
        "Focus: Git/Version Control. Prioritize repository operations and collaboration workflow.",
    ),
}


def _detect_domain(text: str) -> tuple[str, str]:
    """Score keyword hits and return the best-matching (domain, context) pair."""
    text_lower = text.lower()
    best_domain = "general"
    best_score = 0
    best_context = ""

    for domain, (keywords, context) in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_domain = domain
            best_context = context

    return best_domain, best_context


async def context_router_node(state: VocoState) -> dict:
    """Detect the domain of the user's last message and inject focused context."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_text = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    domain, context = _detect_domain(last_text)
    logger.info("[Context Router] Detected domain: %s", domain)

    return {"focused_context": context}


_SYSTEM_PROMPT = (
    "You are Voco, an elite voice-native AI coding assistant and autonomous Intent OS. "
    "You operate like Anthropic's 'Claude Code', but through a faceless, voice-first desktop interface.\n\n"
    "Your Capabilities:\n"
    "1. search_codebase — search the user's local project with ripgrep.\n"
    "2. propose_command — propose a terminal command (git, npm, cargo, pytest, etc.) for user approval before execution.\n"
    "3. tavily_search — look up current documentation, library updates, or external knowledge on the web.\n"
    "4. github_read_issue — fetch a GitHub issue's title, body, and labels.\n"
    "5. github_create_pr — open a Pull Request on GitHub.\n"
    "6. propose_file_creation / propose_file_edit — propose file changes for user review before writing.\n\n"
    "Async Execution Model (CRITICAL):\n"
    "- You are an autonomous Intent OS. All tools execute asynchronously in the background.\n"
    "- When you call a tool, you will receive an IMMEDIATE confirmation: "
    "'Action queued in background with Job ID: <id>. You may continue conversing with the user.'\n"
    "- Do NOT wait silently after receiving this confirmation. "
    "Immediately tell the user what task is running in the background and invite them to keep talking.\n"
    "- You will be notified via a system message '[BACKGROUND JOB COMPLETE] Job <id> ...' when a task finishes.\n"
    "- When you see a background job completion message, summarize the result concisely for the user.\n\n"
    "Workflow Rules:\n"
    "- ALL terminal commands MUST go through propose_command. Never run commands directly.\n"
    "- The user will see the command and approve or reject it before Rust executes it.\n"
    "- If asked to fix a GitHub issue: read it with github_read_issue, search the codebase, "
    "propose fixes, use propose_command for git branch/commit/push, then github_create_pr.\n"
    "- Never write files directly — always use the proposal tools so the user can review first.\n"
    "- Be concise — your responses are spoken aloud via TTS."
)

_model_with_tools = None
_bound_tool_count = 0


def _get_model():
    """Lazily create the Claude model, re-binding tools when the registry grows."""
    global _model_with_tools, _bound_tool_count

    all_tools = get_all_tools()
    if _model_with_tools is None or len(all_tools) != _bound_tool_count:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Check .env in services/cognitive-engine/"
            )
        _model_with_tools = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0,
            api_key=api_key,
        ).bind_tools(all_tools)
        _bound_tool_count = len(all_tools)
        logger.info("[Model] Bound %d tools (including %d external MCP tools).",
                     _bound_tool_count, _bound_tool_count - 7)
    return _model_with_tools


async def orchestrator_node(state: VocoState) -> dict:
    """Call Claude 3.5 Sonnet with the full conversation history.

    If the model decides to use a tool, the resulting AIMessage will contain
    ``tool_calls``. The conditional router will then send execution to
    ``mcp_gateway_node``. Otherwise it routes to END.
    """
    last_message = state["messages"][-1]
    logger.info("[Orchestrator 🧠] User said: %s", last_message.content)

    focused = state.get("focused_context", "")
    system_prompt = f"{focused}\n\n{_SYSTEM_PROMPT}" if focused else _SYSTEM_PROMPT

    response: AIMessage = await _get_model().ainvoke(
        [SystemMessage(content=system_prompt), *state["messages"]]
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
        # Separate tool calls into proposals, commands, and MCP actions
        file_proposals = []
        command_proposals = []
        mcp_action = None
        for tc in response.tool_calls:
            if tc["name"] == "propose_command":
                command_proposals.append(tc)
            elif tc["name"].startswith("propose_"):
                file_proposals.append(tc)
            elif mcp_action is None:
                mcp_action = tc

        if file_proposals:
            updates["pending_proposals"] = [tc["args"] for tc in file_proposals]
        if command_proposals:
            updates["pending_commands"] = [tc["args"] for tc in command_proposals]
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


async def command_review_node(state: VocoState) -> dict:
    """Process HITL decisions on pending command proposals.

    This node is reached after an ``interrupt_before`` pause. The WebSocket
    handler in ``main.py`` collects user decisions and resumes the graph
    with ``command_decisions`` populated. Approved commands are executed
    by Tauri before resume.
    """
    commands = state.get("pending_commands", [])
    decisions = state.get("command_decisions", [])

    logger.info(
        "[Command Review 🛡️] %d commands, %d decisions",
        len(commands),
        len(decisions),
    )

    decision_map = {d["command_id"]: d for d in decisions}
    lines = []
    for c in commands:
        cid = c.get("command_id", "?")
        d = decision_map.get(cid, {})
        status = d.get("status", "unknown")
        output = d.get("output", "")
        line = f"- `{c.get('command', '?')}`: {status}"
        if output:
            line += f"\n  Output: {output}"
        lines.append(line)

    summary = "Command execution results:\n" + "\n".join(lines) if lines else "No commands to review."

    # Find the tool_call_id from the last AI message
    tool_call_id = "command-review"
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "propose_command":
                    tool_call_id = tc["id"]
                    break
            break

    return {
        "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
        "pending_commands": [],
        "command_decisions": [],
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
