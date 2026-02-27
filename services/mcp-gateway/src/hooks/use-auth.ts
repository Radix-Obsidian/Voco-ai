import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import type { User, Session } from "@supabase/supabase-js";

const FOUNDER_EMAILS = new Set([
  "autrearchitect@gmail.com",
  "architect@viperbyproof.com",
]);

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [userTier, setUserTier] = useState<string>(() => localStorage.getItem("voco-tier") ?? "free");

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
      }
    );

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Fetch tier from Supabase (source of truth) whenever user changes
  useEffect(() => {
    if (!user?.email) return;

    supabase
      .from("users")
      .select("tier")
      .eq("email", user.email)
      .limit(1)
      .single()
      .then(({ data, error }) => {
        if (error || !data) return;
        const tier = (data as { tier?: string }).tier || "free";
        setUserTier(tier);
        localStorage.setItem("voco-tier", tier);
      });
  }, [user?.email]);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  const isFounder = !!(user?.email && FOUNDER_EMAILS.has(user.email));

  return { user, session, loading, signOut, isFounder, userTier };
}
