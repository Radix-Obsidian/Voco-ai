"""VocoState — the LangGraph state container for the cognitive engine."""

from typing import Annotated, TypedDict

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
    """

    messages: Annotated[list[BaseMessage], add_messages]
    project_map: dict
    barge_in_detected: bool
    pending_mcp_action: dict | None
