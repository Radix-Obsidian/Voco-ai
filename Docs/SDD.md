# Voco V2: System Security Document (SDD)

## 1. Zero-Trust MCP Execution
Unlike V1 where the MCP server was remote and harmless, V2's Tauri MCP server has access to the user's hard drive. 
* **The Python Sandbox:** The Cloud AI (Railway) has ZERO direct disk access. It must request operations via JSON-RPC to Tauri.
* **Tauri Boundaries:** Rust logic enforces that file operations (`fs.read`, `fs.write`) can ONLY occur within the directory of the currently active `voco_project`. Path traversal (`../`) is strictly blocked.

## 2. Command Blocklist & HITL
* **Inline Blocklist:** Tauri automatically rejects commands like `rm -rf`, `sudo`, or `chmod`.
* **Human-in-the-Loop (HITL):** For high-impact commands (`git push --force`, database migrations), the Python LangGraph triggers an `interrupt()`. Voco synthesizes voice: *"I am about to execute a database migration. Do you approve?"*. Tauri will not execute the command until a positive transcribed response is routed back through the graph.

## 3. API Key & Token Management
* **V1 Migration:** V1 stored BYOK (Bring Your Own Key) in localStorage. V2 will migrate these keys to the secure OS Keychain via Tauri's secure storage APIs.
* **Auth:** V2 will continue using Supabase JWTs, but the connection between Tauri and the Python engine requires a short-lived WebSocket ticket to prevent unauthorized audio streaming.