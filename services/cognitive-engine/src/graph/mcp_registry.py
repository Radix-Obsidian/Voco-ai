"""Universal MCP Registry — dynamic tool discovery from external MCP servers.

Reads ``voco-mcp.json``, connects to each declared MCP server via stdio,
fetches their advertised tools, and wraps each one as a LangChain
``StructuredTool`` so the LangGraph orchestrator can invoke them.
"""

from __future__ import annotations

import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

# Resolve the default config path relative to this file so the registry
# finds voco-mcp.json at the project root regardless of the working directory.
# Path: mcp_registry.py → graph/ → src/ → cognitive-engine/ → services/ → Voco-ai/
# In Docker the path is shorter (/app/src/graph/), so we climb safely.
_MAX_PARENTS = len(Path(__file__).parents) - 1
_PROJECT_ROOT = Path(__file__).parents[min(4, _MAX_PARENTS)]
_DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "voco-mcp.json")


# ---------------------------------------------------------------------------
# JSON Schema → Pydantic translator
# ---------------------------------------------------------------------------

_JSON_TYPE_MAP: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _jsonschema_to_pydantic(
    tool_name: str, schema: Dict[str, Any]
) -> Type[BaseModel]:
    """Convert a JSON Schema ``properties`` dict into a dynamic Pydantic model.

    This is needed because ``StructuredTool.from_function`` expects an
    ``args_schema`` Pydantic class so Claude knows how to format its tool calls.
    """
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    fields: Dict[str, Any] = {}
    for name, info in properties.items():
        py_type = _JSON_TYPE_MAP.get(info.get("type", "string"), Any)
        desc = info.get("description", "")

        if name in required_fields:
            fields[name] = (py_type, Field(..., description=desc))
        else:
            fields[name] = (Optional[py_type], Field(default=None, description=desc))

    # create_model dynamically builds a BaseModel subclass
    model_name = "".join(part.capitalize() for part in tool_name.split("_")) + "Input"
    return create_model(model_name, **fields)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class UniversalMCPRegistry:
    """Manages connections to external MCP servers declared in ``voco-mcp.json``."""

    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH) -> None:
        self.config_path = config_path
        self.dynamic_tools: List[StructuredTool] = []
        self._exit_stack = AsyncExitStack()

    # -- public API ----------------------------------------------------------

    async def initialize(self) -> None:
        """Parse the config file and connect to every declared MCP server."""
        cfg_path = Path(self.config_path)
        if not cfg_path.exists():
            logger.warning(
                "[MCP Registry] %s not found — no external tools loaded.", cfg_path
            )
            return

        with open(cfg_path) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        for name, server_cfg in servers.items():
            try:
                await self._connect_server(name, server_cfg)
            except Exception:
                logger.exception("[MCP Registry] Failed to connect to %s", name)

        logger.info(
            "[MCP Registry] Initialised — %d external tools registered.",
            len(self.dynamic_tools),
        )

    async def shutdown(self) -> None:
        """Cleanly close all MCP server sub-processes."""
        await self._exit_stack.aclose()
        logger.info("[MCP Registry] All MCP server connections closed.")

    def get_tools(self) -> List[StructuredTool]:
        """Return the list of LangChain tools discovered from external servers."""
        return list(self.dynamic_tools)

    # -- internals -----------------------------------------------------------

    async def _connect_server(self, name: str, config: dict) -> None:
        """Spin up one MCP server, list its tools, and wrap them."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env", None),
        )

        logger.info("[MCP Registry] Connecting to '%s' (%s)…", name, config["command"])

        # Use AsyncExitStack so the subprocess stays alive for the app lifetime
        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = transport

        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        # Discover tools
        tools_response = await session.list_tools()
        logger.info(
            "[MCP Registry] '%s' exposes %d tools.", name, len(tools_response.tools)
        )

        for mcp_tool in tools_response.tools:
            pydantic_schema = _jsonschema_to_pydantic(
                mcp_tool.name, mcp_tool.inputSchema
            )

            # Build a closure that calls the tool on this specific session
            def _make_invoker(tool_name: str = mcp_tool.name, sess: ClientSession = session):
                async def _invoke(**kwargs: Any) -> str:
                    try:
                        result = await sess.call_tool(tool_name, arguments=kwargs)
                        
                        # Handle MCP's native error flag
                        if getattr(result, "isError", False):
                            texts = [b.text for b in result.content if hasattr(b, "text")]
                            return f"Tool returned an error: {' '.join(texts)}"
                            
                        # Concatenate all text content blocks
                        parts = []
                        for block in result.content:
                            if hasattr(block, "text"):
                                parts.append(block.text)
                            else:
                                parts.append(f"[{block.type} content]")
                        return "\n".join(parts) if parts else "(no output)"
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"[MCP Tool Error] {tool_name} failed: {e}")
                        # Return string so LangGraph wraps it in a valid ToolMessage
                        return f"Error executing tool {tool_name}: {str(e)}. Please inform the user."
                return _invoke

            lc_tool = StructuredTool.from_function(
                coroutine=_make_invoker(),
                name=f"{name}_{mcp_tool.name}",
                description=mcp_tool.description or f"Tool '{mcp_tool.name}' from {name} MCP server.",
                args_schema=pydantic_schema,
            )
            self.dynamic_tools.append(lc_tool)
            logger.info("[MCP Registry] Registered: %s", lc_tool.name)
