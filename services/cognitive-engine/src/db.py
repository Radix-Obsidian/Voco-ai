"""Supabase Logic Ledger — persistent sync of LangGraph execution state.

Writes every conversational turn and background job result into two Postgres tables:
  - ledger_sessions  : one row per WebSocket session (thread_id)
  - ledger_nodes     : one row per Visual Ledger node per session

The client is initialised per-session using the authenticated user's JWT so that
all writes go through Row Level Security (RLS).  When no JWT is available the
ledger sync is silently disabled — the voice pipeline is never affected.

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
_auth_uid: str = "local"


def set_auth_jwt(access_token: str, uid: str, refresh_token: str = "") -> None:
    """Re-initialise the Supabase client with the user's JWT for RLS.

    Called by ``main.py`` when an ``auth_sync`` message arrives from the
    frontend.  The client is created with the **anon key** and then the
    session is overridden with the user's access token so that Postgres
    RLS policies see ``auth.uid()`` correctly.

    Per official Supabase docs, ``set_session`` requires both access_token
    and refresh_token. Without a valid refresh_token, the session cannot
    be refreshed and will expire silently.
    See: https://supabase.com/docs/reference/python/auth-setsession
    """
    global _client, _auth_uid
    _auth_uid = uid or "local"

    url = os.environ.get("SUPABASE_URL", "")
    anon_key = os.environ.get("VITE_SUPABASE_PUBLISHABLE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")

    if not url or not anon_key:
        logger.debug(
            "[Ledger] SUPABASE_URL or SUPABASE_ANON_KEY not set — "
            "Logic Ledger sync disabled."
        )
        _client = None
        return

    if not access_token:
        logger.debug("[Ledger] No JWT provided — Logic Ledger sync disabled.")
        _client = None
        return

    if not refresh_token:
        logger.warning("[Ledger] No refresh_token provided — session cannot auto-refresh.")

    try:
        from supabase import create_client

        client = create_client(url, anon_key)
        # Override the session with the user's JWT so RLS policies apply.
        # Both tokens required per Supabase official docs.
        client.auth.set_session(access_token, refresh_token or access_token)
        _client = client
        logger.info("[Ledger] Supabase client initialised with user JWT (uid=%s).", uid)
    except Exception as exc:
        logger.warning("[Ledger] Failed to initialise Supabase client with JWT: %s", exc)
        _client = None


def _get_client() -> "Client | None":
    """Return the current per-session Supabase client.

    Returns None when no JWT has been provided yet (pre-login), so callers
    can safely no-op without extra checks.
    """
    if _client is None:
        logger.debug("[Ledger] No authenticated Supabase client — sync skipped.")
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
