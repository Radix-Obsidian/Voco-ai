# Voco V2 — Changelog

## Week of Feb 27 – Mar 5, 2026

### New Features

- **Direct Anthropic Mode** — Voco now connects directly to Claude without needing a proxy server. Simpler setup: just add your Anthropic API key and go. The LiteLLM proxy is still available as an opt-in for power users.

- **Local-First Desktop App** — Voco runs entirely on your machine. The cognitive engine auto-starts when you launch the app, with a streamlined 3-second splash screen and live setup progress on first launch. No remote server dependency.

- **Live Demo Mode** — Try Voco with real microphone input and speech-to-text, using scripted AI responses. Full HITL review flow (file proposals, command approvals) works with real clicks.

- **Claude Code Delegation** — Power users can say "use Claude Code" to hand off complex coding tasks to Claude Code CLI. Progress streams live in the visual ledger.

- **Customizable Keyboard Shortcuts** — Configure your own keybindings via Settings. Defaults to empty so nothing clashes with your IDE or OS shortcuts.

- **Usage Tracking & Free Tier** — 50 free turns per month with smart warnings at 50% and 10% remaining. Usage syncs to Supabase per-user, with a progress bar in the pricing modal.

- **Commands Reference** — New Commands tab (Ctrl+?) with searchable, categorized voice command reference. Copy any command to clipboard.

- **IDE Integration (Co-Work)** — Cursor and Windsurf can now connect to Voco's MCP server for web search, GitHub issues, and full AI reasoning directly from your editor.

### Improvements

- **Smaller Install** — Switched from PyTorch (~800MB) to ONNX Runtime (~12MB) for voice activity detection. Same accuracy, 98% smaller download.

- **Better Error Messages** — Microphone permission errors, missing API keys, and AI model issues now show clear, actionable toasts instead of failing silently.

- **Resilient Voice Pipeline** — Speech-to-text retries with exponential backoff on server errors. TTS failures no longer block the approval flow — you can still review and approve file changes even if voice synthesis fails.

- **Smarter Auth Modal** — Sign-in can no longer be accidentally dismissed. Added "sign out and switch account" option to the upgrade screen.

- **Preserved Decisions on Disconnect** — If your connection drops while reviewing proposals or commands, your decisions are preserved instead of lost. Resubmit after reconnection.

### Bug Fixes

- Fixed WebSocket timeout causing disconnects during long-running tasks (keepalive ping disabled on localhost)
- Fixed TTS producing silence due to missing language field in Cartesia API calls
- Fixed graph checkpointer crash on every WebSocket connect (context manager not awaited)
- Fixed zombie sessions from unresponsive HITL — auto-rejects after timeout
- Fixed free-tier usage being shared across accounts (now scoped per user)
- Fixed VAD model download hanging indefinitely on slow connections (now retries 3x with 30s timeout)
