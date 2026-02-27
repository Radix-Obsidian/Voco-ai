# Coding Agent Session — Building Voco's Real-Time Voice-to-Code Pipeline

**Founder:** Jordan Autrey (AJ) · **Tool:** Windsurf (Cascade) & Claude Code · **Date:** Feb 2026  
**What this is:** A single session where I paired with Cascade to build the hardest part of Voco — a sub-300ms voice pipeline that lets you *talk* to your codebase. The AI never touches your filesystem directly; every action routes through a zero-trust Rust sandbox.

**Why this session:** It shows how I use AI coding tools to ship systems-level architecture, not just CRUD. In ~90 minutes, we wired Silero VAD → Deepgram STT → a LangGraph state machine → Cartesia TTS, with barge-in interrupts and human-in-the-loop command approval — all streaming over a single WebSocket.

---

## Context

Voco V2 is a voice-native coding orchestrator. Two runtimes:
- **Cognitive Engine** (Python): LangGraph brain, audio pipeline, Claude Sonnet with tools.  
- **MCP Gateway** (Tauri/Rust): Local filesystem access, terminal execution, zero-trust sandbox.

The Python side **never** touches the user's disk. When Claude wants to grep a codebase or run `git push`, it emits a JSON-RPC 2.0 payload over WebSocket → Rust validates the path against `fs_scope` → executes → returns results. The human approves destructive commands via voice ("Yes" / "No") before Rust runs them.

---

## Session Transcript (Abridged)

### Turn 1 — Laying the VAD foundation

> **Me:** We need a Silero VAD wrapper that streams raw PCM-16 audio and fires callbacks on barge-in (speech onset, 64ms) and turn-end (sustained silence, 800ms). The model is heavy — load once at startup, inject into every connection.

**Cascade** searched the codebase for existing audio handling, found the empty `src/audio/` package, then wrote:

```python
# services/cognitive-engine/src/audio/vad.py

class VocoVADStreamer:
    SAMPLE_RATE = 16_000
    CHUNK_SAMPLES = 512   # 32ms at 16 kHz
    CHUNK_BYTES = CHUNK_SAMPLES * 2

    def __init__(self, model, *, speech_threshold=0.5,
                 barge_in_frames=2, silence_frames_for_turn_end=25):
        self._model = model
        self._speech_threshold = speech_threshold
        self._barge_in_frames = barge_in_frames
        self._silence_frames = silence_frames_for_turn_end
        # ...

    async def feed(self, raw_bytes, on_barge_in, on_turn_end):
        """Feed PCM-16 chunk → Silero → fire callbacks."""
        # Convert bytes → float32 tensor, run model inference
        # Track consecutive speech/silence frame counts
        # Trigger barge_in after 2 consecutive speech frames (64ms)
        # Trigger turn_end after 25 consecutive silence frames (800ms)
```

Key detail it got right on first pass: **barge-in must fire in 64ms** (2 frames × 32ms) to feel instant, but turn-end waits 800ms to avoid cutting off mid-sentence pauses. I didn't have to correct this — Cascade inferred the asymmetry from my spec.

---

### Turn 2 — The LangGraph state machine

> **Me:** Now the brain. I need a StateGraph with: context_router → boss_router (Haiku classifies simple vs complex) → orchestrator (Sonnet with tools). Conditional edges: if Claude calls a tool → mcp_gateway_node. If it proposes a file edit → proposal_review_node (interrupt). If barge-in fires mid-generation → loop back to orchestrator.

**Cascade** produced the full `router.py` in one shot:

```python
# services/cognitive-engine/src/graph/router.py

def _route_after_orchestrator(state: VocoState) -> str:
    if state.get("barge_in_detected"):
        return "orchestrator_node"          # Re-enter on interrupt
    if state.get("pending_proposals"):
        return "proposal_review_node"       # HITL file review
    if state.get("pending_commands"):
        return "command_review_node"         # HITL terminal approval
    if state.get("pending_mcp_action"):
        return "mcp_gateway_node"            # JSON-RPC → Tauri
    return END

builder = StateGraph(VocoState)
builder.add_node("context_router_node", context_router_node)
builder.add_node("boss_router_node", boss_router_node)
builder.add_node("orchestrator_node", orchestrator_node)
builder.add_node("mcp_gateway_node", mcp_gateway_node)
builder.add_node("proposal_review_node", proposal_review_node)
builder.add_node("command_review_node", command_review_node)

builder.add_edge(START, "context_router_node")
builder.add_edge("context_router_node", "boss_router_node")
builder.add_edge("boss_router_node", "orchestrator_node")
builder.add_conditional_edges("orchestrator_node", _route_after_orchestrator, { ... })

graph = builder.compile(
    interrupt_before=["proposal_review_node", "command_review_node"],
)
```

The `interrupt_before` is critical — it's how LangGraph pauses the graph, speaks the proposed command via TTS ("I want to run git push origin main. Say yes to approve."), waits for the user's voice response, then resumes. **The AI literally asks permission out loud before touching your code.**

---

### Turn 3 — Zero-trust tool bridge

> **Me:** Tools must return JSON-RPC payloads, not execute anything. Python is blind to the filesystem. Tauri validates every path against fs_scope.

**Cascade** wrote `tools.py` where every tool returns a *payload*, not a result:

```python
@tool
def search_codebase(pattern: str, project_path: str, ...) -> dict:
    """Search code via ripgrep — but Python doesn't run rg.
    Returns JSON-RPC 2.0 payload for Tauri to execute."""
    return {
        "jsonrpc": "2.0",
        "method": "search_project",
        "params": {"pattern": pattern, "project_path": project_path},
    }
```

On the Rust side, every command validates scope:

```rust
// src-tauri/src/commands.rs
#[tauri::command]
async fn search_project(pattern: String, project_path: String, app: AppHandle) -> Result<...> {
    // Validate path against Tauri's fs_scope before touching disk
    // Execute ripgrep, return results over WebSocket
}
```

This architecture means even if Claude hallucinates a path like `../../etc/passwd`, Rust rejects it before any I/O occurs.

---

### Turn 4 — Wiring the full pipeline

> **Me:** Connect it all in main.py. Single WebSocket: Tauri streams PCM bytes up, we stream TTS audio bytes down. Control messages are JSON. Handle barge-in mid-TTS.

This was the hardest turn — ~200 lines of async coordination. Cascade scaffolded the WebSocket handler:

```python
async def voco_stream(websocket: WebSocket):
    vad = VocoVADStreamer(app.state.silero_model)
    stt = DeepgramSTT(api_key=os.environ["DEEPGRAM_API_KEY"])
    tts = CartesiaTTS(api_key=os.environ["CARTESIA_API_KEY"])

    async def _on_turn_end():
        # 1. STT: buffer → Deepgram → transcript
        transcript = await stt.transcribe_once(bytes(audio_buffer))
        # 2. LangGraph: transcript → Claude (tools bound)
        result = await graph.ainvoke({"messages": [HumanMessage(content=transcript)]}, config)
        # 3. Check for HITL interrupt (proposals/commands)
        snapshot = await graph.aget_state(config)
        if "proposal_review_node" in snapshot.next:
            # Speak proposals via TTS, wait for voice approval
            ...
        # 4. TTS: response → Cartesia → PCM stream back to Tauri
        async for chunk in tts.synthesize_stream(response_text):
            await websocket.send_bytes(chunk)
```

I caught one issue Cascade missed: the VAD needs to be **reset after TTS ends**, otherwise it immediately triggers turn-end on the silence between TTS stopping and the user speaking. I added a grace period + `vad.reset()` — a 2-line fix, but the kind of thing you only find by actually talking to the system.

---

### Turn 5 — Boss Router (cost optimization)

> **Me:** Most voice turns are "hey what does this function do" — we're burning Sonnet tokens on trivia. Add a Haiku classifier that routes simple queries to Haiku (no tools, fast) and complex ones to Sonnet.

**Cascade** added the boss router node with a zero-shot classifier prompt:

```python
_BOSS_CLASSIFY_PROMPT = (
    "Classify the user's request as ONE of two routes:\n"
    "- haiku — Simple/conversational: greetings, short explanations, status checks\n"
    "- sonnet — Complex/technical: code writing, debugging, file edits, tool use\n"
    "Reply with ONLY 'haiku' or 'sonnet'."
)
```

One Haiku call (~0.001¢) routes the turn. Simple questions get answered in ~80ms instead of ~400ms, and cost drops ~10x for conversational turns. This was Cascade's suggestion after I described the latency budget.

---

## What I Learned

**AI coding tools are a 10x multiplier for architecture, not just autocomplete.** This session produced ~1,200 lines of production code across Python and Rust in 90 minutes. But the real value wasn't speed — it was that Cascade held the full system context (VAD timing constraints, JSON-RPC contract, LangGraph interrupt semantics) across turns while I focused on the design decisions that matter: the 64ms barge-in threshold, the zero-trust boundary, the cost/latency tradeoff of the boss router.

The things I caught that the AI missed (VAD reset after TTS, grace period timing) are exactly the things you only discover by *using* the system with your voice. That's the feedback loop: I talk to Voco, Voco breaks, I fix it with Voco's own agent, and Voco gets better. We're building the tool by using the tool.
