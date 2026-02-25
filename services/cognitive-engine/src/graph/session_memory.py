"""Session memory — persist and recall decisions across Voco sessions.

Saves one JSONL line per turn to ``{project}/.voco/sessions.jsonl`` and
loads the most recent entries for system-prompt injection so the LLM
"remembers" what happened in prior sessions.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ENTRIES = 20


def _sessions_path(project_path: str) -> Path:
    """Return the canonical JSONL path for a project."""
    return Path(project_path) / ".voco" / "sessions.jsonl"


def save_session_entry(
    project_path: str,
    transcript: str,
    actions: list[str] | None = None,
    files: list[str] | None = None,
    summary: str = "",
    session_id: str | None = None,
    model: str = "",
) -> None:
    """Append a single JSONL line capturing one conversation turn.

    Parameters
    ----------
    project_path : str
        Absolute path to the user's project root.
    transcript : str
        The user's message (transcribed speech or typed text).
    actions : list[str] | None
        Tool-call names executed during this turn.
    files : list[str] | None
        File paths referenced or modified during this turn.
    summary : str
        Short AI response summary (first ~200 chars of what Voco said).
    session_id : str | None
        Unique session identifier; auto-generated if not provided.
    model : str
        Model ID used for this turn (e.g. ``claude-sonnet-4-5-20250929``).
    """
    if not project_path:
        logger.debug("[SessionMemory] No project_path — skipping save.")
        return

    path = _sessions_path(project_path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id or f"session-{uuid.uuid4().hex[:8]}",
            "model": model,
            "transcript": transcript,
            "actions": actions or [],
            "files": files or [],
            "summary": summary,
        }

        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.debug("[SessionMemory] Saved entry to %s", path)
    except Exception as exc:
        logger.warning("[SessionMemory] Failed to save: %s", exc)


def load_session_history(
    project_path: str,
    max_entries: int = _DEFAULT_MAX_ENTRIES,
) -> str:
    """Read the last *max_entries* turns and return formatted text.

    Returns an empty string when there is no project path, no file, or
    the file is empty — the caller can safely prepend the result to a
    system prompt without extra guards.
    """
    if not project_path:
        return ""

    path = _sessions_path(project_path)
    if not path.exists():
        return ""

    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception as exc:
        logger.warning("[SessionMemory] Failed to read %s: %s", path, exc)
        return ""

    if not lines:
        return ""

    # Keep only the tail
    recent = lines[-max_entries:]

    formatted: list[str] = []
    for raw in recent:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        ts = entry.get("ts", "")
        # Pretty-print the timestamp if possible
        try:
            dt = datetime.fromisoformat(ts)
            ts_label = dt.strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            ts_label = ts

        transcript = entry.get("transcript", "")
        actions = entry.get("actions", [])
        summary = entry.get("summary", "")

        block = f"[{ts_label}] User: \"{transcript}\""
        if actions:
            block += f"\n  → Actions: {', '.join(actions)}"
        if summary:
            block += f"\n  → Summary: {summary}"
        formatted.append(block)

    if not formatted:
        return ""

    return "## Session Memory (recent history from this project)\n" + "\n".join(formatted)
