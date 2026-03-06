import { useEffect, useRef, useState } from "react";
import { Square, Maximize2, Minimize2, ChevronDown, ChevronUp, Monitor } from "lucide-react";

export interface OrgoSandboxState {
  computerId: string;
  status: "booting" | "running" | "stopped";
  vncUrl: string | null;
  vncPassword: string | null;
  commandHistory: Array<{ command: string; output: string; timestamp: number }>;
}

interface OrgoSandboxViewProps {
  sandbox: OrgoSandboxState;
  onClose: () => void;
}

export function OrgoSandboxView({ sandbox, onClose }: OrgoSandboxViewProps) {
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<unknown>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showTerminal, setShowTerminal] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal to bottom
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [sandbox.commandHistory]);

  // Initialize noVNC connection
  useEffect(() => {
    if (!sandbox.vncUrl || !sandbox.vncPassword || !canvasContainerRef.current) {
      return;
    }

    let rfb: { disconnect: () => void } | null = null;

    const connectVnc = async () => {
      try {
        // Dynamic import of noVNC
        const { default: RFB } = await import("@novnc/novnc/core/rfb.js");

        setConnectionStatus("connecting");

        rfb = new RFB(canvasContainerRef.current!, sandbox.vncUrl!, {
          credentials: { password: sandbox.vncPassword! },
        });

        rfb.scaleViewport = true;
        rfb.resizeSession = true;
        rfb.background = "#080808";

        rfb.addEventListener("connect", () => {
          setConnectionStatus("connected");
        });

        rfb.addEventListener("disconnect", () => {
          setConnectionStatus("disconnected");
        });

        rfbRef.current = rfb;
      } catch (err) {
        console.error("[OrgoSandbox] Failed to initialize noVNC:", err);
        setConnectionStatus("disconnected");
      }
    };

    connectVnc();

    return () => {
      if (rfb) {
        try {
          rfb.disconnect();
        } catch {
          // Ignore cleanup errors
        }
      }
      rfbRef.current = null;
    };
  }, [sandbox.vncUrl, sandbox.vncPassword]);

  const handleFullscreen = () => {
    if (!canvasContainerRef.current) return;
    if (!isFullscreen) {
      canvasContainerRef.current.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div className="flex flex-col h-full bg-[#080808] border-l border-white/[0.05]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.05] shrink-0">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connectionStatus === "connected"
                ? "bg-voco-green animate-pulse"
                : connectionStatus === "connecting"
                ? "bg-yellow-500 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <Monitor className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-xs text-zinc-400 font-mono tracking-wide">cloud sandbox</span>
          <span className="text-[10px] text-zinc-600 font-mono">{sandbox.computerId.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => setShowTerminal(!showTerminal)}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-zinc-600 hover:text-zinc-300 transition-colors"
            title={showTerminal ? "Hide terminal" : "Show terminal"}
          >
            {showTerminal ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={handleFullscreen}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-zinc-600 hover:text-zinc-300 transition-colors"
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-red-600 hover:text-red-400 transition-colors"
            title="Stop sandbox"
          >
            <Square className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* VNC Desktop Stream */}
      <div ref={canvasContainerRef} className="relative flex-1 overflow-hidden bg-[#080808]">
        {sandbox.status === "booting" && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[#080808]">
            <Monitor className="w-6 h-6 text-voco-green animate-pulse" />
            <span className="text-xs text-zinc-500">Booting cloud sandbox...</span>
          </div>
        )}
        {connectionStatus === "disconnected" && sandbox.status === "running" && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[#080808]/80">
            <span className="text-xs text-zinc-500">VNC connection lost</span>
            <button
              onClick={() => {
                // Force reconnect by re-mounting
                setConnectionStatus("connecting");
              }}
              className="text-xs text-voco-green hover:underline"
            >
              Retry connection
            </button>
          </div>
        )}
      </div>

      {/* Command output terminal */}
      {showTerminal && sandbox.commandHistory.length > 0 && (
        <div className="border-t border-white/[0.05] max-h-[200px] overflow-y-auto bg-[#0a0a0a]">
          <div className="px-3 py-1.5 text-[10px] text-zinc-600 font-mono uppercase tracking-wider border-b border-white/[0.03]">
            Terminal Output
          </div>
          <div className="p-2 space-y-2">
            {sandbox.commandHistory.map((entry, idx) => (
              <div key={idx} className="text-xs font-mono">
                <div className="text-voco-green">$ {entry.command}</div>
                {entry.output && (
                  <pre className="text-zinc-500 whitespace-pre-wrap break-all mt-0.5 max-h-[80px] overflow-y-auto">
                    {entry.output}
                  </pre>
                )}
              </div>
            ))}
            <div ref={terminalEndRef} />
          </div>
        </div>
      )}
    </div>
  );
}
