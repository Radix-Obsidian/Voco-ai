-- IP-based free account limiting: one free account per IP address.
-- Used by POST /auth/check-ip and POST /auth/record-ip endpoints.

CREATE TABLE IF NOT EXISTS public.signup_ips (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address  TEXT NOT NULL,
    user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    email       TEXT DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.signup_ips ENABLE ROW LEVEL SECURITY;

-- Only service role can read/write (backend uses service key)
DROP POLICY IF EXISTS signup_ips_service_all ON public.signup_ips;
CREATE POLICY signup_ips_service_all ON public.signup_ips
    FOR ALL USING (auth.role() = 'service_role');

-- Fast IP lookups for the check endpoint
CREATE INDEX IF NOT EXISTS idx_signup_ips_ip ON public.signup_ips(ip_address);
CREATE INDEX IF NOT EXISTS idx_signup_ips_user ON public.signup_ips(user_id);
