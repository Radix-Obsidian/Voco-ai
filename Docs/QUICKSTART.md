# Voco V2: Quick-Start Guide (Architect Edition)

Welcome to the future of eyes-free engineering. Voco V2 isn't just a coding assistant; it's a stateful orchestrator that bridges the gap between your intent and your codebase.

## 1. The 60-Second Setup

Voco V2 uses a hybrid architecture to ensure maximum speed and local security.

1. **Launch the Gateway:** Open the `Voco.app` (Tauri) in your system tray.
2. **Verify the Connection:** Look for the **Emerald Pulse** in the tray icon—this means you are securely connected to the Railway Cognitive Engine.
3. **The Global Hotkey:** Press `Cmd + Shift + V` (Mac) or `Ctrl + Shift + V` (Windows) to activate the microphone.

## 2. The "Magic" Commands

Voco V2 understands context. You don't need to be overly formal. Try these "Zero-to-One" interactions:

* **The PR Brief:** *"Voco, read the current git diff and give me a 30-second audio summary."*
* **The Intent Fix:** *"Look at the login controller. We're missing the rate-limiting middleware required by our Ledger. Fix it."*
* **The Barge-in:** While Voco is talking, just say *"Wait, skip the tests for now"* to see the 300ms interrupt in action.

## 3. The Architectural Intent Ledger

Voco follows the rules you set in your `CLAUDE.md`. To update the "Constitution" of your project:

1. Open `@docs/CLAUDE.md`.
2. Add a path-based pattern (e.g., `src/services/*: All services must use the Singleton pattern`).
3. Voco will now automatically enforce this rule during every voice-generated refactor.

## 4. Troubleshooting the 300ms Barrier

* **Latency?** Ensure you aren't on a high-latency VPN. Voco requires a clean WebSocket path to Railway.
* **Muffled Audio?** Voco uses a neural VAD (Silero). If it's not picking you up, ensure your input gain is sufficient in System Settings.
* **Billing Sync?** Your **Architect** status is synced via Stripe. If features are locked, check the "Billing" tab in the Settings Modal.

## Final Checklist

* [ ] **Local Check:** Run `uv run python -m src.main` in the engine.
* [ ] **Tauri Check:** Run `bun tauri dev` in the gateway.
* [ ] **First Voice Turn:** Speak. If it hears you, it's over for the competition.
