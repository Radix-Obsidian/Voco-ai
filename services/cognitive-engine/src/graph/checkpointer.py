"""SQLite-backed checkpointer for LangGraph sessions.

Provides deterministic replay by persisting graph state to a local SQLite
database.  Each session gets its own file at:
    ``{app_data}/sessions/{session_id}/checkpoints.db``

Includes ``prune_checkpoints()`` to enforce a 50-turn maximum, preventing
unbounded memory/disk growth (Issue #9).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger(__name__)

_TAURI_APP_ID = "com.voco.mcp-gateway"
_DEFAULT_MAX_TURNS = 50


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


def get_checkpoint_path(session_id: str) -> str:
    """Return the absolute path to the SQLite checkpoint DB for *session_id*."""
    session_dir = _get_app_data_dir() / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return str(session_dir / "checkpoints.db")


async def get_checkpointer(session_id: str) -> AsyncSqliteSaver:
    """Create and return an ``AsyncSqliteSaver`` for the given session.

    ``AsyncSqliteSaver.from_conn_string()`` returns an async context manager.
    We enter it here and return the live saver instance.  The caller is
    responsible for closing it when done (``await saver.conn.close()``).
    """
    db_path = get_checkpoint_path(session_id)
    ctx = AsyncSqliteSaver.from_conn_string(db_path)
    saver = await ctx.__aenter__()
    logger.info("[Checkpointer] Opened SQLite checkpoint: %s", db_path)
    return saver


async def prune_checkpoints(session_id: str, max_turns: int = _DEFAULT_MAX_TURNS) -> int:
    """Delete the oldest checkpoints beyond *max_turns* for the session.

    Returns the number of checkpoints deleted.
    """
    import aiosqlite

    db_path = get_checkpoint_path(session_id)
    if not Path(db_path).exists():
        return 0

    deleted = 0
    try:
        async with aiosqlite.connect(db_path) as db:
            # Count total checkpoints for this thread
            cursor = await db.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            total = row[0] if row else 0

            if total > max_turns:
                excess = total - max_turns
                await db.execute(
                    """
                    DELETE FROM checkpoints
                    WHERE thread_id = ? AND checkpoint_id IN (
                        SELECT checkpoint_id FROM checkpoints
                        WHERE thread_id = ?
                        ORDER BY checkpoint_id ASC
                        LIMIT ?
                    )
                    """,
                    (session_id, session_id, excess),
                )
                await db.commit()
                deleted = excess
                logger.info(
                    "[Checkpointer] Pruned %d old checkpoints for %s (kept %d)",
                    deleted, session_id, max_turns,
                )
    except Exception as exc:
        logger.warning("[Checkpointer] Prune failed for %s: %s", session_id, exc)

    return deleted
