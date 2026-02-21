"""LangGraph tool definitions for the Voco MCP bridge.

Each tool here maps to a Tauri command invokable via JSON-RPC 2.0 over
the WebSocket. The Python engine never touches the filesystem directly —
it signals intent and Tauri executes locally (SDD §1).
"""

from __future__ import annotations

from langchain_core.tools import tool


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


ALL_TOOLS = [search_codebase]
