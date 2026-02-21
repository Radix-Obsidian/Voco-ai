Core Functionality & Features List (MVP)
Global Voice Activation: Cmd+Shift+V to summon the Voco System Tray overlay and start listening.

Sub-300ms Barge-in: User can interrupt the AI mid-sentence.

The Logic Ledger (V1 Parity): UI to view the DAG of architectural decisions, synced with Supabase.

Local Context Indexing: Ported from V1, the ability to crawl package.json and directory trees to build the ProjectMap.

Agentic Terminal Execution: Voco can run commands (e.g., bun run test) locally via Tauri and read the outputs.

IDE Auto-Config: One-click button in the UI to automatically write the Voco local MCP server configuration into ~/.cursor/mcp.json or ~/.windsurf/mcp.json.