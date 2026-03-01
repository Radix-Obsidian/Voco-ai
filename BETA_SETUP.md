# Voco Beta Setup Guide

Get Voco running in under 7 minutes.

## Quick Start (Installer Build — Zero Prerequisites)

If you received the Voco installer (`.msi` / `.dmg`), just double-click and launch.
The app bundles everything it needs — Python, dependencies, and the AI engine start automatically on first launch.

**First launch takes ~60 seconds** (one-time Python setup). Subsequent launches are instant.

## Developer Setup (From Source)

### Prerequisites

| Tool | Install |
|---|---|
| **Node.js 18+** | [nodejs.org](https://nodejs.org) |
| **Rust** | [rustup.rs](https://rustup.rs) |
| **uv** (Python package manager) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (macOS/Linux) or `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` (Windows) |
| **Python 3.12+** | Installed automatically by `uv` on first run |

### Steps

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd "Voco V2"

# 2. Install frontend dependencies
cd services/mcp-gateway && npm install

# 3. Set up cognitive engine API keys
cp services/cognitive-engine/.env.example services/cognitive-engine/.env
# Edit .env and fill in:
#   DEEPGRAM_API_KEY=your_key    (required — speech-to-text)
#   CARTESIA_API_KEY=your_key    (required — text-to-speech)
#   GITHUB_TOKEN=ghp_...         (optional — GitHub tools)
#   TAVILY_API_KEY=tvly-...      (optional — web search)

# 4. Start everything
npm run dev
# This launches: Tauri desktop app + cognitive engine + LiteLLM proxy
```

The app opens automatically. Sign in with your beta credentials.

### API Keys

| Key | Required | Get it from |
|---|---|---|
| `DEEPGRAM_API_KEY` | Yes | [console.deepgram.com](https://console.deepgram.com) — free tier available |
| `CARTESIA_API_KEY` | Yes | [play.cartesia.ai](https://play.cartesia.ai) — free tier available |
| `GITHUB_TOKEN` | No | [github.com/settings/tokens](https://github.com/settings/tokens) — for GitHub tools |
| `TAVILY_API_KEY` | No | [app.tavily.com](https://app.tavily.com) — for web search |

Put these in `services/cognitive-engine/.env` or enter them in **Settings** (Ctrl+,) inside the app.

### Building the Installer

```bash
# Bundle Python runtime + build the installer
cd services/mcp-gateway
npm run build:bundle
```

The installer will be in `services/mcp-gateway/src-tauri/target/release/bundle/`.

## Troubleshooting

**"Failed to start backend services"**
- Check that `uv` is installed: `uv --version`
- Check that port 8001 is free: `netstat -an | grep 8001`
- Start engine manually: `cd services/cognitive-engine && uv run uvicorn src.main:app --port 8001`

**No voice response (STT/TTS silent)**
- Verify `DEEPGRAM_API_KEY` and `CARTESIA_API_KEY` are set in `.env`
- Check the engine logs in the terminal where you ran `npm run dev`

**WebSocket won't connect**
- Default URL: `ws://127.0.0.1:8001/ws/voco-stream`
- If using a remote server, set `VITE_COGNITIVE_ENGINE_WS` in `services/mcp-gateway/.env`
