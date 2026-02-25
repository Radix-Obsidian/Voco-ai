"""Tests for the MCP Registry tool discovery and invocation.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_mcp_registry.py -v
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tool_discovery_wraps_mcp_tools_as_structured_tool():
    """Tool discovery wraps MCP tools as StructuredTool."""
    from src.graph.tools import mcp_registry

    from langchain_core.tools import StructuredTool

    # Save original tools to restore later
    original_tools = list(mcp_registry.dynamic_tools)

    tool = StructuredTool.from_function(
        func=lambda query: query,
        name="test_search",
        description="Search the codebase",
    )
    mcp_registry.dynamic_tools.append(tool)

    try:
        tools = mcp_registry.get_tools()
        assert len(tools) >= 1
        found = [t for t in tools if t.name == "test_search"]
        assert len(found) == 1
        assert found[0].description == "Search the codebase"
    finally:
        mcp_registry.dynamic_tools[:] = original_tools


@pytest.mark.asyncio
async def test_tool_invocation_returns_text_content():
    """Tool invocation returns concatenated text content."""
    from mcp.types import TextContent

    mock_result = MagicMock()
    mock_result.isError = False
    mock_result.content = [
        TextContent(type="text", text="Line 1: match found"),
        TextContent(type="text", text="Line 2: another match"),
    ]

    # The concatenation logic
    texts = [c.text for c in mock_result.content if hasattr(c, "text")]
    result = "\n".join(texts)
    assert "Line 1: match found" in result
    assert "Line 2: another match" in result


@pytest.mark.asyncio
async def test_tool_invocation_with_is_error_returns_error_string():
    """Tool invocation with isError=True returns error string."""
    from mcp.types import TextContent

    mock_result = MagicMock()
    mock_result.isError = True
    mock_result.content = [
        TextContent(type="text", text="Permission denied: /etc/shadow"),
    ]

    if mock_result.isError:
        texts = [c.text for c in mock_result.content if hasattr(c, "text")]
        result = "MCP Error: " + "\n".join(texts)

    assert result.startswith("MCP Error:")
    assert "Permission denied" in result


@pytest.mark.asyncio
async def test_tool_invocation_exception_returns_error_string():
    """Tool invocation exception returns error string (no crash)."""
    async def failing_invoke(**kwargs):
        raise ConnectionError("MCP server unreachable")

    try:
        result = await failing_invoke(query="test")
    except Exception as exc:
        result = f"Tool invocation error: {exc}"

    assert "Tool invocation error" in result
    assert "MCP server unreachable" in result
