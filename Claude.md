
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

Voco V2 is a sub-300ms **voice-native coding orchestrator** — not a chatbot. It streams raw PCM audio from a Tauri desktop app to a Python LangGraph backend, transcribes it, runs it through Claude, and synthesizes a spoken response. All local file operations (search, write, execute) happen in Rust via a HITL approval loop — the Python engine never touches the filesystem directly.

### Milestone Status
- **Milestone 5 (COMPLETE):** Audio pipeline (Deepgram STT, Cartesia TTS) and LangGraph brain active.
- **Milestone 6 (ACTIVE):** Search Vertical Slice — Voco is a **Local-First Orchestrator**.

---

## Monorepo Structure & Boundaries (Strict)

Two entirely separate runtimes. **Never mix their dependencies.**

```
services/
├── mcp-gateway/        # Tauri v2 (Rust) + React + Vite + Shadcn UI + Bun + TypeScript
└── cognitive-engine/   # Python 3.12+ + FastAPI + LangGraph + Silero-VAD + uv
```

- In `services/mcp-gateway/`: use `bun install` / `bun run` only.
- In `services/cognitive-engine/`: use `uv add` / `uv run` only.

---

## Dev Commands

### Start Everything (Recommended)
```bash
cd services/mcp-gateway
npm run dev
# Runs: Tauri desktop app (frontend) + cognitive-engine uvicorn on :8001 concurrently
```

### Frontend Only
```bash
cd services/mcp-gateway
bun run dev:frontend   # Vite dev server (browser preview only, no Tauri)
npx tauri dev          # Full Tauri desktop build
```

### Cognitive Engine Only
```bash
cd services/cognitive-engine
uv run uvicorn src.main:app --host 0.0.0.0 --port 8001
```

### Tests (Python)
```bash
cd services/cognitive-engine
uv run pytest tests/ -v
# Run a single test file:
uv run pytest tests/test_bargein_routing.py -v
```

### Lint (Frontend)
```bash
cd services/mcp-gateway
bun run lint
```

### Build (Frontend)
```bash
cd services/mcp-gateway
bun run build
```

---

## Environment Variables

Copy `.env.example` files in each service directory. Keys consumed at runtime via `update_env` WebSocket message (sent by frontend) or from the `.env` file:

| Key | Service | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | cognitive-engine | Claude claude-sonnet-4-5-20250929 |
| `DEEPGRAM_API_KEY` | cognitive-engine | STT transcription |
| `CARTESIA_API_KEY` | cognitive-engine | TTS synthesis |
| `GITHUB_TOKEN` | cognitive-engine | GitHub issue/PR tools |
| `TAVILY_API_KEY` | cognitive-engine | Web search |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` | mcp-gateway | Auth |

---

## Architecture: Full Voice Pipeline

```
[Tauri mic] → raw 16kHz PCM → WebSocket ws://localhost:8001/ws/voco-stream
    → Silero VAD (detects turn-end after 1.28s silence)
    → Deepgram STT → transcript
    → LangGraph StateGraph (Claude claude-sonnet-4-5-20250929 + tools)
    → If tool call → JSON-RPC 2.0 → Tauri invoke() → Rust executes locally
    → Cartesia TTS → PCM audio streamed back to Tauri
    → Native Rust audio playback (bypasses webview)
```

---

## Python Cognitive Engine (`services/cognitive-engine/src/`)

### Key Files
| File | Role |
|---|---|
| `main.py` | FastAPI app; WebSocket handler; orchestrates the full pipeline per turn |
| `graph/state.py` | `VocoState` TypedDict — all LangGraph state fields |
| `graph/router.py` | `StateGraph` definition; conditional routing after orchestrator |
| `graph/nodes.py` | All node functions: `context_router_node`, `orchestrator_node`, `mcp_gateway_node`, `proposal_review_node`, `command_review_node` |
| `graph/tools.py` | LangChain `@tool` definitions (search, propose_command, GitHub, file proposals) |
| `graph/mcp_registry.py` | Dynamic MCP server discovery from `voco-mcp.json`; wraps external tools as `StructuredTool` |
| `graph/background_worker.py` | `BackgroundJobQueue` — Instant ACK + async task pattern |
| `audio/stt.py` | Deepgram transcription |
| `audio/tts.py` | Cartesia streaming synthesis |
| `audio/vad.py` | Silero VAD chunked streaming |

### LangGraph Flow
```
START → context_router_node → orchestrator_node
    ↓ (conditional)
    ├─ barge_in_detected → orchestrator_node (loop)
    ├─ pending_proposals → proposal_review_node → orchestrator_node
    ├─ pending_commands  → command_review_node  → orchestrator_node
    ├─ pending_mcp_action → mcp_gateway_node → END
    └─ (else) → END
```
Both `proposal_review_node` and `command_review_node` use `interrupt_before` — the graph pauses and `main.py` collects user decisions over the WebSocket before resuming with `graph.ainvoke(Command(resume=...))`.

### Async Tool Pattern (Milestone 11: Instant ACK)
When Claude calls a tool, the graph immediately returns an ACK `ToolMessage` (satisfying Anthropic's strict tool_call→tool_result requirement), then fires the real Tauri RPC as an `asyncio.Task`. On completion, `graph.aupdate_state()` injects a `SystemMessage` into the checkpoint; Claude sees the result on the user's next turn.

### VocoState Fields
- `messages`: conversation history (LangGraph `add_messages` reducer)
- `barge_in_detected`: set by VAD when user interrupts TTS
- `pending_mcp_action`: tool call awaiting Tauri dispatch
- `pending_proposals` / `proposal_decisions`: file creation/edit HITL flow
- `pending_commands` / `command_decisions`: terminal command HITL flow
- `focused_context`: domain hint injected by `context_router_node`
- `active_project_path`: current project for local searches

---

## Tauri Gateway (`services/mcp-gateway/`)

### Rust Commands (`src-tauri/src/commands.rs`)
| Command | Purpose |
|---|---|
| `search_project` | Run bundled `rg` sidecar against absolute project path |
| `write_file` | Write file content; validates path stays within `project_root` |
| `execute_command` | Run shell command in `project_path` (`cmd /C` on Windows, `sh -c` on Unix) |

All commands enforce canonical path checks — no path traversal possible.

### TypeScript Frontend
| File | Role |
|---|---|
| `src/hooks/use-voco-socket.ts` | WebSocket connection, VAD mic streaming, message routing, Tauri `invoke()` dispatch |
| `src/pages/AppPage.tsx` | Main app shell |
| `src/components/VisualLedger.tsx` | Real-time LangGraph node status display |
| `src/components/ReviewDeck.tsx` | File proposal HITL UI |
| `src/components/CommandApproval.tsx` | Terminal command HITL UI |
| `src/components/GhostTerminal.tsx` | Terminal output display |

The `use-voco-socket.ts` hook routes incoming JSON messages by `type`:
- `mcp_request` (method `local/*`) → `tauriInvoke()` → result sent back as `mcp_result`
- `proposal` → updates `proposals` state → `ReviewDeck` renders
- `command_proposal` → updates `commandProposals` state → `CommandApproval` renders
- `ledger_update` / `ledger_clear` → `VisualLedger` state
- `background_job_start` / `async_job_update` → background job tracking

---

## JSON-RPC 2.0 Contract (Python ↔ Tauri)

All cross-boundary calls use this format over the WebSocket:

```json
// Request: Python → Tauri
{ "jsonrpc": "2.0", "method": "local/search_project", "params": { "pattern": "...", "project_path": "/abs/path" }, "id": "unique-id" }

// Success: Tauri → Python
{ "jsonrpc": "2.0", "result": "<rg output>", "id": "unique-id" }

// Error: Tauri → Python
{ "jsonrpc": "2.0", "error": { "code": -32000, "message": "Security Violation: ..." }, "id": "unique-id" }
```

Method namespacing: `local/` for Rust commands, `web/` for WebMCP calls.

---

## External MCP Servers (`voco-mcp.json`)

Configured servers (github, git, fetch, puppeteer, filesystem, postgres, linear, slack) are connected at startup via stdio. Their tools are dynamically discovered and registered into `get_all_tools()` alongside the built-in tools. Fill in API keys before enabling each server.

---

## Security Rules (Non-Negotiable)

1. **Python has ZERO filesystem access.** All file reads/writes/executes go via JSON-RPC to Tauri.
2. **All terminal commands** must use `propose_command` → user approves in UI → Rust executes.
3. **All file changes** must use `propose_file_creation` / `propose_file_edit` → user approves in `ReviewDeck`.
4. **No browser voice.** Audio capture = raw PCM over WebSocket to Python. Never `SpeechRecognition` API.
5. **No cloud MCP.** MCP execution lives in Tauri Rust only.
6. **No sequential LLM loops.** All AI reasoning = LangGraph `StateGraph`.

---

## Docs Hierarchy

Read these before any architectural change:
1. `Docs/PRD.md` — Product requirements
2. `Docs/TDD.md` — LangGraph & streaming audio architecture
3. `Docs/SDD.md` — Zero-trust MCP & HITL sandbox design
