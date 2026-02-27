import { useState, useEffect, useRef, useCallback } from "react";
import { supabase } from "@/integrations/supabase/client";

export const FREE_TURN_LIMIT = 50;
const HALF_MARK = Math.floor(FREE_TURN_LIMIT * 0.5);  // 25 — 50% used
const NEAR_CAP_MARK = FREE_TURN_LIMIT - Math.floor(FREE_TURN_LIMIT * 0.1); // 45 — 10% remaining

export type UsageWarning = "half" | "near_cap" | "capped" | null;

export interface UsageState {
  /** Total turns consumed this period */
  turnCount: number;
  /** 0–100 percentage consumed */
  usagePercent: number;
  /** Turns left before the cap */
  turnsRemaining: number;
  /** True when the free cap is exhausted */
  isCapped: boolean;
  /** Active warning level for upgrade prompts */
  activeWarning: UsageWarning;
  /** Persist a new turn — increments Supabase + localStorage */
  recordTurn: () => Promise<void>;
  /** Reset all usage (used after successful upgrade) */
  resetUsage: () => void;
}

export function useUsageTracking(userId: string | null | undefined, isFounder: boolean, userTier: string): UsageState {
  const [turnCount, setTurnCount] = useState<number>(() => {
    return parseInt(localStorage.getItem("voco-free-turns") ?? "0", 10);
  });

  // Track which warnings have already fired this session to avoid repeat toasts
  const firedHalf = useRef(false);
  const firedNearCap = useRef(false);

  // On mount: hydrate from Supabase for the current billing period
  useEffect(() => {
    if (!userId || isFounder || userTier !== "free") return;

    const periodStart = new Date();
    periodStart.setDate(1);
    periodStart.setHours(0, 0, 0, 0);

    supabase
      .from("usage_tracking")
      .select("generation_count")
      .eq("user_id", userId)
      .gte("period_start", periodStart.toISOString())
      .order("period_start", { ascending: false })
      .limit(1)
      .single()
      .then(({ data, error }) => {
        if (error || !data) return;
        const serverCount = data.generation_count ?? 0;
        const localCount = parseInt(localStorage.getItem("voco-free-turns") ?? "0", 10);
        // Take the higher of the two to avoid letting users reset by clearing localStorage
        const resolved = Math.max(serverCount, localCount);
        setTurnCount(resolved);
        localStorage.setItem("voco-free-turns", String(resolved));
      });
  }, [userId, isFounder, userTier]);

  // Mark warnings already fired for turn counts that existed on load
  useEffect(() => {
    if (turnCount >= HALF_MARK) firedHalf.current = true;
    if (turnCount >= NEAR_CAP_MARK) firedNearCap.current = true;
  }, []); // only on mount, intentionally

  const recordTurn = useCallback(async () => {
    if (isFounder || userTier !== "free") return;

    setTurnCount((prev) => {
      const next = prev + 1;
      localStorage.setItem("voco-free-turns", String(next));
      return next;
    });

    // Persist to Supabase asynchronously (fire-and-forget; localStorage is the real-time source)
    if (userId) {
      try {
        await supabase.rpc("increment_usage", { p_user_id: userId });
      } catch (err) {
        console.warn("[usage-tracking] Supabase increment failed (offline?):", err);
      }
    }
  }, [userId, isFounder, userTier]);

  const resetUsage = useCallback(() => {
    setTurnCount(0);
    localStorage.setItem("voco-free-turns", "0");
    firedHalf.current = false;
    firedNearCap.current = false;
  }, []);

  // For founders and paid users — no caps
  if (isFounder || userTier !== "free") {
    return {
      turnCount: 0,
      usagePercent: 0,
      turnsRemaining: Infinity,
      isCapped: false,
      activeWarning: null,
      recordTurn,
      resetUsage,
    };
  }

  const usagePercent = Math.min(100, Math.round((turnCount / FREE_TURN_LIMIT) * 100));
  const turnsRemaining = Math.max(0, FREE_TURN_LIMIT - turnCount);
  const isCapped = turnCount >= FREE_TURN_LIMIT;

  let activeWarning: UsageWarning = null;
  if (isCapped) {
    activeWarning = "capped";
  } else if (turnCount >= NEAR_CAP_MARK && !firedNearCap.current) {
    activeWarning = "near_cap";
    firedNearCap.current = true;
  } else if (turnCount >= HALF_MARK && !firedHalf.current) {
    activeWarning = "half";
    firedHalf.current = true;
  }

  return {
    turnCount,
    usagePercent,
    turnsRemaining,
    isCapped,
    activeWarning,
    recordTurn,
    resetUsage,
  };
}
