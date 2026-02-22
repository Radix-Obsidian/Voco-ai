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
def search_codebase(pattern: str, project_path: str) -> dict:
    """Search for code patterns in the active project using ripgrep.

    Use this when the user asks to find code, locate a function, discover
    where something is defined, or grep for any text across the codebase.

    Args:
        pattern: Regex or literal string to search for (passed to rg).
        project_path: Absolute path to the project directory to search.

    Returns:
        A dict encoding the JSON-RPC 2.0 request to dispatch to Tauri.
        The caller (mcp_gateway_node) is responsible for sending this over
        the WebSocket and awaiting the result.
    """
    return {
        "jsonrpc": "2.0",
        "method": "search_project",
        "params": {
            "pattern": pattern,
            "project_path": project_path,
        },
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
    from github import Github

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return "Error: GITHUB_TOKEN environment variable is not set."

    g = Github(token)
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
    from github import Github

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return "Error: GITHUB_TOKEN environment variable is not set."

    g = Github(token)
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
def propose_file_edit(file_path: str, diff: str, description: str) -> dict:
    """Propose editing an existing file in the user's project.

    Use this when the user asks you to modify, update, or fix an existing file.
    The proposal will be sent to the user for review before any changes are made.

    Args:
        file_path: Relative path within the project of the file to edit.
        diff: A unified diff or clear description of the changes to make.
        description: A short human-readable summary of what this edit does.

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
    }


def get_all_tools():
    """Return all tools, lazily instantiating Tavily so .env is loaded first.

    Dynamic MCP tools (from ``voco-mcp.json``) are appended after
    ``mcp_registry.initialize()`` is awaited during FastAPI startup.
    """
    return [
        search_codebase,
        propose_command,
        get_web_search(),
        github_read_issue,
        github_create_pr,
        propose_file_creation,
        propose_file_edit,
        *mcp_registry.get_tools(),
    ]
