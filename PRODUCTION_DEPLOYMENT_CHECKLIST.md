# Voco V2 Production Deployment Checklist

Complete guide for bundling and deploying Voco as a desktop app like Claude Code.

---

## 🔑 Required API Keys & Tokens

### **Critical (App Won't Function Without These)**

#### 1. Supabase (Authentication & Database)
```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```
**Where to get:** https://supabase.com/dashboard → Project Settings → API
**Used for:** User authentication (login/signup), workspaces, projects, feedback, usage tracking
**Location:** `services/mcp-gateway/.env`

---

#### 2. Deepgram (Speech-to-Text)
```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
```
**Where to get:** https://console.deepgram.com/ → API Keys
**Used for:** Voice transcription (converts user speech to text)
**Location:** `services/cognitive-engine/.env`

---

#### 3. Cartesia (Text-to-Speech)
```bash
CARTESIA_API_KEY=your_cartesia_api_key
TTS_VOICE=sonic-english  # Default voice ID
```
**Where to get:** https://cartesia.ai/ → API Keys
**Used for:** AI voice responses (converts AI text to speech)
**Location:** `services/cognitive-engine/.env`

---

#### 4. LiteLLM Gateway (Claude API Proxy)
```bash
LITELLM_GATEWAY_URL=http://YOUR_DO_IP:4000/v1
LITELLM_SESSION_TOKEN=your_virtual_key
```
**Where to get:** Self-hosted LiteLLM proxy (see setup below)
**Used for:** Claude 3.5 Sonnet API calls for reasoning
**Location:** `services/cognitive-engine/.env`

**LiteLLM Setup:**
```bash
# Install LiteLLM on DigitalOcean/Railway
pip install litellm[proxy]
litellm --model claude-3-5-sonnet-20241022 --api_base https://api.anthropic.com
```
You'll need an **Anthropic API key** to configure LiteLLM.

---

### **Optional (Enhanced Features)**

#### 5. GitHub Integration (Optional)
```bash
GITHUB_TOKEN=ghp_your_github_personal_access_token
```
**Where to get:** https://github.com/settings/tokens → Generate new token (classic)
**Permissions needed:** `repo`, `read:org`
**Used for:** GitHub issue/PR tools, repository context
**Location:** `services/cognitive-engine/.env`

---

#### 6. Tavily Web Search (Optional)
```bash
TAVILY_API_KEY=tvly-your_tavily_api_key
```
**Where to get:** https://tavily.com/ → API Keys
**Used for:** Web search tool (fallback when local search insufficient)
**Location:** `services/cognitive-engine/.env`

---

#### 7. Google Gemini (Synapse MCP - Optional)
```bash
GOOGLE_API_KEY=your_google_api_key
```
**Where to get:** https://aistudio.google.com/app/apikey
**Used for:** YouTube video analysis via Synapse MCP server
**Location:** Stored in Tauri secure config (via Settings UI)

---

#### 8. Stripe (Billing - Optional for Beta)
```bash
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
VITE_STRIPE_PRICE_LISTENER=price_xxx  # Free tier price ID
VITE_STRIPE_PRICE_ORCHESTRATOR=price_xxx  # Pro tier price ID
VITE_STRIPE_PRICE_ARCHITECT=price_xxx  # Enterprise tier price ID
```
**Where to get:** https://dashboard.stripe.com/apikeys
**Used for:** Subscription management (can defer until post-beta)
**Location:** `services/mcp-gateway/.env` (frontend), edge function (webhooks)

---

## 📦 Pre-Build Steps

### 1. Install Dependencies
```bash
# Tauri Desktop App
cd services/mcp-gateway
bun install

# Python Cognitive Engine
cd ../cognitive-engine
uv sync
```

### 2. Configure Environment Files
```bash
# Desktop app
cp services/mcp-gateway/.env.example services/mcp-gateway/.env
# Edit .env with Supabase keys

# Cognitive engine
cp services/cognitive-engine/.env.example services/cognitive-engine/.env
# Edit .env with Deepgram, Cartesia, LiteLLM, GitHub, Tavily
```

### 3. Build Synapse MCP Sidecar (if using)
```bash
cd services/synapse-mcp
# Windows
.\build.ps1
# macOS/Linux
chmod +x build.sh && ./build.sh
```

---

## 🚀 Building the Desktop App

### Development Build
```bash
cd services/mcp-gateway
npm run dev  # Starts Tauri + cognitive-engine concurrently
```

### Production Build
```bash
cd services/mcp-gateway
bun run build  # Build frontend
npx tauri build  # Build desktop app

# Output locations:
# Windows: src-tauri/target/release/bundle/msi/voco_0.0.0_x64_en-US.msi
# macOS: src-tauri/target/release/bundle/dmg/voco_0.0.0_x64.dmg
# Linux: src-tauri/target/release/bundle/deb/voco_0.0.0_amd64.deb
```

---

## 🎯 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Desktop Machine                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Voco Desktop App (Tauri v2 + Rust + React)           │ │
│  │  • Microphone capture (16kHz PCM)                      │ │
│  │  • Auth UI (Supabase)                                  │ │
│  │  • Settings, Billing, Feedback                         │ │
│  │  • Zero-trust MCP execution (local file ops)           │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │ WebSocket                        │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Python Cognitive Engine (FastAPI + LangGraph)        │ │
│  │  • Silero VAD (barge-in detection)                     │ │
│  │  • Deepgram STT (voice → text)                         │ │
│  │  • Claude Sonnet (reasoning)                           │ │
│  │  • Cartesia TTS (text → voice)                         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Services (Required)                 │
│  • Supabase (auth, DB)                                      │
│  • Deepgram (STT)                                           │
│  • Cartesia (TTS)                                           │
│  • LiteLLM → Anthropic Claude                               │
└─────────────────────────────────────────────────────────────┘
```

**Key Point:** The Python cognitive-engine runs **locally** on the user's machine (bundled with Tauri or as a separate process). It's NOT deployed to Railway in production desktop mode.

---

## 🔒 Security Checklist

- [ ] All API keys stored in Tauri secure config (not hardcoded)
- [ ] `.env` files added to `.gitignore`
- [ ] Supabase RLS policies enabled for `voco_projects`, `voco_ledger`
- [ ] LiteLLM virtual keys rotated per deployment
- [ ] Stripe webhook signing secret configured
- [ ] No `console.log` with sensitive data in production build

---

## 📋 First-Launch User Experience

1. User downloads `.msi` / `.dmg` / `.deb` installer from marketing site
2. Installer runs, places Voco in Applications
3. User launches Voco → sees **AuthModal** (no landing page)
4. User signs in via email/password or Google OAuth
5. If no API keys configured → **SettingsModal** auto-opens
6. User pastes Deepgram, Cartesia, LiteLLM keys (copied from docs)
7. Keys saved to Tauri secure config (`config.json`)
8. Cognitive engine auto-starts, WebSocket connects
9. User sees **OnboardingTour** (4 steps)
10. Ready to voice orchestrate

---

## 🧪 Testing Before Release

```bash
# 1. Test auth flow
- [ ] Sign up with email/password
- [ ] Sign in with Google OAuth
- [ ] Sign out and back in

# 2. Test voice pipeline
- [ ] Speak → see transcript
- [ ] Get AI voice response
- [ ] Interrupt mid-response (barge-in)

# 3. Test MCP tools
- [ ] File search (ripgrep)
- [ ] File proposal → approval → write
- [ ] Terminal command → approval → execute

# 4. Test billing (if enabled)
- [ ] Open PricingModal
- [ ] Mock Stripe checkout
- [ ] Verify tier in Header

# 5. Test cross-platform
- [ ] Windows 11 build
- [ ] macOS 13+ build
- [ ] Ubuntu 22.04 build
```

---

## 📊 Minimum Viable Production Config

**Critical keys only (skip GitHub, Tavily, Stripe for beta):**

```bash
# Desktop app (.env)
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=eyJxxx

# Cognitive engine (.env)
DEEPGRAM_API_KEY=xxx
CARTESIA_API_KEY=xxx
TTS_VOICE=sonic-english
LITELLM_GATEWAY_URL=http://YOUR_IP:4000/v1
LITELLM_SESSION_TOKEN=xxx
```

**Total cost estimate:**
- Supabase: Free tier (up to 50k auth users)
- Deepgram: Pay-as-you-go (~$0.0125/min)
- Cartesia: Pay-as-you-go (~$0.06/min)
- LiteLLM/Claude: Pay-as-you-go (~$3/1M input tokens)

**Estimated cost per active user/month:** $5-15 (depending on usage)

---

## 🎁 Bonus: Auto-Update Setup

Add to `tauri.conf.json`:
```json
{
  "updater": {
    "active": true,
    "endpoints": ["https://releases.voco.ai/{{target}}/{{current_version}}"],
    "dialog": true,
    "pubkey": "YOUR_PUBLIC_KEY"
  }
}
```

Generate signing key:
```bash
npx tauri signer generate -w ~/.tauri/voco.key
```

---

## 📞 Support Resources

- **Tauri Docs:** https://tauri.app/v2/
- **Supabase Docs:** https://supabase.com/docs
- **Deepgram Docs:** https://developers.deepgram.com/
- **Cartesia Docs:** https://docs.cartesia.ai/
- **LiteLLM Docs:** https://docs.litellm.ai/

---

**Last Updated:** Feb 22, 2026
**Status:** ✅ Ready for production bundling
