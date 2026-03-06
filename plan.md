# Voco V2.5 — Text-First Simplification Plan

## Vision
Remove the bidirectional voice conversation loop (mic → VAD → STT → barge-in). Keep everything else: text chat input, optional TTS playback, Eyes (screen capture), Hands (MCP tools), YouTube/Video MCP, WebMCP, Live Sandbox, Claude Code delegation, HITL proposals. The app becomes a **text-first coding agent with optional voice output** — like ChatGPT/Gemini's "read aloud" button.

---

## What Gets REMOVED

### 1. Voice Input Pipeline
- **`services/cognitive-engine/src/audio/vad.py`** — Delete entire file (Silero VAD)
- **`services/cognitive-engine/src/audio/stt.py`** — Delete entire file (Deepgram STT, Whisper)
- **`services/mcp-gateway/src/hooks/use-audio-capture.ts`** — Delete entire file (browser mic capture)
- **`services/cognitive-engine/src/voice_bridge.py`** — Delete entire file (MCP client TTS bridge + mic routing)

### 2. Barge-in / Interrupt Logic
- Remove `VocoVADStreamer` usage, `_on_barge_in()`, barge-in state from main.py
- Remove `bargeInActive`, `bargeInBridge`, `bridgeTtsActive` from frontend hooks
- Remove `halt_native_audio` barge-in usage (keep the Tauri command for TTS stop control)

### 3. Voice-First UI
- **`services/mcp-gateway/src/components/FloatingOrb.tsx`** — Delete (48px floating orb window)
- Remove orb window creation from `lib.rs`
- Remove `speak` mode from `AppPage.tsx` (make text mode the default and only mode)
- Remove dictation mode (`voco` / `app` toggle, `type_diff`, enigo typing)
- Remove wake word logic, VAD suppression, audio buffer accumulation

### 4. Dependencies to Remove
- **Python:** `torch`, `onnxruntime`, `torchaudio` (Silero VAD deps) — saves ~500MB
- **Python:** `deepgram-sdk` (STT)
- **Rust:** Remove `rodio` usage for streaming playback (keep for optional TTS playback)

---

## What Gets KEPT (and simplified)

### 1. TTS Playback (Optional "Read Aloud")
- **Keep `services/cognitive-engine/src/audio/tts.py`** (Cartesia)
- **Keep `services/mcp-gateway/src-tauri/src/audio.rs`** (native playback via rodio)
- Change: TTS is no longer automatic after every response. Instead:
  - Frontend shows a "Read aloud" button on each AI response
  - User clicks → frontend sends `{"type": "tts_request", "text": "..."}` over WebSocket
  - Backend streams Cartesia audio back, frontend plays via Tauri native audio
  - User can stop playback with a "Stop" button (sends `halt_native_audio`)
- Remove: VAD suppression during TTS, barge-in detection, grace periods, echo prevention

### 2. Eyes (Screen Capture) — No Changes
- **Keep `services/mcp-gateway/src-tauri/src/screen.rs`** (rolling JPEG buffer)
- **Keep `analyze_screen` tool** in `tools.py`
- Works exactly as before: Claude calls tool → frontend captures → vision analysis

### 3. Hands (MCP Tools) — No Changes
- **Keep all tools in `tools.py`**: search_codebase, propose_command, propose_file_creation, propose_file_edit, read_file, list_directory, glob_find, github_read_issue, github_create_pr, scan_vulnerabilities, generate_and_preview_mvp, update_sandbox_preview, delegate_to_claude_code
- **Keep `mcp_registry.py`** (external MCP servers)
- **Keep `commands.rs`** (Tauri MCP commands)
- **Keep background_worker.py** (async job queue)

### 4. YouTube/Video MCP — No Changes
- **Keep `services/synapse-mcp/`** entirely

### 5. WebMCP — No Changes
- **Keep `voco-mcp.json`** fetch server config

### 6. LangGraph Brain — Simplified
- **Keep**: `state.py`, `router.py`, `nodes.py`, `tools.py`, `mcp_registry.py`, `checkpointer.py`, `token_guard.py`, `session_memory.py`, `turn_archive.py`
- **Remove from state.py**: `barge_in_detected` field
- **Remove from router.py**: barge-in conditional edge (`orchestrator_node → orchestrator_node` loop)
- **Update system prompt**: Remove "voice-first" and "spoken aloud" language, update to text-first identity

---

## What Gets BUILT (New)

### 1. Chat UI (Replace voice panel in AppPage.tsx)
Replace the voice orb + text toggle with a proper **chat message thread**:
- Scrollable message list showing user messages and AI responses
- Each AI response has a "Read aloud" button (speaker icon)
- Text input bar at bottom with send button (keep existing textarea, enhance)
- Activity feed in sidebar (keep existing `SidebarPanel` with ledger, proposals, jobs)
- Remove mode toggle (speak/type) — text is the only input mode
- Keep connection status indicator

### 2. Simplified main.py WebSocket Handler
The 900-line monolith becomes ~400 lines:
- **Remove**: VAD initialization, audio buffer, streaming STT, barge-in handler, wake word gate, voice bridge registration, TTS-after-every-response
- **Keep**: text_input handler, LangGraph invocation, JSON-RPC tool loop, HITL proposal/command flow, auth_sync, sandbox, screen capture, Claude Code delegation
- **Add**: `tts_request` message handler (on-demand TTS playback)
- **Remove from lifespan**: Silero model loading (saves startup time + memory)

### 3. Simplified Frontend Hook (use-voco-socket.ts)
- Remove: `sendAudioChunk`, `bargeInActive`, `bridgeTtsActive`, `bargeInBridge`, `voiceInputRequested`, `liveTranscript`, `interimTranscript`, `dictationMode`, `setDictationMode`
- Add: `messages` array (chat history), `sendMessage(text)` function, `requestTTS(text)` function, `stopTTS()` function, `isTTSPlaying` state
- Keep: `isConnected`, `connect`, `disconnect`, `terminalOutput`, `proposals`, `commandProposals`, `submitProposalDecisions`, `submitCommandDecisions`, `ledgerState`, `backgroundJobs`, `sandboxUrl`, `sendAuthSync`, `wsRef`

### 4. AI Response Streaming (text)
- Instead of waiting for full response then TTS, stream text tokens to frontend
- Backend sends `{"type": "ai_chunk", "text": "..."}` as Claude generates
- Frontend renders progressively (typewriter effect)
- When complete, send `{"type": "ai_complete", "text": "full response"}`
- This is the ChatGPT/Gemini UX users expect

---

## Implementation Order

### Phase 1: Backend Simplification (cognitive-engine)
1. Remove VAD/STT imports and Silero loading from `main.py` lifespan
2. Delete `vad.py`, `stt.py`, `voice_bridge.py`
3. Strip audio processing from WebSocket handler (remove bytes handling for audio, keep for TTS response)
4. Remove barge-in handler and voice bridge registration
5. Simplify `_on_turn_end` → rename to `_handle_message(text: str)`
6. Add `tts_request` handler (on-demand playback)
7. Remove `barge_in_detected` from `state.py` and router
8. Update system prompt to text-first identity
9. Send AI response text via WebSocket as `ai_response` message (not just TTS)

### Phase 2: Frontend Simplification (mcp-gateway React)
1. Delete `FloatingOrb.tsx`, `use-audio-capture.ts`
2. Strip voice state from `use-voco-socket.ts`
3. Add chat message state and handlers to socket hook
4. Build chat message thread component (new `ChatThread.tsx`)
5. Add "Read aloud" button per message
6. Rewrite `AppPage.tsx` — text-only layout with chat thread
7. Remove orb window from `lib.rs`

### Phase 3: Cleanup
1. Remove unused Rust commands (if any)
2. Remove Python dependencies (torch, onnxruntime, deepgram-sdk)
3. Update `requirements.txt` / `pyproject.toml`
4. Update `Docs/TDD.md` with new architecture
5. Remove `test_bargein_routing.py`
6. Run remaining tests, fix any breakage

---

## Files Changed Summary

| Action | File | Reason |
|--------|------|--------|
| DELETE | `cognitive-engine/src/audio/vad.py` | Voice input removed |
| DELETE | `cognitive-engine/src/audio/stt.py` | Voice input removed |
| DELETE | `cognitive-engine/src/voice_bridge.py` | Voice bridge removed |
| DELETE | `mcp-gateway/src/hooks/use-audio-capture.ts` | Mic capture removed |
| DELETE | `mcp-gateway/src/components/FloatingOrb.tsx` | Orb UI replaced by chat |
| DELETE | `cognitive-engine/tests/test_bargein_routing.py` | Barge-in removed |
| HEAVY EDIT | `cognitive-engine/src/main.py` | Remove voice pipeline, add text streaming |
| EDIT | `cognitive-engine/src/graph/state.py` | Remove `barge_in_detected` |
| EDIT | `cognitive-engine/src/graph/router.py` | Remove barge-in edge |
| EDIT | `cognitive-engine/src/graph/nodes.py` | Update system prompt |
| HEAVY EDIT | `mcp-gateway/src/hooks/use-voco-socket.ts` | Remove voice state, add chat state |
| HEAVY EDIT | `mcp-gateway/src/pages/AppPage.tsx` | Replace voice UI with chat UI |
| EDIT | `mcp-gateway/src-tauri/src/lib.rs` | Remove orb window |
| CREATE | `mcp-gateway/src/components/ChatThread.tsx` | New chat message thread |
| KEEP | `cognitive-engine/src/audio/tts.py` | Optional playback |
| KEEP | `mcp-gateway/src-tauri/src/audio.rs` | Native playback |
| KEEP | `mcp-gateway/src-tauri/src/screen.rs` | Eyes |
| KEEP | `mcp-gateway/src-tauri/src/commands.rs` | Hands |
| KEEP | `cognitive-engine/src/graph/tools.py` | All tools |
| KEEP | `cognitive-engine/src/graph/mcp_registry.py` | External MCPs |
| KEEP | `synapse-mcp/` | YouTube/Video |
| KEEP | `cognitive-engine/src/ide_mcp_server.py` | IDE integration |

---

## Risk Assessment

- **Low risk**: Deleting voice files — clean cuts, no shared state with text path
- **Medium risk**: Rewriting main.py WebSocket handler — core orchestration logic, but we're simplifying not adding
- **Medium risk**: New chat UI — net new React code, but pattern is well-understood
- **Low risk**: LangGraph changes — minimal (remove one state field, one edge)

## What This Enables for V3
- Voice can return as a **separate, properly engineered module** (WebRTC, server-side VAD, proper echo cancellation)
- Text-first gives you a shippable product NOW
- Eyes + Hands + YouTube MCP are your differentiators — they don't need voice to be valuable
