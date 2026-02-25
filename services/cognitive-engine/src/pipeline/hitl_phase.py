"""HITL phase — handle proposal and command interrupts.

These functions encapsulate the Human-in-the-Loop review flows for
file proposals and terminal commands, previously inline in ``main.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from fastapi import WebSocket
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer()


async def handle_proposal_interrupt(
    websocket: WebSocket,
    graph: Any,
    config: dict,
    result: dict,
    receive_filtered_fn: Any,
) -> dict:
    """Send file proposals to the frontend, wait for decisions, resume graph.

    Returns the updated graph result after resuming.
    """
    with tracer.start_as_current_span("voco.hitl.proposals"):
        snapshot = await graph.aget_state(config)
        if not (snapshot.next and "proposal_review_node" in snapshot.next):
            return result

        proposals = snapshot.values.get("pending_proposals", [])
        project_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
        logger.info("[HITL] Interrupt: %d proposals pending review", len(proposals))

        for p in proposals:
            await websocket.send_json({
                "type": "proposal",
                "proposal_id": p.get("proposal_id", ""),
                "action": p.get("action", ""),
                "file_path": p.get("file_path", ""),
                "content": p.get("content", ""),
                "diff": p.get("diff", ""),
                "description": p.get("description", ""),
                "project_root": project_path,
            })

        decisions = []
        try:
            decision_msg = await receive_filtered_fn("proposal_decision", timeout=120.0)
            decisions = decision_msg.get("decisions", [])
        except asyncio.TimeoutError:
            logger.warning("[HITL] Proposal decision timeout")
        except Exception as exc:
            logger.warning("[HITL] Proposal decision error: %s", exc)

        # For approved create_file proposals, dispatch write_file to Tauri
        decision_map = {d["proposal_id"]: d for d in decisions}
        for p in proposals:
            pid = p.get("proposal_id", "")
            decision = decision_map.get(pid, {})
            if decision.get("status") == "approved" and p.get("action") == "create_file":
                file_path = p.get("file_path", "")
                if not os.path.isabs(file_path):
                    file_path = os.path.join(project_path, file_path)
                write_rpc = {
                    "jsonrpc": "2.0",
                    "id": f"write_{pid}",
                    "method": "local/write_file",
                    "params": {
                        "file_path": file_path,
                        "content": p.get("content", ""),
                        "project_root": project_path,
                    },
                }
                await websocket.send_json(write_rpc)
                try:
                    write_resp_raw = await websocket.receive_text()
                    write_resp = json.loads(write_resp_raw)
                    logger.info("[HITL] write_file result for %s: %s", pid, write_resp.get("result", write_resp.get("error", "")))
                except Exception as exc:
                    logger.warning("[HITL] write_file response error: %s", exc)

        result = await graph.ainvoke(
            Command(resume=None, update={"proposal_decisions": decisions}),
            config=config,
        )
        return result


async def handle_command_interrupt(
    websocket: WebSocket,
    graph: Any,
    config: dict,
    result: dict,
    receive_filtered_fn: Any,
) -> dict:
    """Send command proposals to the frontend, wait for decisions, resume graph.

    Returns the updated graph result after resuming.
    """
    with tracer.start_as_current_span("voco.hitl.commands"):
        snapshot = await graph.aget_state(config)
        if not (snapshot.next and "command_review_node" in snapshot.next):
            return result

        commands = snapshot.values.get("pending_commands", [])
        project_path = result.get("active_project_path") or os.environ.get("VOCO_PROJECT_PATH", "")
        logger.info("[HITL] Command interrupt: %d commands pending approval", len(commands))

        for c in commands:
            await websocket.send_json({
                "type": "command_proposal",
                "command_id": c.get("command_id", ""),
                "command": c.get("command", ""),
                "description": c.get("description", ""),
                "project_path": c.get("project_path", project_path),
            })

        cmd_decisions = []
        try:
            decision_msg = await receive_filtered_fn("command_decision", timeout=120.0)
            cmd_decisions = decision_msg.get("decisions", [])
        except asyncio.TimeoutError:
            logger.warning("[HITL] Command decision timeout")
        except Exception as exc:
            logger.warning("[HITL] Command decision error: %s", exc)

        # Execute approved commands via Tauri
        for d in cmd_decisions:
            if d.get("status") != "approved":
                continue
            cid = d["command_id"]
            cmd_data = next((c for c in commands if c.get("command_id") == cid), None)
            if not cmd_data:
                continue
            exec_rpc = {
                "jsonrpc": "2.0",
                "id": f"cmd_{cid}",
                "method": "local/execute_command",
                "params": {
                    "command": cmd_data.get("command", ""),
                    "project_path": cmd_data.get("project_path", project_path),
                },
            }
            await websocket.send_json(exec_rpc)
            try:
                exec_resp_raw = await websocket.receive_text()
                exec_resp = json.loads(exec_resp_raw)
                cmd_output = exec_resp.get("result", exec_resp.get("error", {}).get("message", ""))
                d["output"] = str(cmd_output)
                logger.info("[HITL] execute_command result for %s: %.200s", cid, cmd_output)
            except Exception as exc:
                d["output"] = f"execution error: {exc}"
                logger.warning("[HITL] execute_command response error: %s", exc)

        result = await graph.ainvoke(
            Command(resume=None, update={"command_decisions": cmd_decisions}),
            config=config,
        )
        return result
