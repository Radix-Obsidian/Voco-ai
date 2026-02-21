# Voco V2: Product Requirements Document (PRD)

## 1. Product Vision & Strategy
Voco V1 successfully validated the "Logic Ledger" concept—proving developers want version-controlled architectural intent rather than massive, stale `SYSTEM_PROMPT.md` files. However, V1 is constrained by browser limitations (Chrome `SpeechRecognition`) and a cloud-hosted MCP server that lacks local execution capabilities. 

Voco V2 transitions the product from a web-based prompt generator to an **always-on, voice-native desktop orchestrator**. Utilizing a First Principles approach, V2 abandons the browser for a Tauri System Tray app, enabling sub-300ms voice interactions (barge-in enabled) and secure, local MCP terminal execution.

## 2. Target Audience
* **Primary:** Expert developers (Cursor, Windsurf, Claude Code users) who experience "Context Drift" when AI agents forget architectural decisions.
* **The Wedge:** Voice-Native Pull Request Reviews and instant architectural pivoting.

## 3. Core Requirements (V1 Parity + V2 Upgrades)
### 3.1. V1 Feature Parity (Must Retain)
* **Auth & Billing:** Supabase Auth, Stripe integration (`usage_tracking`, `early_bird_subscriptions`).
* **The Logic Ledger:** Visualizing the DAG (Directed Acyclic Graph) of decisions (`voco_ledger` table).
* **Project Context:** The ability to ingest GitHub repositories or local folders to detect stacks (`ProjectMap`).
* **BYOK (Bring Your Own Key):** Retain the Anthropic/OpenAI/Google key injection logic.

### 3.2. V2 Core Upgrades (0-to-1 Features)
* **Desktop-Native (Tauri):** Move out of the browser. Operate as a global hotkey-activated System Tray app.
* **Local MCP Gateway:** Move the MCP server from a Supabase Edge Function to the local Tauri client to allow local file system reads/writes and terminal commands.
* **Streaming Audio Engine:** Replace browser `SpeechRecognition` with a Python-hosted Silero VAD + Whisper pipeline for <300ms latency and "barge-in" support.
* **Stateful Graph Reasoning:** Replace the sequential Edge Function generation (`generate-prp`) with a persistent Python LangGraph state machine.

## 4. Success Metrics
* **Latency:** Time-to-First-Token (TTFT) < 150ms; Voice-to-voice response < 300ms.
* **Interruptibility:** 100% success rate on human barge-in halting TTS playback.
* **Local Execution:** AI can successfully run `bun test` or `git diff` locally via the Tauri MCP gateway.