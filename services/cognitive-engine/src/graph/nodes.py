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
        ["component", "button", "css", "style", "layout", "tailwind", "react", "html", "frontend", "ui", "modal", "form", "page", "app", "mvp", "prototype", "dashboard", "landing", "website", "sandbox", "preview", "build me", "create an app"],
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
    "You are Voco, an elite voice-native AI coding assistant, autonomous Intent OS, "
    "and MVP builder for non-technical users. "
    "You operate like Anthropic's 'Claude Code', but through a faceless, voice-first desktop interface.\n\n"
    "Your Capabilities:\n"
    "1. search_codebase — search the user's local project with ripgrep.\n"
    "2. propose_command — propose a terminal command for user approval before execution.\n"
    "3. tavily_search — look up current documentation, library updates, or external knowledge on the web.\n"
    "4. github_read_issue — fetch a GitHub issue's title, body, and labels.\n"
    "5. github_create_pr — open a Pull Request on GitHub.\n"
    "6. propose_file_creation / propose_file_edit — propose file changes for user review before writing.\n"
    "7. analyze_screen — visually inspect the user's screen to diagnose UI bugs.\n"
    "8. scan_vulnerabilities — scan the project for exposed secrets and vulnerable dependencies.\n"
    "9. generate_and_preview_mvp — instantly generate a complete web app and serve it in the Live Sandbox "
    "preview visible on the right side of the screen. PRIMARY tool for any app/UI building request.\n"
    "10. update_sandbox_preview — update the current sandbox with revised HTML for iterative edits.\n\n"
    "Non-Coder MVP Builder Mode (CRITICAL):\n"
    "- When any user asks you to build, create, prototype, or preview ANY app, website, dashboard, "
    "tool, landing page, or UI: call generate_and_preview_mvp IMMEDIATELY.\n"
    "- Generate a complete, self-contained HTML document using Tailwind CSS CDN. "
    "Use a premium dark design: dark bg (bg-gray-950 or #0D0D0D), white text, "
    "rounded-2xl cards, subtle borders (ring-1 ring-white/10), emerald accent (#10b981). "
    "The result must look like a $10,000 agency built it — not a generic template.\n"
    "- When the user requests changes ('make the button green', 'add a sidebar', 'dark mode toggle'): "
    "call update_sandbox_preview with the COMPLETE revised HTML. Changes appear instantly.\n"
    "- NEVER show raw HTML/CSS/JS code to the user unless they explicitly ask to see the code.\n"
    "- After the sandbox goes live, describe what you built in 1-2 sentences and invite feedback.\n\n"
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

# ---------------------------------------------------------------------------
# Phase 2: Boss Router — model registry
# ---------------------------------------------------------------------------

_BOSS_CLASSIFY_PROMPT = (
    "You are a task classifier for Voco, a voice coding assistant.\n"
    "Classify the user's request as ONE of two routes:\n"
    "- haiku  — Simple/conversational: greetings, short explanations, status checks, "
    "questions answerable without tools, no code required.\n"
    "- sonnet — Complex/technical: code writing, debugging, file edits, terminal commands, "
    "GitHub operations, web search, multi-step reasoning, any tool use.\n\n"
    "Reply with ONLY the single word 'haiku' or 'sonnet'. No punctuation. No explanation."
)

_sonnet_model = None
_sonnet_tool_count = 0
_haiku_model = None


def _get_sonnet():
    """Lazily return claude-sonnet-4-5 bound to all tools."""
    global _sonnet_model, _sonnet_tool_count
    all_tools = get_all_tools()
    if _sonnet_model is None or len(all_tools) != _sonnet_tool_count:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        _sonnet_model = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0,
            api_key=api_key,
        ).bind_tools(all_tools)
        _sonnet_tool_count = len(all_tools)
        logger.info("[Model] Sonnet bound with %d tools.", _sonnet_tool_count)
    return _sonnet_model


def _get_haiku():
    """Lazily return claude-haiku-4-5 (no tools — fast conversational responses)."""
    global _haiku_model
    if _haiku_model is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        _haiku_model = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            api_key=api_key,
        )
        logger.info("[Model] Haiku ready (conversational fast-path).")
    return _haiku_model


def _get_boss():
    """Lazily return the Haiku classifier (no tools — classification only)."""
    return _get_haiku()


# ---------------------------------------------------------------------------
# Boss Router node
# ---------------------------------------------------------------------------


async def boss_router_node(state: VocoState) -> dict:
    """Use Claude Haiku to classify the task and pick the right execution model.

    Routes:
      haiku  → simple/conversational, no tools needed  → fast + cheap
      sonnet → technical/code/tool-use                 → full capability
    """
    messages = state.get("messages", [])
    if not messages:
        return {"routed_model": "sonnet"}

    last_text = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])

    try:
        boss = _get_boss()
        response: AIMessage = await boss.ainvoke(
            [SystemMessage(content=_BOSS_CLASSIFY_PROMPT),
             *[m for m in messages[-6:]]]  # only last 6 messages for speed
        )
        route = response.content.strip().lower().split()[0] if response.content else "sonnet"
        route = route if route in ("haiku", "sonnet") else "sonnet"
    except Exception as exc:
        logger.warning("[Boss Router] Classification failed, defaulting to sonnet: %s", exc)
        route = "sonnet"

    logger.info("[Boss Router 🧠] '%s...' → %s", last_text[:60], route.upper())
    return {"routed_model": route}


async def orchestrator_node(state: VocoState) -> dict:
    """Invoke the routed model (Haiku or Sonnet) with the full conversation history.

    Boss Router pre-selects:
      haiku  → lightweight conversational turns (fast, cheap, no tools)
      sonnet → technical tasks with full tool access
    """
    last_message = state["messages"][-1]
    route = state.get("routed_model", "sonnet")
    logger.info("[Orchestrator 🧠] Model=%s | User: %s", route.upper(), last_message.content)

    focused = state.get("focused_context", "")
    system_prompt = f"{focused}\n\n{_SYSTEM_PROMPT}" if focused else _SYSTEM_PROMPT

    model = _get_sonnet() if route == "sonnet" else _get_haiku()

    response: AIMessage = await model.ainvoke(
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
