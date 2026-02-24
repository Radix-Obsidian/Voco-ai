import { useState } from "react";
import { X, Mic, Brain, Shield, Zap } from "lucide-react";

interface OnboardingTourProps {
  onComplete: () => void;
}

const steps = [
  {
    title: "Welcome to the Beta",
    subtitle: "You're one of the Founding 50",
    icon: Zap,
    body: "Voco is a sub-300ms voice-to-code orchestrator. Speak naturally, and Voco will search your codebase, write files, run terminal commands, and explain results — all locally on your machine.",
  },
  {
    title: "Voice First, Always",
    subtitle: "Speak or Type — ⌘K to switch",
    icon: Mic,
    body: "Tap the orb to start speaking. Voco uses neural voice activity detection (Silero VAD) to know when you're done. Need precision? Hit ⌘K to switch to text mode anytime.",
  },
  {
    title: "Your Intent Ledger",
    subtitle: "See What Voco is Thinking",
    icon: Brain,
    body: "The Visual Ledger shows every step of Voco's LangGraph reasoning pipeline in real-time: domain detection, AI orchestration, and tool execution. Full transparency, zero black boxes.",
  },
  {
    title: "Human-in-the-Loop",
    subtitle: "You Approve Every Action",
    icon: Shield,
    body: "Voco's AI engine has zero direct filesystem access. File writes, git operations, and terminal commands all require your explicit approval. High-risk commands are spoken aloud before execution.",
  },
];

export function OnboardingTour({ onComplete }: OnboardingTourProps) {
  const [step, setStep] = useState(0);
  const current = steps[step];
  const Icon = current.icon;
  const isLast = step === steps.length - 1;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-zinc-900 border border-white/[0.06] p-8 shadow-2xl">
        {/* Close button */}
        <button
          onClick={onComplete}
          className="absolute top-4 right-4 text-zinc-600 hover:text-zinc-400 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Progress indicator */}
        <div className="flex items-center gap-1.5 mb-8">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-1 rounded-full transition-all duration-300 ${
                i === step
                  ? "w-6 bg-gradient-to-r from-voco-green to-voco-cyan"
                  : i < step
                    ? "w-3 bg-voco-green/40"
                    : "w-3 bg-zinc-700 border border-dashed border-zinc-600"
              }`}
            />
          ))}
        </div>

        {/* Icon */}
        <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-voco-green/10 border border-voco-cyan/20 mb-6">
          <Icon className="w-6 h-6 text-voco-cyan" />
        </div>

        {/* Content */}
        <h2 className="text-xl font-semibold text-white mb-1">{current.title}</h2>
        <p className="text-sm text-voco-cyan/70 mb-4">{current.subtitle}</p>
        <p className="text-sm text-zinc-400 leading-relaxed mb-8">{current.body}</p>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            onClick={onComplete}
            className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors"
          >
            Skip tour
          </button>

          <button
            onClick={() => {
              if (isLast) onComplete();
              else setStep(step + 1);
            }}
            className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-voco-green to-voco-cyan text-white text-sm font-medium hover:opacity-90 transition-opacity shadow-voco-glow-sm"
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
