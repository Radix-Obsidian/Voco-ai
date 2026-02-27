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

/** Per-user localStorage key so each account has isolated usage */
function storageKey(uid: string): string {
  return `voco-free-turns-${uid}`;
}

function readLocalCount(uid: string | null | undefined): number {
  if (!uid) return 0;
  return parseInt(localStorage.getItem(storageKey(uid)) ?? "0", 10);
}

function writeLocalCount(uid: string, count: number): void {
  localStorage.setItem(storageKey(uid), String(count));
}

/** Safe defaults returned while auth is loading or for unlimited accounts */
const UNCAPPED: Omit<UsageState, "recordTurn" | "resetUsage"> = {
  turnCount: 0,
  usagePercent: 0,
  turnsRemaining: FREE_TURN_LIMIT,
  isCapped: false,
  activeWarning: null,
};

export function useUsageTracking(userId: string | null | undefined, isFounder: boolean, userTier: string): UsageState {
  const [turnCount, setTurnCount] = useState<number>(() => readLocalCount(userId));

  // Track which warnings have already fired this session to avoid repeat toasts
  const firedHalf = useRef(false);
  const firedNearCap = useRef(false);

  // Migrate: remove old global key that was shared across all users
  useEffect(() => {
    localStorage.removeItem("voco-free-turns");
  }, []);

  // When userId changes (login / logout / account switch) — reload that user's count
  useEffect(() => {
    const count = readLocalCount(userId);
    setTurnCount(count);
    // Reset warning guards for the new user
    firedHalf.current = count >= HALF_MARK;
    firedNearCap.current = count >= NEAR_CAP_MARK;
  }, [userId]);

  // Hydrate from Supabase for the current billing period (free users only)
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
        const localCount = readLocalCount(userId);
        // Take the higher of the two to prevent circumvention via localStorage clear
        const resolved = Math.max(serverCount, localCount);
        setTurnCount(resolved);
        writeLocalCount(userId, resolved);
      });
  }, [userId, isFounder, userTier]);

  const recordTurn = useCallback(async () => {
    if (isFounder || userTier !== "free" || !userId) return;

    setTurnCount((prev) => {
      const next = prev + 1;
      writeLocalCount(userId, next);
      return next;
    });

    // Persist to Supabase asynchronously (fire-and-forget)
    try {
      await supabase.rpc("increment_usage", { p_user_id: userId });
    } catch (err) {
      console.warn("[usage-tracking] Supabase increment failed (offline?):", err);
    }
  }, [userId, isFounder, userTier]);

  const resetUsage = useCallback(() => {
    setTurnCount(0);
    if (userId) writeLocalCount(userId, 0);
    firedHalf.current = false;
    firedNearCap.current = false;
  }, [userId]);

  // ── Safe defaults while auth is loading (userId not yet known) ──
  if (!userId) {
    return { ...UNCAPPED, recordTurn, resetUsage };
  }

  // ── Founders and paid users — unlimited, never capped ──
  if (isFounder || userTier !== "free") {
    return { ...UNCAPPED, recordTurn, resetUsage };
  }

  // ── Free-tier user with known userId ──
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
