# Voco V2.0 — Release Notes

**Your V1 subscription migrates automatically. No action required.**

---

## Why V2?

Voco V1 was a voice wrapper around an LLM. V2 is a stateful operating system for your codebase. Every component has been rebuilt from first principles to eliminate the latency, fragility, and trust issues that limited V1.

## What Changed

### Voice Pipeline — Rebuilt from Scratch

| | V1 | V2 |
|---|---|---|
| **Speech Recognition** | Browser SpeechRecognition API | Deepgram streaming over WebSocket |
| **Voice Activity Detection** | Timer-based silence threshold | Silero neural VAD (sub-20ms) |
| **Barge-in** | Not supported | Real-time interrupt — speak over Voco mid-sentence |
| **Text-to-Speech** | Browser speechSynthesis | Cartesia streaming audio with chunk playback |
| **Round-trip Latency** | 800ms–2s | Sub-300ms |

### AI Engine — From Stateless to Stateful

V1 sent your prompt to an LLM and returned the response. V2 runs a **LangGraph state machine** that:

- **Routes by domain** — mentions "database" and the orchestrator focuses on schema design, not CSS.
- **Proposes before executing** — file edits and terminal commands appear for your approval before anything touches disk.
- **Interrupts on danger** — `git push --force`, database mutations, and destructive commands trigger a spoken confirmation loop.
- **Connects to external tools** — GitHub, Linear, Slack, Postgres, and any MCP-compatible server via the Universal Gateway.

### Security — Zero-Trust by Default

V1 ran MCP logic in cloud edge functions with broad filesystem access. V2 enforces a hard boundary:

- The AI engine (Python, Railway) has **zero direct access** to your local machine.
- Every file read, search, and command execution flows through the **Tauri Rust gateway** with scope validation.
- High-risk operations require your spoken "Yes" before execution. No exceptions.

### Frontend — The Visual Ledger

The new desktop app (Tauri) replaces the browser-only V1 interface:

- **Visual Ledger** — see exactly which graph nodes are executing in real time.
- **Intent Proposals** — review file edits as diffs and terminal commands as cards before they run.
- **BYOK Settings** — bring your own API keys. They stay on your machine, pushed to the engine over WebSocket.

## Your V1 Subscription

Your existing Stripe customer ID carries over. Tier mapping:

| V1 Tier | V2 Tier | What You Get |
|---|---|---|
| Basic | **The Listener** (Free) | 500 voice turns/month |
| Premium | **The Orchestrator** ($39/mo) | Unlimited voice + Intent Ledger |
| Enterprise | **The Architect** ($149/mo) | Priority GPU + Custom Skills |

No payment changes. No new accounts. Your billing continues uninterrupted.

## Getting Started

1. Download `Voco.app` from the releases page.
2. Launch it — your V1 credentials sync automatically.
3. Press `Ctrl+Shift+V` (Windows) or `Cmd+Shift+V` (Mac) and speak.

For the full walkthrough, see [QUICKSTART.md](./QUICKSTART.md).

## Known Limitations

- **MCP servers require local tooling** — `npx` must be available for servers like `@anthropic/fetch` and `@puppeteer/mcp`.
- **Tavily web search** requires a `TAVILY_API_KEY` in your environment or BYOK settings.
- **Custom Skills** (Architect tier) are not yet exposed in the UI — configurable via `voco-mcp.json` only.

## What's Next

- Speculative pre-fetch during voice pauses
- WebMCP integration for in-browser tool discovery
- Seat-based billing for team workspaces
- Usage-based TTS overage metering

---

*Sub-300ms speed. Zero-trust safety. Intent-driven code.*
