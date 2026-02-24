"""IDE MCP Server — SSE-based MCP server for Cursor / Windsurf integration.

Exposes Voco's tools to any MCP-compatible IDE over HTTP + SSE.

Configure in your IDE (e.g. ~/.cursor/mcp.json or ~/.windsurf/mcp.json):
  { "mcpServers": { "voco-local": { "url": "http://localhost:8001/mcp" } } }

Routes registered on the main FastAPI app by `attach_ide_mcp_routes()`:
  GET  /mcp          — IDE connects here; server streams SSE events
  POST /mcp/messages — IDE posts JSON-RPC tool calls here

Available tools:
  voco_search_web        — Tavily web search
  voco_read_github_issue — Read a GitHub issue
  voco_ask               — Full LangGraph reasoning (requires LiteLLM gateway)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singletons — one MCP server + one SSE transport for the process lifetime.
# ---------------------------------------------------------------------------

_mcp = Server("voco-local")

# The path passed here is sent to the IDE as the "messages" endpoint URL.
_sse = SseServerTransport("/mcp/messages")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@_mcp.list_tools()
async def _list_tools() -> list[Tool]:
    """Advertise Voco's tools to the connected IDE."""
    return [
        Tool(
            name="voco_search_web",
            description=(
                "Search the web for current documentation, library updates, "
                "error solutions, or technical knowledge. Powered by Tavily. "
                "Use when local codebase search isn't enough."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="voco_read_github_issue",
            description=(
                "Fetch the title, body, and labels of a GitHub issue. "
                "Requires GITHUB_TOKEN to be configured in Voco Settings."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Repository in 'owner/repo' format.",
                    },
                    "issue_number": {
                        "type": "integer",
                        "description": "The integer issue number.",
                    },
                },
                "required": ["repo_name", "issue_number"],
            },
        ),
        Tool(
            name="voco_ask",
            description=(
                "Send a question or task to Voco's full LangGraph reasoning engine. "
                "Voco can search the web, read GitHub issues, and reason about code. "
                "Use for complex questions that benefit from multi-step AI reasoning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The question or task for Voco.",
                    }
                },
                "required": ["prompt"],
            },
        ),
    ]


@_mcp.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to the appropriate handler."""
    logger.info("[IDE MCP] Tool call: %s args=%s", name, list(arguments.keys()))

    # ---- voco_search_web ----
    if name == "voco_search_web":
        query = arguments.get("query", "")
        try:
            from langchain_tavily import TavilySearch
            searcher = TavilySearch(max_results=3)
            result = await searcher.ainvoke(query)
            return [TextContent(type="text", text=str(result))]
        except Exception as exc:
            logger.warning("[IDE MCP] voco_search_web error: %s", exc)
            return [TextContent(type="text", text=f"Search error: {exc}")]

    # ---- voco_read_github_issue ----
    if name == "voco_read_github_issue":
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            return [TextContent(
                type="text",
                text="Error: GITHUB_TOKEN is not set. Add it in the Voco Settings modal.",
            )]
        try:
            from github import Github
            g = Github(token)
            repo = g.get_repo(arguments["repo_name"])
            issue = repo.get_issue(number=int(arguments["issue_number"]))
            labels = ", ".join(lbl.name for lbl in issue.labels) or "none"
            text = (
                f"Issue #{issue.number}: {issue.title}\n"
                f"Labels: {labels}\n\n"
                f"{issue.body or '(no body)'}"
            )
            return [TextContent(type="text", text=text)]
        except Exception as exc:
            logger.warning("[IDE MCP] voco_read_github_issue error: %s", exc)
            return [TextContent(type="text", text=f"Error: {exc}")]

    # ---- voco_ask ----
    if name == "voco_ask":
        gateway_url = os.environ.get("LITELLM_GATEWAY_URL", "")
        session_token = os.environ.get("LITELLM_SESSION_TOKEN", "")
        if not gateway_url or not session_token:
            return [TextContent(
                type="text",
                text=(
                    "Error: LiteLLM gateway not configured. "
                    "Set LITELLM_GATEWAY_URL and LITELLM_SESSION_TOKEN in the cognitive-engine .env file."
                ),
            )]
        try:
            from langchain_core.messages import HumanMessage
            from src.graph.router import graph

            thread_id = f"ide-{uuid.uuid4().hex[:8]}"
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=arguments["prompt"])]},
                config={"configurable": {"thread_id": thread_id}},
            )
            final_msg = result["messages"][-1]
            text = (
                final_msg.content
                if isinstance(final_msg.content, str)
                else str(final_msg.content)
            )
            return [TextContent(type="text", text=text)]
        except Exception as exc:
            logger.error("[IDE MCP] voco_ask error: %s", exc, exc_info=True)
            return [TextContent(type="text", text=f"Error: {exc}")]

    return [TextContent(type="text", text=f"Unknown tool: '{name}'")]


# ---------------------------------------------------------------------------
# FastAPI route attachment
# ---------------------------------------------------------------------------

def attach_ide_mcp_routes(app: FastAPI) -> None:
    """Register GET /mcp and POST /mcp/messages on the main FastAPI app.

    Called once after ``app = FastAPI(...)`` in main.py.
    """

    @app.get("/mcp")
    async def handle_mcp_sse(request: Request) -> None:
        """SSE endpoint — IDEs connect here to establish the MCP session."""
        logger.info("[IDE MCP] IDE connected from %s", request.client)
        async with _sse.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as streams:
            await _mcp.run(
                streams[0],
                streams[1],
                _mcp.create_initialization_options(),
            )

    @app.post("/mcp/messages")
    async def handle_mcp_messages(request: Request) -> None:
        """JSON-RPC message endpoint — IDEs POST tool calls here."""
        await _sse.handle_post_message(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        )

    logger.info("[IDE MCP] Routes live: GET /mcp, POST /mcp/messages")
