import { useState } from "react";
import { Check, Zap, Loader2 } from "lucide-react";
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
}

const FREE_FEATURES = [
  "500 voice-turns / month",
  "Local file search (ripgrep)",
  "Basic coding assistant",
  "Cursor & Windsurf IDE sync",
  "Community Discord access",
];

const PRO_FEATURES = [
  "Unlimited voice commands",
  "All LangGraph tools & agents",
  "GitHub issue & PR automation",
  "Tavily web search",
  "Priority response speed",
  "Human-in-the-Loop terminal execution",
  "Founding Member badge",
];

async function openInBrowser(url: string): Promise<void> {
  if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_url", { url });
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

export function PricingModal({ open, onOpenChange }: PricingModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleUpgrade = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch("http://localhost:8001/billing/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100 sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-zinc-100 text-xl">
            <Zap className="h-5 w-5 text-voco-cyan" />
            Upgrade Voco
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Unlock unlimited voice commands and every tool in the arsenal.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 py-4">
          {/* Free card */}
          <div className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
            <div className="mb-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-zinc-500 mb-1">
                The Listener
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
              Current plan
            </Button>
          </div>

          {/* Pro card */}
          <div className="flex flex-col rounded-xl border border-voco-purple/40 bg-voco-purple/5 p-5 relative overflow-hidden">
            {/* Glow accent */}
            <div className="absolute inset-0 rounded-xl pointer-events-none ring-1 ring-voco-purple/20" />

            <div className="mb-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-voco-cyan mb-1">
                The Orchestrator
              </p>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-zinc-100">$15</span>
                <span className="text-sm text-zinc-400">/ month</span>
              </div>
              <p className="text-[10px] text-voco-purple/70 mt-1">Early Bird &mdash; locked forever (reg. $39)</p>
            </div>

            <ul className="space-y-2.5 flex-1 mb-5">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-zinc-200">
                  <Check className="h-4 w-4 shrink-0 mt-0.5 text-voco-cyan" />
                  {f}
                </li>
              ))}
            </ul>

            <Button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full bg-gradient-to-r from-voco-purple to-voco-cyan hover:opacity-90 text-white font-semibold py-2.5 rounded-lg transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Opening Stripe…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Upgrade to Pro
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
          Secure payment via Stripe &middot; Cancel anytime &middot; 50 Founding Member spots
        </p>
      </DialogContent>
    </Dialog>
  );
}
