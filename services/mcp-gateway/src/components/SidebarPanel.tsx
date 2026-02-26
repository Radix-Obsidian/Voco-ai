import { useState } from "react";
import type { LedgerState, BackgroundJob, TerminalOutput, Proposal, CommandProposal } from "@/hooks/use-voco-socket";
import { VisualLedger } from "@/components/VisualLedger";
import { GhostTerminal } from "@/components/GhostTerminal";
import { ReviewDeck } from "@/components/ReviewDeck";
import { CommandApproval } from "@/components/CommandApproval";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarPanelProps {
  ledgerState: LedgerState | null;
  backgroundJobs: BackgroundJob[];
  terminalOutput: TerminalOutput | null;
  proposals: Proposal[];
  commandProposals: CommandProposal[];
  onCloseTerminal: () => void;
  onSubmitProposalDecisions: (decisions: Array<{ proposal_id: string; status: "approved" | "rejected" }>) => void;
  onSubmitCommandDecisions: (decisions: Array<{ command_id: string; status: "approved" | "rejected" }>) => void;
}

export function SidebarPanel({
  ledgerState,
  backgroundJobs,
  terminalOutput,
  proposals,
  commandProposals,
  onCloseTerminal,
  onSubmitProposalDecisions,
  onSubmitCommandDecisions,
}: SidebarPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const hasLedger = !!ledgerState || backgroundJobs.length > 0;
  const hasTerminal = !!terminalOutput;
  const hasProposals = proposals.length > 0;
  const hasCommands = commandProposals.length > 0;
  const hasContent = hasLedger || hasTerminal || hasProposals || hasCommands;

  // Nothing to show — render nothing
  if (!hasContent) return null;

  // Collapsed state — just show a toggle pill
  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="fixed top-16 right-4 z-40 flex items-center gap-2 px-3 py-2 rounded-lg
          bg-zinc-950/95 backdrop-blur-xl border border-zinc-800 shadow-lg
          text-xs text-zinc-400 hover:text-zinc-200 transition-all duration-200
          hover:border-zinc-700 hover:shadow-xl"
      >
        <PanelRightOpen className="w-4 h-4" />
        <span className="font-mono">Panel</span>
        {(hasProposals || hasCommands) && (
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 text-[10px] font-bold">
            {proposals.length + commandProposals.length}
          </span>
        )}
      </button>
    );
  }

  return (
    <aside
      className={cn(
        "fixed top-14 right-0 bottom-0 z-40",
        "w-full sm:w-[420px] lg:w-[480px] xl:w-[540px] sm:max-w-[45vw]",
        "flex flex-col min-w-0",
        "bg-zinc-950/95 backdrop-blur-xl",
        "border-l border-zinc-800",
        "shadow-[-8px_0_32px_rgba(0,0,0,0.4)]",
        "animate-in slide-in-from-right-4 fade-in duration-300",
        // Responsive: on small screens take full width
        "max-sm:w-full max-sm:max-w-full",
      )}
    >
      {/* ── Sidebar header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/80 shrink-0 min-w-0">
        <h2 className="text-[11px] font-medium uppercase tracking-widest text-zinc-500 truncate">
          Activity Panel
        </h2>
        <button
          onClick={() => setCollapsed(true)}
          className="flex items-center justify-center w-7 h-7 rounded-md shrink-0 ml-2
            text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]
            transition-all duration-150"
          aria-label="Collapse panel"
        >
          <PanelRightClose className="w-4 h-4" />
        </button>
      </div>

      {/* ── Scrollable content ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
        {/* Section 1: Visual Ledger (pipeline + background jobs) */}
        {hasLedger && (
          <section className="p-4 border-b border-zinc-800/50">
            <VisualLedger state={ledgerState} backgroundJobs={backgroundJobs} />
          </section>
        )}

        {/* Section 2: HITL — Command Approval (takes priority) */}
        {hasCommands && (
          <section className="p-4 border-b border-zinc-800/50">
            <CommandApproval commands={commandProposals} onSubmitDecisions={onSubmitCommandDecisions} />
          </section>
        )}

        {/* Section 3: HITL — Review Deck */}
        {hasProposals && (
          <section className="p-4 border-b border-zinc-800/50">
            <ReviewDeck proposals={proposals} onSubmitDecisions={onSubmitProposalDecisions} />
          </section>
        )}

        {/* Section 4: Ghost Terminal */}
        {hasTerminal && (
          <section className="p-4">
            <GhostTerminal output={terminalOutput} onClose={onCloseTerminal} />
          </section>
        )}
      </div>
    </aside>
  );
}
