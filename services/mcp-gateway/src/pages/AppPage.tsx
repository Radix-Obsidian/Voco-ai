import { useEffect, useState, useCallback, useRef } from "react";
import Header from "@/components/Header";
import { useVocoSocket, type TerminalOutput } from "@/hooks/use-voco-socket";
import { useAudioCapture } from "@/hooks/use-audio-capture";
import { useSettings } from "@/hooks/use-settings";
import { GhostTerminal } from "@/components/GhostTerminal";
import { ReviewDeck } from "@/components/ReviewDeck";
import { CommandApproval } from "@/components/CommandApproval";
import { VisualLedger } from "@/components/VisualLedger";
import { SettingsModal } from "@/components/SettingsModal";
import { PricingModal } from "@/components/PricingModal";
import { OnboardingTour } from "@/components/OnboardingTour";
import { SandboxPreview } from "@/components/SandboxPreview";
import { FeedbackWidget } from "@/components/FeedbackWidget";
import { Mic, Send } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useAppUpdater } from "@/hooks/use-app-updater";
import { useDemoMode } from "@/hooks/use-demo-mode";

const isDemoMode = new URLSearchParams(window.location.search).get("demo") === "true";

const AppPage = () => {
  const liveSocket = useVocoSocket();
  const demoSocket = useDemoMode();
  const {
    isConnected,
    bargeInActive,
    sendAudioChunk,
    connect,
    disconnect,
    terminalOutput,
    setTerminalOutput,
    proposals,
    commandProposals,
    submitProposalDecisions,
    submitCommandDecisions,
    ledgerState,
    backgroundJobs,
    wsRef,
    sandboxUrl,
    sandboxRefreshKey,
    setSandboxUrl,
    sendAuthSync,
    liveTranscript,
  } = isDemoMode ? demoSocket : liveSocket;

  const { settings, updateSetting, hasRequiredKeys, pushToBackend, saveSettings } = useSettings();
  const { session } = useAuth();
  useAppUpdater();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pricingOpen, setPricingOpen] = useState(false);

  // Turn counter — persisted to localStorage, enforces 50-turn free cap
  const FREE_TURN_LIMIT = 50;
  const [turnCount, setTurnCount] = useState<number>(() => {
    return parseInt(localStorage.getItem("voco-free-turns") ?? "0", 10);
  });
  const userTier: string = localStorage.getItem("voco-tier") ?? "free";
  const atTurnLimit = !isDemoMode && userTier === "free" && turnCount >= FREE_TURN_LIMIT;
  const prevTerminalOutput = useRef<TerminalOutput | null>(null);
  const [mode, setMode] = useState<"speak" | "type">("speak");
  const [textInput, setTextInput] = useState("");
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem("voco-onboarding-done");
  });

  const { isCapturing, startCapture, stopCapture } =
    useAudioCapture(isConnected ? sendAudioChunk : null);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const needsKeys = !isDemoMode && !hasRequiredKeys;
  useEffect(() => {
    if (needsKeys) {
      const id = requestAnimationFrame(() => setSettingsOpen(true));
      return () => cancelAnimationFrame(id);
    }
  }, [needsKeys]);

  // Increment turn counter when a new AI response arrives (terminalOutput transitions to non-null)
  useEffect(() => {
    if (terminalOutput !== null && prevTerminalOutput.current === null) {
      setTurnCount((prev) => {
        const next = prev + 1;
        localStorage.setItem("voco-free-turns", String(next));
        return next;
      });
    }
    prevTerminalOutput.current = terminalOutput;
  }, [terminalOutput]);

  // Force paywall when free user hits the limit
  useEffect(() => {
    if (atTurnLimit) {
      setPricingOpen(true);
      if (isCapturing) stopCapture();
    }
  }, [atTurnLimit]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-start mic in speak mode when connected
  useEffect(() => {
    if (mode === "speak" && isConnected && hasRequiredKeys && !isCapturing && !atTurnLimit) {
      startCapture();
    }
    if (mode === "type" && isCapturing) {
      stopCapture();
    }
  }, [mode, isConnected, hasRequiredKeys]);

  const handleCloseTerminal = () => setTerminalOutput(null);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      // Cmd/Ctrl+K — toggle voice/text mode
      if (mod && e.key === "k") {
        e.preventDefault();
        setMode((prev) => (prev === "speak" ? "type" : "speak"));
      }
      // Cmd/Ctrl+, — open settings
      if (mod && e.key === ",") {
        e.preventDefault();
        setSettingsOpen(true);
      }
      // Escape — close modals / stop capture
      if (e.key === "Escape") {
        if (settingsOpen) setSettingsOpen(false);
        else if (pricingOpen && !atTurnLimit) setPricingOpen(false); // blocked when forced paywall
        else if (isCapturing) stopCapture();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [settingsOpen, pricingOpen, isCapturing, stopCapture]);

  const handleSettingsSave = () => {
    saveSettings();                   // persist to OS config file
    pushToBackend(wsRef.current);     // push to Python over WebSocket
  };

  // Auto-push keys whenever the WebSocket (re)connects so Python always has them.
  useEffect(() => {
    if (isConnected) pushToBackend(wsRef.current);
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Send auth session to Python backend whenever WS connects or session changes.
  useEffect(() => {
    if (isConnected && session?.access_token && session.user?.id) {
      sendAuthSync(session.access_token, session.user.id, session.refresh_token);
    }
  }, [isConnected, session, sendAuthSync]);

  const handleSendText = useCallback(() => {
    if (!textInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "text_input", text: textInput.trim() }));
    setTextInput("");
  }, [textInput, wsRef]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  const renderOverlay = () => {
    if (commandProposals.length > 0) {
      return <CommandApproval commands={commandProposals} onSubmitDecisions={submitCommandDecisions} />;
    }
    if (proposals.length > 0) {
      return <ReviewDeck proposals={proposals} onSubmitDecisions={submitProposalDecisions} />;
    }
    return <GhostTerminal output={terminalOutput} onClose={handleCloseTerminal} />;
  };

  const isSandboxActive = !!sandboxUrl;

  /* ====== Voice / Text panel (shared between both layout modes) ====== */
  const voiceTextPanel = (
    <main
      className={`flex flex-col items-center justify-center px-6 transition-all duration-500
        ${isSandboxActive ? "w-[420px] min-w-[340px] shrink-0 h-full" : "min-h-screen flex-1"}
        ${!isDemoMode && !hasRequiredKeys ? "blur-sm pointer-events-none select-none opacity-50" : ""}
      `}
    >
      {mode === "speak" ? (
        /* ====== VOICE MODE: The Orb ====== */
        <div className="flex flex-col items-center gap-8">
          {/* Connection status dot */}
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-voco-green" : "bg-red-500"}`} />
            <span>{isConnected ? "Connected" : "Connecting..."}</span>
          </div>

          {/* The Orb */}
          <button
            onClick={() => {
              if (isCapturing) stopCapture();
              else startCapture();
            }}
            disabled={!isConnected || atTurnLimit}
            className={`
              relative flex items-center justify-center w-32 h-32 rounded-full
              bg-[#0D0D0D] border border-white/[0.06]
              transition-all duration-500 cursor-pointer
              ${isCapturing
                ? "animate-orb-listening shadow-voco-glow-lg"
                : "animate-orb-pulse hover:shadow-voco-glow"
              }
              ${bargeInActive ? "!shadow-[0_0_40px_rgba(239,68,68,0.5)]" : ""}
              disabled:opacity-30 disabled:cursor-not-allowed
            `}
          >
            {/* Inner glow ring */}
            <div className={`
              absolute inset-2 rounded-full border transition-all duration-500
              ${isCapturing
                ? "border-voco-green/40 bg-voco-green/[0.06]"
                : "border-white/[0.04] bg-transparent"
              }
            `} />

            {/* Mic icon */}
            <Mic className={`
              w-8 h-8 relative z-10 transition-colors duration-300
              ${isCapturing ? "text-voco-green" : "text-zinc-500"}
            `} />
          </button>

          {/* Live transcript */}
          {liveTranscript && isCapturing && (
            <p className="text-sm text-zinc-300 max-w-sm text-center italic animate-pulse">
              "{liveTranscript}"
            </p>
          )}

          {/* Status text */}
          <p className="text-sm text-zinc-500">
            {!isConnected
              ? "Connecting to Voco..."
              : isCapturing
                ? bargeInActive
                  ? "Listening for your interruption..."
                  : "Listening..."
                : "Tap to start speaking"
            }
          </p>

          {/* Mode switch */}
          <button
            onClick={() => setMode("type")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs text-zinc-500 hover:text-zinc-300 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.04] transition-all"
          >
            Type instead
            <kbd className="ml-1.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] text-zinc-600 font-mono">⌘K</kbd>
          </button>
        </div>
      ) : (
        /* ====== TEXT MODE ====== */
        <div className="flex flex-col items-center gap-6 w-full max-w-xl">
          {/* Connection dot */}
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-voco-green" : "bg-red-500"}`} />
            <span>{isConnected ? "Connected" : "Connecting..."}</span>
          </div>

          {/* Text input area */}
          <div className="relative w-full">
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Dump your raw thoughts here..."
              rows={4}
              className="w-full resize-none rounded-xl bg-[#111] border border-white/[0.06] text-sm text-zinc-200 placeholder-zinc-600 p-4 pr-12 focus:outline-none focus:border-voco-green/30 focus:shadow-voco-glow-sm transition-all"
            />
            <button
              onClick={handleSendText}
              disabled={!textInput.trim() || !isConnected}
              className="absolute bottom-3 right-3 flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-r from-voco-green to-voco-cyan text-white hover:opacity-90 transition-opacity disabled:opacity-20 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* Mode switch */}
          <button
            onClick={() => setMode("speak")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs text-zinc-500 hover:text-zinc-300 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.04] transition-all"
          >
            <Mic className="w-3 h-3" />
            Speak instead
            <kbd className="ml-1.5 px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px] text-zinc-600 font-mono">⌘K</kbd>
          </button>
        </div>
      )}
    </main>
  );

  return (
    <div className={`noise-overlay bg-background text-foreground relative
      ${isSandboxActive ? "h-screen flex flex-col overflow-hidden" : "min-h-screen"}
    `}>
      <Header
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenPricing={() => setPricingOpen(true)}
      />

      <SettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onUpdate={updateSetting}
        onSave={handleSettingsSave}
      />

      <PricingModal
        open={pricingOpen}
        onOpenChange={setPricingOpen}
        forcedOpen={atTurnLimit}
        userEmail={session?.user?.email ?? ""}
      />

      {/* Content area — single-column or split-screen depending on sandbox state */}
      {isSandboxActive ? (
        <div className="flex flex-1 overflow-hidden">
          {voiceTextPanel}
          <div className="flex-1 overflow-hidden">
            <SandboxPreview
              url={sandboxUrl!}
              refreshKey={sandboxRefreshKey}
              onClose={() => setSandboxUrl(null)}
            />
          </div>
        </div>
      ) : (
        voiceTextPanel
      )}

      <VisualLedger state={ledgerState} backgroundJobs={backgroundJobs} />
      {renderOverlay()}

      {showOnboarding && (
        <OnboardingTour
          onComplete={() => {
            setShowOnboarding(false);
            localStorage.setItem("voco-onboarding-done", "1");
          }}
        />
      )}

      <FeedbackWidget />
    </div>
  );
};

export default AppPage;
