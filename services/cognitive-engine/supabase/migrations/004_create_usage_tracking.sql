-- Voco V2 Usage Tracking Migration
-- Table: usage_tracking — per-user monthly turn counter for free-tier cap
-- Function: increment_usage — atomic upsert + increment for the current billing period

-- ============================================================
-- 1. usage_tracking — one row per user per billing period
-- ============================================================
CREATE TABLE IF NOT EXISTS public.usage_tracking (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    period_start      TIMESTAMPTZ NOT NULL,
    generation_count  INTEGER NOT NULL DEFAULT 0,

    UNIQUE (user_id, period_start)
);

COMMENT ON TABLE public.usage_tracking IS 'Monthly turn counter per user for free-tier usage cap.';

-- Index for the query pattern: .eq(user_id).gte(period_start).order(desc).limit(1)
CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_period
    ON public.usage_tracking (user_id, period_start DESC);

ALTER TABLE public.usage_tracking ENABLE ROW LEVEL SECURITY;

-- Users can read their own usage.
DROP POLICY IF EXISTS usage_tracking_select_own ON public.usage_tracking;
CREATE POLICY usage_tracking_select_own ON public.usage_tracking
    FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own rows (initial period creation).
DROP POLICY IF EXISTS usage_tracking_insert_own ON public.usage_tracking;
CREATE POLICY usage_tracking_insert_own ON public.usage_tracking
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own rows (increment count).
DROP POLICY IF EXISTS usage_tracking_update_own ON public.usage_tracking;
CREATE POLICY usage_tracking_update_own ON public.usage_tracking
    FOR UPDATE USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Service role has full access (billing webhooks, admin resets).
DROP POLICY IF EXISTS usage_tracking_service_all ON public.usage_tracking;
CREATE POLICY usage_tracking_service_all ON public.usage_tracking
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
-- 2. increment_usage(p_user_id) — atomic upsert + increment
--    Returns the new generation_count for the current period.
--    Called as: supabase.rpc("increment_usage", { p_user_id })
-- ============================================================
CREATE OR REPLACE FUNCTION public.increment_usage(p_user_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
    current_period TIMESTAMPTZ;
    new_count INTEGER;
BEGIN
    -- First day of the current month at midnight UTC
    current_period := date_trunc('month', now());

    INSERT INTO public.usage_tracking (user_id, period_start, generation_count)
    VALUES (p_user_id, current_period, 1)
    ON CONFLICT (user_id, period_start)
    DO UPDATE SET generation_count = usage_tracking.generation_count + 1
    RETURNING generation_count INTO new_count;

    RETURN new_count;
END;
$$;

COMMENT ON FUNCTION public.increment_usage IS 'Atomically increment the turn counter for the current billing period. Creates the row if it does not exist.';
