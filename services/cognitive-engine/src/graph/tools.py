"""LangGraph tool definitions for the Voco MCP bridge.

Each tool here maps to a Tauri command invokable via JSON-RPC 2.0 over
the WebSocket. The Python engine never touches the filesystem directly —
it signals intent and Tauri executes locally (SDD §1).
"""

from __future__ import annotations
import os
import uuid
from langchain_core.tools import tool

from .mcp_registry import UniversalMCPRegistry

# Singleton registry — call ``await mcp_registry.initialize()`` at app startup
mcp_registry = UniversalMCPRegistry()


@tool
def search_codebase(
    pattern: str,
    project_path: str,
    file_glob: str = "",
    max_results: int = 50,
    context_lines: int = 0,
) -> dict:
    """Search for code patterns in the active project using ripgrep.

    Use this when the user asks to find code, locate a function, discover
    where something is defined, or grep for any text across the codebase.

    Args:
        pattern: Regex or literal string to search for (passed to rg).
        project_path: Absolute path to the project directory to search.
        file_glob: Only search files matching this glob (e.g. "*.ts").
        max_results: Cap output to this many matches (default 50).
        context_lines: Lines of context around each match (default 0).

    Returns:
        A dict encoding the JSON-RPC 2.0 request to dispatch to Tauri.
        The caller (mcp_gateway_node) is responsible for sending this over
        the WebSocket and awaiting the result.
    """
    params: dict = {
        "pattern": pattern,
        "project_path": project_path,
    }
    if file_glob:
        params["file_glob"] = file_glob
    if max_results != 50:
        params["max_count"] = max_results
    if context_lines > 0:
        params["context_lines"] = context_lines
    return {
        "jsonrpc": "2.0",
        "method": "search_project",
        "params": params,
    }


_web_search_instance = None


def get_web_search():
    """Lazily instantiate TavilySearch so .env is loaded before reading TAVILY_API_KEY."""
    global _web_search_instance
    if _web_search_instance is None:
        from langchain_tavily import TavilySearch
        _web_search_instance = TavilySearch(
            max_results=3,
            description=(
                "Search the web for current documentation, library updates, error solutions, "
                "or external technical knowledge. Use this when the user asks about something "
                "not found in their local codebase. Returns concise JSON results."
            ),
        )
    return _web_search_instance


@tool
def propose_command(command: str, description: str, project_path: str) -> dict:
    """Propose a terminal command for the user to approve before execution.

    ALL shell commands must go through this tool. The command will be shown
    to the user in the UI for approval before Rust executes it. This ensures
    the human always stays in the loop for operations like git push, npm install,
    database migrations, or any other terminal command.

    Args:
        command: The shell command to execute (e.g. 'git push', 'npm test').
        description: A short human-readable explanation of what this command does.
        project_path: Absolute path to the project directory to run the command in.

    Returns:
        A command proposal dict that will be sent to the frontend for HITL approval.
    """
    command_id = uuid.uuid4().hex[:8]
    return {
        "command_id": command_id,
        "command": command,
        "description": description,
        "project_path": project_path,
    }


@tool
def github_read_issue(repo_name: str, issue_number: int) -> str:
    """Fetch the title, body, and labels of a GitHub issue.

    Use this when the user asks you to read, check, or work on a GitHub issue.

    Args:
        repo_name: Repository in 'owner/repo' format (e.g. 'Radix-Obsidian/Voco-ai').
        issue_number: The integer issue number.

    Returns:
        A formatted string with the issue title, labels, and body.
    """
    from github import Auth, Github

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return "Error: GITHUB_TOKEN environment variable is not set."

    g = Github(auth=Auth.Token(token))
    try:
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        labels = ", ".join(l.name for l in issue.labels) or "none"
        return f"Issue #{issue.number}: {issue.title}\nLabels: {labels}\n\n{issue.body or '(no body)'}"
    except Exception as e:
        return f"Failed to fetch issue: {e}"


@tool
def github_create_pr(
    repo_name: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = "main",
) -> str:
    """Create a Pull Request on GitHub.

    Before calling this, ensure the code has been committed and pushed to
    head_branch using execute_local_command.

    Args:
        repo_name: Repository in 'owner/repo' format.
        title: PR title.
        body: PR description / body (markdown).
        head_branch: The branch with the changes.
        base_branch: The target branch to merge into (default: main).

    Returns:
        Success message with PR number and URL, or error message.
    """
    from github import Auth, Github

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return "Error: GITHUB_TOKEN environment variable is not set."

    g = Github(auth=Auth.Token(token))
    try:
        repo = g.get_repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
        return f"Created PR #{pr.number}: {pr.html_url}"
    except Exception as e:
        return f"Failed to create PR: {e}"


@tool
def propose_file_creation(file_path: str, content: str, description: str) -> dict:
    """Propose creating a new file in the user's project.

    Use this when the user asks you to create, write, or add a new file.
    The proposal will be sent to the user for review before any file is written.

    Args:
        file_path: Relative path within the project where the file should be created.
        content: The full content of the new file.
        description: A short human-readable summary of what this file does.

    Returns:
        A proposal dict that will be sent to the frontend for HITL approval.
    """
    proposal_id = uuid.uuid4().hex[:8]
    return {
        "proposal_id": proposal_id,
        "action": "create_file",
        "file_path": file_path,
        "content": content,
        "description": description,
    }


@tool
def analyze_screen(user_description: str = "") -> dict:
    """Visually analyze the user's screen to diagnose UI bugs or crashes.

    Use this when the user says:
      - "watch this bug" / "look at my screen" / "can you see this?"
      - "analyze this error" / "what's happening on my screen?"
      - Any request to visually examine the current UI state.

    The tool triggers capture of the last ~5 seconds of screen frames, then
    Claude uses its vision capabilities to identify what went wrong.

    Args:
        user_description: What the user wants analyzed (optional context).

    Returns:
        A signal dict that main.py intercepts to trigger the capture flow.
    """
    return {
        "method": "local/get_recent_frames",
        "params": {"user_description": user_description},
    }


@tool
def scan_vulnerabilities(project_path: str) -> dict:
    """Scan the project for exposed secrets and vulnerable dependencies.

    Use this when the user asks:
      - "scan my dependencies" / "check for vulnerabilities"
      - "are there any secrets exposed?" / "audit my security"
      - "check my env files" / "is my project secure?"
      - "run a security scan" / "look for API keys in my project"

    Scans (all local, no network calls):
      - package.json for dependency names and versions (for CVE analysis).
      - .env* files for exposed API keys, tokens, and private key headers.

    Args:
        project_path: Absolute path to the project directory to scan.

    Returns:
        A signal dict that main.py intercepts to trigger the Rust scanner.
    """
    return {
        "method": "local/scan_security",
        "params": {"project_path": project_path},
    }


@tool
def generate_and_preview_mvp(app_description: str, html_code: str) -> dict:
    """Generate a complete MVP app and instantly serve it in the Live Sandbox.

    Use this when the user asks to build, prototype, or preview ANY kind of app,
    website, dashboard, tool, or UI. This is the PRIMARY tool for non-technical
    users — the app appears in the Live Sandbox preview immediately with ZERO setup.

    You MUST generate a complete, self-contained HTML document that includes:
    - Tailwind CSS via CDN: <script src="https://cdn.tailwindcss.com"></script>
    - Optional React via CDN + Babel for interactive UIs
    - Dark premium design: bg-gray-950 background, white text, rounded-2xl cards,
      subtle ring-white/10 borders, voco-emerald (#10b981) accent colour
    - All JavaScript inline — NO npm, NO build steps, NO external imports
    The app is visible on the right side of the Voco UI instantly. Never show raw
    code to the user unless they explicitly ask for it.

    Args:
        app_description: Brief description of what the app does (for logging).
        html_code: Complete <!DOCTYPE html>...</html> document, self-contained.

    Returns:
        A signal dict that main.py intercepts to serve the sandbox preview.
    """
    return {
        "method": "local/sandbox_preview",
        "params": {"app_description": app_description, "html_code": html_code},
    }


@tool
def update_sandbox_preview(html_code: str) -> dict:
    """Update the Live Sandbox with revised HTML code for iterative edits.

    Use this when the user asks to change, modify, tweak, or iterate on anything
    currently visible in the sandbox preview. Changes appear instantly.
    Always provide the COMPLETE updated HTML document, not just the changed parts.

    Args:
        html_code: Complete updated <!DOCTYPE html>...</html> document.

    Returns:
        A signal dict that main.py intercepts to update the sandbox.
    """
    return {
        "method": "local/sandbox_preview",
        "params": {"app_description": "update", "html_code": html_code},
    }


@tool
def read_file(file_path: str, project_path: str, start_line: int = 0, end_line: int = 0) -> dict:
    """Read the contents of a file. Use after grep to inspect matching files.

    Args:
        file_path: Absolute path to the file to read.
        project_path: Absolute path to the project root (for security validation).
        start_line: 1-indexed start line (0 = from beginning).
        end_line: 1-indexed end line (0 = to end of file).

    Returns:
        A dict encoding the JSON-RPC 2.0 request to dispatch to Tauri.
    """
    params: dict = {
        "file_path": file_path,
        "project_root": project_path,
    }
    if start_line > 0:
        params["start_line"] = start_line
    if end_line > 0:
        params["end_line"] = end_line
    return {
        "jsonrpc": "2.0",
        "method": "local/read_file",
        "params": params,
    }


@tool
def list_directory(path: str, project_path: str, max_depth: int = 3) -> dict:
    """List files and directories. Use to explore project structure.

    Args:
        path: Absolute path to the directory to list.
        project_path: Absolute path to the project root (for security validation).
        max_depth: Maximum directory depth to recurse (default 3).

    Returns:
        A dict encoding the JSON-RPC 2.0 request to dispatch to Tauri.
    """
    return {
        "jsonrpc": "2.0",
        "method": "local/list_directory",
        "params": {
            "dir_path": path,
            "project_root": project_path,
            "max_depth": max_depth,
        },
    }


@tool
def glob_find(pattern: str, project_path: str, file_type: str = "file", max_results: int = 50) -> dict:
    """Find files by name pattern. Use to locate specific files in a project.

    Args:
        pattern: Glob pattern to match (e.g. "*.test.ts", "**/*.rs").
        project_path: Absolute path to the project directory to search.
        file_type: Filter by type — "file", "directory", or "any" (default "file").
        max_results: Maximum number of results to return (default 50).

    Returns:
        A dict encoding the JSON-RPC 2.0 request to dispatch to Tauri.
    """
    return {
        "jsonrpc": "2.0",
        "method": "local/glob_find",
        "params": {
            "pattern": pattern,
            "project_path": project_path,
            "file_type": file_type,
            "max_results": max_results,
        },
    }


@tool
def propose_file_edit(file_path: str, diff: str, description: str, cowork_ready: bool = False) -> dict:
    """Propose editing an existing file in the user's project.

    Use this when the user asks you to modify, update, or fix an existing file.
    The proposal will be sent to the user for review before any changes are made.

    Args:
        file_path: Relative path within the project of the file to edit.
        diff: A unified diff or clear description of the changes to make.
        description: A short human-readable summary of what this edit does.
        cowork_ready: If True, the edit is also sent as a cowork_edit message
            so IDE-connected users (Cursor, Windsurf, VS Code) see it inline.

    Returns:
        A proposal dict that will be sent to the frontend for HITL approval.
    """
    proposal_id = uuid.uuid4().hex[:8]
    return {
        "proposal_id": proposal_id,
        "action": "edit_file",
        "file_path": file_path,
        "diff": diff,
        "description": description,
        "cowork_ready": cowork_ready,
    }


def get_all_tools():
    """Return all tools, lazily instantiating Tavily so .env is loaded first.

    Dynamic MCP tools (from ``voco-mcp.json``) are appended after
    ``mcp_registry.initialize()`` is awaited during FastAPI startup.
    """
    return [
        search_codebase,
        read_file,
        list_directory,
        glob_find,
        propose_command,
        get_web_search(),
        github_read_issue,
        github_create_pr,
        propose_file_creation,
        propose_file_edit,
        analyze_screen,
        scan_vulnerabilities,
        generate_and_preview_mvp,
        update_sandbox_preview,
        *mcp_registry.get_tools(),
    ]
