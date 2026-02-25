import { useState } from "react";
import { CommandProposal } from "@/hooks/use-voco-socket";
import { Badge } from "@/components/ui/badge";

interface CommandApprovalProps {
  commands: CommandProposal[];
  onSubmitDecisions: (decisions: Array<{ command_id: string; status: "approved" | "rejected" }>) => void;
}

export function CommandApproval({ commands, onSubmitDecisions }: CommandApprovalProps) {
  const [localStatuses, setLocalStatuses] = useState<Record<string, "pending" | "approved" | "rejected">>({});

  const getStatus = (id: string) => localStatuses[id] ?? "pending";

  const setStatus = (id: string, status: "approved" | "rejected") => {
    setLocalStatuses((prev) => ({ ...prev, [id]: status }));
  };

  const handleApproveAll = () => {
    const updated: Record<string, "approved"> = {};
    for (const c of commands) updated[c.command_id] = "approved";
    setLocalStatuses(updated);
  };

  const handleRejectAll = () => {
    const updated: Record<string, "rejected"> = {};
    for (const c of commands) updated[c.command_id] = "rejected";
    setLocalStatuses(updated);
  };

  const allDecided = commands.every((c) => getStatus(c.command_id) !== "pending");

  const handleSubmit = () => {
    const decisions = commands.map((c) => ({
      command_id: c.command_id,
      status: getStatus(c.command_id) === "pending" ? ("rejected" as const) : (getStatus(c.command_id) as "approved" | "rejected"),
    }));
    onSubmitDecisions(decisions);
  };

  if (!commands.length) return null;

  return (
    <div className="fixed bottom-4 right-4 w-[420px] max-h-[320px] bg-zinc-950/95 backdrop-blur-xl border border-zinc-800 rounded-lg shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-zinc-400 font-mono ml-2">
            Voco Command Sandbox
          </span>
          <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs ml-1">
            HITL
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleApproveAll}
            className="px-2 py-1 text-xs font-mono rounded bg-voco-cyan/10 text-voco-cyan hover:bg-voco-cyan/20 border border-voco-cyan/20 transition-colors"
          >
            Ship All
          </button>
          <button
            onClick={handleRejectAll}
            className="px-2 py-1 text-xs font-mono rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* Command Cards */}
      <div className="p-3 space-y-3 max-h-[200px] overflow-y-auto">
        {commands.map((c) => {
          const status = getStatus(c.command_id);
          return (
            <div
              key={c.command_id}
              className={`bg-zinc-900/70 border rounded-md overflow-hidden transition-colors ${
                status === "approved"
                  ? "border-voco-cyan/40"
                  : status === "rejected"
                  ? "border-red-500/40"
                  : "border-amber-500/30"
              }`}
            >
              {/* Command display */}
              <div className="px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  {status === "approved" && (
                    <Badge className="bg-voco-cyan/20 text-voco-cyan border-voco-cyan/30 text-xs">APPROVED</Badge>
                  )}
                  {status === "rejected" && (
                    <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-xs">REJECTED</Badge>
                  )}
                  {status === "pending" && (
                    <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">AWAITING</Badge>
                  )}
                  <span className="text-xs text-zinc-500">{c.description}</span>
                </div>

                {/* The actual command */}
                <div className="bg-zinc-950 border border-zinc-800 rounded px-3 py-2 font-mono text-sm">
                  <span className="text-voco-cyan mr-2">$</span>
                  <span className="text-zinc-200">{c.command}</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 px-4 py-2 border-t border-zinc-800/50 bg-zinc-900/30">
                <button
                  onClick={() => setStatus(c.command_id, "approved")}
                  className={`flex-1 px-3 py-1.5 text-xs font-mono rounded transition-colors ${
                    status === "approved"
                      ? "bg-voco-cyan/30 text-voco-cyan border border-voco-cyan/40"
                      : "bg-zinc-800 text-zinc-400 hover:text-voco-cyan hover:bg-voco-cyan/10 border border-zinc-700"
                  }`}
                >
                  Ship It
                </button>
                <button
                  onClick={() => setStatus(c.command_id, "rejected")}
                  className={`flex-1 px-3 py-1.5 text-xs font-mono rounded transition-colors ${
                    status === "rejected"
                      ? "bg-red-500/30 text-red-300 border border-red-500/40"
                      : "bg-zinc-800 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 border border-zinc-700"
                  }`}
                >
                  Not Yet
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-zinc-800/50 bg-zinc-900/30 flex items-center justify-between">
        <span className="text-xs text-zinc-600 font-mono">
          {allDecided ? "All commands reviewed" : "Approve or reject each command"}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!allDecided}
          className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
            allDecided
              ? "bg-voco-cyan/20 text-voco-cyan hover:bg-voco-cyan/30 border border-voco-cyan/30"
              : "bg-zinc-800 text-zinc-600 border border-zinc-700 cursor-not-allowed"
          }`}
        >
          Confirm
        </button>
      </div>
    </div>
  );
}
