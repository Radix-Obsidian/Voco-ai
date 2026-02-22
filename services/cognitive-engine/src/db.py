"""Supabase Logic Ledger — persistent sync of LangGraph execution state.

Writes every conversational turn and background job result into two Postgres tables:
  - ledger_sessions  : one row per WebSocket session (thread_id)
  - ledger_nodes     : one row per Visual Ledger node per session

The client is initialised lazily so the app starts cleanly even when
SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are absent.

All I/O is wrapped in ``asyncio.to_thread`` because the supabase-py SDK is
synchronous.  Every error is caught and logged — a database write failure must
never crash the voice pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)

_client: "Client | None" = None
_init_attempted = False


def _get_client() -> "Client | None":
    """Return the shared Supabase client, creating it on first call.

    Returns None (and logs a debug message) when credentials are missing,
    so callers can safely no-op without extra checks.
    """
    global _client, _init_attempted
    if _init_attempted:
        return _client

    _init_attempted = True
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        logger.debug(
            "[Ledger] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — "
            "Logic Ledger sync disabled."
        )
        return None

    try:
        from supabase import create_client

        _client = create_client(url, key)
        logger.info("[Ledger] Supabase client initialised.")
    except Exception as exc:
        logger.warning("[Ledger] Failed to initialise Supabase client: %s", exc)

    return _client


# ---------------------------------------------------------------------------
# Public async helpers
# ---------------------------------------------------------------------------


async def sync_ledger_to_supabase(
    session_id: str,
    user_id: str,
    project_id: str,
    domain: str,
    nodes: list[dict],
    session_status: str = "active",
) -> None:
    """Upsert the full session + node state into Supabase.

    Args:
        session_id:     WebSocket thread_id  (e.g. "session-abc12345")
        user_id:        User identifier      (defaults to "local")
        project_id:     Active project path / identifier
        domain:         Detected context domain (e.g. "general", "database")
        nodes:          List of node dicts mirroring the Visual Ledger schema.
                        Expected keys per node: id, iconType, title,
                        description, status, execution_output (optional).
        session_status: "active" | "completed" | "failed"
    """
    client = _get_client()
    if client is None:
        return

    def _sync() -> None:
        try:
            client.table("ledger_sessions").upsert(
                {
                    "id": session_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "domain": domain,
                    "status": session_status,
                },
                on_conflict="id",
            ).execute()
        except Exception as exc:
            logger.warning("[Ledger] Failed to upsert ledger_session %s: %s", session_id, exc)
            return

        for node in nodes:
            row_id = f"{session_id}_{node['id']}"
            try:
                client.table("ledger_nodes").upsert(
                    {
                        "id": row_id,
                        "session_id": session_id,
                        "parent_node_id": node.get("parent_node_id"),
                        "title": node.get("title", ""),
                        "description": node.get("description", ""),
                        "icon_type": node.get("iconType", "FileCode2"),
                        "status": node.get("status", "pending"),
                        "execution_output": node.get("execution_output"),
                    },
                    on_conflict="id",
                ).execute()
            except Exception as exc:
                logger.warning("[Ledger] Failed to upsert ledger_node %s: %s", row_id, exc)

    await asyncio.to_thread(_sync)


async def update_ledger_node(
    session_id: str,
    node_id: str,
    status: str,
    execution_output: str | None = None,
) -> None:
    """Update a single node's status and output — called when a background job finishes.

    Args:
        session_id:       WebSocket thread_id.
        node_id:          Visual Ledger node id (e.g. "3" for the Execute node).
        status:           "completed" | "failed" | "active"
        execution_output: Truncated tool result string (max 4 000 chars).
    """
    client = _get_client()
    if client is None:
        return

    row_id = f"{session_id}_{node_id}"

    def _update() -> None:
        row: dict = {"id": row_id, "status": status}
        if execution_output is not None:
            row["execution_output"] = execution_output[:4000]
        try:
            client.table("ledger_nodes").upsert(row, on_conflict="id").execute()
            logger.info("[Ledger] Node %s → %s", row_id, status)
        except Exception as exc:
            logger.warning("[Ledger] Failed to update ledger_node %s: %s", row_id, exc)

    await asyncio.to_thread(_update)
