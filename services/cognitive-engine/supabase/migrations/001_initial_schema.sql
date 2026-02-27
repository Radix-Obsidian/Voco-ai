-- Voco V2 Initial Schema Migration
-- Tables: users, ledger_sessions, ledger_nodes
-- All tables use Row Level Security (RLS) so that each user
-- can only access their own data via auth.uid().

-- ============================================================
-- 1. users — extended profile (Supabase Auth handles login)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.users (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT DEFAULT '',
    tier            TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    stripe_customer_id      TEXT DEFAULT '',
    stripe_subscription_id  TEXT DEFAULT '',
    stripe_meter_item_id    TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.users IS 'Extended user profile for billing tier and Stripe integration.';

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own row.
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own ON public.users
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS users_update_own ON public.users;
CREATE POLICY users_update_own ON public.users
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Service role (billing webhooks) can read/write any row.
DROP POLICY IF EXISTS users_service_all ON public.users;
CREATE POLICY users_service_all ON public.users
    FOR ALL USING (auth.role() = 'service_role');

-- Auto-create a users row when a new auth.users entry appears.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (id, email)
    VALUES (NEW.id, NEW.email)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- 2. ledger_sessions — one row per WebSocket session
-- ============================================================
CREATE TABLE IF NOT EXISTS public.ledger_sessions (
    id          TEXT PRIMARY KEY,                    -- thread_id e.g. "session-abc12345"
    user_id     TEXT NOT NULL DEFAULT 'local',
    project_id  TEXT NOT NULL DEFAULT 'unknown',
    domain      TEXT NOT NULL DEFAULT 'general',
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.ledger_sessions IS 'One row per Voco WebSocket session for the Visual Ledger.';

ALTER TABLE public.ledger_sessions ENABLE ROW LEVEL SECURITY;

-- Authenticated users can manage their own sessions.
DROP POLICY IF EXISTS ledger_sessions_select ON public.ledger_sessions;
CREATE POLICY ledger_sessions_select ON public.ledger_sessions
    FOR SELECT USING (user_id = auth.uid()::text OR user_id = 'local');

DROP POLICY IF EXISTS ledger_sessions_insert ON public.ledger_sessions;
CREATE POLICY ledger_sessions_insert ON public.ledger_sessions
    FOR INSERT WITH CHECK (user_id = auth.uid()::text OR user_id = 'local');

DROP POLICY IF EXISTS ledger_sessions_update ON public.ledger_sessions;
CREATE POLICY ledger_sessions_update ON public.ledger_sessions
    FOR UPDATE USING (user_id = auth.uid()::text OR user_id = 'local');

-- Service role has full access.
DROP POLICY IF EXISTS ledger_sessions_service ON public.ledger_sessions;
CREATE POLICY ledger_sessions_service ON public.ledger_sessions
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- 3. ledger_nodes — one row per Visual Ledger node per session
-- ============================================================
CREATE TABLE IF NOT EXISTS public.ledger_nodes (
    id              TEXT PRIMARY KEY,               -- "{session_id}_{node_id}"
    session_id      TEXT NOT NULL REFERENCES public.ledger_sessions(id) ON DELETE CASCADE,
    parent_node_id  TEXT,
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    icon_type       TEXT NOT NULL DEFAULT 'FileCode2',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'completed', 'failed')),
    execution_output TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.ledger_nodes IS 'Individual nodes in the Visual Ledger DAG per session.';

ALTER TABLE public.ledger_nodes ENABLE ROW LEVEL SECURITY;

-- RLS via the parent session's user_id.
DROP POLICY IF EXISTS ledger_nodes_select ON public.ledger_nodes;
CREATE POLICY ledger_nodes_select ON public.ledger_nodes
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.ledger_sessions ls
            WHERE ls.id = ledger_nodes.session_id
              AND (ls.user_id = auth.uid()::text OR ls.user_id = 'local')
        )
    );

DROP POLICY IF EXISTS ledger_nodes_insert ON public.ledger_nodes;
CREATE POLICY ledger_nodes_insert ON public.ledger_nodes
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.ledger_sessions ls
            WHERE ls.id = ledger_nodes.session_id
              AND (ls.user_id = auth.uid()::text OR ls.user_id = 'local')
        )
    );

DROP POLICY IF EXISTS ledger_nodes_update ON public.ledger_nodes;
CREATE POLICY ledger_nodes_update ON public.ledger_nodes
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.ledger_sessions ls
            WHERE ls.id = ledger_nodes.session_id
              AND (ls.user_id = auth.uid()::text OR ls.user_id = 'local')
        )
    );

-- Service role has full access.
DROP POLICY IF EXISTS ledger_nodes_service ON public.ledger_nodes;
CREATE POLICY ledger_nodes_service ON public.ledger_nodes
    FOR ALL USING (auth.role() = 'service_role');

-- Index for fast lookups by session.
CREATE INDEX IF NOT EXISTS idx_ledger_nodes_session ON public.ledger_nodes(session_id);

-- ============================================================
-- 4. updated_at auto-trigger
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS users_updated_at ON public.users;
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS ledger_sessions_updated_at ON public.ledger_sessions;
CREATE TRIGGER ledger_sessions_updated_at
    BEFORE UPDATE ON public.ledger_sessions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS ledger_nodes_updated_at ON public.ledger_nodes;
CREATE TRIGGER ledger_nodes_updated_at
    BEFORE UPDATE ON public.ledger_nodes
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
