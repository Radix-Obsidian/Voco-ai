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

## 🌐 Distribution — CrabNebula Cloud (Primary)

Voco uses **CrabNebula Cloud** (official Tauri partner) for enterprise-grade
distribution, auto-updates, release channels, and download metrics.

### Release Workflow
```bash
# Tag a release — GitHub Actions handles the rest
git tag v2.0.0
git push origin v2.0.0
```

The CI pipeline (`.github/workflows/release.yml`) will:
1. Build for Windows, macOS, and Linux in parallel
2. Sign all artifacts with the Tauri signing key
3. Upload everything to CrabNebula Cloud CDN

### CrabNebula Dashboard
- **Org:** `radix-obsidian`
- **App:** `voco`
- **CDN endpoint:** `https://cdn.crabnebula.app/update/radix-obsidian/voco/{{target}}-{{arch}}/{{current_version}}`
- **Console:** https://crabnebula.cloud

### Release Channels (via Keygen.sh license gating)
| Tier | Channel | Update Delay |
|------|---------|-------------|
| Architect ($149/mo) | nightly | Immediate |
| Orchestrator ($39/mo) | beta | 48h after nightly |
| Listener (Free) | stable | 1 week after beta |

### Required GitHub Secrets
| Secret | Description |
|--------|-------------|
| `TAURI_SIGNING_PRIVATE_KEY` | Contents of `~/.tauri/voco.key` |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Password used during key generation |
| `CN_API_KEY` | CrabNebula Cloud API key |

### Fallback: GitHub Releases
Only for emergency distribution if CrabNebula is unavailable:
```bash
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


## 🔐 Auto-Update Infrastructure (Required)

Auto-updates are wired into the Tauri build via `tauri-plugin-updater` + CrabNebula Cloud.

### Signing Key
```bash
cd services/mcp-gateway
npx tauri signer generate -w ~/.tauri/voco.key
```
Store the private key password in your vault. The public key goes into `tauri.conf.json`.

### Config (`tauri.conf.json`)
```json
{
  "bundle": {
    "createUpdaterArtifacts": true
  },
  "plugins": {
    "updater": {
      "endpoints": [
        "https://cdn.crabnebula.app/update/radix-obsidian/voco/{{target}}-{{arch}}/{{current_version}}"
      ],
      "pubkey": "YOUR_PUBLIC_KEY"
    }
  }
}
```

### Rust Plugins (`lib.rs`)
Both `tauri-plugin-updater` and `tauri-plugin-dialog` are initialized in the Tauri builder.

### Frontend
`useAppUpdater()` hook in `AppPage.tsx` checks for updates on launch (production only) and prompts the user via native dialog.

### License Gating (Keygen.sh)
- **Account:** `298d9fbb-0ff7-4040-bafc-9d4359f61ab0`
- `validate_license` Rust command calls Keygen API to resolve tier
- `licensing.ts` maps tier → update channel (nightly/beta/stable)
- License key stored in Tauri secure config alongside API keys

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
