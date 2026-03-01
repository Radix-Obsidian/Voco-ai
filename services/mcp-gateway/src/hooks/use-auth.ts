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

  // Tier is pushed from the backend over WebSocket (user_info message)
  // and written to localStorage. Listen for storage events to stay in sync.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "voco-tier" && e.newValue) {
        setUserTier(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  const isFounder = !!(user?.email && FOUNDER_EMAILS.has(user.email));

  return { user, session, loading, signOut, isFounder, userTier };
}
