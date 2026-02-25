"""Graph phase — invoke LangGraph with the user's transcript."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from src.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer()


async def run_graph(transcript: str, graph: Any, config: dict) -> dict:
    """Run the LangGraph cognitive engine with *transcript* as a HumanMessage.

    Returns the full graph result dict.
    """
    with tracer.start_as_current_span("voco.graph", attributes={"transcript.len": len(transcript)}):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=transcript)]},
            config=config,
        )
        logger.info("[Graph] Complete. Messages: %d", len(result.get("messages", [])))
        return result
