import { useState } from "react";
import { X, ExternalLink, RefreshCw } from "lucide-react";

interface SandboxPreviewProps {
  url: string;
  refreshKey: number;
  onClose: () => void;
}

export function SandboxPreview({ url, refreshKey, onClose }: SandboxPreviewProps) {
  const [isLoading, setIsLoading] = useState(true);

  const handleRefresh = () => {
    setIsLoading(true);
    // Bumping the key is handled by the parent via refreshKey prop;
    // this button lets the user manually force a reload.
    const iframe = document.querySelector<HTMLIFrameElement>("#voco-sandbox-iframe");
    if (iframe) {
      iframe.src = iframe.src;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#080808] border-l border-white/[0.05]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.05] shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-voco-green animate-pulse" />
          <span className="text-xs text-zinc-400 font-mono tracking-wide">live sandbox</span>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-zinc-600 hover:text-zinc-300 transition-colors"
            title="Refresh sandbox"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => window.open(url, "_blank")}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-zinc-600 hover:text-zinc-300 transition-colors"
            title="Open in browser"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/[0.06] text-zinc-600 hover:text-zinc-300 transition-colors"
            title="Close sandbox"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Preview area */}
      <div className="relative flex-1 overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[#080808]">
            <RefreshCw className="w-5 h-5 text-voco-green animate-spin" />
            <span className="text-xs text-zinc-500">Rendering sandbox…</span>
          </div>
        )}
        <iframe
          id="voco-sandbox-iframe"
          key={refreshKey}
          src={url}
          title="Voco Live Sandbox"
          className="w-full h-full"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          onLoad={() => setIsLoading(false)}
        />
      </div>
    </div>
  );
}
