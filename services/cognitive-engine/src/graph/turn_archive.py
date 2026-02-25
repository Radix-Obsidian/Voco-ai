"""Per-turn prompt archival for replay and debugging.

Writes a JSON file per turn to ``{app_data}/sessions/{session_id}/turn_{N}.json``
containing the full system prompt, messages, tool calls, and model metadata.

The ``prompt_hash`` (SHA-256, first 12 hex chars) enables quick diffing of prompt
changes across sessions without storing the full text in the graph state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TAURI_APP_ID = "com.voco.mcp-gateway"


def _get_app_data_dir() -> Path:
    """Return the platform-specific app data directory (mirrors Tauri's app_data_dir)."""
    platform: str = sys.platform
    if platform == "win32":
        base = os.environ.get("APPDATA", "")
        return Path(base) / _TAURI_APP_ID
    elif platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _TAURI_APP_ID
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base_dir = Path(xdg) if xdg else Path.home() / ".local" / "share"
        return base_dir / _TAURI_APP_ID


def compute_prompt_hash(system_prompt: str) -> str:
    """Return the first 12 hex characters of the SHA-256 of *system_prompt*."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]


def archive_turn(
    session_id: str,
    turn_number: int,
    system_prompt: str,
    model_name: str,
    messages: list[Any],
    tool_calls: list[Any] | None = None,
) -> str:
    """Write a full turn snapshot to disk and return the ``prompt_hash``.

    Parameters
    ----------
    session_id : str
        The LangGraph thread_id / session identifier.
    turn_number : int
        Monotonically increasing turn counter within this session.
    system_prompt : str
        The full system prompt sent to the model this turn.
    model_name : str
        Model identifier string (e.g. ``"claude-sonnet-4-5-20250929"``).
    messages : list
        The conversation messages fed to the model (serialized to JSON-safe dicts).
    tool_calls : list | None
        Tool calls returned by the model, if any.

    Returns
    -------
    str
        The prompt hash (first 12 hex chars of SHA-256).
    """
    prompt_hash = compute_prompt_hash(system_prompt)

    session_dir = _get_app_data_dir() / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    archive_path = session_dir / f"turn_{turn_number}.json"

    # Serialize messages to JSON-safe dicts
    serialized_messages = []
    for m in messages:
        if hasattr(m, "model_dump"):
            try:
                serialized_messages.append(m.model_dump())
            except Exception:
                serialized_messages.append({"content": str(m)})
        elif hasattr(m, "dict"):
            try:
                serialized_messages.append(m.dict())
            except Exception:
                serialized_messages.append({"content": str(m)})
        else:
            serialized_messages.append({"content": str(m)})

    payload = {
        "session_id": session_id,
        "turn_number": turn_number,
        "prompt_hash": prompt_hash,
        "model_name": model_name,
        "system_prompt": system_prompt,
        "messages": serialized_messages,
        "tool_calls": tool_calls or [],
    }

    try:
        archive_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        logger.debug("[TurnArchive] Wrote %s (%d bytes)", archive_path, archive_path.stat().st_size)
    except Exception as exc:
        logger.warning("[TurnArchive] Failed to write %s: %s", archive_path, exc)

    return prompt_hash
