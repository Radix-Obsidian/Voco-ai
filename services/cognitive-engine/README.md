# Voco Cognitive Engine

Python backend service for Voco V2. Provides the LangGraph state schema, Silero VAD audio pipeline, and FastAPI WebSocket bridge.

## Setup

```bash
cd services/cognitive-engine
pip install -e ".[dev]"
```

## Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Endpoint | Type | Description |
|---|---|---|
| `/health` | GET | Health check — returns `{"status": "ok"}` |
| `/ws/voco-stream` | WebSocket | Audio streaming + control |

## Architecture

- **`src/graph/state.py`** — `VocoState` TypedDict used by LangGraph
- **`src/audio/vad.py`** — `VocoVADStreamer` wrapping Silero VAD for barge-in and end-of-turn detection
- **`src/main.py`** — FastAPI app with WebSocket endpoint wiring VAD callbacks to JSON control messages
