# Voco V2: Technical Design Document (TDD)

## 1. System Architecture
Voco V2 adopts a distributed Hybrid Architecture:
* **Database/Auth Layer (Supabase):** Re-uses the exact V1 schema (`profiles`, `voco_projects`, `voco_ledger`, `usage_tracking`). 
* **Local Client (Tauri + React/Vite):** The user's interface. Re-uses V1's Shadcn UI components. Written in Rust/TypeScript. Acts as the local audio capturer and the Local MCP Server.
* **Cognitive Engine (Python + LangGraph):** Hosted on Railway. Replaces V1's `synthesize-logic` edge function. Handles WebRTC audio streams, VAD, and LLM orchestration.

## 2. The Audio Pipeline (Sub-300ms)
* **Ingestion:** Tauri captures 16kHz PCM audio and streams it via WebSockets to the Python Engine.
* **VAD (Silero):** Python evaluates 32ms audio chunks. 
  * *Barge-in Trigger:* 64ms of sustained speech instantly fires a `halt_audio` command down the WebSocket to Tauri.
  * *End-of-Turn Trigger:* 800ms of silence passes the buffer to STT (Deepgram/Whisper).
* **Synthesis:** ElevenLabs/Cartesia streams TTS audio bytes back to Tauri.

## 3. The LangGraph State Machine
Replaces standard sequential API calls. The Python engine maintains this state:
\`\`\`python
class VocoState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    project_map: dict # V1's detected stack and tree
    barge_in_detected: bool
    pending_mcp_action: dict | None
\`\`\`
* If `barge_in_detected` is triggered by VAD, the graph immediately routes back to the Orchestrator node, preserving context without crashing.

## 4. Local MCP Integration
In V1, the IDE queried a remote Supabase URL. In V2, the IDE queries the local Tauri app.
* Tauri runs an MCP server on `stdio` or local `http`.
* When the Python Cognitive Engine needs to read a file, it sends an RPC request *down* the WebSocket to Tauri.
* Tauri executes the read, and sends the string back *up* to Python.