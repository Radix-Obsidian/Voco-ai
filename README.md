# Voco V2

**The Voice-to-Context Engine for AI-Native Builders**

Voco turns 60-second voice memos into production-ready architectural context. Your AI agent finally understands what you actually mean.

## Quick Start (5 Minutes)

```bash
# 1. Clone and install
git clone https://github.com/Radix-Obsidian/Voco-ai.git
cd Voco-ai/services/mcp-gateway
npm install

# 2. Set up environment
cp .env.example .env
# Add your API keys from https://voco.ai/dashboard

# 3. Start development
npm run dev
```

## Features & Capabilities

### 🎙️ Voice-to-Context Engine
- Sub-300ms voice transcription via Deepgram
- Barge-in support with Silero VAD
- Instant voice feedback via Cartesia TTS
- Context-aware LangGraph state machine

### 🔒 Zero-Trust MCP Gateway
- Tauri v2 secure sandbox
- Human-in-the-loop terminal approval
- Filesystem scope validation
- Row-level security via Supabase

### 💡 Enterprise Features
- "Seat + Meter" billing ($19/mo + $0.02/turn)
- Team workspaces & shared context
- Audit logs & usage analytics
- SOC 2 compliance ready

## Architecture

Voco V2 is a monorepo with two independent runtimes:

```
services/
├── mcp-gateway/        # Local frontend & MCP execution sandbox
│   ├── Tauri v2 (Rust) # Zero-trust security layer
│   ├── React 18       # Modern UI with Shadcn components
│   └── TypeScript     # Type-safe codebase
│
└── cognitive-engine/   # Cloud reasoning & audio engine
    ├── LangGraph      # Stateful AI orchestration
    ├── Silero-VAD     # Voice activity detection
    ├── FastAPI        # WebSocket bridge
    └── Python 3.12+   # Async runtime
```

### MCP Gateway (`services/mcp-gateway/`)

The local desktop application built with Tauri. Provides:
- Zero-trust MCP execution sandbox
- Human-in-the-loop terminal approval
- Filesystem scope validation
- WebSocket bridge to cognitive engine
- Supabase auth & RLS integration
- Modern React UI with Shadcn/UI

**Stack:** Tauri v2 • React 18 • TypeScript • Vite • Tailwind CSS 3 • Shadcn/UI • Supabase • Framer Motion

### Cognitive Engine (`services/cognitive-engine/`)

The cloud reasoning service that handles:
- Voice transcription (Deepgram)
- Text-to-speech (Cartesia)
- LangGraph state machine
- Tool execution & validation
- Background job queue
- Usage metering & billing

**Stack:** Python 3.12+ • FastAPI • LangGraph • Silero-VAD • Supabase • Stripe

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) >= 18
- npm (or bun)

### Setup

```bash
# Clone the repository
git clone https://github.com/Radix-Obsidian/Voco-ai.git
cd Voco-ai

# Install MCP Gateway dependencies
cd services/mcp-gateway
npm install

# Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# Start the dev server
npm run dev
```

The app will be available at `http://localhost:8080`.

### Environment Variables

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Your Supabase anon/public key |

## Project Structure

```
.
├── Docs/                          # Product & technical documentation
│   ├── PRD.md                     # Product Requirements Document
│   ├── TDD.md                     # Technical Design Document
│   ├── SDD.md                     # System Design Document
│   ├── Core-Features-List.md      # Feature inventory
│   └── GTM.md                     # Go-to-Market strategy
├── services/
│   └── mcp-gateway/
│       ├── src/
│       │   ├── assets/            # SVG branding (logo, mascot, icon)
│       │   ├── components/
│       │   │   ├── ui/            # Shadcn UI primitives (48 components)
│       │   │   ├── AuthModal.tsx   # Supabase email/password + Google OAuth
│       │   │   ├── Header.tsx      # App header with logo
│       │   │   └── ProtectedRoute.tsx
│       │   ├── hooks/             # React hooks (auth, settings, projects, toast)
│       │   ├── integrations/
│       │   │   └── supabase/      # Supabase client & generated types
│       │   ├── lib/               # Utilities (cn helper)
│       │   └── pages/             # Landing, AppPage, NotFound
│       ├── tailwind.config.ts
│       ├── vite.config.ts
│       └── components.json        # Shadcn configuration
├── .windsurfrules                 # AI agent architectural guardrails
└── README.md
```

## Documentation

Detailed documentation lives in the `Docs/` directory:

- **PRD.md** — Product requirements and feature parity with V1
- **TDD.md** — LangGraph & streaming audio architecture
- **SDD.md** — Zero-trust MCP & human-in-the-loop sandbox design
- **Core-Features-List.md** — Complete feature inventory
- **GTM.md** — Go-to-market strategy

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Submit a pull request with a clear description

## License

Proprietary. All rights reserved.
