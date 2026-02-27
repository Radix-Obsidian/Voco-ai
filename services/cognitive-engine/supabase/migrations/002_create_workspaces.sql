CREATE TABLE IF NOT EXISTS public.workspaces (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;

-- Users can read/write their own workspaces
DROP POLICY IF EXISTS workspaces_select_own ON public.workspaces;
CREATE POLICY workspaces_select_own ON public.workspaces
    FOR SELECT USING (auth.uid() = owner_id);

DROP POLICY IF EXISTS workspaces_insert_own ON public.workspaces;
CREATE POLICY workspaces_insert_own ON public.workspaces
    FOR INSERT WITH CHECK (auth.uid() = owner_id);

DROP POLICY IF EXISTS workspaces_update_own ON public.workspaces;
CREATE POLICY workspaces_update_own ON public.workspaces
    FOR UPDATE USING (auth.uid() = owner_id)
    WITH CHECK (auth.uid() = owner_id);

-- Service role has full access
DROP POLICY IF EXISTS workspaces_service_all ON public.workspaces;
CREATE POLICY workspaces_service_all ON public.workspaces
    FOR ALL USING (auth.role() = 'service_role');

CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON public.workspaces(owner_id);
