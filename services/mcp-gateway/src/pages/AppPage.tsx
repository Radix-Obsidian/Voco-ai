import { useEffect, useState, useCallback } from "react";
import Header from "@/components/Header";
import { useVocoSocket } from "@/hooks/use-voco-socket";
import { useAudioCapture } from "@/hooks/use-audio-capture";
import { useSettings } from "@/hooks/use-settings";
import { GhostTerminal } from "@/components/GhostTerminal";
import { ReviewDeck } from "@/components/ReviewDeck";
import { CommandApproval } from "@/components/CommandApproval";
import { VisualLedger } from "@/components/VisualLedger";
import { SettingsModal } from "@/components/SettingsModal";
import { PricingModal } from "@/components/PricingModal";
import { OnboardingTour } from "@/components/OnboardingTour";
import { Mic, Send, ArrowRight } from "lucide-react";

const AppPage = () => {
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
  } = useVocoSocket();

  const { settings, updateSetting, hasRequiredKeys, pushToBackend, saveSettings } = useSettings();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pricingOpen, setPricingOpen] = useState(false);
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

  useEffect(() => {
    if (!hasRequiredKeys) {
      setSettingsOpen(true);
    }
  }, [hasRequiredKeys]);

  // Auto-start mic in speak mode when connected
  useEffect(() => {
    if (mode === "speak" && isConnected && hasRequiredKeys && !isCapturing) {
      startCapture();
    }
    if (mode === "type" && isCapturing) {
      stopCapture();
    }
  }, [mode, isConnected, hasRequiredKeys]);

  const handleCloseTerminal = () => setTerminalOutput(null);

  const handleSettingsSave = () => {
    saveSettings();                   // persist to OS config file
    pushToBackend(wsRef.current);     // push to Python over WebSocket
  };

  // Auto-push keys whenever the WebSocket (re)connects so Python always has them.
  useEffect(() => {
    if (isConnected) pushToBackend(wsRef.current);
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

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

  return (
    <div className="noise-overlay min-h-screen bg-background text-foreground relative">
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

      <PricingModal open={pricingOpen} onOpenChange={setPricingOpen} />

      {/* Main interaction area */}
      <main
        className={`flex flex-col items-center justify-center min-h-screen px-6 transition-all duration-300 ${
          !hasRequiredKeys ? "blur-sm pointer-events-none select-none opacity-50" : ""
        }`}
      >
        {mode === "speak" ? (
          /* ====== VOICE MODE: The Orb ====== */
          <div className="flex flex-col items-center gap-8">
            {/* Connection status dot */}
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-voco-emerald" : "bg-red-500"}`} />
              <span>{isConnected ? "Connected" : "Connecting..."}</span>
            </div>

            {/* The Orb */}
            <button
              onClick={() => {
                if (isCapturing) stopCapture();
                else startCapture();
              }}
              disabled={!isConnected}
              className={`
                relative flex items-center justify-center w-32 h-32 rounded-full
                bg-[#0D0D0D] border border-white/[0.06]
                transition-all duration-500 cursor-pointer
                ${isCapturing
                  ? "animate-orb-listening shadow-emerald-glow-lg"
                  : "animate-orb-pulse hover:shadow-emerald-glow"
                }
                ${bargeInActive ? "!shadow-[0_0_40px_rgba(239,68,68,0.5)]" : ""}
                disabled:opacity-30 disabled:cursor-not-allowed
              `}
            >
              {/* Inner glow ring */}
              <div className={`
                absolute inset-2 rounded-full border transition-all duration-500
                ${isCapturing
                  ? "border-voco-emerald/40 bg-voco-emerald/[0.06]"
                  : "border-white/[0.04] bg-transparent"
                }
              `} />

              {/* Mic icon */}
              <Mic className={`
                w-8 h-8 relative z-10 transition-colors duration-300
                ${isCapturing ? "text-voco-emerald" : "text-zinc-500"}
              `} />
            </button>

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
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        ) : (
          /* ====== TEXT MODE ====== */
          <div className="flex flex-col items-center gap-6 w-full max-w-xl">
            {/* Connection dot */}
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-voco-emerald" : "bg-red-500"}`} />
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
                className="w-full resize-none rounded-xl bg-[#111] border border-white/[0.06] text-sm text-zinc-200 placeholder-zinc-600 p-4 pr-12 focus:outline-none focus:border-voco-emerald/30 focus:shadow-emerald-glow-sm transition-all"
              />
              <button
                onClick={handleSendText}
                disabled={!textInput.trim() || !isConnected}
                className="absolute bottom-3 right-3 flex items-center justify-center w-8 h-8 rounded-lg bg-voco-emerald text-black hover:bg-voco-emerald/90 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
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
            </button>
          </div>
        )}
      </main>

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
    </div>
  );
};

export default AppPage;
