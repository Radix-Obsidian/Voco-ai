"""LangGraph node functions for the Voco cognitive engine."""

from __future__ import annotations

import hashlib
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .state import VocoState
from .tools import get_all_tools
from .token_guard import trim_messages_to_budget
from .session_memory import load_session_history, save_session_entry
from .turn_archive import archive_turn

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
    "You are Voco, an elite AI coding assistant, autonomous Intent OS, "
    "and MVP builder for non-technical users. "
    "You operate like Anthropic's 'Claude Code', but through a desktop chat interface "
    "with screen vision, MCP tool execution, and live sandbox preview.\n\n"
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
    "10. update_sandbox_preview — update the current sandbox with revised HTML for iterative edits.\n"
    "11. read_file — read the contents of a file by path, optionally with a line range. Use after grep to inspect matches.\n"
    "12. list_directory — list files and directories in a path with configurable depth. Use to explore project structure.\n"
    "13. glob_find — find files by name pattern (e.g. '*.test.ts'). Use to locate specific files in a project.\n"
    "14. orgo_create_sandbox — create a real cloud Linux VM for full-stack projects (npm, servers, databases).\n"
    "15. orgo_run_command — run shell commands in the cloud sandbox (no user approval needed, it's isolated).\n"
    "16. orgo_run_python — execute Python code in the cloud sandbox.\n"
    "17. orgo_screenshot — capture the cloud sandbox desktop to verify state.\n"
    "18. orgo_upload_file — upload files to the cloud sandbox filesystem.\n"
    "19. orgo_stop_sandbox — destroy the active cloud sandbox.\n\n"
    "Cloud Sandbox Strategy (CRITICAL):\n"
    "- For simple HTML/CSS/JS prototypes (landing pages, dashboards, calculators): "
    "use generate_and_preview_mvp. Instant, zero setup, appears in the Live Sandbox.\n"
    "- For full-stack apps (React+Express, Python+FastAPI, databases, multi-file projects): "
    "use orgo_create_sandbox. This boots a real Linux VM with terminal access.\n"
    "- The cloud sandbox is ISOLATED — commands run there, NOT on the user's machine. "
    "No user approval needed for sandbox commands.\n"
    "- After creating a sandbox: upload files → run setup commands → take a screenshot to verify.\n"
    "- The user sees a live interactive desktop stream of the sandbox in the right panel.\n\n"
    "Non-Coder MVP Builder Mode:\n"
    "- When any user asks you to build, create, prototype, or preview ANY simple app, website, "
    "dashboard, tool, landing page, or UI: call generate_and_preview_mvp.\n"
    "- Generate a complete, self-contained HTML document using Tailwind CSS CDN. "
    "Use a premium dark design: dark bg (bg-gray-950 or #0D0D0D), white text, "
    "rounded-2xl cards, subtle borders (ring-1 ring-white/10), emerald accent (#10b981). "
    "The result must look like a $10,000 agency built it — not a generic template.\n"
    "- When the user requests changes ('make the button green', 'add a sidebar', 'dark mode toggle'): "
    "call update_sandbox_preview with the COMPLETE revised HTML. Changes appear instantly.\n"
    "- For complex apps requiring build steps or servers, use the cloud sandbox tools instead.\n"
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
    "- Use markdown formatting in your responses — the user reads them in a chat interface.\n"
    "- Be concise but thorough. The user can click 'Read aloud' on any response to hear it.\n\n"
    "Co-Work Mode (IDE Integration):\n"
    "- You can propose edits that appear directly in the user's IDE via the Tauri MCP gateway.\n"
    "- When using propose_file_edit, set cowork_ready=True to signal that the edit should be "
    "displayed inline in the user's IDE (Cursor, Windsurf, VS Code) rather than just the Voco UI.\n"
    "- IDE-connected users see a native diff view; non-IDE users see the standard proposal card.\n"
    "- This enables seamless pair-programming: you describe the change, the user sees it in their editor."
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
_haiku_tools_model = None
_haiku_tools_count = 0

# Per-session LiteLLM virtual key (set by main.py on auth_sync)
_session_token: str = ""


def set_session_token(token: str) -> None:
    """Update the LiteLLM session token and invalidate cached models.

    Called by ``main.py`` when an ``auth_sync`` message provides a new
    ``voco_session_token``.  Invalidating the cached models forces them
    to be re-created with the new api_key on the next invocation.
    """
    global _session_token, _sonnet_model, _haiku_model, _haiku_tools_model
    _session_token = token
    _sonnet_model = None
    _haiku_model = None
    _haiku_tools_model = None
    logger.info("[Model] Session token updated — cached models invalidated.")


def _use_direct_anthropic() -> bool:
    """Return True if we should use ChatAnthropic directly (no LiteLLM proxy)."""
    # Direct mode if: no LiteLLM URL set, or ANTHROPIC_API_KEY is available and LiteLLM is down
    gateway = os.environ.get("LITELLM_GATEWAY_URL", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key and not gateway:
        return True
    if anthropic_key and gateway:
        # Quick health check — if LiteLLM is unreachable, fall back to direct
        try:
            import urllib.request
            urllib.request.urlopen(gateway.replace("/v1", "/health"), timeout=1)
            return False  # LiteLLM is healthy, use it
        except Exception:
            logger.info("[Model] LiteLLM at %s not reachable — using direct Anthropic API.", gateway)
            return True
    return False


def _get_gateway_url() -> str:
    """Return the LiteLLM gateway base URL from env."""
    url = os.environ.get("LITELLM_GATEWAY_URL", "")
    if not url:
        raise RuntimeError(
            "LITELLM_GATEWAY_URL is not set and ANTHROPIC_API_KEY is not available. "
            "Configure one of them to connect to Claude."
        )
    return url


def _get_api_key() -> str:
    """Return the session token or fall back to LITELLM_SESSION_TOKEN env var."""
    key = _session_token or os.environ.get("LITELLM_SESSION_TOKEN", "")
    if not key:
        raise RuntimeError(
            "No LiteLLM session token available. "
            "Please log in so Voco can authenticate with the AI gateway."
        )
    return key


def _get_sonnet():
    """Lazily return claude-sonnet-4-5 bound to all tools.

    Uses direct Anthropic API if available, otherwise routes through LiteLLM proxy.
    """
    global _sonnet_model, _sonnet_tool_count
    all_tools = get_all_tools()
    if _sonnet_model is None or len(all_tools) != _sonnet_tool_count:
        if _use_direct_anthropic():
            from langchain_anthropic import ChatAnthropic
            _sonnet_model = ChatAnthropic(
                model="claude-sonnet-4-5-20250929",
                temperature=0,
                api_key=os.environ["ANTHROPIC_API_KEY"],
            ).bind_tools(all_tools)
            logger.info("[Model] Sonnet bound with %d tools (direct Anthropic API).", len(all_tools))
        else:
            _sonnet_model = ChatOpenAI(
                base_url=_get_gateway_url(),
                api_key=_get_api_key(),
                model="claude-sonnet-4-5-20250929",
                temperature=0,
            ).bind_tools(all_tools)
            logger.info("[Model] Sonnet bound with %d tools (via LiteLLM proxy).", len(all_tools))
        _sonnet_tool_count = len(all_tools)
    return _sonnet_model


def _get_haiku():
    """Lazily return claude-haiku-4-5 (no tools — fast conversational responses).

    Uses direct Anthropic API if available, otherwise routes through LiteLLM proxy.
    """
    global _haiku_model
    if _haiku_model is None:
        if _use_direct_anthropic():
            from langchain_anthropic import ChatAnthropic
            _haiku_model = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0,
                api_key=os.environ["ANTHROPIC_API_KEY"],
            )
            logger.info("[Model] Haiku ready (direct Anthropic API).")
        else:
            _haiku_model = ChatOpenAI(
                base_url=_get_gateway_url(),
                api_key=_get_api_key(),
                model="claude-haiku-4-5-20251001",
                temperature=0,
            )
            logger.info("[Model] Haiku ready (via LiteLLM proxy).")
    return _haiku_model


def _get_haiku_with_tools():
    """Lazily return claude-haiku-4-5 bound to all tools (cheap tool-use for free tier).

    Uses direct Anthropic API if available, otherwise routes through LiteLLM proxy.
    """
    global _haiku_tools_model, _haiku_tools_count
    all_tools = get_all_tools()
    if _haiku_tools_model is None or len(all_tools) != _haiku_tools_count:
        if _use_direct_anthropic():
            from langchain_anthropic import ChatAnthropic
            _haiku_tools_model = ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                temperature=0,
                api_key=os.environ["ANTHROPIC_API_KEY"],
            ).bind_tools(all_tools)
            logger.info("[Model] Haiku+Tools bound with %d tools (direct Anthropic API).", len(all_tools))
        else:
            _haiku_tools_model = ChatOpenAI(
                base_url=_get_gateway_url(),
                api_key=_get_api_key(),
                model="claude-haiku-4-5-20251001",
                temperature=0,
            ).bind_tools(all_tools)
            logger.info("[Model] Haiku+Tools bound with %d tools (via LiteLLM proxy).", len(all_tools))
        _haiku_tools_count = len(all_tools)
    return _haiku_tools_model


def _get_boss():
    """Lazily return the Haiku classifier (no tools — classification only)."""
    return _get_haiku()


# ---------------------------------------------------------------------------
# Boss Router node
# ---------------------------------------------------------------------------


_FREE_TIER_TOOL_KEYWORDS = frozenset([
    "search", "find", "edit", "write", "create", "delete", "run",
    "execute", "debug", "fix", "github", "commit", "push", "pull",
    "deploy", "install", "terminal", "command", "file", "code",
    "read", "open", "build", "test", "lint",
])


async def boss_router_node(state: VocoState) -> dict:
    """Tier-aware model router.

    Free tier: keyword-only classification (no LLM call) → haiku or haiku_tools.
    Paid/Founder: Haiku LLM classification → haiku or sonnet.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"routed_model": "haiku_tools"}

    user_tier = state.get("user_tier", "free")
    last_text = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])

    if user_tier == "free":
        # Free tier: skip LLM classification entirely to save cost
        text_lower = last_text.lower()
        has_tool_signal = any(kw in text_lower for kw in _FREE_TIER_TOOL_KEYWORDS)
        route = "haiku_tools" if has_tool_signal else "haiku"
        logger.info("[Boss Router] user_tier=free → %s | '%s...'", route.upper(), last_text[:60])
        return {"routed_model": route}

    # Paid / Founder: use Haiku LLM classification
    try:
        boss = _get_boss()
        recent = [m for m in messages[-6:] if not isinstance(m, SystemMessage)]
        response: AIMessage = await boss.ainvoke(
            [SystemMessage(content=_BOSS_CLASSIFY_PROMPT), *recent]
        )
        route = response.content.strip().lower().split()[0] if response.content else "haiku_tools"
        route = route if route in ("haiku", "sonnet") else "haiku_tools"
    except Exception as exc:
        logger.warning("[Boss Router] Classification failed, defaulting to haiku_tools: %s", exc)
        route = "haiku_tools"

    logger.info("[Boss Router] user_tier=%s → %s | '%s...'", user_tier, route.upper(), last_text[:60])
    return {"routed_model": route}


async def orchestrator_node(state: VocoState) -> dict:
    """Invoke the routed model (Haiku or Sonnet) with the full conversation history.

    Boss Router pre-selects:
      haiku  → lightweight conversational turns (fast, cheap, no tools)
      sonnet → technical tasks with full tool access
    """
    last_message = state["messages"][-1]
    route = state.get("routed_model", "haiku_tools")
    logger.info("[Orchestrator 🧠] Model=%s | User: %s", route.upper(), last_message.content)

    focused = state.get("focused_context", "")
    project_path = state.get("active_project_path", "")
    session_history = load_session_history(project_path)
    parts = [p for p in (focused, session_history, _SYSTEM_PROMPT) if p]
    system_prompt = "\n\n".join(parts)

    # Prompt hash + model ID for observability (Issue #7)
    prompt_hash = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]
    model_id = "claude-sonnet-4-5-20250929" if route == "sonnet" else "claude-haiku-4-5-20251001"  # haiku and haiku_tools share model ID
    prev_meta = state.get("turn_metadata") or {}
    turn_number = prev_meta.get("turn_number", 0) + 1
    logger.info("[Orchestrator] prompt_hash=%s model=%s turn=%d", prompt_hash, model_id, turn_number)

    if route == "sonnet":
        model = _get_sonnet()
    elif route == "haiku_tools":
        model = _get_haiku_with_tools()
    else:
        model = _get_haiku()

    # Token budget guard — trim oldest messages if context would overflow (Issue #3)
    trimmed_messages = trim_messages_to_budget(
        system_prompt=system_prompt,
        messages=state["messages"],
        model=model_id,
    )

    # Anthropic API requires system messages to be consecutive at the start.
    # Background job completions inject SystemMessages mid-conversation via
    # aupdate_state — convert those to HumanMessages so the API accepts them.
    sanitized = []
    for m in trimmed_messages:
        if isinstance(m, SystemMessage):
            sanitized.append(HumanMessage(content=f"[System notification] {m.content}"))
        else:
            sanitized.append(m)

    try:
        response: AIMessage = await model.ainvoke(
            [SystemMessage(content=system_prompt), *sanitized]
        )
    except Exception as llm_exc:
        exc_str = str(llm_exc).lower()
        # Detect rate limit / overloaded errors from Anthropic or LiteLLM
        if any(k in exc_str for k in ("529", "overloaded", "rate limit", "429", "too many requests")):
            raise RuntimeError(
                "E_MODEL_OVERLOADED: Claude is temporarily overloaded. Please wait a moment and try again."
            ) from llm_exc
        if any(k in exc_str for k in ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication")):
            raise RuntimeError(
                "E_AUTH_EXPIRED: API authentication failed. Check your API key configuration."
            ) from llm_exc
        if any(k in exc_str for k in ("timeout", "timed out", "connect", "network")):
            raise RuntimeError(
                f"E_GRAPH_FAILED: Network error reaching the AI model: {llm_exc}"
            ) from llm_exc
        raise RuntimeError(
            f"E_GRAPH_FAILED: AI model error: {llm_exc}"
        ) from llm_exc

    logger.info(
        "[Orchestrator 🧠] Claude response (tool_calls=%d): %.120s",
        len(response.tool_calls) if response.tool_calls else 0,
        response.content,
    )

    # Archive full turn for replay/debugging (Issue #7)
    config = state.get("configurable", {})
    session_id = config.get("thread_id", "unknown")
    try:
        archive_turn(
            session_id=session_id,
            turn_number=turn_number,
            system_prompt=system_prompt,
            model_name=model_id,
            messages=state["messages"],
            tool_calls=response.tool_calls if response.tool_calls else None,
        )
    except Exception as arc_exc:
        logger.warning("[Orchestrator] Turn archive failed: %s", arc_exc)

    # --- Session memory: persist this turn ---
    try:
        transcript = last_message.content if hasattr(last_message, "content") else str(last_message)
        action_names = [tc["name"] for tc in (response.tool_calls or [])]
        file_refs: list[str] = []
        for tc in (response.tool_calls or []):
            for key in ("file_path", "project_path", "path"):
                val = tc.get("args", {}).get(key)
                if val:
                    file_refs.append(val)
        summary_text = (response.content or "")[:200]
        save_session_entry(
            project_path=project_path,
            transcript=transcript,
            actions=action_names,
            files=file_refs,
            summary=summary_text,
            session_id=session_id,
            model=model_id,
        )
    except Exception as mem_exc:
        logger.warning("[Orchestrator] Session memory save failed: %s", mem_exc)

    updates: dict = {
        "messages": [response],
        "turn_metadata": {
            "prompt_hash": prompt_hash,
            "model_id": model_id,
            "turn_number": turn_number,
        },
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
