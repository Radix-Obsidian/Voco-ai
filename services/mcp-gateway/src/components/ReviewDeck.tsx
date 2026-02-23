import { useState } from "react";
import { Proposal } from "@/hooks/use-voco-socket";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

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
    <div className="fixed bottom-4 right-4 w-[640px] max-h-[520px] bg-zinc-950/95 backdrop-blur-xl border border-zinc-800 rounded-lg shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-zinc-400 font-mono ml-2">
            Voco Review Deck — {proposals.length} proposal{proposals.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => bulkSet("approved")}
            className="px-2 py-1 text-xs font-mono rounded bg-voco-cyan/10 text-voco-cyan hover:bg-voco-cyan/20 border border-voco-cyan/20 transition-colors"
          >
            Approve All
          </button>
          <button
            onClick={() => bulkSet("rejected")}
            className="px-2 py-1 text-xs font-mono rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* Proposal Cards */}
      <ScrollArea className="max-h-[400px]">
        <div className="p-3 space-y-3">
          {proposals.map((p) => {
            const status = getStatus(p.proposal_id);
            return (
              <div
                key={p.proposal_id}
                className="bg-zinc-900/70 border border-zinc-800 rounded-md overflow-hidden"
              >
                {/* Card Header */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/50">
                  <div className="flex items-center gap-2">
                    {statusBadge(status)}
                    {actionBadge(p.action)}
                    <span className="text-xs font-mono text-zinc-300">{p.file_path}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setStatus(p.proposal_id, "approved")}
                      className={`px-2 py-0.5 text-xs font-mono rounded transition-colors ${
                        status === "approved"
                          ? "bg-voco-cyan/30 text-voco-cyan border border-voco-cyan/40"
                          : "bg-zinc-800 text-zinc-400 hover:text-voco-cyan hover:bg-voco-cyan/10 border border-zinc-700"
                      }`}
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => setStatus(p.proposal_id, "rejected")}
                      className={`px-2 py-0.5 text-xs font-mono rounded transition-colors ${
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
                <div className="px-3 py-2 text-xs text-zinc-400">
                  {p.description}
                </div>

                {/* Code Preview */}
                {(p.content || p.diff) && (
                  <div className="px-3 pb-2">
                    <pre className="bg-zinc-950 border border-zinc-800 rounded p-2 text-xs text-zinc-300 font-mono overflow-x-auto max-h-[160px] overflow-y-auto whitespace-pre-wrap">
                      {p.content || p.diff}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-zinc-800/50 bg-zinc-900/30 flex items-center justify-between">
        <span className="text-xs text-zinc-600 font-mono">
          {allDecided ? "All proposals reviewed" : "Review each proposal above"}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!allDecided}
          className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
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
