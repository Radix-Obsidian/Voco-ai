# Voco V2: Production Deployment Guide

**Last updated:** Feb 27, 2026  
**Stack:** Docker Compose + NGINX 1.27 + Let's Encrypt (certbot) + DigitalOcean

---

## Prerequisites

- A VPS (DigitalOcean Droplet, AWS EC2, etc.) with Docker + Docker Compose installed
- A domain pointing to the VPS IP (e.g. `voco-api.yourdomain.com`)
- All required API keys (see `.env.example`)

---

## 1. Server Setup

```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Clone the repo (or copy the cognitive-engine directory)
git clone https://github.com/Radix-Obsidian/Voco-ai.git
cd Voco-ai/services/cognitive-engine
```

## 2. Environment Configuration

```bash
# Copy and fill in the production .env
cp .env.example .env
nano .env
```

**Required variables:**

| Variable | Description |
|----------|-------------|
| `LITELLM_GATEWAY_URL` | LiteLLM proxy endpoint (e.g. `http://YOUR_DO_IP:4000/v1`) |
| `LITELLM_SESSION_TOKEN` | LiteLLM session key (`sk-voco-...`) |
| `LITELLM_MASTER_KEY` | LiteLLM proxy master key |
| `DEEPGRAM_API_KEY` | Deepgram STT API key |
| `CARTESIA_API_KEY` | Cartesia TTS API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service-role key |
| `DOMAIN` | Your domain (e.g. `voco-api.yourdomain.com`) |
| `CERTBOT_EMAIL` | Email for Let's Encrypt notifications |
| `VOCO_WS_TOKEN` | Secret token for WebSocket auth (**required in production**) |

**Optional variables:**

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe billing (leave blank to disable) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook verification |
| `GITHUB_TOKEN` | GitHub integration |
| `TAVILY_API_KEY` | Web search |
| `GOOGLE_API_KEY` | Google services |
| `TTS_VOICE` | Cartesia voice ID (default provided) |

## 3. TLS Certificate (First Time)

The production compose uses NGINX as a TLS-terminating reverse proxy with Let's Encrypt certificates via certbot.

```bash
# Step 1: Obtain the initial certificate
docker compose -f docker-compose.prod.yml run --rm certbot

# Step 2: Start all services
docker compose -f docker-compose.prod.yml up -d
```

Certbot will:
1. Spin up temporarily to request a certificate via the ACME HTTP-01 challenge
2. Store the cert in a Docker volume (`certbot_certs`)
3. NGINX reads the cert from that shared volume

## 4. Start Production Services

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts three containers:

| Container | Role | Ports |
|-----------|------|-------|
| `voco-cognitive-engine` | FastAPI + LangGraph + Audio pipeline | 8001 (internal only) |
| `voco-nginx` | TLS termination + reverse proxy | 80, 443 |
| `voco-certbot` | Certificate management (on-demand) | — |

## 5. NGINX Configuration

The NGINX config at `nginx/nginx.conf` provides:

- **HTTP → HTTPS redirect** on port 80
- **Mozilla Modern TLS** (TLSv1.2 + TLSv1.3, strong cipher suite)
- **HSTS** header (1 year, includeSubDomains)
- **WebSocket proxy** at `/ws/` with 1-hour keepalive timeouts
- **REST API proxy** for `/health`, `/billing/*`, `/sandbox`, `/mcp`
- **ACME challenge** passthrough for certbot renewals

### WebSocket-specific settings

Voice streaming sessions can be long-lived. The NGINX config sets:
```
proxy_read_timeout 3600s;   # 1 hour
proxy_send_timeout 3600s;   # 1 hour
```

These match the `Connection: upgrade` and `Upgrade: websocket` headers required for the WSS bridge.

## 6. Certificate Renewal

Certificates auto-expire after 90 days. Set up a daily cron job:

```bash
crontab -e
```

Add this line:
```cron
0 3 * * * cd /root/cognitive-engine && docker compose -f docker-compose.prod.yml run --rm certbot renew && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

This runs at 3 AM daily. Certbot only renews when the cert is within 30 days of expiry.

## 7. Health Check

```bash
# From outside the server
curl https://voco-api.yourdomain.com/health
# Expected: {"status":"ok"}

# WebSocket test (wscat)
wscat -c "wss://voco-api.yourdomain.com/ws/voco-stream?token=YOUR_VOCO_WS_TOKEN"
```

## 8. Logs & Monitoring

```bash
# View cognitive engine logs
docker logs -f voco-cognitive-engine

# View NGINX access/error logs
docker logs -f voco-nginx

# Log rotation is automatic (10MB max, 3 files retained)
```

Session checkpoint data persists in the `session_data` Docker volume.

## 9. Updating

```bash
cd /root/cognitive-engine

# Pull latest code
git pull

# Rebuild and restart (zero-downtime with --build)
docker compose -f docker-compose.prod.yml up -d --build
```

## 10. Security Checklist

- [ ] `VOCO_WS_TOKEN` is set to a strong random value
- [ ] `SUPABASE_SERVICE_KEY` is never exposed to the frontend
- [ ] `STRIPE_WEBHOOK_SECRET` is configured for webhook verification
- [ ] NGINX HSTS is active (verify with `curl -I https://yourdomain`)
- [ ] Firewall allows only ports 80, 443, and SSH (22)
- [ ] Docker volumes are backed up regularly

---

## Architecture Overview

```
Internet
   │
   ├── :80  ─→ NGINX ─→ 301 redirect to HTTPS
   └── :443 ─→ NGINX (TLS termination)
                  │
                  ├── /health        ─→ cognitive-engine:8001
                  ├── /ws/           ─→ cognitive-engine:8001  (WebSocket upgrade)
                  ├── /billing/*     ─→ cognitive-engine:8001
                  ├── /sandbox       ─→ cognitive-engine:8001
                  └── /mcp           ─→ cognitive-engine:8001  (SSE for IDE)
```

The cognitive engine container is **not exposed** to the public internet — all traffic flows through NGINX.
