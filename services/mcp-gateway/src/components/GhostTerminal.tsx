import { useEffect, useRef } from "react";
import { TerminalOutput } from "@/hooks/use-voco-socket";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

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
    <div className="fixed bottom-4 right-4 w-[420px] max-w-[calc(100vw-2rem)] max-h-[300px] bg-zinc-950/95 backdrop-blur-xl border border-zinc-800 rounded-lg shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-300">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-zinc-400 font-mono ml-2">
            Voco Terminal
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={`${scopeColors[scope]} text-xs border`}>
            {scope.toUpperCase()}
          </Badge>
          {onClose && (
            <button
              onClick={onClose}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
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

      <div className="px-3 py-1.5 font-mono text-xs">
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="text-voco-cyan">$</span>
          <span className="text-zinc-400">{output.command}</span>
        </div>
      </div>

      <ScrollArea className="h-[180px] px-3 pb-3">
        <div ref={scrollRef} className="font-mono text-xs">
          {output.isLoading && (
            <div className="flex items-center gap-2 text-zinc-500 py-2">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
              <span className="text-zinc-500 text-xs">Searching...</span>
            </div>
          )}

          {output.error && (
            <div className="text-red-400 py-2 whitespace-pre-wrap">
              <span className="text-red-500">error:</span> {output.error}
            </div>
          )}

          {output.output && (
            <pre className="text-zinc-300 py-1 whitespace-pre-wrap leading-snug text-xs">
              {output.output}
            </pre>
          )}

          {!output.isLoading && !output.error && !output.output && (
            <div className="text-zinc-600 py-2 text-xs">No output</div>
          )}
        </div>
      </ScrollArea>

      <div className="px-4 py-2 border-t border-zinc-800/50 bg-zinc-900/30">
        <div className="flex items-center justify-between text-xs text-zinc-600">
          <span>Press Esc to close</span>
          <span className="font-mono">
            {scope === "local" ? "ripgrep" : scope === "web" ? "WebMCP" : "hybrid"}
          </span>
        </div>
      </div>
    </div>
  );
}
