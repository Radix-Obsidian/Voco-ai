# Voco Cognitive Engine

The cloud reasoning service for Voco V2. Provides stateful AI orchestration via LangGraph, real-time voice processing, and secure MCP tool execution.

## Features

### 🧠 LangGraph State Machine
- Stateful conversation context
- Multi-model routing (Sonnet/Haiku)
- Background job queue
- Speculative pre-fetching
- Tool execution validation

### 🎙️ Audio Pipeline
- Deepgram STT (sub-300ms latency)
- Silero VAD for barge-in detection
- Cartesia TTS for voice feedback
- WebSocket streaming protocol
- Audio buffer management

### 🔐 Security & Enterprise
- Row-level security (RLS) via Supabase
- JWT-based authentication
- Usage metering via Stripe
- Audit logging
- SOC 2 compliance ready

## Quick Start

```bash
# 1. Install dependencies
cd services/cognitive-engine
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Add API keys (see PRODUCTION_DEPLOYMENT_CHECKLIST.md)

# 3. Start services
# Terminal 1: LiteLLM proxy
litellm --model claude-3-sonnet-20240229 --api_base https://api.anthropic.com

# Terminal 2: Cognitive engine
uvicorn src.main:app --host 0.0.0.0 --port 8001
```

## API Reference

### HTTP Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check & API key validation |
| `/billing/create-checkout-session` | POST | Create Stripe checkout for Pro tier |
| `/billing/webhook` | POST | Handle Stripe subscription events |
| `/billing/report-voice-turn` | POST | Record metered usage |

### WebSocket Protocol

**Endpoint:** `/ws/voco-stream`

**Incoming Messages:**
- Raw audio chunks (16kHz PCM)
- JSON control messages:
  ```typescript
  {
    type: "text_input" | "auth_sync" | "mcp_result" | "update_env";
    // Message-specific payload
  }
  ```

**Outgoing Messages:**
- JSON state updates:
  ```typescript
  {
    type: "terminal_output" | "search_results" | "background_job";
    // State-specific payload
  }
  ```

## Architecture

### Core Components

- **`src/graph/nodes.py`** — LangGraph state machine
  - Model routing (Sonnet/Haiku)
  - Tool execution
  - Background jobs
  - Speculative reasoning

- **`src/audio/vad.py`** — Voice processing
  - Silero VAD integration
  - Barge-in detection
  - Audio buffer management
  - WebSocket protocol

- **`src/billing/routes.py`** — Enterprise features
  - Stripe integration
  - Usage metering
  - Webhook handling
  - Subscription management

- **`src/db.py`** — Data persistence
  - Supabase integration
  - Row-level security
  - JWT validation
  - Audit logging

### State Machine

```python
@dataclass
class VocoState:
    # Core state
    thread_id: str
    user_id: str
    project_id: str
    domain: str
    
    # Conversation
    messages: list[Message]
    pending_mcp_action: Optional[dict]
    
    # Background jobs
    job_queue: BackgroundJobQueue
    pending_rpc_futures: dict[str, Future]
```

## Development

### Prerequisites
- Python 3.12+
- Poetry or uv
- LiteLLM proxy
- Stripe CLI (optional)

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `DEEPGRAM_API_KEY` | STT API key | Yes |
| `CARTESIA_API_KEY` | TTS API key | Yes |
| `SUPABASE_URL` | Database URL | Yes |
| `SUPABASE_SERVICE_KEY` | Database key | Yes |
| `STRIPE_SECRET_KEY` | Billing key | No |
| `GITHUB_TOKEN` | GitHub integration | No |
| `TAVILY_API_KEY` | Web search | No |

### Testing

```bash
# Unit tests
pytest

# Integration tests
pytest --integration

# Load testing
python -m locust
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

Proprietary. All rights reserved.
