"""LangGraph tool definitions for the Voco MCP bridge.

Each tool here maps to a Tauri command invokable via JSON-RPC 2.0 over
the WebSocket. The Python engine never touches the filesystem directly —
it signals intent and Tauri executes locally (SDD §1).
"""

from __future__ import annotations
import os
import uuid
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
    """Return all tools, lazily instantiating Tavily so .env is loaded first."""
    return [search_codebase, get_web_search(), propose_file_creation, propose_file_edit]
