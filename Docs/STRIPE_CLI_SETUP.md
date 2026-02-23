# Voco Stripe Billing Setup — CLI Workflow

Complete guide for setting up Voco's three-tier subscription model using the Stripe CLI.

---

## 📦 Voco Pricing Tiers

| Tier | Name | Price | Stripe Price ID Env Var |
|---|---|---|---|
| Free | Listener | $0/mo | `VITE_STRIPE_PRICE_LISTENER` |
| Pro | Orchestrator | $29/mo | `VITE_STRIPE_PRICE_ORCHESTRATOR` |
| Enterprise | Architect | $99/mo | `VITE_STRIPE_PRICE_ARCHITECT` |

---

## 1. Install Stripe CLI

```powershell
# Windows (Scoop)
scoop install stripe

# Or download directly:
# https://github.com/stripe/stripe-cli/releases/latest
```

## 2. Authenticate

```bash
stripe login
# Opens browser → log in to Stripe dashboard → authorize CLI
```

---

## 3. Create Products & Prices

### Free Tier (Listener)
```bash
# Create product
stripe products create \
  --name="Voco Listener" \
  --description="Free tier: 10 voice turns/day, local tools only"

# Create free price (using $0/month recurring)
stripe prices create \
  --product=<PRODUCT_ID_FROM_ABOVE> \
  --unit-amount=0 \
  --currency=usd \
  --recurring[interval]=month \
  --nickname="Listener Free"
# → Copy the price ID (price_xxx) → VITE_STRIPE_PRICE_LISTENER
```

### Pro Tier (Orchestrator)
```bash
stripe products create \
  --name="Voco Orchestrator" \
  --description="Pro tier: Unlimited turns, web search, GitHub tools"

stripe prices create \
  --product=<PRODUCT_ID> \
  --unit-amount=2900 \
  --currency=usd \
  --recurring[interval]=month \
  --nickname="Orchestrator Pro"
# → Copy price ID → VITE_STRIPE_PRICE_ORCHESTRATOR
```

### Enterprise Tier (Architect)
```bash
stripe products create \
  --name="Voco Architect" \
  --description="Enterprise tier: All tools, team workspaces, priority support"

stripe prices create \
  --product=<PRODUCT_ID> \
  --unit-amount=9900 \
  --currency=usd \
  --recurring[interval]=month \
  --nickname="Architect Enterprise"
# → Copy price ID → VITE_STRIPE_PRICE_ARCHITECT
```

---

## 4. Get Your Secret Key

```bash
# List keys (shows last 4 chars only)
stripe api-keys list

# Your secret key is in the Stripe dashboard:
# https://dashboard.stripe.com/apikeys
# → Copy sk_live_xxx (production) or sk_test_xxx (testing)
```

---

## 5. Update Environment Files

### `services/cognitive-engine/.env`
```bash
STRIPE_SECRET_KEY=sk_live_xxx
```

### `services/mcp-gateway/.env`
```bash
VITE_STRIPE_PRICE_LISTENER=price_xxx
VITE_STRIPE_PRICE_ORCHESTRATOR=price_xxx
VITE_STRIPE_PRICE_ARCHITECT=price_xxx
```

---

## 6. Set Up Webhook (for subscription events)

```bash
# Start local webhook listener (dev)
stripe listen --forward-to localhost:8001/api/billing/webhook

# The CLI will output a webhook signing secret (whsec_xxx)
# → Add to cognitive-engine/.env:
# STRIPE_WEBHOOK_SECRET=whsec_xxx
```

---

## 7. Test the Billing Flow (Dev)

```bash
# Trigger a test checkout session
stripe trigger checkout.session.completed

# Trigger subscription created
stripe trigger customer.subscription.created

# List recent events
stripe events list --limit=10
```

---

## 8. Useful CLI Commands

```bash
# List all products
stripe products list

# List all prices
stripe prices list

# Update a price nickname
stripe prices update price_xxx --nickname="New Name"

# Archive a product (can't delete if it has subscriptions)
stripe products update prod_xxx --active=false

# Get a customer's subscriptions
stripe subscriptions list --customer=cus_xxx

# Cancel a subscription
stripe subscriptions cancel sub_xxx
```

---

## Notes

- Use `sk_test_xxx` keys during development (test mode)
- Switch to `sk_live_xxx` only for production deployment
- Stripe test cards: `4242 4242 4242 4242` (any future date, any CVC)
- Webhook signing secret changes per `stripe listen` session in dev

---

**Last Updated:** Feb 2026
