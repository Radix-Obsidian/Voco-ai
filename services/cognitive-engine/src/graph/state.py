"""VocoState — the LangGraph state container for the cognitive engine."""

from typing import Annotated, TypedDict, Optional
from typing_extensions import NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class VocoState(TypedDict):
    """Root state passed through every LangGraph node.

    Fields
    ------
    messages : conversation history managed by LangGraph's add_messages reducer.
    project_map : detected stack, file tree, and other project metadata.
    barge_in_detected : set True by VAD when the user interrupts during playback.
    pending_mcp_action : JSON-RPC payload awaiting execution via Tauri MCP bridge.
    terminal_output : What the user sees in the Ghost Terminal.
    search_results : Data for Claude to analyze.
    active_project_path : Current project path for local searches.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    project_map: NotRequired[dict]
    barge_in_detected: NotRequired[bool]
    pending_mcp_action: NotRequired[Optional[dict]]
    terminal_output: NotRequired[str]
    search_results: NotRequired[list[str]]
    active_project_path: NotRequired[str]
    pending_proposals: NotRequired[list[dict]]
    proposal_decisions: NotRequired[list[dict]]
    pending_commands: NotRequired[list[dict]]
    command_decisions: NotRequired[list[dict]]
    focused_context: NotRequired[str]
    routed_model: NotRequired[str]  # "haiku" | "sonnet" — set by boss_router_node
