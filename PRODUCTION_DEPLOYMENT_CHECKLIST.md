# Voco V2 Production Deployment Checklist

Complete guide for bundling and deploying Voco as a desktop app.

## 🔑 Required API Keys & Configuration

### 1. Core Services

#### Supabase (Auth & Database)
```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your_anon_key
```
**Location:** `services/mcp-gateway/.env`

#### Deepgram (STT)
```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
```
**Location:** `services/cognitive-engine/.env`

#### Cartesia (TTS)
```bash
CARTESIA_API_KEY=your_cartesia_api_key
TTS_VOICE=sonic-english
```
**Location:** `services/cognitive-engine/.env`

#### LiteLLM Gateway
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key
LITELLM_GATEWAY_URL=http://localhost:4000/v1
LITELLM_SESSION_TOKEN=your_session_token
```
**Location:** `services/cognitive-engine/.env`

### 2. Enterprise Features

#### GitHub Integration
```bash
GITHUB_TOKEN=your_github_personal_access_token
```
**Location:** Both `.env` files

#### Google Gemini
```bash
GOOGLE_API_KEY=your_google_api_key
```
**Location:** Both `.env` files

#### Stripe Billing
```bash
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PRO_PRICE_ID=your_pro_price_id
STRIPE_METER_PRICE_ID=your_meter_price_id
STRIPE_METER_ID=your_meter_id
STRIPE_METER_EVENT_NAME=heavy_voice_turn
```
**Location:** `services/cognitive-engine/.env`

## 🚀 Production Build

### 1. Install Dependencies
```bash
# Frontend
cd services/mcp-gateway
npm install

# Backend
cd ../cognitive-engine
uv sync
```

### 2. Configure Environment
```bash
# Copy and fill both .env files
cp services/mcp-gateway/.env.example services/mcp-gateway/.env
cp services/cognitive-engine/.env.example services/cognitive-engine/.env
```

### 3. Build Desktop App
```bash
cd services/mcp-gateway

# Build frontend
npm run build

# Package desktop app
npm run tauri build
```

Output: `src-tauri/target/release/bundle/`
- Windows: `Voco_2.0.0_x64_en-US.msi` (4.9 MB)
- Windows: `Voco_2.0.0_x64-setup.exe` (3.2 MB)

## 🔒 Security Checklist

### API Keys
- [x] All keys stored in Tauri secure storage
- [x] No keys in version control
- [x] Keys rotated for production

### Authentication
- [x] Supabase RLS policies enabled
- [x] JWT validation in WebSocket
- [x] Session token rotation

### Filesystem Access
- [x] Zero-trust sandbox
- [x] Path validation
- [x] Symlink protection

### Command Execution
- [x] HITL approval flow
- [x] Risk assessment
- [x] Audit logging

## 📊 Usage & Billing

### Free Tier
- 50 voice turns
- Local file search
- Basic coding assistant

### Pro Tier ($19/mo + $0.02/turn)
- Unlimited voice commands
- All LangGraph tools
- GitHub automation
- Priority response

## 🌐 Distribution

### Primary: AWS S3 + CloudFront
```bash
# Upload installers
aws s3 cp src-tauri/target/release/bundle/ s3://voco-releases/v2.0.0/ --recursive

# Generate signed URLs
aws cloudfront sign \
  --url https://d1234.cloudfront.net/v2.0.0/Voco_2.0.0_x64_en-US.msi \
  --key-pair-id APKA... \
  --private-key file://pk-*.pem \
  --date-less-than 2026-12-31
```

### Secondary: GitHub Releases
```bash
# Create release
git tag v2.0.0
git push origin v2.0.0

# Upload assets
gh release create v2.0.0 \
  src-tauri/target/release/bundle/msi/Voco_2.0.0_x64_en-US.msi \
  src-tauri/target/release/bundle/nsis/Voco_2.0.0_x64-setup.exe
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
