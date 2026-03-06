import { useEffect, useState, useCallback, useRef } from "react";
import Header from "@/components/Header";
import { useVocoSocket, type TerminalOutput } from "@/hooks/use-voco-socket";
import { useSettings } from "@/hooks/use-settings";
import { SidebarPanel } from "@/components/SidebarPanel";
import { SettingsModal } from "@/components/SettingsModal";
import { PricingModal } from "@/components/PricingModal";
import { OnboardingTour } from "@/components/OnboardingTour";
import { SandboxPreview } from "@/components/SandboxPreview";
import { OrgoSandboxView } from "@/components/OrgoSandboxView";
import { FeedbackWidget } from "@/components/FeedbackWidget";
import { ChatThread } from "@/components/ChatThread";
import { Send } from "lucide-react";
import vocoIcon from "@/assets/voco-icon.png";
import { useAuth } from "@/hooks/use-auth";
import { useAppUpdater } from "@/hooks/use-app-updater";
import { useUsageTracking, FREE_TURN_LIMIT } from "@/hooks/use-usage-tracking";
import { useToast } from "@/hooks/use-toast";
import { useKeybindings, useGlobalShortcuts, formatCombo } from "@/hooks/use-keybindings";
import type { KeybindingAction } from "@/hooks/use-keybindings";
import { useDemoMode } from "@/hooks/use-demo-mode";

const IS_DEMO = new URLSearchParams(window.location.search).has("demo");

const AppPage = () => {
  const liveSocket = useVocoSocket();
  const demoSocket = useDemoMode();
  const source = IS_DEMO ? demoSocket : liveSocket;

  const {
    isConnected,
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
    orgoSandbox,
    setOrgoSandbox,
    sendAuthSync,
    messages,
    sendMessage,
    isThinking,
    requestTTS,
    stopTTS,
    isTTSPlaying,
  } = source;
  const cancelBackgroundJob = IS_DEMO ? undefined : liveSocket.cancelBackgroundJob;
  const claudeCodeDelegation = IS_DEMO ? undefined : liveSocket.claudeCodeDelegation;

  const { settings, updateSetting, hasRequiredKeys, pushToBackend, saveSettings } = useSettings();
  const { session, isFounder, signOut, userTier } = useAuth();
  const { toast } = useToast();
  useAppUpdater();
  const { bindings, updateBinding, resetBindings } = useKeybindings();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pricingOpen, setPricingOpen] = useState(false);
  const [commandsOpen, setCommandsOpen] = useState(false);
  const usage = useUsageTracking(session?.user?.id, isFounder, userTier);
  const { turnCount, isCapped: atTurnLimit, activeWarning, recordTurn } = usage;
  const prevTerminalOutput = useRef<TerminalOutput | null>(null);
  const [textInput, setTextInput] = useState("");
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem("voco-onboarding-done");
  });

  // Stable connect/disconnect
  const connectRef = useRef(connect);
  const disconnectRef = useRef(disconnect);
  connectRef.current = connect;
  disconnectRef.current = disconnect;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    connectRef.current();
    return () => disconnectRef.current();
  }, []);

  // Record turn + fire upgrade warnings when a new AI response arrives
  useEffect(() => {
    if (terminalOutput !== null && prevTerminalOutput.current === null) {
      recordTurn();
    }
    prevTerminalOutput.current = terminalOutput;
  }, [terminalOutput, recordTurn]);

  // React to usage warning levels
  useEffect(() => {
    if (activeWarning === "half") {
      toast({
        title: "Half your free turns used",
        description: `You've used ${FREE_TURN_LIMIT / 2} of ${FREE_TURN_LIMIT} free turns. Upgrade for unlimited access.`,
        duration: 6000,
      });
    } else if (activeWarning === "near_cap") {
      toast({
        title: "Only 5 free turns left!",
        description: "You're almost out of free turns. Upgrade now to keep the momentum.",
        duration: 8000,
      });
      setPricingOpen(true);
    } else if (activeWarning === "capped") {
      setPricingOpen(true);
    }
  }, [activeWarning]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCloseTerminal = () => setTerminalOutput(null);

  // Global keyboard shortcuts
  const shortcutHandlers = {
    open_settings: () => setSettingsOpen(true),
    voice_commands: () => setCommandsOpen((prev) => !prev),
    dismiss: () => {
      if (settingsOpen) setSettingsOpen(false);
      else if (commandsOpen) setCommandsOpen(false);
      else if (pricingOpen && !atTurnLimit) setPricingOpen(false);
    },
  } satisfies Partial<Record<KeybindingAction, () => void>>;
  useGlobalShortcuts(bindings, shortcutHandlers);

  const handleSettingsSave = () => {
    saveSettings();
    pushToBackend(wsRef.current);
  };

  // Auto-push keys whenever the WebSocket (re)connects
  useEffect(() => {
    if (isConnected) pushToBackend(wsRef.current);
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Send auth session to Python backend
  useEffect(() => {
    if (isConnected && session?.access_token && session.user?.id) {
      sendAuthSync(session.access_token, session.user.id, session.refresh_token);
    }
  }, [isConnected, session, sendAuthSync]);

  // Sync global hotkey to Rust
  useEffect(() => {
    if (settings.GLOBAL_HOTKEY) {
      import("@tauri-apps/api/core")
        .then(({ invoke }) => invoke("set_global_hotkey", { combo: settings.GLOBAL_HOTKEY }))
        .catch(() => {});
    }
  }, [settings.GLOBAL_HOTKEY]);

  const handleSendText = useCallback(() => {
    if (!textInput.trim() || atTurnLimit) return;
    sendMessage(textInput);
    setTextInput("");
  }, [textInput, sendMessage, atTurnLimit]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  const hasSidebarContent = !!ledgerState || backgroundJobs.length > 0 || !!terminalOutput || proposals.length > 0 || commandProposals.length > 0 || !!claudeCodeDelegation;

  const isSandboxActive = !!sandboxUrl;
  const isOrgoActive = !!orgoSandbox;
  const hasSplitPanel = isSandboxActive || isOrgoActive;

  /* ====== Chat panel ====== */
  const chatPanel = (
    <main
      className={`flex flex-col transition-all duration-500
        ${hasSplitPanel ? "w-[420px] min-w-[340px] shrink-0 h-full" : "flex-1 min-h-screen"}
        ${hasSidebarContent && !hasSplitPanel ? "lg:pr-[440px]" : ""}
      `}
    >
      {/* Connection status */}
      <div className="flex items-center justify-center gap-2 py-2 text-xs text-zinc-500">
        <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-voco-green" : "bg-red-500"}`} />
        <span>{isConnected ? "Connected" : "Connecting..."}</span>
      </div>

      {/* Chat messages */}
      <ChatThread
        messages={messages}
        isThinking={isThinking}
        isTTSPlaying={isTTSPlaying}
        onRequestTTS={requestTTS}
        onStopTTS={stopTTS}
      />

      {/* Text input bar */}
      <div className="border-t border-white/[0.06] p-4">
        <div className="relative max-w-3xl mx-auto">
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={atTurnLimit ? "Turn limit reached — upgrade to continue" : "Message Voco..."}
            disabled={!isConnected || atTurnLimit}
            rows={2}
            className="w-full resize-none rounded-xl bg-[#111] border border-white/[0.06] text-sm text-zinc-200 placeholder-zinc-600 p-4 pr-12 focus:outline-none focus:border-voco-green/30 focus:shadow-voco-glow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSendText}
            disabled={!textInput.trim() || !isConnected || atTurnLimit}
            className="absolute bottom-3 right-3 flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-r from-voco-green to-voco-cyan text-white hover:opacity-90 transition-opacity disabled:opacity-20 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </main>
  );

  return (
    <div className={`noise-overlay bg-background text-foreground relative
      ${isSandboxActive ? "h-screen flex flex-col overflow-hidden" : "min-h-screen flex flex-col"}
    `}>
      <Header
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenPricing={() => setPricingOpen(true)}
        commandsOpen={commandsOpen}
        onCommandsOpenChange={setCommandsOpen}
        voiceCommandsBinding={bindings.voice_commands}
      />

      <SettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onUpdate={updateSetting}
        onSave={handleSettingsSave}
        keybindings={bindings}
        onUpdateBinding={updateBinding}
        onResetBindings={resetBindings}
      />

      <PricingModal
        open={pricingOpen}
        onOpenChange={setPricingOpen}
        forcedOpen={atTurnLimit}
        userEmail={session?.user?.email ?? ""}
        isFounder={isFounder}
        turnCount={turnCount}
        turnLimit={FREE_TURN_LIMIT}
        onSignOut={signOut}
      />

      {/* Content area */}
      {hasSplitPanel ? (
        <div className="flex flex-1 overflow-hidden">
          {chatPanel}
          <div className="flex-1 overflow-hidden">
            {isOrgoActive ? (
              <OrgoSandboxView
                sandbox={orgoSandbox!}
                onClose={() => setOrgoSandbox?.(null)}
              />
            ) : (
              <SandboxPreview
                url={sandboxUrl!}
                refreshKey={sandboxRefreshKey}
                onClose={() => setSandboxUrl(null)}
              />
            )}
          </div>
        </div>
      ) : (
        chatPanel
      )}

      <SidebarPanel
        ledgerState={ledgerState}
        backgroundJobs={backgroundJobs}
        terminalOutput={terminalOutput}
        proposals={proposals}
        commandProposals={commandProposals}
        onCloseTerminal={handleCloseTerminal}
        onSubmitProposalDecisions={submitProposalDecisions}
        onSubmitCommandDecisions={submitCommandDecisions}
        onCancelJob={cancelBackgroundJob}
        claudeCodeDelegation={claudeCodeDelegation}
      />

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
