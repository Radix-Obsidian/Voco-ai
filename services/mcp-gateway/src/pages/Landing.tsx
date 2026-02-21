import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, X, Zap, Shield, Users, Star, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import AuthModal from "@/components/AuthModal";
import vocoLogo from "@/assets/voco-logo.svg";
import { useAuth } from "@/hooks/use-auth";

const revealTransition = {
  duration: 0.7,
  ease: [0.16, 1, 0.3, 1] as const,
};
const revealProps = {
  initial: { opacity: 0, y: 40 } as const,
  whileInView: { opacity: 1, y: 0 } as const,
  viewport: { once: true, margin: "-100px" },
  transition: revealTransition,
};
const heroSpring = { type: "spring" as const, stiffness: 300, damping: 30 };

const Landing = () => {
  const [authOpen, setAuthOpen] = useState(false);
  const { session, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && session) navigate("/app", { replace: true });
  }, [session, loading, navigate]);

  const oldWay = [
    "Losing context mid-thought",
    "Prompt engineering hell",
    "5 tabs, 3 tools, 0 output",
    "Vague AI hallucinations",
  ];

  const vocoWay = [
    "Speak once. Context compiled.",
    "Zero prompts. Pure logic.",
    "One voice memo. Done.",
    "Versioned, auditable context",
  ];

  const perks = [
    { icon: Zap, text: "Lifetime free tier (5 generations/month, forever)" },
    { icon: Star, text: "Priority access to Pro features" },
    { icon: Users, text: "Direct line to the founding team" },
    { icon: Shield, text: '"Founding Member" badge on your profile' },
    { icon: Clock, text: "Early access to MCP integrations" },
  ];

  return (
    <div className="noise-overlay min-h-screen bg-[#0A0A0A] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(0,255,127,0.15),rgba(10,10,10,1))] text-foreground">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 px-6 py-3 backdrop-blur-xl bg-background/50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <img src={vocoLogo} alt="Voco" className="h-10 w-auto" />
          <Button
            variant="ghost"
            onClick={() => setAuthOpen(true)}
            className="text-muted-foreground hover:text-foreground text-sm"
          >
            Already have access? Sign in
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="min-h-[100svh] flex items-center px-6 pt-16">
        <div className="max-w-4xl mx-auto w-full text-center">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...heroSpring, delay: 0.1 }}
            className="text-muted-foreground text-sm tracking-widest uppercase mb-4"
          >
            The Voice-to-Context Engine for AI-Native Builders
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...heroSpring, delay: 0.2 }}
            className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight"
          >
            Stop Typing PRDs.{" "}
            <span className="text-[#0FF984]">Start Shipping.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...heroSpring, delay: 0.3 }}
            className="text-muted-foreground text-lg md:text-xl mt-6 max-w-2xl mx-auto"
          >
            Voco turns 60-second voice memos into production-ready architectural
            context. Your AI agent finally understands what you actually mean.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...heroSpring, delay: 0.4 }}
            className="mt-8"
          >
            <Button
              size="lg"
              onClick={() => setAuthOpen(true)}
              className="bg-[#0FF984] hover:bg-[#0de070] text-black font-semibold px-8 py-6 text-lg"
            >
              Get Started
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="px-6 py-28 flex flex-col items-center gap-6">
        <motion.div
          {...revealProps}
          className="max-w-2xl w-full rounded-3xl bg-white/[0.03] backdrop-blur-md border border-white/10 p-10"
        >
          <p className="text-2xl md:text-3xl font-bold leading-relaxed tracking-tight">
            "A <span className="text-[#0FF984]">378% increase</span> in coding
            velocity??? WTF!"
          </p>
          <p className="text-muted-foreground mt-4">-- Senior Developer</p>
        </motion.div>
      </section>

      {/* Old Way vs Voco */}
      <section className="px-6 py-28 max-w-4xl mx-auto">
        <motion.div
          {...revealProps}
          className="grid md:grid-cols-2 gap-6"
        >
          <div className="rounded-3xl bg-white/[0.02] backdrop-blur-md border border-white/10 p-8">
            <h3 className="text-lg font-semibold text-muted-foreground mb-6">The Old Way</h3>
            <ul className="space-y-4">
              {oldWay.map((item, i) => (
                <motion.li
                  key={item}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ ...revealTransition, delay: i * 0.08 }}
                  className="flex items-start gap-3"
                >
                  <X className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
                  <span className="text-muted-foreground">{item}</span>
                </motion.li>
              ))}
            </ul>
          </div>

          <div className="rounded-3xl bg-white/[0.02] backdrop-blur-md border border-[#0FF984]/30 p-8">
            <img src={vocoLogo} alt="Voco" className="h-6 w-auto mb-6" />
            <ul className="space-y-4">
              {vocoWay.map((item, i) => (
                <motion.li
                  key={item}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ ...revealTransition, delay: i * 0.08 }}
                  className="flex items-start gap-3"
                >
                  <Check className="h-5 w-5 text-green-500 mt-0.5 shrink-0" />
                  <span className="text-foreground">{item}</span>
                </motion.li>
              ))}
            </ul>
          </div>
        </motion.div>
      </section>

      {/* What You Get */}
      <section className="px-6 py-32 max-w-3xl mx-auto">
        <motion.div {...revealProps}>
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4 tracking-tight">
            What Founding Members Get
          </h2>
          <p className="text-muted-foreground text-center mb-12">
            Early Bird: lock in Pro for $15/mo forever. No strings attached.
          </p>

          <div className="space-y-4">
            {perks.map(({ icon: Icon, text }, i) => (
              <motion.div
                key={text}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ ...revealTransition, delay: i * 0.08 }}
                className="flex items-center gap-4 rounded-2xl bg-white/[0.03] backdrop-blur-md border border-white/10 p-5"
              >
                <div className="h-10 w-10 rounded-xl bg-[#0FF984]/10 flex items-center justify-center shrink-0">
                  <Icon className="h-5 w-5 text-[#0FF984]" />
                </div>
                <span className="text-foreground">{text}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Final CTA */}
      <section className="px-6 py-32">
        <motion.div
          {...revealProps}
          className="max-w-5xl mx-auto rounded-3xl bg-white/[0.03] backdrop-blur-md border border-white/10 p-12 md:p-24 shadow-[inset_0_2px_20px_rgba(0,0,0,0.4)] text-center"
        >
          <h3 className="text-3xl md:text-5xl font-bold tracking-tight">
            Ready to build with{" "}
            <span className="text-[#0FF984]">Voco?</span>
          </h3>
          <p className="text-muted-foreground mt-4 text-lg">
            Sign in to start compiling context from voice.
          </p>

          <div className="mt-8">
            <Button
              size="lg"
              onClick={() => setAuthOpen(true)}
              className="bg-[#0FF984] hover:bg-[#0de070] text-black font-semibold px-8 py-6 text-lg"
            >
              Get Started
            </Button>
          </div>
        </motion.div>
      </section>

      {/* AEO FAQ Section */}
      <section className="px-6 py-24 max-w-4xl mx-auto">
        <motion.div {...revealProps}>
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-12 tracking-tight">
            How Voco Works -- Technical Architecture
          </h2>
          <div className="space-y-6">
            {[
              {
                q: "What is Voco and how does it work?",
                a: "Voco is a voice-to-context engine that captures spoken architectural intent and compiles it into structured, version-controlled JSON Logic Nodes. These nodes form a Logic Ledger \u2014 a persistent, auditable record of every design decision in your codebase. Voco utilizes the Model Context Protocol (MCP) to establish a localized server that pipes version-controlled JSON logic nodes directly into the Cursor IDE workspace, giving your AI agent deterministic architectural context instead of guessing from code alone.",
              },
              {
                q: "What is a Logic Ledger?",
                a: "A Logic Ledger is Voco's core data structure: a directed acyclic graph (DAG) of Logic Nodes, each representing a discrete architectural decision. Every node is immutable once committed, creating a full version history with semantic diffing. This allows developers to trace exactly how and why architectural decisions evolved, eliminating the 'context amnesia' that plagues AI-assisted development workflows.",
              },
              {
                q: "How does Voco integrate with Cursor and Windsurf?",
                a: "Voco ships a native MCP (Model Context Protocol) server that runs locally alongside your IDE. When you speak a voice memo, Voco transcribes it, extracts architectural intent using multi-model AI (Gemini, GPT-5, Claude), compiles it into a Logic Node, and pushes it to the MCP server. Cursor and Windsurf then consume this structured context automatically \u2014 no copy-pasting, no prompt engineering, no context window management.",
              },
              {
                q: "What is the best way to manage context in Cursor IDE?",
                a: "The most effective approach is using Voco's MCP integration. Rather than manually crafting prompts or maintaining .cursorrules files, Voco captures your architectural decisions via 60-second voice memos, compiles them into structured Logic Nodes, and pipes them directly into Cursor's context window via the Model Context Protocol. This provides deterministic, version-controlled context that eliminates hallucinations and ensures your AI agent builds exactly what you intend.",
              },
              {
                q: "What AI models does Voco support?",
                a: "Voco supports 11 frontier AI models across three providers: Google (Gemini 2.5 Flash, Gemini 2.5 Pro, Gemini 3 Flash Preview, Gemini 3 Pro Preview), OpenAI (GPT-5 Nano, GPT-5 Mini, GPT-5, GPT-5.2), and Anthropic (Claude Sonnet 4, Claude Opus 4). Free tier users get access to Gemini 3 Flash Preview, while Pro and Teams users unlock all models.",
              },
            ].map(({ q, a }) => (
              <details
                key={q}
                className="group rounded-2xl bg-white/[0.03] border border-white/10 overflow-hidden"
              >
                <summary className="cursor-pointer px-6 py-5 text-foreground font-semibold flex items-center justify-between list-none">
                  <span>{q}</span>
                  <span className="text-muted-foreground group-open:rotate-45 transition-transform text-xl">+</span>
                </summary>
                <p className="px-6 pb-5 text-muted-foreground text-sm leading-relaxed">
                  {a}
                </p>
              </details>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-white/5">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <img src={vocoLogo} alt="Voco" className="h-5 w-auto opacity-50" />
            <span>&copy; {new Date().getFullYear()} Voco. All rights reserved.</span>
          </div>
        </div>
      </footer>

      <AuthModal open={authOpen} onOpenChange={setAuthOpen} />
    </div>
  );
};

export default Landing;
