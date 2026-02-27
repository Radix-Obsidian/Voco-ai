# Voco V2: Post-Beta Roadmap

**Created:** Feb 27, 2026  
**Status:** Tracked — deferred from third-party audit

---

## GAP 3: project_map Population

**Priority:** Medium  
**Effort:** 3-4 hours  
**Source:** Third-party audit GAP 3, PRD §3.1

### Context
`VocoState.project_map` field exists in `src/graph/state.py` but is never populated. Currently, project context flows through `active_project_path` + `focused_context` (domain keyword matching). The `project_map` field is a placeholder for richer stack detection.

### Implementation Plan
1. **Stack detector node** — Add a `stack_detector_node` to the LangGraph that runs once per session (or when `active_project_path` changes):
   - Read `package.json` → detect JS/TS framework (React, Next.js, Svelte, etc.)
   - Read `pyproject.toml` / `requirements.txt` → detect Python framework (FastAPI, Django, Flask)
   - Read `Cargo.toml` → detect Rust crate type
   - Read `Dockerfile` / `docker-compose.yml` → detect containerization
2. **Populate `project_map`** — Write detected stack info into the `VocoState.project_map` field as a structured dict:
   ```python
   project_map = {
       "framework": "nextjs",
       "language": "typescript",
       "package_manager": "bun",
       "has_docker": True,
       "has_tests": True,
       "test_runner": "vitest",
   }
   ```
3. **Inject into system prompt** — The `context_router_node` reads `project_map` to generate more specific focused context (e.g., "This is a Next.js 15 project using App Router and Tailwind CSS").

### Dependencies
- Requires `local/read_file` Tauri command (already implemented)
- No new third-party deps needed

---

## GAP 17: Audit Log Table

**Priority:** Low (enterprise tier)  
**Effort:** 4-6 hours  
**Source:** Third-party audit GAP 17, SDD §5

### Context
The `audit_log` table referenced in `SDD.md` §5 is not present in `001_initial_schema.sql`. Current logging goes to stdout/JSON files via Python's `logging` module. The `db.py` module only writes to `ledger_sessions` and `ledger_nodes`.

### Implementation Plan
1. **Migration** — Create `002_audit_log.sql`:
   ```sql
   CREATE TABLE IF NOT EXISTS audit_log (
       id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
       session_id  TEXT NOT NULL,
       user_id     UUID REFERENCES auth.users(id),
       event_type  TEXT NOT NULL,  -- 'tool_call', 'proposal', 'command', 'auth', 'error'
       event_data  JSONB NOT NULL DEFAULT '{}',
       created_at  TIMESTAMPTZ DEFAULT now()
   );

   CREATE INDEX IF NOT EXISTS idx_audit_log_session ON audit_log(session_id);
   CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
   CREATE INDEX IF NOT EXISTS idx_audit_log_type ON audit_log(event_type);

   ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

   DROP POLICY IF EXISTS "service_role_full_access" ON audit_log;
   CREATE POLICY "service_role_full_access" ON audit_log
       FOR ALL USING (auth.role() = 'service_role');

   DROP POLICY IF EXISTS "users_read_own" ON audit_log;
   CREATE POLICY "users_read_own" ON audit_log
       FOR SELECT USING (auth.uid() = user_id);
   ```
2. **Python writer** — Add `write_audit_event()` to `src/db.py` that inserts rows via the Supabase service-role client.
3. **Integration points** — Call `write_audit_event()` from:
   - `main.py` — on tool calls, proposal decisions, command approvals
   - `billing/routes.py` — on checkout, webhook events
   - `ide_mcp_server.py` — on IDE tool calls
4. **Enterprise Splunk forwarding** — Configure Supabase Log Drains or a Postgres `pg_notify` trigger to forward audit events to Splunk/Datadog.

### Dependencies
- Supabase service-role key (already configured)
- No new third-party deps needed

---

## Tracking

| Gap | Feature | Priority | Effort | Target |
|-----|---------|----------|--------|--------|
| 3 | project_map population | Medium | 3-4h | Post-beta sprint 1 |
| 17 | Audit log table | Low | 4-6h | Enterprise tier launch |
