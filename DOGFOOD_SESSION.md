# Voco V2 Dogfood Session Guide

**Date:** Feb 27, 2026  
**Goal:** Production dogfooding — auth-gated app, founder bypass, Stripe payment testing

---

## Quick Start (5 min setup)

### 1. Start the Cognitive Engine + LiteLLM

```bash
cd services/cognitive-engine
uv run uvicorn src.main:app --host 0.0.0.0 --port 8001 &
uv run litellm --config litellm_config.yaml --port 4000 &
```

### 2. Start the Tauri Desktop App

```bash
cd services/mcp-gateway
npm run dev:tauri
# or: npx tauri dev
```

This launches the Voco desktop app with WebSocket bridge to the cognitive engine.

### 3. Auth Flow

The app now **requires Supabase authentication** for all users (demo mode has been retired).

1. Launch the app — you'll see the **splash screen** for ~7 seconds
2. After splash, the **auth modal** appears (sign in / sign up)
3. Sign in with your founder email to get unlimited access

### 4. Configure Windsurf MCP

Windsurf reads MCP servers from `~/.codeium/windsurf/mcp_servers.json` (or project-level `voco-mcp.json`).

The repo already has `voco-mcp.json` configured with:
- `fetch` — web search (MCP)
- `filesystem` — local file access (MCP)
- `synapse` — Voco IDE MCP server (custom)

**To enable in Windsurf:**
1. Open Windsurf settings → MCP Servers
2. Add the project's `voco-mcp.json` path
3. Restart Windsurf

---

## Founder Setup

Founder accounts bypass the 50-turn free cap and can dismiss the paywall modal.

**Founder email(s):** `autrearchitect@gmail.com`

To add more founder emails, edit `services/mcp-gateway/src/hooks/use-auth.ts` → `FOUNDER_EMAILS` set.

### Founder Verification
1. Sign in with a founder email
2. Use 50+ voice turns — you should **not** see the paywall
3. Open the Pricing modal manually (Upgrade button) — it should say **"Founder Access"**
4. You can still click "Secure Founding Pricing" to test the Stripe flow

---

## Payment Testing

Founders can test Stripe without being blocked:

1. Open Pricing modal → click **Secure Founding Pricing**
2. Complete checkout with a [Stripe test card](https://docs.stripe.com/testing#cards) (`4242 4242 4242 4242`)
3. Verify the webhook fires and `voco-tier` updates to `"pro"` in localStorage
4. **Refund** the charge in the Stripe dashboard
5. Verify founder still has full access (founder bypass is email-based, not tier-based)

---

## Dogfood Workflow

### Phase 1: Basic Voice Interaction (10 min)
1. Open Voco desktop app
2. Say: *"Show me the structure of the cognitive-engine project"*
3. Voco should:
   - Detect "database" or "api" domain
   - Use `search_codebase` to find key files
   - Speak back a summary
   - Display results in the Visual Ledger

### Phase 2: Co-work IDE Integration (15 min)
1. Say: *"Create a new utility function in services/mcp-gateway/src/utils/helpers.ts that validates email addresses"*
2. Voco should:
   - Generate the function with `propose_file_creation`
   - Set `cowork_ready=True` on the proposal
   - Send both `proposal` (Voco UI) + `cowork_edit` (Windsurf IDE) messages
   - **In Windsurf:** The edit should appear inline in the editor
   - **In Voco:** Standard proposal card for approval
3. Say: *"Approve"* to accept the edit

### Phase 3: File Editing via Voice (10 min)
1. Say: *"Edit services/mcp-gateway/src/hooks/use-voco-socket.ts — add a comment explaining the turnCount state"*
2. Voco should:
   - Use `read_file` to fetch the current content
   - Generate a diff with the comment
   - Propose with `cowork_ready=True`
   - Display in both Voco + Windsurf
3. Approve the edit

### Phase 4: Turn Counting Validation (5 min)
1. Complete 3-5 voice turns (ask questions, make edits)
2. Check browser console (F12) in Voco desktop app
3. Look for logs like: `[TurnCount] Client/server mismatch: client=5 server=5`
4. Verify counts match (no mismatch warnings = ✅)

### Phase 5: Background Jobs (10 min)
1. Say: *"Search the codebase for all uses of AsyncSqliteSaver"*
2. Voco should:
   - Dispatch `search_codebase` to background queue
   - Send `background_job_start` message
   - Display job in the Visual Ledger
   - Return results when complete
   - Send `background_job_complete` message

---

## Session Recording Template

Create a file `DOGFOOD_SESSION_<DATE>.md` with:

```markdown
# Dogfood Session — Feb 27, 2026

## Setup
- Cognitive engine: ✅ Running on 8001
- Tauri app: ✅ Running
- Windsurf: ✅ MCP configured
- Turn count: Starting at 0

## Interactions

### Turn 1: [Time] — [User Request]
**Request:** "..."
**Voco Response:** "..."
**Observations:**
- Domain detected: [database/ui/api/general]
- Tools used: [search_codebase/read_file/propose_file_edit]
- Turn count: 1 → 1 (✅ match)
- Co-work: [proposal/cowork_edit sent]

### Turn 2: ...

## Issues Found
- [ ] Issue 1: ...
- [ ] Issue 2: ...

## Successes
- ✅ Co-work IDE integration works
- ✅ Turn counting syncs correctly
- ✅ Background jobs dispatch properly

## Next Steps
- [ ] Test with larger codebase
- [ ] Test proposal rejection flow
- [ ] Test command approval flow
```

---

## Key Metrics to Track

| Metric | Target | Status |
|--------|--------|--------|
| Voice latency (STT → response) | <2s | ? |
| Co-work proposal display time | <500ms | ? |
| Turn count sync accuracy | 100% | ? |
| Background job completion | <30s | ? |
| Windsurf IDE integration | Works | ? |

---

## Troubleshooting

### Voco app won't connect to engine
```bash
# Check engine is running
curl http://localhost:8001/health
# Expected: {"status":"ok"}
```

### Turn count mismatch
- Check browser console for `[TurnCount]` warnings
- Verify server is sending `turn_count` in `turn_ended` messages
- Check frontend is syncing with `setTurnCount()`

### Co-work edits not showing in Windsurf
- Verify `cowork_ready=True` is set on proposal
- Check Windsurf MCP server is connected
- Look for `[CoWork]` logs in cognitive-engine stdout

### LiteLLM proxy errors
```bash
# Check proxy is running
curl http://localhost:4000/health
# Check logs for auth issues
```

---

## Notes for Future Sessions

- Record all voice interactions for training data
- Note any UX friction points
- Test with real project edits (not just demo)
- Measure actual latency with browser DevTools
- Test proposal rejection + re-proposal flow

---

## Archived Demo

The demo mode (`?demo=true`) has been retired. Demo files are preserved for future feature showcases:
- `src/data/demo-script.archived.ts`
- `src/hooks/use-demo-mode.archived.ts`
