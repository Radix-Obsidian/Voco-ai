"""Tool dispatch phase — route pending MCP actions to the appropriate handler.

Handles screen analysis, security scans, sandbox preview, and standard
background RPC dispatch. Each handler is a standalone async function
receiving explicit dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from fastapi import WebSocket
from langchain_core.messages import ToolMessage

from src.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer()


async def dispatch_screen_analysis(
    websocket: WebSocket,
    graph: Any,
    config: dict,
    call_id: str,
    tool_args: dict,
) -> dict:
    """Request screen frames from Tauri, build a vision ToolMessage, re-invoke graph."""
    with tracer.start_as_current_span("voco.rpc.screen_analysis"):
        logger.info("[VocoEyes] Requesting screen frames for call_id=%s", call_id)
        await websocket.send_json({"type": "screen_capture_request", "id": call_id})

        frames: list[str] = []
        media_type = "image/jpeg"
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            frames_msg = json.loads(raw)
            if frames_msg.get("type") == "screen_frames":
                frames = frames_msg.get("frames", [])
                media_type = frames_msg.get("media_type", "image/jpeg")
        except asyncio.TimeoutError:
            logger.warning("[VocoEyes] Timed out waiting for screen_frames")
        except Exception as exc:
            logger.warning("[VocoEyes] Error receiving screen_frames: %s", exc)

        user_desc = tool_args.get("user_description", "")
        if frames:
            sampled = frames[-5:]
            vision_content: list = [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{f}"}}
                for f in sampled
            ]
            vision_content.append({
                "type": "text",
                "text": (
                    f"These are {len(sampled)} sequential screenshots of the user's screen "
                    "captured at 500ms intervals (most recent last). "
                    + (f"User says: {user_desc}. " if user_desc else "")
                    + "Analyze the visual state and diagnose any visible bugs, errors, or UI issues."
                ),
            })
            screen_tool_msg = ToolMessage(content=vision_content, tool_call_id=call_id)
            logger.info("[VocoEyes] Sending %d frames to Claude vision.", len(sampled))
        else:
            screen_tool_msg = ToolMessage(
                content="Screen buffer was empty — no frames captured yet. Tell the user to try again in a moment.",
                tool_call_id=call_id,
            )

        return await graph.ainvoke({"messages": [screen_tool_msg]}, config=config)


async def dispatch_security_scan(
    websocket: WebSocket,
    graph: Any,
    config: dict,
    call_id: str,
    tool_args: dict,
) -> dict:
    """Request a security scan from Tauri, build a ToolMessage, re-invoke graph."""
    with tracer.start_as_current_span("voco.rpc.security_scan"):
        project_path_arg = tool_args.get("project_path", os.environ.get("VOCO_PROJECT_PATH", ""))
        logger.info("[AutoSec] Requesting scan for call_id=%s path=%s", call_id, project_path_arg)

        await websocket.send_json({
            "type": "scan_security_request",
            "id": call_id,
            "project_path": project_path_arg,
        })

        findings_str = ""
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            scan_msg = json.loads(raw)
            if scan_msg.get("type") == "scan_security_result":
                findings_str = json.dumps(scan_msg.get("findings", {}), indent=2)
            else:
                findings_str = json.dumps(scan_msg, indent=2)
        except asyncio.TimeoutError:
            findings_str = '{"error": "Scan timed out after 30 seconds."}'
        except Exception as exc:
            findings_str = json.dumps({"error": str(exc)})

        sec_tool_msg = ToolMessage(
            content=(
                "Security scan complete. Analyze these findings and provide a "
                "prioritized threat summary with actionable remediation steps. "
                "Be concise — your response will be spoken aloud.\n\n"
                + findings_str
            ),
            tool_call_id=call_id,
        )
        return await graph.ainvoke({"messages": [sec_tool_msg]}, config=config)


async def dispatch_sandbox(
    websocket: WebSocket,
    graph: Any,
    config: dict,
    call_id: str,
    tool_name: str,
    tool_args: dict,
    sandbox_html: dict[str, str],
) -> dict:
    """Store sandbox HTML and notify frontend, then re-invoke graph."""
    with tracer.start_as_current_span("voco.rpc.sandbox"):
        html_code = tool_args.get("html_code", "")
        sandbox_html["current"] = html_code
        is_update = tool_name == "update_sandbox_preview"
        sandbox_url = "http://localhost:8001/sandbox"

        await websocket.send_json({
            "type": "sandbox_updated" if is_update else "sandbox_live",
            "url": sandbox_url,
        })
        logger.info("[Sandbox] %s served at %s (%d bytes)", "Updated" if is_update else "Live", sandbox_url, len(html_code))

        sandbox_tool_msg = ToolMessage(
            content=(
                "Sandbox preview updated. The user can see the changes instantly."
                if is_update else
                "MVP sandbox is live at http://localhost:8001/sandbox. "
                "The preview is now visible on the right side of the screen."
            ),
            tool_call_id=call_id,
        )
        return await graph.ainvoke({"messages": [sandbox_tool_msg]}, config=config)
