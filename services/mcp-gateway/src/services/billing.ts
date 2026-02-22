/**
 * Voco V2 Billing Skeleton — Stripe plumbing for V1→V2 migration.
 *
 * Architecture note: The mcp-gateway is a Tauri desktop app, NOT a server.
 * Stripe webhooks require an HTTP endpoint. Two deployment options:
 *   1. Add webhook routes to the Python FastAPI cognitive-engine.
 *   2. Deploy a lightweight edge function (Cloudflare Workers / Vercel / Railway).
 *
 * This module provides:
 *   - Types and tier definitions compatible with V1 customer IDs
 *   - Stripe client initialisation
 *   - Checkout session creation (callable from Tauri → opens browser)
 *   - Webhook event handler (portable — wire into whichever server hosts the endpoint)
 *   - Tier resolution from a subscription object
 */

import Stripe from "stripe";

// ---------------------------------------------------------------------------
// Tier definitions (Hormozi value-based model)
// ---------------------------------------------------------------------------

export type SubscriptionTier = "listener" | "orchestrator" | "architect";

export interface TierConfig {
  name: string;
  priceMonthly: number;
  voiceTurnsPerMonth: number | null; // null = unlimited
  intentLedger: boolean;
  priorityGpu: boolean;
  customSkills: boolean;
}

export const TIERS: Record<SubscriptionTier, TierConfig> = {
  listener: {
    name: "The Listener",
    priceMonthly: 0,
    voiceTurnsPerMonth: 500,
    intentLedger: false,
    priorityGpu: false,
    customSkills: false,
  },
  orchestrator: {
    name: "The Orchestrator",
    priceMonthly: 39,
    voiceTurnsPerMonth: null,
    intentLedger: true,
    priorityGpu: false,
    customSkills: false,
  },
  architect: {
    name: "The Architect",
    priceMonthly: 149,
    voiceTurnsPerMonth: null,
    intentLedger: true,
    priorityGpu: true,
    customSkills: true,
  },
};

// ---------------------------------------------------------------------------
// Stripe Price ID mapping (set via environment variables)
// ---------------------------------------------------------------------------

export interface StripePriceIds {
  listener: string;
  orchestrator: string;
  architect: string;
}

function getPriceIds(): StripePriceIds {
  return {
    listener: import.meta.env.VITE_STRIPE_PRICE_LISTENER ?? "",
    orchestrator: import.meta.env.VITE_STRIPE_PRICE_ORCHESTRATOR ?? "",
    architect: import.meta.env.VITE_STRIPE_PRICE_ARCHITECT ?? "",
  };
}

// ---------------------------------------------------------------------------
// Stripe client (lazy — only initialised if a secret key is available)
// ---------------------------------------------------------------------------

let _stripe: Stripe | null = null;

/**
 * Get the Stripe instance. Intended for server-side usage only
 * (edge function / FastAPI). Returns null if no secret key is set.
 */
export function getStripe(secretKey?: string): Stripe | null {
  const key = secretKey ?? (typeof process !== "undefined" ? process.env.STRIPE_SECRET_KEY : undefined);
  if (!key) return null;
  if (!_stripe) {
    _stripe = new Stripe(key, { apiVersion: "2025-12-18.acacia" });
  }
  return _stripe;
}

// ---------------------------------------------------------------------------
// V1 → V2 customer migration helpers
// ---------------------------------------------------------------------------

export interface V1Customer {
  stripeCustomerId: string;
  email: string;
  v1Tier: "basic" | "premium" | "enterprise";
}

const V1_TO_V2_TIER: Record<V1Customer["v1Tier"], SubscriptionTier> = {
  basic: "listener",
  premium: "orchestrator",
  enterprise: "architect",
};

/**
 * Map a V1 tier string to the corresponding V2 tier.
 * Preserves the customer's Stripe customer_id — no new Customer object needed.
 */
export function migrateV1Tier(v1Tier: V1Customer["v1Tier"]): SubscriptionTier {
  return V1_TO_V2_TIER[v1Tier] ?? "listener";
}

// ---------------------------------------------------------------------------
// Checkout session creation (Tauri calls this, opens browser)
// ---------------------------------------------------------------------------

export interface CreateCheckoutParams {
  customerId?: string; // Existing Stripe customer_id (V1 migration)
  email?: string;
  tier: SubscriptionTier;
  successUrl: string;
  cancelUrl: string;
}

/**
 * Create a Stripe Checkout Session for the given tier.
 * Returns the session URL to open in the user's browser.
 *
 * TODO: Wire this into a Tauri command or edge function endpoint.
 */
export async function createCheckoutSession(
  stripe: Stripe,
  params: CreateCheckoutParams,
): Promise<string | null> {
  const priceIds = getPriceIds();
  const priceId = priceIds[params.tier];
  if (!priceId) return null;

  const sessionParams: Stripe.Checkout.SessionCreateParams = {
    mode: "subscription",
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: params.successUrl,
    cancel_url: params.cancelUrl,
  };

  // Reuse V1 customer ID if provided — prevents duplicate Stripe customers
  if (params.customerId) {
    sessionParams.customer = params.customerId;
  } else if (params.email) {
    sessionParams.customer_email = params.email;
  }

  const session = await stripe.checkout.sessions.create(sessionParams);
  return session.url;
}

// ---------------------------------------------------------------------------
// Webhook handler (portable — wire into your HTTP server of choice)
// ---------------------------------------------------------------------------

export interface WebhookResult {
  event: string;
  customerId: string | null;
  tier: SubscriptionTier;
}

/**
 * Process a Stripe webhook event. Returns the resolved tier for the customer.
 *
 * Usage (in an edge function or FastAPI route):
 * ```
 * const result = await handleWebhookEvent(stripe, rawBody, sig, webhookSecret);
 * // Then persist result.tier to your user store / Redis
 * ```
 *
 * TODO: Persist tier to shared store (Redis / Supabase) so the Python
 *       cognitive-engine can check it per voice turn.
 * TODO: Handle `customer.subscription.deleted` for downgrades.
 * TODO: Handle `invoice.payment_failed` for grace period logic.
 */
export async function handleWebhookEvent(
  stripe: Stripe,
  rawBody: string | Buffer,
  signature: string,
  webhookSecret: string,
): Promise<WebhookResult | null> {
  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  } catch {
    // Signature verification failed
    return null;
  }

  switch (event.type) {
    case "customer.subscription.created":
    case "customer.subscription.updated": {
      const subscription = event.data.object as Stripe.Subscription;
      const customerId =
        typeof subscription.customer === "string"
          ? subscription.customer
          : subscription.customer.id;
      const tier = resolveTierFromSubscription(subscription);

      // TODO: UPDATE SHARED STORE HERE
      // e.g. redis.set(`user:${customerId}:tier`, tier)
      // or   supabase.from('profiles').update({ tier }).eq('stripe_id', customerId)

      return { event: event.type, customerId, tier };
    }

    case "customer.subscription.deleted": {
      const subscription = event.data.object as Stripe.Subscription;
      const customerId =
        typeof subscription.customer === "string"
          ? subscription.customer
          : subscription.customer.id;

      // TODO: DOWNGRADE TO LISTENER IN SHARED STORE

      return { event: event.type, customerId, tier: "listener" };
    }

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Tier resolution from a live subscription
// ---------------------------------------------------------------------------

/**
 * Given a Stripe Subscription object, determine which V2 tier the user is on
 * by matching the price ID against our configured tier prices.
 */
export function resolveTierFromSubscription(
  subscription: Stripe.Subscription,
): SubscriptionTier {
  const priceIds = getPriceIds();
  const activePriceId = subscription.items?.data?.[0]?.price?.id;

  if (activePriceId === priceIds.architect) return "architect";
  if (activePriceId === priceIds.orchestrator) return "orchestrator";
  return "listener";
}
