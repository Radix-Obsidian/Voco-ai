import {
  Database,
  FileCode2,
  Terminal,
  ArrowRight,
  ShieldCheck,
  Globe,
  Github,
  MessageSquare,
  LayoutList,
  GitBranch,
  HardDrive,
  type LucideIcon,
} from "lucide-react";
import type { LedgerState, LedgerNode } from "@/hooks/use-voco-socket";

const staticIconMap: Record<string, LucideIcon> = {
  Database: Database,
  FileCode2: FileCode2,
  Terminal: Terminal,
  Globe: Globe,
  Github: Github,
  MessageSquare: MessageSquare,
  LayoutList: LayoutList,
  GitBranch: GitBranch,
  HardDrive: HardDrive,
};

function getIconForNode(node: LedgerNode): LucideIcon {
  // 1. Exact match from Python-provided iconType
  if (staticIconMap[node.iconType]) return staticIconMap[node.iconType];

  // 2. Fuzzy match on title/description for dynamic MCP tools
  const hint = `${node.title} ${node.description}`.toLowerCase();
  if (hint.includes("github") || hint.includes("pr") || hint.includes("issue"))
    return Github;
  if (hint.includes("puppeteer") || hint.includes("fetch") || hint.includes("web") || hint.includes("browse"))
    return Globe;
  if (hint.includes("slack") || hint.includes("message") || hint.includes("chat"))
    return MessageSquare;
  if (hint.includes("linear") || hint.includes("jira") || hint.includes("kanban") || hint.includes("ticket"))
    return LayoutList;
  if (hint.includes("postgres") || hint.includes("database") || hint.includes("sql") || hint.includes("db"))
    return Database;
  if (hint.includes("git") || hint.includes("branch") || hint.includes("commit"))
    return GitBranch;
  if (hint.includes("filesystem") || hint.includes("file") || hint.includes("disk"))
    return HardDrive;
  if (hint.includes("propose") || hint.includes("code") || hint.includes("edit"))
    return FileCode2;

  return Terminal;
}

const DagNode = ({ node }: { node: LedgerNode }) => {
  const Icon = getIconForNode(node);

  return (
    <div
      className={`relative flex flex-col items-center p-4 rounded-xl border-2 transition-all duration-300 w-32 ${
        node.status === "active"
          ? "bg-emerald-950/40 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)] animate-pulse"
          : node.status === "completed"
            ? "bg-zinc-900 border-emerald-500/30 text-emerald-400"
            : "bg-zinc-950 border-zinc-800 text-zinc-500"
      }`}
    >
      <Icon
        className={`w-8 h-8 mb-2 ${node.status === "active" ? "text-emerald-400" : ""}`}
      />
      <h3 className="text-sm font-bold tracking-wide text-center">
        {node.title}
      </h3>
      <p className="text-xs mt-1 text-center opacity-80">{node.description}</p>
    </div>
  );
};

export function VisualLedger({ state }: { state: LedgerState | null }) {
  if (!state) return null;

  return (
    <div className="fixed top-24 left-1/2 -translate-x-1/2 z-40 w-full max-w-4xl p-6 bg-zinc-950/95 border border-zinc-800 rounded-2xl backdrop-blur-xl shadow-2xl animate-in slide-in-from-top-4 fade-in duration-300">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-mono text-emerald-500 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5" />
          Intent Ledger:{" "}
          <span className="text-zinc-300">{state.domain}</span>
        </h2>
        <span className="text-xs uppercase tracking-widest text-emerald-500 bg-emerald-500/10 px-3 py-1 rounded-full">
          Pipeline Active
        </span>
      </div>

      <div className="flex items-center justify-center gap-4">
        {state.nodes.map((node, index) => (
          <div key={node.id} className="flex items-center gap-4">
            <DagNode node={node} />
            {index < state.nodes.length - 1 && (
              <ArrowRight
                className={`w-6 h-6 ${node.status === "completed" ? "text-emerald-500/50" : "text-zinc-800"}`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
