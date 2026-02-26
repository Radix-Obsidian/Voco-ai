import { useState } from "react";
import { Proposal } from "@/hooks/use-voco-socket";
import { Badge } from "@/components/ui/badge";

interface ReviewDeckProps {
  proposals: Proposal[];
  onSubmitDecisions: (decisions: Array<{ proposal_id: string; status: "approved" | "rejected" }>) => void;
}

export function ReviewDeck({ proposals, onSubmitDecisions }: ReviewDeckProps) {
  const [localStatuses, setLocalStatuses] = useState<Record<string, "pending" | "approved" | "rejected">>({});

  const getStatus = (id: string) => localStatuses[id] ?? "pending";

  const setStatus = (id: string, status: "approved" | "rejected") => {
    setLocalStatuses((prev) => ({ ...prev, [id]: status }));
  };

  const bulkSet = (status: "approved" | "rejected") => {
    const updated: Record<string, "approved" | "rejected"> = {};
    for (const p of proposals) {
      updated[p.proposal_id] = status;
    }
    setLocalStatuses(updated);
  };

  const allDecided = proposals.every((p) => getStatus(p.proposal_id) !== "pending");

  const handleSubmit = () => {
    const decisions = proposals.map((p) => ({
      proposal_id: p.proposal_id,
      status: getStatus(p.proposal_id) === "pending" ? ("rejected" as const) : (getStatus(p.proposal_id) as "approved" | "rejected"),
    }));
    onSubmitDecisions(decisions);
  };

  const statusBadge = (status: string) => {
    if (status === "approved") return <Badge className="bg-voco-cyan/20 text-voco-cyan border-voco-cyan/30 text-xs">APPROVED</Badge>;
    if (status === "rejected") return <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-xs">REJECTED</Badge>;
    return <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">PENDING</Badge>;
  };

  const actionBadge = (action: string) => {
    if (action === "create_file") return <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-xs">NEW</Badge>;
    return <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 text-xs">EDIT</Badge>;
  };

  if (!proposals.length) return null;

  return (
    <div className="w-full rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden animate-in fade-in duration-200 flex flex-col min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-y-2 px-4 py-3 border-b border-zinc-800/60 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0 pr-2">
          <div className="flex gap-1.5 shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/80" />
          </div>
          <span className="text-[11px] text-zinc-400 font-mono ml-1 shrink-0">
            Review Deck
          </span>
          <span className="text-[10px] text-zinc-500 font-mono shrink-0">
            {proposals.length} proposal{proposals.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => bulkSet("approved")}
            className="px-2.5 py-1.5 text-[11px] font-mono rounded-lg bg-voco-cyan/10 text-voco-cyan hover:bg-voco-cyan/20 border border-voco-cyan/20 transition-all duration-150"
          >
            Approve All
          </button>
          <button
            onClick={() => bulkSet("rejected")}
            className="px-2.5 py-1.5 text-[11px] font-mono rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-all duration-150"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* Proposal Cards */}
      <div className="overflow-y-auto min-h-0 max-h-[50vh]">
        <div className="p-4 space-y-3">
          {proposals.map((p) => {
            const status = getStatus(p.proposal_id);
            return (
              <div
                key={p.proposal_id}
                className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden transition-all duration-150 hover:border-zinc-700/80 min-w-0"
              >
                {/* Card Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-zinc-800/40">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="shrink-0">{statusBadge(status)}</span>
                    <span className="shrink-0">{actionBadge(p.action)}</span>
                    <span className="text-[11px] font-mono text-zinc-300 truncate min-w-0" title={p.file_path}>{p.file_path}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => setStatus(p.proposal_id, "approved")}
                      className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition-all duration-150 ${
                        status === "approved"
                          ? "bg-voco-cyan/30 text-voco-cyan border border-voco-cyan/40"
                          : "bg-zinc-800 text-zinc-400 hover:text-voco-cyan hover:bg-voco-cyan/10 border border-zinc-700"
                      }`}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setStatus(p.proposal_id, "rejected")}
                      className={`px-2.5 py-1 text-[11px] font-mono rounded-lg transition-all duration-150 ${
                        status === "rejected"
                          ? "bg-red-500/30 text-red-300 border border-red-500/40"
                          : "bg-zinc-800 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 border border-zinc-700"
                      }`}
                    >
                      Reject
                    </button>
                  </div>
                </div>

                {/* Description */}
                <div className="px-4 py-3 text-xs text-zinc-400 leading-relaxed break-words whitespace-pre-wrap">
                  {p.description}
                </div>

                {/* Code Preview */}
                {(p.content || p.diff) && (
                  <div className="px-4 pb-3 min-w-0">
                    <pre className="bg-zinc-950/80 border border-zinc-800/60 rounded-lg p-3 text-[11px] text-zinc-300 font-mono w-full overflow-x-auto max-h-[120px] overflow-y-auto whitespace-pre-wrap leading-relaxed break-words">
                      {p.content || p.diff}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-zinc-800/50 shrink-0 flex flex-wrap gap-y-2 items-center justify-between min-w-0">
        <span className="text-[11px] text-zinc-600 font-mono truncate mr-2">
          {allDecided ? "All proposals reviewed" : "Review each proposal above"}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!allDecided}
          className={`px-4 py-2 text-xs font-mono rounded-lg transition-all duration-150 min-h-[32px] shrink-0 ${
            allDecided
              ? "bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/30"
              : "bg-zinc-800 text-zinc-600 border border-zinc-700 cursor-not-allowed"
          }`}
        >
          Submit Decisions
        </button>
      </div>
    </div>
  );
}
