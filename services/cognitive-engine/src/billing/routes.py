"""Stripe billing endpoints — Checkout, Customer Portal, Webhook.

Environment variables required:
  STRIPE_SECRET_KEY        — Stripe secret key (sk_live_... or sk_test_...)
  STRIPE_WEBHOOK_SECRET    — Stripe webhook signing secret (whsec_...)
  STRIPE_PRO_PRICE_ID      — Stripe Price ID for the Pro subscription
  SUPABASE_URL             — Supabase project URL
  SUPABASE_SERVICE_KEY     — Supabase service-role key (for admin writes)

Stripe CLI quick-start:
  stripe listen --forward-to localhost:8001/billing/webhook
  stripe trigger checkout.session.completed
"""

from __future__ import annotations

import logging
import os

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_stripe() -> None:
    """Set stripe.api_key from env; raise 503 if not configured."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Stripe not configured — set STRIPE_SECRET_KEY")
    stripe.api_key = key


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    customer_email: str = ""
    success_url: str = "http://localhost:1420"
    cancel_url: str = "http://localhost:1420"


class PortalRequest(BaseModel):
    customer_id: str
    return_url: str = "http://localhost:1420"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/create-checkout-session")
async def create_checkout_session(req: CheckoutRequest) -> dict:
    """Return a Stripe Checkout Session URL for the Pro subscription."""
    _require_stripe()

    price_id = os.environ.get("STRIPE_PRO_PRICE_ID", "")
    if not price_id:
        raise HTTPException(status_code=503, detail="STRIPE_PRO_PRICE_ID not configured")

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": req.success_url,
        "cancel_url": req.cancel_url,
        # Allow promotion codes on the checkout page
        "allow_promotion_codes": True,
    }
    if req.customer_email:
        params["customer_email"] = req.customer_email

    session = stripe.checkout.Session.create(**params)
    logger.info("[Billing] Checkout session created: %s", session.id)
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


@router.post("/webhook")
async def stripe_webhook(request: Request) -> Response:
    """Verify Stripe webhook signature and handle subscription lifecycle events.

    CRITICAL: `await request.body()` must be called BEFORE any JSON parsing —
    Stripe's HMAC signature verification requires the raw bytes.
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        logger.warning("[Billing] STRIPE_WEBHOOK_SECRET not set — rejecting webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()  # raw bytes — required for HMAC verification
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

    elif event_type in (
        "customer.subscription.deleted",
        "customer.subscription.updated",
    ):
        sub = event["data"]["object"]
        customer_id = sub.get("customer", "")
        status: str = sub.get("status", "")
        if status in ("canceled", "unpaid", "past_due"):
            await _deactivate_subscription(customer_id)

    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Supabase tier management
# ---------------------------------------------------------------------------


async def _update_supabase_tier(
    email: str,
    customer_id: str,
    subscription_id: str,
    tier: str,
) -> None:
    """PATCH the users table in Supabase via the REST API."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not service_key:
        logger.warning(
            "[Billing] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — tier update skipped"
        )
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
        logger.error(
            "[Billing] Supabase PATCH failed: %s — %s", resp.status_code, resp.text
        )
    else:
        logger.info("[Billing] Supabase: tier=%s set for %s", tier, email)


async def _activate_subscription(
    email: str, customer_id: str, subscription_id: str
) -> None:
    logger.info("[Billing] Activating Pro for customer=%s email=%s", customer_id, email)
    await _update_supabase_tier(email, customer_id, subscription_id, "pro")


async def _deactivate_subscription(customer_id: str) -> None:
    """Look up the customer email from Stripe, then downgrade tier in Supabase."""
    logger.info("[Billing] Deactivating Pro for customer=%s", customer_id)
    _require_stripe()
    try:
        customer = stripe.Customer.retrieve(customer_id)
        email: str = getattr(customer, "email", "") or ""
        if email:
            await _update_supabase_tier(email, customer_id, "", "free")
        else:
            logger.warning("[Billing] No email found for customer %s", customer_id)
    except Exception as exc:
        logger.error("[Billing] Failed to deactivate customer %s: %s", customer_id, exc)
