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

const DRAG_THRESHOLD = 4; // px of movement before we switch from click → drag

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
  const draggingRef = useRef(false);
  const mouseOriginRef = useRef<{ x: number; y: number } | null>(null);

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

  // Click-vs-drag: track mouseDown origin, start OS drag only after threshold
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // left-click only
    draggingRef.current = false;
    mouseOriginRef.current = { x: e.screenX, y: e.screenY };
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const origin = mouseOriginRef.current;
      if (!origin || draggingRef.current) return;

      const dx = Math.abs(e.screenX - origin.x);
      const dy = Math.abs(e.screenY - origin.y);
      if (dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD) {
        draggingRef.current = true;
        mouseOriginRef.current = null;
        import("@tauri-apps/api/window").then(({ getCurrentWindow }) => {
          getCurrentWindow().startDragging();
        });
      }
    };

    const onUp = () => {
      mouseOriginRef.current = null;
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleClick = useCallback(() => {
    // If we just finished a drag, don't fire the click action
    if (draggingRef.current) {
      draggingRef.current = false;
      return;
    }
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

  if (!state.isConnected) {
    return null;
  }

  return (
    <div
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
      className="fixed inset-0 flex items-center justify-center cursor-grab active:cursor-grabbing"
      style={{ background: "transparent" }}
    >
      <button
        onClick={handleClick}
        className={`
          relative flex items-center justify-center w-9 h-9 rounded-full
          bg-[#0D0D0D]/90 border border-white/[0.08]
          transition-all duration-500 cursor-pointer
          ${state.isListening
            ? state.dictationMode === "app"
              ? "shadow-[0_0_16px_rgba(59,130,246,0.5)]"
              : "shadow-[0_0_16px_rgba(239,68,68,0.5)]"
            : "hover:shadow-[0_0_10px_rgba(0,255,200,0.3)]"
          }
          ${state.bargeInActive ? "!shadow-[0_0_20px_rgba(239,68,68,0.5)]" : ""}
          ${state.bridgeTtsActive ? "!shadow-[0_0_14px_rgba(59,130,246,0.5)] animate-pulse" : ""}
        `}
      >
        <div
          className={`
            absolute inset-1 rounded-full border transition-all duration-500
            ${state.isListening
              ? state.dictationMode === "app"
                ? "border-blue-500/40 bg-blue-500/[0.08]"
                : "border-red-500/40 bg-red-500/[0.08]"
              : "border-white/[0.04] bg-transparent"
            }
          `}
        />
        <img
          src={vocoIcon}
          alt="Voco"
          className={`w-4 h-4 relative z-10 transition-opacity duration-300 ${state.isListening ? "opacity-100" : "opacity-40"}`}
        />
      </button>

      {/* Context menu */}
      {showMenu && (
        <div
          ref={menuRef}
          className="absolute top-full mt-1 min-w-[130px] bg-[#1a1a1a] border border-white/[0.08] rounded-lg shadow-xl overflow-hidden z-50"
        >
          <button
            onClick={handleToggleDictation}
            className="w-full px-3 py-2 text-left text-xs text-zinc-300 hover:bg-white/[0.06] transition-colors"
          >
            {state.dictationMode === "app" ? "Dictate to Voco" : "Dictate to App"}
          </button>
          <button
            onClick={handleShowMain}
            className="w-full px-3 py-2 text-left text-xs text-zinc-300 hover:bg-white/[0.06] transition-colors"
          >
            Show Voco
          </button>
          <button
            onClick={handleQuit}
            className="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-white/[0.06] transition-colors"
          >
            Quit
          </button>
        </div>
      )}
    </div>
  );
}
