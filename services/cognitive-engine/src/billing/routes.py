"""Stripe billing — Seat + Meter hybrid model.

Seat  : Fixed monthly subscription fee per user  (STRIPE_PRO_PRICE_ID).
Meter : Pay-per-voice-turn usage billing          (STRIPE_METER_PRICE_ID, usage_type=metered).

Every completed voice turn calls ``report_voice_turn()`` which increments the
Stripe usage record by 1.  The Stripe invoice at month-end = seat fee + (turns × meter rate).

Environment variables:
  STRIPE_SECRET_KEY        — sk_live_... or sk_test_...
  STRIPE_WEBHOOK_SECRET    — whsec_... (from Stripe dashboard or CLI)
  STRIPE_PRO_PRICE_ID      — Price ID for the flat seat fee (recurring, monthly)
  STRIPE_METER_PRICE_ID    — Price ID for per-turn meter (usage_type=metered, monthly)
  STRIPE_METER_ITEM_ID     — Auto-populated at runtime after first checkout; persists via env
  SUPABASE_URL             — Supabase project URL
  SUPABASE_SERVICE_KEY     — Supabase service-role key

Stripe CLI dev workflow:
  stripe listen --forward-to localhost:8001/billing/webhook
  stripe trigger checkout.session.completed
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# In-memory cache of the active metered subscription item ID.
# Populated by the checkout.session.completed webhook; also reads from
# STRIPE_METER_ITEM_ID env var so it survives server restarts.
_meter_item_id: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_stripe() -> None:
    """Configure stripe.api_key; raise 503 if STRIPE_SECRET_KEY is absent."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Stripe not configured — set STRIPE_SECRET_KEY")
    stripe.api_key = key


def _get_meter_item_id() -> str:
    """Return the active metered subscription item ID from memory or env."""
    return _meter_item_id or os.environ.get("STRIPE_METER_ITEM_ID", "")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    customer_email: str = ""
    success_url: str = "http://localhost:1420"
    cancel_url: str = "http://localhost:1420"


class PortalRequest(BaseModel):
    customer_id: str
    return_url: str = "http://localhost:1420"


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.post("/create-checkout-session")
async def create_checkout_session(req: CheckoutRequest) -> dict:
    """Create a Stripe Checkout Session for the Seat + Meter Pro plan.

    Line items:
      1. Seat  — flat monthly fee           (STRIPE_PRO_PRICE_ID, quantity=1)
      2. Meter — per voice-turn usage fee   (STRIPE_METER_PRICE_ID, no quantity)

    The meter price must be created in Stripe with ``usage_type=metered``.
    Usage is reported programmatically via ``report_voice_turn()`` after each turn.
    """
    _require_stripe()

    seat_price_id = os.environ.get("STRIPE_PRO_PRICE_ID", "")
    meter_price_id = os.environ.get("STRIPE_METER_PRICE_ID", "")

    if not seat_price_id:
        raise HTTPException(status_code=503, detail="STRIPE_PRO_PRICE_ID not configured")

    # Seat is a flat recurring charge; meter has no quantity (usage reported separately)
    line_items: list[dict] = [{"price": seat_price_id, "quantity": 1}]
    if meter_price_id:
        line_items.append({"price": meter_price_id})

    params: dict = {
        "mode": "subscription",
        "line_items": line_items,
        "success_url": req.success_url,
        "cancel_url": req.cancel_url,
        "allow_promotion_codes": True,
    }
    if req.customer_email:
        params["customer_email"] = req.customer_email

    session = stripe.checkout.Session.create(**params)
    logger.info("[Billing] Checkout session created: %s (seat + meter)", session.id)
    return {"url": session.url, "session_id": session.id}


@router.post("/create-portal-session")
async def create_portal_session(req: PortalRequest) -> dict:
    """Return a Stripe Customer Portal URL for managing subscriptions."""
    _require_stripe()
    portal = stripe.billing_portal.Session.create(
        customer=req.customer_id,
        return_url=req.return_url,
    )
    logger.info("[Billing] Portal session created for customer: %s", req.customer_id)
    return {"url": portal.url}


@router.get("/usage")
async def get_current_usage() -> dict:
    """Return active meter item info and a link to the Stripe dashboard."""
    item_id = _get_meter_item_id()
    return {
        "meter_item_id": item_id,
        "configured": bool(item_id),
        "dashboard_url": "https://dashboard.stripe.com/subscriptions" if item_id else None,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request) -> Response:
    """Verify Stripe webhook signature and handle subscription lifecycle events.

    CRITICAL: ``await request.body()`` must be called BEFORE any JSON parsing —
    Stripe's HMAC verification requires the raw bytes.
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.warning("[Billing] STRIPE_WEBHOOK_SECRET not set — rejecting webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("[Billing] Webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error("[Billing] Webhook parse error: %s", exc)
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    event_type: str = event["type"]
    logger.info("[Billing] Stripe event: %s", event_type)

    if event_type == "checkout.session.completed":
        data = event["data"]["object"]
        customer_id: str = data.get("customer", "")
        customer_email: str = data.get("customer_details", {}).get("email", "")
        subscription_id: str = data.get("subscription", "")
        await _activate_subscription(customer_email, customer_id, subscription_id)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        sub = event["data"]["object"]
        customer_id = sub.get("customer", "")
        status: str = sub.get("status", "")
        if status in ("canceled", "unpaid", "past_due"):
            await _deactivate_subscription(customer_id)

    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Voice pipeline integration — call this after every turn
# ---------------------------------------------------------------------------


async def report_voice_turn(quantity: int = 1) -> None:
    """Increment the Stripe meter by ``quantity`` voice turns.

    Fire-and-forget safe: all errors are caught and logged so a Stripe outage
    never blocks the voice pipeline.  Uses ``asyncio.to_thread`` because the
    stripe-python SDK is synchronous.
    """
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    item_id = _get_meter_item_id()

    if not key or not item_id:
        logger.debug("[Billing] Usage reporting skipped (Stripe not fully configured).")
        return

    def _report() -> None:
        stripe.api_key = key
        stripe.SubscriptionItem.create_usage_record(
            item_id,
            quantity=quantity,
            action="increment",
        )

    try:
        await asyncio.to_thread(_report)
        logger.info("[Billing] Reported %d voice turn(s) → meter %s.", quantity, item_id)
    except Exception as exc:
        logger.warning("[Billing] Usage report failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Supabase tier management
# ---------------------------------------------------------------------------


async def _update_supabase_tier(
    email: str,
    customer_id: str,
    subscription_id: str,
    meter_item_id: str,
    tier: str,
) -> None:
    """PATCH the users table in Supabase via the PostgREST REST API."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        logger.warning("[Billing] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — skipping tier update")
        return

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    body = {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_meter_item_id": meter_item_id,
        "tier": tier,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{supabase_url}/rest/v1/users",
            json=body,
            headers=headers,
            params={"email": f"eq.{email}"},
        )

    if resp.status_code not in (200, 204):
        logger.error("[Billing] Supabase PATCH failed: %s — %s", resp.status_code, resp.text)
    else:
        logger.info("[Billing] Supabase: tier=%s for %s (meter=%s)", tier, email, meter_item_id)


async def _activate_subscription(
    email: str, customer_id: str, subscription_id: str
) -> None:
    """Activate Pro tier and extract + cache the metered subscription item ID."""
    global _meter_item_id
    logger.info("[Billing] Activating Pro — customer=%s email=%s", customer_id, email)

    # Retrieve the subscription items to find the meter price item ID
    meter_item_id = ""
    meter_price_id = os.environ.get("STRIPE_METER_PRICE_ID", "")

    if subscription_id and meter_price_id:
        def _fetch_items() -> str:
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            sub = stripe.Subscription.retrieve(subscription_id, expand=["items"])
            for item in sub["items"]["data"]:
                if item["price"]["id"] == meter_price_id:
                    return item["id"]
            return ""

        try:
            meter_item_id = await asyncio.to_thread(_fetch_items)
        except Exception as exc:
            logger.warning("[Billing] Could not retrieve meter item ID: %s", exc)

    # Cache in memory and env so it survives between voice turns and server restarts
    if meter_item_id:
        _meter_item_id = meter_item_id
        os.environ["STRIPE_METER_ITEM_ID"] = meter_item_id
        logger.info("[Billing] Meter item ID cached: %s", meter_item_id)
    else:
        logger.warning("[Billing] Meter item ID not found — per-turn billing disabled until resolved")

    await _update_supabase_tier(email, customer_id, subscription_id, meter_item_id, "pro")


async def _deactivate_subscription(customer_id: str) -> None:
    """Downgrade to free tier and clear the cached meter item ID."""
    global _meter_item_id
    logger.info("[Billing] Deactivating Pro — customer=%s", customer_id)
    _require_stripe()

    try:
        customer = await asyncio.to_thread(stripe.Customer.retrieve, customer_id)
        email: str = getattr(customer, "email", "") or ""
        if email:
            _meter_item_id = ""
            os.environ.pop("STRIPE_METER_ITEM_ID", None)
            await _update_supabase_tier(email, customer_id, "", "", "free")
        else:
            logger.warning("[Billing] No email on Stripe customer %s", customer_id)
    except Exception as exc:
        logger.error("[Billing] Failed to deactivate customer %s: %s", customer_id, exc)
