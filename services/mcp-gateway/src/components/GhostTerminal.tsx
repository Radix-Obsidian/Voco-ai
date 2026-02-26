import { useEffect, useRef } from "react";
import { TerminalOutput } from "@/hooks/use-voco-socket";
import { Badge } from "@/components/ui/badge";

interface GhostTerminalProps {
  output: TerminalOutput | null;
  onClose?: () => void;
}

export function GhostTerminal({ output, onClose }: GhostTerminalProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [output?.output]);

  if (!output) return null;

  const scope = output.scope ?? "local";

  const scopeColors = {
    local: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    web: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    hybrid: "bg-voco-cyan/20 text-voco-cyan border-voco-cyan/30",
  };

  return (
    <div className="w-full rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden animate-in fade-in duration-200 flex flex-col min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-y-2 px-4 py-3 border-b border-zinc-800/60 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0 pr-2">
          <div className="flex gap-1.5 shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/80" />
          </div>
          <span className="text-[11px] text-zinc-400 font-mono ml-1 shrink-0">
            Terminal
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="outline" className={`${scopeColors[scope]} text-[10px] border px-2 py-0.5`}>
            {scope.toUpperCase()}
          </Badge>
          {onClose && (
            <button
              onClick={onClose}
              className="flex items-center justify-center w-6 h-6 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-all duration-150"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="px-4 py-2 font-mono text-xs border-b border-zinc-800/30 min-w-0">
        <div className="flex items-center gap-2 text-zinc-300 min-w-0 break-all">
          <span className="text-voco-cyan shrink-0">$</span>
          <span className="text-zinc-400 min-w-0 break-words">{output.command}</span>
        </div>
      </div>

      <div className="overflow-y-auto px-4 py-3 flex-1 min-h-0 max-h-[50vh]">
        <div ref={scrollRef} className="font-mono text-xs leading-relaxed min-w-0">
          {output.isLoading && (
            <div className="flex items-center gap-2.5 text-zinc-500 py-2">
              <div className="flex gap-1 shrink-0">
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
              <span className="text-zinc-500 text-xs shrink-0">Searching...</span>
            </div>
          )}

          {output.error && (
            <div className="text-red-400 py-2 whitespace-pre-wrap break-words text-xs min-w-0">
              <span className="text-red-500 font-semibold shrink-0">error:</span> {output.error}
            </div>
          )}

          {output.output && (
            <pre className="text-zinc-300 py-1 whitespace-pre-wrap break-words leading-relaxed text-xs min-w-0 w-full">
              {output.output}
            </pre>
          )}

          {!output.isLoading && !output.error && !output.output && (
            <div className="text-zinc-600 py-2 text-xs min-w-0">No output</div>
          )}
        </div>
      </div>

      <div className="px-4 py-2.5 border-t border-zinc-800/40 shrink-0 min-w-0">
        <div className="flex flex-wrap gap-y-1 items-center justify-between text-[11px] text-zinc-600">
          <span className="shrink-0">Esc to dismiss</span>
          <span className="font-mono text-zinc-500 shrink-0">
            {scope === "local" ? "ripgrep" : scope === "web" ? "WebMCP" : "hybrid"}
          </span>
        </div>
      </div>
    </div>
  );
}
