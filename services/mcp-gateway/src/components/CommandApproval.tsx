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
            Command Sandbox
          </span>
          <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-[10px] ml-1 shrink-0">
            HITL
          </Badge>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleApproveAll}
            className="px-2.5 py-1.5 text-[11px] font-mono rounded-lg bg-voco-cyan/10 text-voco-cyan hover:bg-voco-cyan/20 border border-voco-cyan/20 transition-all duration-150"
          >
            Ship All
          </button>
          <button
            onClick={handleRejectAll}
            className="px-2.5 py-1.5 text-[11px] font-mono rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-all duration-150"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* Command Cards */}
      <div className="p-4 space-y-3 overflow-y-auto min-h-0 max-h-[50vh]">
        {commands.map((c) => {
          const status = getStatus(c.command_id);
          return (
            <div
              key={c.command_id}
              className={`bg-zinc-900/60 border rounded-xl overflow-hidden transition-all duration-150 min-w-0 ${
                status === "approved"
                  ? "border-voco-cyan/40"
                  : status === "rejected"
                  ? "border-red-500/40"
                  : "border-amber-500/30"
              }`}
            >
              {/* Command display */}
              <div className="px-4 py-4 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <div className="flex items-center gap-2 shrink-0">
                    {status === "approved" && (
                      <Badge className="bg-voco-cyan/20 text-voco-cyan border-voco-cyan/30 text-[10px]">APPROVED</Badge>
                    )}
                    {status === "rejected" && (
                      <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-[10px]">REJECTED</Badge>
                    )}
                    {status === "pending" && (
                      <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-[10px]">AWAITING</Badge>
                    )}
                  </div>
                  <span className="text-xs text-zinc-500 leading-relaxed break-words min-w-0 flex-1">{c.description}</span>
                </div>

                {/* The actual command */}
                <div className="bg-zinc-950/80 border border-zinc-800/60 rounded-lg px-4 py-3 font-mono text-xs w-full overflow-x-auto max-h-[120px] overflow-y-auto whitespace-pre-wrap break-words">
                  <span className="text-voco-cyan mr-2">$</span>
                  <span className="text-zinc-200 leading-relaxed">{c.command}</span>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 px-4 py-3 border-t border-zinc-800/40 min-w-0">
                <button
                  onClick={() => setStatus(c.command_id, "approved")}
                  className={`flex-1 px-3 py-2 text-xs font-mono rounded-lg transition-all duration-150 min-h-[32px] min-w-0 truncate ${
                    status === "approved"
                      ? "bg-voco-cyan/30 text-voco-cyan border border-voco-cyan/40"
                      : "bg-zinc-800 text-zinc-400 hover:text-voco-cyan hover:bg-voco-cyan/10 border border-zinc-700"
                  }`}
                >
                  Ship It
                </button>
                <button
                  onClick={() => setStatus(c.command_id, "rejected")}
                  className={`flex-1 px-3 py-2 text-xs font-mono rounded-lg transition-all duration-150 min-h-[32px] min-w-0 truncate ${
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
      <div className="px-4 py-3 border-t border-zinc-800/50 flex flex-wrap gap-y-2 items-center justify-between shrink-0 min-w-0">
        <span className="text-[11px] text-zinc-600 font-mono truncate mr-2">
          {allDecided ? "All commands reviewed" : "Approve or reject each command"}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!allDecided}
          className={`px-4 py-2 text-xs font-mono rounded-lg transition-all duration-150 min-h-[32px] shrink-0 ${
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
