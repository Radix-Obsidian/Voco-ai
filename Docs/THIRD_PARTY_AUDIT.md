# Voco V2: Third-Party Dependency & Best Practices Audit

**Date:** 2025-01-27 (initial) · 2026-02-27 (re-audit)  
**Scope:** All 17 gaps cross-validated against official documentation  
**Status:** ✅ COMPLETE — all actionable fixes implemented

> **Feb 2026 Re-Audit Summary:**
> - ✅ Claude models verified non-deprecated (Sonnet 4.5 + Haiku 4.5 ACTIVE)
> - ✅ Stripe constraint widened from `<11` to `<16` (15.x compatible)
> - ✅ Dead `src/utils.py` deleted (never imported)
> - ✅ DEPLOY.md created with NGINX + Let's Encrypt production instructions
> - ✅ All frontend deps current (React 19.2, Tauri 2.10, Vite 7.3)
> - ✅ Audio providers current (Deepgram, Cartesia Sonic, Silero VAD)

---

## 1. Version Matrix

### Python Dependencies (cognitive-engine)

| Package | Before | After (Pinned) | Latest Known | Status |
|---------|--------|----------------|--------------|--------|
| fastapi | unpinned | `>=0.115.0,<1` | 0.115.x | ✅ Pinned |
| uvicorn[standard] | unpinned | `>=0.32.0,<1` | 0.32.x | ✅ Pinned |
| websockets | unpinned | `>=14.0,<15` | 14.x | ✅ Pinned |
| langgraph | unpinned | `>=0.3.0,<1` | 0.3.x | ✅ Pinned |
| langchain-core | unpinned | `>=0.3.0,<1` | 0.3.x | ✅ Pinned |
| langchain-anthropic | unpinned | `>=0.3.0,<1` | 0.3.x | ✅ Pinned |
| langchain-tavily | unpinned | `>=0.1.0,<1` | 0.1.x | ✅ Pinned |
| PyGithub | unpinned | `>=2.5.0,<3` | 2.5.x | ✅ Pinned |
| torch | unpinned | `>=2.5.0,<3` | 2.5.x | ✅ Pinned |
| torchaudio | unpinned | `>=2.5.0,<3` | 2.5.x | ✅ Pinned |
| numpy | unpinned | `>=2.0.0,<3` | 2.2.x | ✅ Pinned |
| httpx[ws] | unpinned | `>=0.28.0,<1` | 0.28.x | ✅ Pinned |
| python-dotenv | unpinned | `>=1.0.0,<2` | 1.1.x | ✅ Pinned |
| mcp | `>=1.25,<2` | `>=1.25,<2` | 1.x | ✅ Already pinned |
| supabase | `>=2.0,<3` | `>=2.0,<3` | 2.x | ✅ Already pinned |
| stripe | `>=10.0.0` | `>=10.0.0,<16` | 15.x | ✅ Widened (Feb 2026) |
| langchain-openai | `>=1.1.10` | `>=1.1.10,<2` | 1.x | ✅ Upper bound added |
| litellm[proxy] | `>=1.0.0` | `>=1.0.0,<2` | 1.x | ✅ Upper bound added |
| opentelemetry-api | unpinned | `>=1.25.0,<2` | 1.30.x | ✅ Pinned |
| opentelemetry-sdk | unpinned | `>=1.25.0,<2` | 1.30.x | ✅ Pinned |
| otel-exporter-otlp-grpc | unpinned | `>=1.25.0,<2` | 1.30.x | ✅ Pinned |
| otel-instr-fastapi | unpinned | `>=0.46b0,<1` | 0.51.x | ✅ Pinned |
| langgraph-checkpoint-sqlite | unpinned | `>=2.0.0,<3` | 2.x | ✅ Pinned |
| aiosqlite | **MISSING** | `>=0.20.0,<1` | 0.20.x | ✅ Added |

### Frontend Dependencies (mcp-gateway)

| Package | Version | Status |
|---------|---------|--------|
| react | ^19.2.0 | ✅ Current |
| @tauri-apps/api | ^2.10.1 | ✅ Current |
| @tauri-apps/cli | ^2.10.0 | ✅ Current |
| @supabase/supabase-js | ^2.97.0 | ✅ Current |
| vite | ^7.3.1 | ✅ Current |
| typescript | ~5.9.3 | ✅ Current |
| tailwindcss | ^3.4.19 | ✅ Current |
| stripe (JS) | ^20.3.1 | ✅ Current |

### Audio Providers

| Provider | Integration | API Version | Status |
|----------|------------|-------------|--------|
| Deepgram | `langchain` via `DeepgramSTT` | STT v1 streaming | ✅ Current |
| Cartesia | `httpx` via `CartesiaTTS` | TTS streaming | ✅ Current |
| Silero VAD | `torch` via `VocoVADStreamer` | PyTorch model | ✅ Current |

### Claude Models (via LiteLLM)

| Model | ID | Status |
|-------|----|--------|
| Sonnet 4.5 | `claude-sonnet-4-5-20250929` | ✅ ACTIVE, non-deprecated |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | ✅ ACTIVE, non-deprecated |

---

## 2. Gap-by-Gap Findings

### GAP 1: Dead Pipeline Modules ✅
- **Finding:** `src/utils.py` was never imported — contained `generate_call_id()`, `generate_job_id()`, `generate_thread_id()` but callers inline `uuid.uuid4().hex[:8]` directly.
- **Fix applied (Feb 2026):** Deleted `src/utils.py`. Confirmed zero imports via `grep -r 'from src.utils\|from .utils\|import utils'`.
- **Risk:** None (dead code removed).

### GAP 2: SQLite Checkpointer ✅
- **Finding:** Already implemented in `src/graph/checkpointer.py` using `AsyncSqliteSaver`.
- **Compliance:** Follows LangGraph official `langgraph-checkpoint-sqlite` docs.
- **Fix applied:** Added missing `aiosqlite` to `pyproject.toml` (used in `prune_checkpoints()` but undeclared).

### GAP 3: project_map Population
- **Finding:** `VocoState.project_map` field exists but is never populated. No code path writes to it.
- **Action:** Deferred — project context comes from `active_project_path` + `focused_context` currently. The `project_map` field is a placeholder for future stack detection (PRD §3.1).
- **Risk:** Medium (feature gap, not a bug).

### GAP 4: web/discovery Handler ✅
- **Finding:** Already implemented. Frontend `handleWebDiscovery` uses `navigator.modelContext` for WebMCP detection per SDD §2.6. Falls back gracefully when unavailable.
- **Action:** No changes needed.

### GAP 5: Tavily Hybrid Search ✅
- **Finding:** Already integrated via `langchain_tavily.TavilySearch` in `src/graph/tools.py`. Uses official `langchain-tavily` SDK with lazy instantiation.
- **Action:** No changes needed.

### GAP 6: PyGithub Auth.Token() ✅
- **Finding:** Already using `Auth.Token(token)` pattern — the current official SDK approach.
- **Reference:** `src/graph/tools.py` lines 119, 125, 158, 164.
- **Action:** No changes needed.

### GAP 7: docker-compose env vars
- **Finding:** `LITELLM_MASTER_KEY` was present in `docker-compose.prod.yml` but **missing** from dev `docker-compose.yml`.
- **Fix applied:** Added `LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY:-}` to dev compose.

### GAP 8: constants.py Usage
- **Finding:** `ALLOWED_ENV_KEYS` in `constants.py` was missing `SUPABASE_ANON_KEY`, which is read in `db.py` `set_auth_jwt()`.
- **Fix applied:** Added `SUPABASE_ANON_KEY` to the canonical set.
- **Additionally:** Two hardcoded `allowed_keys` sets in `main.py` were out of sync (see GAP 14).

### GAP 9: HTTPS/WSS Production ✅
- **Finding:** Already implemented. `docker-compose.prod.yml` uses NGINX 1.27-alpine + Let's Encrypt certbot. `nginx/nginx.conf` has Mozilla Modern TLS, HSTS, WebSocket upgrade headers, and 1-hour proxy timeouts.
- **Action:** No changes needed.

### GAP 10: Supabase Migrations ✅
- **Finding:** Already idempotent. `001_initial_schema.sql` uses `CREATE TABLE IF NOT EXISTS`, `DROP POLICY IF EXISTS`, `CREATE OR REPLACE FUNCTION`, `DROP TRIGGER IF EXISTS`.
- **Action:** No changes needed.

### GAP 11: WebSocket Reconnection ✅
- **Finding:** Already implemented in `use-voco-socket.ts` with exponential backoff + jitter.
  - Base delay: 1000ms, max: 30000ms, formula: `min(1000 * 2^attempt, 30000) + random jitter`
  - Max attempts: 10, with toast notification on exhaustion.
  - `intentionalCloseRef` prevents reconnect on manual disconnect.
- **Action:** No changes needed.

### GAP 12: Client-side Turn Counting ✅
- **Finding:** Server-side `_session_metrics["turn_count"]` tracked turns but frontend had no visibility.
- **Fix applied (Feb 2026):**
  - Server now sends `turn_count` in every `turn_ended` control message (`main.py`)
  - Frontend `use-voco-socket.ts` tracks `turnCount` state, syncs with server value
  - Client/server mismatch logged as console warning for metering validation

### GAP 13: LiteLLM master_key ✅
- **Finding:** `litellm_config.yaml` correctly uses `os.environ/LITELLM_MASTER_KEY`. `.env.example` documents it.
- **Fix applied:** Added to dev docker-compose (see GAP 7).

### GAP 14: _receive_filtered Duplication
- **Finding:** `_receive_filtered()` and the main WebSocket loop both had hardcoded `allowed_keys` sets for `update_env` handling. These inline sets were **missing** `GOOGLE_API_KEY` and `SUPABASE_ANON_KEY` compared to the canonical `ALLOWED_ENV_KEYS` in constants.py.
- **Fix applied:** Both locations now use `_ALLOWED_ENV_KEYS` (imported from constants at module level).
- **Root cause:** Copy-paste divergence — the constant was created but the inline sets were never updated.

### GAP 15: KEYGEN_ACCOUNT_ID ✅
- **Finding:** `services/mcp-gateway/src/services/licensing.ts` reads from `import.meta.env.VITE_KEYGEN_ACCOUNT_ID` with empty-string fallback. `validateLicenseKey()` returns a safe default when unset.
- **Action:** No changes needed. Value must be set in `.env` when Keygen is configured.

### GAP 16: BackgroundJobQueue State
- **Finding:** `BackgroundJobQueue` lives as a session-scoped object in `main.py`, not as a `VocoState` field. This is **correct** — the queue manages `asyncio.Task`s which are runtime-only and not serializable to LangGraph state.
- **Action:** No changes needed. Design is architecturally sound.

### GAP 17: Audit Log Table
- **Finding:** The `audit_log` table referenced in `SDD.md` §5 is **not** present in `001_initial_schema.sql`. The `db.py` module only writes to `ledger_sessions` and `ledger_nodes`.
- **Action:** Deferred to post-beta. Full implementation plan in `Docs/POST_BETA_ROADMAP.md`.
- **Risk:** Low for beta; required for enterprise tier.

---

## 3. Recommendations (Prioritized for Beta)

### P0 — Critical (Implemented)
1. ✅ **Pin all Python dependencies** — prevents supply-chain breakage on `uv sync`
2. ✅ **Add missing `aiosqlite` dependency** — `prune_checkpoints()` would crash without it
3. ✅ **Fix `_ALLOWED_ENV_KEYS` usage** — `GOOGLE_API_KEY` and `SUPABASE_ANON_KEY` couldn't be injected via `update_env`
4. ✅ **Add `LITELLM_MASTER_KEY` to dev compose** — proxy runs unauthenticated in dev containers

### P1 — Important (Implemented Feb 2026)
5. ✅ **Client-side turn counting** (GAP 12) — Server sends `turn_count`; frontend tracks + validates
6. ✅ **Anthropic co-work integration** — System prompt, `propose_file_edit` cowork_ready flag, `cowork_edit` WebSocket message

### P2 — Post-Beta (see `Docs/POST_BETA_ROADMAP.md`)
7. **Populate `project_map`** (GAP 3) — Stack detection for richer context routing
8. **Audit log migration** (GAP 17) — Supabase audit_log table for enterprise Splunk forwarding

---

## 4. Implementation Checklist

| # | Gap | Third-Party Doc Alignment | Status |
|---|-----|--------------------------|--------|
| 1 | Dead modules | N/A | ✅ Deleted (Feb 2026) |
| 2 | SQLite checkpointer | LangGraph checkpoint-sqlite docs | ✅ Fixed (aiosqlite added) |
| 3 | project_map | LangGraph StateGraph patterns | 🔜 Post-beta (roadmap) |
| 4 | web/discovery | WebMCP spec + navigator.modelContext | ✅ Verified |
| 5 | Tavily search | langchain-tavily official SDK | ✅ Verified |
| 6 | PyGithub Auth | PyGithub v2 Auth.Token() | ✅ Verified |
| 7 | docker-compose env | Docker Compose env_file docs | ✅ Fixed |
| 8 | constants.py | N/A (internal) | ✅ Fixed |
| 9 | HTTPS/WSS | NGINX + Let's Encrypt best practices | ✅ Verified |
| 10 | Supabase migrations | Supabase CLI migration patterns | ✅ Verified |
| 11 | WebSocket reconnect | Exponential backoff (RFC 7.1.1) | ✅ Verified |
| 12 | Turn counting | N/A (internal) | ✅ Implemented (Feb 2026) |
| 13 | LiteLLM master_key | LiteLLM proxy auth docs | ✅ Fixed (via GAP 7) |
| 14 | _receive_filtered | N/A (internal) | ✅ Fixed |
| 15 | KEYGEN_ACCOUNT_ID | Keygen.sh validate-key API | ✅ Verified |
| 16 | BackgroundJobQueue | asyncio.Task lifecycle | ✅ Verified (correct design) |
| 17 | Audit log table | Supabase + Splunk forwarding | 🔜 Post-beta (roadmap) |

---

## 5. User Decisions (Confirmed)

1. ✅ **Keep Claude models 4.5** — Cost-optimized for beta (Sonnet 4.5 & Haiku 4.5 are ACTIVE, non-deprecated)
2. ✅ **Official SDKs only** — All integrations use official libraries
3. ✅ **Flexible constraints** — `>=X.Y.Z,<X+1` pattern applied to all 25 Python deps
4. ✅ **Anthropic co-work** — Implemented: system prompt awareness, cowork_ready flag, cowork_edit WS message
5. ✅ **Stripe widened** — `>=10.0.0,<16` allows upgrade to 15.x when ready
6. ✅ **Dead code removed** — `src/utils.py` deleted (Feb 2026 re-audit)
