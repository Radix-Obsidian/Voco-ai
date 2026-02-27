"""IP-based free account limit — one free account per IP address.

Prevents abuse where users create unlimited free accounts with throwaway
emails, burning through 50 free turns each time.

Architecture:
  - Supabase table ``signup_ips``: id (uuid PK), ip_address (text),
    user_id (uuid), email (text), created_at (timestamptz).
  - ``POST /auth/check-ip``  — called BEFORE signup; returns allowed/blocked.
  - ``POST /auth/record-ip`` — called AFTER  successful signup; records the IP.

The client IP is read from ``request.client.host`` (direct) or
``X-Forwarded-For`` (behind nginx/proxy).  Founder emails bypass the
check entirely.

Environment variables:
  SUPABASE_URL           — Supabase project URL
  SUPABASE_SERVICE_KEY   — Supabase service-role key (bypasses RLS)
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

FOUNDER_EMAILS = {
    "autrearchitect@gmail.com",
    "architect@viperbyproof.com",
}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class IpCheckRequest(BaseModel):
    email: str = ""


class RecordIpRequest(BaseModel):
    user_id: str
    email: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _supabase_headers() -> dict[str, str]:
    """Build Supabase service-role headers for PostgREST calls."""
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/check-ip")
async def check_ip(req: IpCheckRequest, request: Request) -> dict:
    """Check whether the requesting IP already has a free account.

    Returns ``{"allowed": true}`` if:
      - The email is a founder email, OR
      - No existing row in ``signup_ips`` matches this IP.

    Returns ``{"allowed": false, "message": "..."}`` otherwise.
    """
    # Founders always pass
    if req.email and req.email.lower() in FOUNDER_EMAILS:
        return {"allowed": True, "message": "Founder bypass"}

    client_ip = _get_client_ip(request)
    logger.info("[Auth] IP check for %s (email=%s)", client_ip, req.email)

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        # If Supabase isn't configured, allow signup (graceful degradation)
        logger.warning("[Auth] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — allowing signup")
        return {"allowed": True, "message": "Supabase not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/signup_ips",
                headers=_supabase_headers(),
                params={
                    "ip_address": f"eq.{client_ip}",
                    "select": "id",
                },
            )

        if resp.status_code == 200:
            rows = resp.json()
            if len(rows) > 0:
                logger.info("[Auth] IP %s already has %d account(s) — blocking signup", client_ip, len(rows))
                return {
                    "allowed": False,
                    "message": "One free account per device. Upgrade to Pro for unlimited access.",
                }
            return {"allowed": True, "message": ""}
        else:
            logger.warning("[Auth] Supabase query failed (%d): %s", resp.status_code, resp.text)
            # Fail open — don't block signups due to a DB error
            return {"allowed": True, "message": ""}

    except Exception as exc:
        logger.error("[Auth] IP check error: %s", exc)
        # Fail open
        return {"allowed": True, "message": ""}


@router.post("/record-ip")
async def record_ip(req: RecordIpRequest, request: Request) -> dict:
    """Record a successful signup's IP address in ``signup_ips``.

    Called by the frontend immediately after ``supabase.auth.signUp()``
    succeeds.
    """
    client_ip = _get_client_ip(request)
    logger.info("[Auth] Recording signup IP %s for user %s", client_ip, req.user_id)

    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        logger.warning("[Auth] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — skipping IP record")
        return {"recorded": False, "reason": "Supabase not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{supabase_url}/rest/v1/signup_ips",
                headers=_supabase_headers(),
                json={
                    "ip_address": client_ip,
                    "user_id": req.user_id,
                    "email": req.email,
                },
            )

        if resp.status_code in (200, 201):
            logger.info("[Auth] IP %s recorded for user %s", client_ip, req.user_id)
            return {"recorded": True}
        else:
            logger.warning("[Auth] Failed to record IP (%d): %s", resp.status_code, resp.text)
            return {"recorded": False, "reason": f"HTTP {resp.status_code}"}

    except Exception as exc:
        logger.error("[Auth] Record IP error: %s", exc)
        return {"recorded": False, "reason": str(exc)}
