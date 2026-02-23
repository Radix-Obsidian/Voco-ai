# Voco MCP Gateway

The local desktop application for Voco V2. Provides a zero-trust MCP execution sandbox with human-in-the-loop approval for filesystem operations.

## Features

### 🔒 Zero-Trust Security
- Tauri v2 secure sandbox
- Filesystem scope validation
- Human-in-the-loop terminal approval
- JWT-based authentication
- Row-level security (RLS)

### 💻 Modern Desktop UI
- React 18 with TypeScript
- Shadcn/UI components
- Framer Motion animations
- Split-screen sandbox
- Dark mode by default

### 🌐 Enterprise Integration
- Supabase auth & storage
- Stripe billing integration
- WebSocket bridge to cloud
- Background job tracking
- Usage analytics

## Quick Start

```bash
# 1. Install dependencies
cd services/mcp-gateway
npm install

# 2. Configure environment
cp .env.example .env
# Add keys from PRODUCTION_DEPLOYMENT_CHECKLIST.md

# 3. Start development
npm run dev
```

## Architecture

### Core Components

- **`src-tauri/`** — Zero-trust sandbox
  - Filesystem validation
  - Terminal command approval
  - Secure IPC bridge

- **`src/components/`** — React UI
  - `AuthModal.tsx` — Supabase auth flow
  - `PricingModal.tsx` — Stripe billing
  - `SettingsModal.tsx` — API key management
  - `GhostTerminal.tsx` — Command output

- **`src/hooks/`** — Application logic
  - `use-voco-socket.ts` — WebSocket protocol
  - `use-auth.ts` — Authentication state
  - `use-settings.ts` — Environment sync

### WebSocket Protocol

```typescript
// Outgoing messages
type OutgoingMessage =
  | { type: "audio_chunk"; data: Uint8Array }
  | { type: "text_input"; text: string }
  | { type: "auth_sync"; token: string; uid: string }
  | { type: "command_decision"; decisions: CommandDecision[] };

// Incoming messages
type IncomingMessage =
  | { type: "terminal_output"; content: string }
  | { type: "command_proposal"; command: string }
  | { type: "background_job"; status: JobStatus };
```

## Development

### Prerequisites
- Node.js 18+
- Rust toolchain
- Tauri CLI
- Supabase project

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `VITE_SUPABASE_URL` | Database URL | Yes |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Database key | Yes |
| `VITE_STRIPE_PRICE_ARCHITECT` | Pro tier ID | No |
| `VITE_STRIPE_METER_PRICE` | Usage price ID | No |

### Available Scripts

```bash
# Development
npm run dev          # Start Tauri dev server
npm run dev:frontend # Start Vite only

# Production
npm run build        # Build frontend
npm run tauri build  # Package desktop app

# Testing
npm run test         # Run Jest tests
npm run e2e          # Run Playwright tests
```

### Production Build

```bash
# 1. Build frontend assets
npm run build

# 2. Package desktop app
npm run tauri build

# Output: ./src-tauri/target/release/bundle/
# - Windows: Voco_2.0.0_x64-setup.exe
# - macOS:   Voco_2.0.0_x64.dmg
```

## Security

### Filesystem Access

All filesystem operations are validated against `app.fs_scope()` in Tauri:

```rust
// src-tauri/src/commands.rs
fn validate_path(path: &Path) -> Result<(), Error> {
    if !app.fs_scope().is_allowed(path) {
        return Err(Error::AccessDenied);
    }
    Ok(())
}
```

### Terminal Commands

High-risk operations require explicit user approval:

```rust
#[tauri::command]
async fn execute_command(cmd: &str) -> Result<(), Error> {
    if is_high_risk(cmd) {
        let approved = request_user_approval(cmd).await?;
        if !approved {
            return Err(Error::CommandRejected);
        }
    }
    // Execute command
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

Proprietary. All rights reserved.
