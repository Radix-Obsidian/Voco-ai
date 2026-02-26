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
  Loader2,
  CheckCircle2,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { LedgerState, LedgerNode, BackgroundJob } from "@/hooks/use-voco-socket";

// ---------------------------------------------------------------------------
// Icon resolution
// ---------------------------------------------------------------------------

const staticIconMap: Record<string, LucideIcon> = {
  Database,
  FileCode2,
  Terminal,
  Globe,
  Github,
  MessageSquare,
  LayoutList,
  GitBranch,
  HardDrive,
};

function getIconForNode(node: LedgerNode): LucideIcon {
  if (staticIconMap[node.iconType]) return staticIconMap[node.iconType];
  const hint = `${node.title} ${node.description}`.toLowerCase();
  if (hint.includes("github") || hint.includes("pr") || hint.includes("issue")) return Github;
  if (hint.includes("puppeteer") || hint.includes("fetch") || hint.includes("web") || hint.includes("browse")) return Globe;
  if (hint.includes("slack") || hint.includes("message") || hint.includes("chat")) return MessageSquare;
  if (hint.includes("linear") || hint.includes("jira") || hint.includes("kanban") || hint.includes("ticket")) return LayoutList;
  if (hint.includes("postgres") || hint.includes("database") || hint.includes("sql") || hint.includes("db")) return Database;
  if (hint.includes("git") || hint.includes("branch") || hint.includes("commit")) return GitBranch;
  if (hint.includes("filesystem") || hint.includes("file") || hint.includes("disk")) return HardDrive;
  if (hint.includes("propose") || hint.includes("code") || hint.includes("edit")) return FileCode2;
  return Terminal;
}

function getIconForJob(toolName: string): LucideIcon {
  const hint = toolName.toLowerCase();
  if (hint.includes("search")) return FileCode2;
  if (hint.includes("github") || hint.includes("pr") || hint.includes("issue")) return Github;
  if (hint.includes("web") || hint.includes("fetch") || hint.includes("puppeteer")) return Globe;
  if (hint.includes("database") || hint.includes("sql") || hint.includes("db")) return Database;
  if (hint.includes("git")) return GitBranch;
  return Terminal;
}

// ---------------------------------------------------------------------------
// Status indicator — the core visual upgrade (Milestone 11)
// ---------------------------------------------------------------------------

function StatusIndicator({ status }: { status: LedgerNode["status"] }) {
  switch (status) {
    case "active":
      return <Loader2 className="w-5 h-5 text-primary animate-spin flex-shrink-0" />;
    case "completed":
      return <CheckCircle2 className="w-5 h-5 text-voco-cyan flex-shrink-0" />;
    case "failed":
      return <XCircle className="w-5 h-5 text-destructive animate-pulse flex-shrink-0" />;
    default: // pending
      return (
        <div className="w-5 h-5 rounded-full border-2 border-dashed border-muted-foreground flex-shrink-0 animate-[spin_3s_linear_infinite]" />
      );
  }
}

// ---------------------------------------------------------------------------
// Pipeline DAG node (synchronous / current turn)
// ---------------------------------------------------------------------------

const DagNode = ({ node }: { node: LedgerNode }) => {
  const Icon = getIconForNode(node);
  const isActive = node.status === "active";
  const isCompleted = node.status === "completed";
  const isFailed = node.status === "failed";

  return (
    <div
      className={[
        "relative flex flex-col items-center p-3 rounded-xl border transition-all duration-500 min-w-[72px] max-w-[100px] flex-1 shrink-0 overflow-hidden",
        isActive
          ? "border-primary/50 bg-primary/5 shadow-[0_0_20px_rgba(0,255,170,0.15)]"
          : isCompleted
          ? "bg-zinc-900/80 border-voco-cyan/30 text-voco-cyan"
          : isFailed
          ? "border-destructive/50 bg-destructive/5 text-destructive"
          : "bg-zinc-900/40 border-zinc-800 text-zinc-500",
      ].join(" ")}
    >
      <Icon
        className={`w-5 h-5 mb-1.5 shrink-0 ${
          isActive ? "text-primary" : isCompleted ? "text-voco-cyan" : isFailed ? "text-destructive" : "text-zinc-600"
        }`}
      />
      <h3 className="text-[11px] font-semibold tracking-wide text-center leading-tight truncate w-full">{node.title}</h3>
      <p className="text-[10px] mt-1 text-center opacity-70 leading-tight truncate w-full">
        {isActive ? "Running…" : node.description}
      </p>

      {/* Sliding progress bar for active nodes */}
      {isActive && (
        <div className="absolute bottom-0 left-0 h-[2px] w-full bg-primary/10 overflow-hidden">
          <div className="h-full w-1/3 bg-primary animate-progress-slide" />
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Background job strip — persists across turns while jobs are still running
// ---------------------------------------------------------------------------

const BackgroundJobCard = ({ job }: { job: BackgroundJob }) => {
  const Icon = getIconForJob(job.tool_name);
  const isRunning = job.status === "running";

  return (
    <div
      className={[
        "relative flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-500 overflow-hidden",
        isRunning
          ? "border-primary/40 bg-primary/5 shadow-[0_0_12px_rgba(0,255,170,0.1)]"
          : "border-voco-cyan/30 bg-zinc-900",
      ].join(" ")}
    >
      <div className={`p-1.5 rounded-lg ${isRunning ? "bg-primary/10" : "bg-voco-cyan/10"}`}>
        <Icon className={`w-4 h-4 ${isRunning ? "text-primary" : "text-voco-cyan"}`} />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-foreground truncate">{job.tool_name}</p>
        <p className="text-xs text-muted-foreground">
          {isRunning ? "Running in background…" : "Complete"}
        </p>
      </div>

      {isRunning ? (
        <Loader2 className="w-4 h-4 text-primary animate-spin flex-shrink-0" />
      ) : (
        <CheckCircle2 className="w-4 h-4 text-voco-cyan flex-shrink-0" />
      )}

      {/* Sliding progress bar */}
      {isRunning && (
        <div className="absolute bottom-0 left-0 h-[2px] w-full bg-primary/10 overflow-hidden">
          <div className="h-full w-1/3 bg-primary animate-progress-slide" />
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface VisualLedgerProps {
  state: LedgerState | null;
  backgroundJobs: BackgroundJob[];
}

export function VisualLedger({ state, backgroundJobs }: VisualLedgerProps) {
  const hasBackgroundJobs = backgroundJobs.length > 0;
  if (!state && !hasBackgroundJobs) return null;

  return (
    <div className="w-full animate-in fade-in duration-200">

      {/* ── Pipeline header ── */}
      {state && (
        <>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[11px] font-medium uppercase tracking-widest text-voco-cyan flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              <span>Intent Ledger</span>
              <span className="text-zinc-400 normal-case tracking-normal font-normal">
                {state.domain}
              </span>
            </h2>
            <span className="text-[10px] uppercase tracking-widest text-voco-cyan bg-voco-cyan/10 px-2.5 py-1 rounded-full font-medium">
              Active
            </span>
          </div>

          {/* ── DAG pipeline row ── */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {state.nodes.map((node, index) => (
              <div key={node.id} className="flex items-center gap-2">
                <DagNode node={node} />
                {index < state.nodes.length - 1 && (
                  <ArrowRight
                    className={`w-4 h-4 flex-shrink-0 ${
                      node.status === "completed" ? "text-voco-cyan/50" : "text-zinc-800"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Background jobs strip ── */}
      {hasBackgroundJobs && (
        <div className={state ? "mt-4 pt-4 border-t border-zinc-800/60" : ""}>
          <p className="text-[11px] uppercase tracking-widest text-zinc-500 mb-3 font-medium">
            Background Queue
          </p>
          <div className="flex flex-col gap-2">
            {backgroundJobs.map((job) => (
              <BackgroundJobCard key={job.job_id} job={job} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
