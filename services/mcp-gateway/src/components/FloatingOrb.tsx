import { useEffect, useState, useCallback, useRef } from "react";
import vocoIcon from "@/assets/voco-icon.png";

interface OrbState {
  isConnected: boolean;
  isListening: boolean;
  bargeInActive: boolean;
  bridgeTtsActive: boolean;
  liveTranscript: string;
  dictationMode: "voco" | "app";
}

export function FloatingOrb() {
  const [state, setState] = useState<OrbState>({
    isConnected: false,
    isListening: false,
    bargeInActive: false,
    bridgeTtsActive: false,
    liveTranscript: "",
    dictationMode: "voco",
  });
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Listen for state updates from the main window
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    import("@tauri-apps/api/event").then(({ listen }) => {
      listen<OrbState>("voco://orb-state", (event) => {
        setState(event.payload);
      }).then((fn) => {
        unlisten = fn;
      });
    });
    return () => unlisten?.();
  }, []);

  // Close context menu on outside click
  useEffect(() => {
    if (!showMenu) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showMenu]);

  const handleClick = useCallback(() => {
    import("@tauri-apps/api/event").then(({ emit }) => {
      if (state.bridgeTtsActive) {
        emit("voco://orb-barge-in", {});
      } else {
        emit("voco://orb-toggle-mic", {});
      }
    });
  }, [state.bridgeTtsActive]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setShowMenu(true);
  }, []);

  const handleShowMain = useCallback(() => {
    setShowMenu(false);
    import("@tauri-apps/api/core").then(({ invoke }) => {
      invoke("show_main_window");
    });
  }, []);

  const handleToggleDictation = useCallback(() => {
    setShowMenu(false);
    import("@tauri-apps/api/event").then(({ emit }) => {
      emit("voco://toggle-dictation-mode", {});
    });
  }, []);

  const handleQuit = useCallback(() => {
    import("@tauri-apps/api/core").then(({ invoke }) => {
      invoke("quit_app");
    });
  }, []);

  const handleDragStart = useCallback(() => {
    import("@tauri-apps/api/window").then(({ getCurrentWindow }) => {
      getCurrentWindow().startDragging();
    });
  }, []);

  if (!state.isConnected) {
    return null;
  }

  return (
    <div className="fixed inset-0" style={{ background: "transparent", pointerEvents: "none" }}>
      <div
        className="absolute bottom-2 left-1/2 -translate-x-1/2"
        style={{ pointerEvents: "auto" }}
      >
        {/* Drag handle — outer ring area */}
        <div
          onMouseDown={handleDragStart}
          className="relative flex items-center justify-center w-[80px] h-[80px] cursor-move"
        >
          {/* The Orb Button */}
          <button
            onClick={handleClick}
            onContextMenu={handleContextMenu}
            onMouseDown={(e) => e.stopPropagation()}
            className={`
              relative flex items-center justify-center w-16 h-16 rounded-full
              bg-[#0D0D0D] border border-white/[0.06]
              transition-all duration-500 cursor-pointer
              ${state.isListening
                ? state.dictationMode === "app"
                  ? "animate-orb-listening shadow-[0_0_25px_rgba(59,130,246,0.5)]"
                  : "animate-orb-listening shadow-[0_0_25px_rgba(239,68,68,0.5)]"
                : "animate-orb-pulse shadow-voco-glow hover:shadow-voco-glow-lg"
              }
              ${state.bargeInActive ? "!shadow-[0_0_30px_rgba(239,68,68,0.5)]" : ""}
              ${state.bridgeTtsActive ? "!shadow-[0_0_20px_rgba(59,130,246,0.5)] animate-pulse" : ""}
            `}
          >
            <div
              className={`
                absolute inset-1.5 rounded-full border transition-all duration-500
                ${state.isListening
                  ? state.dictationMode === "app"
                    ? "border-blue-500/40 bg-blue-500/[0.08]"
                    : "border-red-500/40 bg-red-500/[0.08]"
                  : "border-voco-green/30 bg-voco-green/[0.04]"
                }
              `}
            />
            <img
              src={vocoIcon}
              alt="Voco"
              className={`w-6 h-6 relative z-10 transition-opacity duration-300 ${state.isListening ? "opacity-100" : "opacity-80"}`}
            />
          </button>
        </div>

        {/* Live transcript tooltip */}
        {state.liveTranscript && state.isListening && (
          <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 whitespace-nowrap max-w-[200px] truncate px-3 py-1.5 rounded-lg bg-black/90 text-xs text-zinc-300 border border-white/[0.06]">
            &ldquo;{state.liveTranscript}&rdquo;
          </div>
        )}

        {/* Context menu */}
        {showMenu && (
          <div
            ref={menuRef}
            className="absolute bottom-full mb-2 right-0 min-w-[140px] bg-[#1a1a1a] border border-white/[0.08] rounded-lg shadow-xl overflow-hidden z-50"
          >
            <button
              onClick={handleToggleDictation}
              className="w-full px-4 py-2.5 text-left text-sm text-zinc-300 hover:bg-white/[0.06] transition-colors"
            >
              {state.dictationMode === "app" ? "Dictate to Voco" : "Dictate to App"}
            </button>
            <button
              onClick={handleShowMain}
              className="w-full px-4 py-2.5 text-left text-sm text-zinc-300 hover:bg-white/[0.06] transition-colors"
            >
              Show Voco
            </button>
            <button
              onClick={handleQuit}
              className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-white/[0.06] transition-colors"
            >
              Quit
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
