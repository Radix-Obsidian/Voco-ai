# Voco V2

**The Voice-to-Context Engine for AI-Native Builders**

Voco turns 60-second voice memos into production-ready architectural context. Your AI agent finally understands what you actually mean.

## Architecture

Voco V2 is a monorepo containing two independent runtimes:

```
services/
├── mcp-gateway/        # Local frontend & MCP execution sandbox
│   └── Tauri v2 (Rust) + React + Vite + Shadcn UI
│
└── cognitive-engine/   # Cloud reasoning & audio engine (coming soon)
    └── Python 3.12+ / FastAPI / LangGraph / Silero-VAD
```

### MCP Gateway (`services/mcp-gateway/`)

The local desktop application built with Tauri. Handles the UI layer, Supabase auth, and will serve as the secure MCP execution sandbox with human-in-the-loop approval for filesystem operations.

**Stack:** React 18 &bull; TypeScript &bull; Vite &bull; Tailwind CSS 3 &bull; Shadcn/UI &bull; Supabase Auth &bull; Framer Motion

### Cognitive Engine (`services/cognitive-engine/`)

The remote cloud service that handles voice transcription, multi-model AI reasoning, and Logic Ledger compilation. *Not yet scaffolded.*

**Stack:** Python 3.12+ &bull; FastAPI &bull; LangGraph &bull; Silero-VAD

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
