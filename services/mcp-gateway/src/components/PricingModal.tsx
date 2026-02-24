import { useState } from "react";
import { Check, Zap, Loader2, Lock, MonitorPlay, ShieldCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface PricingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When true the modal is a hard paywall — cannot be dismissed */
  forcedOpen?: boolean;
  userEmail?: string;
}

const FREE_FEATURES = [
  "50 voice-turns (hard cap)",
  "Local file search (ripgrep)",
  "Basic coding assistant",
  "Cursor & Windsurf IDE sync",
];

const PRO_FEATURES = [
  { text: "Unlimited Local Intent Orchestration", icon: <Zap className="w-4 h-4 text-voco-cyan" /> },
  { text: "Voco Synapse — YouTube Video Learning", icon: <MonitorPlay className="w-4 h-4 text-voco-cyan" /> },
  { text: "Live MVP Sandbox Rendering", icon: <Check className="w-4 h-4 text-emerald-500" /> },
  { text: "GitHub issue & PR automation", icon: <Check className="w-4 h-4 text-emerald-500" /> },
  { text: "Zero API key leaks (cloud secured)", icon: <ShieldCheck className="w-4 h-4 text-emerald-500" /> },
  { text: "Founding Member badge + price lock", icon: <Lock className="w-4 h-4 text-voco-green" /> },
];

async function openInBrowser(url: string): Promise<void> {
  if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_url", { url });
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

export function PricingModal({ open, onOpenChange, forcedOpen = false, userEmail = "" }: PricingModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleOpenChange = (val: boolean) => {
    if (forcedOpen && !val) return; // hard paywall — block all dismissal
    onOpenChange(val);
  };

  const handleUpgrade = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch("http://localhost:8001/billing/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_email: userEmail }),
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
      }

      const { url } = (await resp.json()) as { url: string };
      await openInBrowser(url);
      onOpenChange(false);
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="bg-zinc-950 border-zinc-800 text-zinc-100 sm:max-w-2xl"
        onPointerDownOutside={forcedOpen ? (e) => e.preventDefault() : undefined}
        onEscapeKeyDown={forcedOpen ? (e) => e.preventDefault() : undefined}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-zinc-100 text-xl">
            {forcedOpen ? <Lock className="h-5 w-5 text-voco-green" /> : <Zap className="h-5 w-5 text-voco-cyan" />}
            {forcedOpen ? "Sandbox Limit Reached" : "Upgrade Voco"}
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            {forcedOpen
              ? "You've used your 50 free turns. Upgrade to keep building at the speed of thought."
              : "Unlock unlimited voice commands and every tool in the arsenal."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 py-4">
          {/* Free card */}
          <div className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
            <div className="mb-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500 mb-1">
                The Sandbox (Trial)
              </p>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-zinc-100">$0</span>
                <span className="text-sm text-zinc-500">/ forever</span>
              </div>
            </div>

            <ul className="space-y-2.5 flex-1 mb-5">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-zinc-400">
                  <Check className="h-4 w-4 shrink-0 mt-0.5 text-zinc-600" />
                  {f}
                </li>
              ))}
            </ul>

            <Button
              variant="outline"
              disabled
              className="w-full border-zinc-700 bg-zinc-900 text-zinc-500 cursor-default"
            >
              {forcedOpen ? "Limit reached" : "Current plan"}
            </Button>
          </div>

          {/* Founding Architect card */}
          <div className="flex flex-col rounded-xl border border-voco-green/40 bg-voco-green/5 p-5 relative overflow-hidden">
            {/* Glow accent */}
            <div className="absolute inset-0 rounded-xl pointer-events-none ring-1 ring-voco-green/20" />

            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-semibold uppercase tracking-widest text-voco-cyan">
                  Founding Architect
                </p>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-400">
                  EARLY BIRD
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-zinc-100">$19</span>
                <span className="text-sm text-zinc-400">/ month</span>
              </div>
              <p className="text-[10px] text-zinc-500 mt-1">
                + $0.02 per heavy turn &middot; locked 24 months (reg. $39)
              </p>
            </div>

            <ul className="space-y-2.5 flex-1 mb-5">
              {PRO_FEATURES.map((f) => (
                <li key={f.text} className="flex items-start gap-2 text-sm text-zinc-200">
                  <span className="shrink-0 mt-0.5">{f.icon}</span>
                  {f.text}
                </li>
              ))}
            </ul>

            <Button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full bg-gradient-to-r from-voco-green to-voco-cyan hover:opacity-90 text-white font-semibold py-2.5 rounded-lg transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Opening Stripe…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Secure Founding Pricing
                </>
              )}
            </Button>
          </div>
        </div>

        {error && (
          <p className="text-xs text-red-400 text-center pb-2">
            {error}
          </p>
        )}

        <p className="text-center text-xs text-zinc-600 pb-1">
          Secure payment via Stripe &middot; 30-day money-back guarantee &middot; 500 Founding spots
        </p>
      </DialogContent>
    </Dialog>
  );
}
