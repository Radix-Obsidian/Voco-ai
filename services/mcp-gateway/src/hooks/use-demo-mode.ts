import { useState, useEffect, useCallback, useRef } from "react";
import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
  BackgroundJob,
} from "@/hooks/use-voco-socket";
import {
  SCENE1_TRANSCRIPT,
  SCENE1_LEDGER_STAGES,
  SCENE2_PROPOSALS,
  SCENE3_COMMAND,
  SCENE3_TERMINAL,
  SCENE3_LEDGER_STAGES,
} from "@/data/demo-script";

type DemoScene = 1 | 2 | 3;
type ScenePhase = "playing" | "waiting" | "hitl";

interface DemoState {
  isConnected: boolean;
  bargeInActive: boolean;
  terminalOutput: TerminalOutput | null;
  proposals: Proposal[];
  commandProposals: CommandProposal[];
  ledgerState: LedgerState | null;
  backgroundJobs: BackgroundJob[];
  sandboxUrl: string | null;
  sandboxRefreshKey: number;
  liveTranscript: string;
  sessionId: string | null;
  lastError: { code: string; message: string; recoverable: boolean } | null;
}

/**
 * Hardcoded demo: "Microservice Extraction" single killer flow.
 *
 * Scene 1 — THE ASK:  Voice → 4-node intent ledger animates
 * Scene 2 — THE PLAN: ReviewDeck with 4 diff proposals (HITL)
 * Scene 3 — THE YES:  CommandApproval → terminal streams file creation
 */
export function useDemoMode() {
  const [scene, setScene] = useState<DemoScene>(1);
  const [scenePhase, setScenePhase] = useState<ScenePhase>("playing");
  const [state, setState] = useState<DemoState>({
    isConnected: true,
    bargeInActive: false,
    terminalOutput: null,
    proposals: [],
    commandProposals: [],
    ledgerState: null,
    backgroundJobs: [],
    sandboxUrl: null,
    sandboxRefreshKey: 0,
    liveTranscript: "",
    sessionId: "demo-session-001",
    lastError: null,
  });

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const schedule = useCallback((fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  }, []);

  // Type the transcript character by character
  const typeTranscript = useCallback((text: string, startMs: number, onDone?: () => void) => {
    const chars = text.split("");
    chars.forEach((_, i) => {
      schedule(() => {
        setState((s) => ({ ...s, liveTranscript: text.slice(0, i + 1) }));
      }, startMs + i * 35);
    });
    if (onDone) {
      schedule(onDone, startMs + chars.length * 35 + 200);
    }
  }, [schedule]);

  // ── Scene 1: THE ASK — Voice → Intent Ledger ──
  const runScene1 = useCallback(() => {
    setScenePhase("playing");
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      commandProposals: [],
      ledgerState: null,
      sandboxUrl: null,
      liveTranscript: "",
    }));

    // Type out: "Extract the auth module into its own microservice…"
    typeTranscript(SCENE1_TRANSCRIPT, 500, () => {
      // Transcript done → ledger stage 0: "Parse Intent — Analyzing voice…"
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    // Ledger stage 1: "Plan Arch — Mapping deps…"
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[1] }));
    }, 6000);

    // Ledger stage 2: "Gen Diffs — Writing code…"
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[2] }));
    }, 8000);

    // Ledger stage 3: "Propose — Review ready" → transition to Scene 2 (HITL)
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[3] }));
    }, 10000);

    // Show proposals (ReviewDeck) — presenter must approve
    schedule(() => {
      setState((s) => ({ ...s, proposals: SCENE2_PROPOSALS }));
      setScenePhase("hitl");
    }, 11000);
  }, [typeTranscript, schedule]);

  // ── Scene 2: THE PLAN — ReviewDeck diffs (entered via HITL from Scene 1) ──
  // This scene is triggered when presenter approves proposals in Scene 1.
  // After approval → show CommandApproval for terminal execution.
  const runScene2 = useCallback(() => {
    setScenePhase("hitl");
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      ledgerState: null,
      liveTranscript: "",
      commandProposals: [SCENE3_COMMAND],
    }));
  }, []);

  // ── Scene 3: THE YES — Terminal execution streams file creation ──
  const runScene3 = useCallback(() => {
    setScenePhase("playing");
    setState((s) => ({
      ...s,
      commandProposals: [],
      proposals: [],
      liveTranscript: "",
      ledgerState: SCENE3_LEDGER_STAGES[0],
    }));

    // Files being created
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE3_LEDGER_STAGES[1],
        terminalOutput: { ...SCENE3_TERMINAL, isLoading: true },
      }));
    }, 1500);

    // Proto compiling
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE3_LEDGER_STAGES[2],
        terminalOutput: SCENE3_TERMINAL,
      }));
    }, 4000);

    // Done — wait for presenter to loop or end
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null }));
      setScenePhase("waiting");
    }, 6500);
  }, [schedule]);

  // ── Presenter controls ──

  const advanceScene = useCallback(() => {
    clearTimers();
    if (scene < 3) {
      setScene((s) => (s + 1) as DemoScene);
    } else {
      // Loop back to Scene 1
      setScene(1);
    }
  }, [scene, clearTimers]);

  // HITL: presenter approves proposals → move to Scene 2 (command approval)
  const handleProposalDecisions = useCallback(() => {
    setState((s) => ({ ...s, proposals: [], ledgerState: null }));
    setTimeout(() => {
      clearTimers();
      setScene(2);
    }, 300);
  }, [clearTimers]);

  // HITL: presenter approves command → move to Scene 3 (terminal execution)
  const handleCommandDecisions = useCallback(() => {
    setState((s) => ({ ...s, commandProposals: [], ledgerState: null }));
    setTimeout(() => {
      clearTimers();
      setScene(3);
    }, 300);
  }, [clearTimers]);

  // Run the current scene
  useEffect(() => {
    clearTimers();
    if (scene === 1) runScene1();
    else if (scene === 2) runScene2();
    else if (scene === 3) runScene3();
    return clearTimers;
  }, [scene, runScene1, runScene2, runScene3, clearTimers]);

  // No-op functions to match useVocoSocket interface
  const noop = useCallback(() => {}, []);
  const noopAsync = useCallback((_bytes: Uint8Array) => {}, []);

  return {
    isConnected: state.isConnected,
    bargeInActive: state.bargeInActive,
    sendAudioChunk: noopAsync,
    connect: noop,
    disconnect: noop,
    terminalOutput: state.terminalOutput,
    setTerminalOutput: (v: TerminalOutput | null) => setState((s) => ({ ...s, terminalOutput: v })),
    proposals: state.proposals,
    commandProposals: state.commandProposals,
    submitProposalDecisions: handleProposalDecisions,
    submitCommandDecisions: handleCommandDecisions,
    ledgerState: state.ledgerState,
    backgroundJobs: state.backgroundJobs,
    wsRef: { current: null } as React.MutableRefObject<WebSocket | null>,
    sandboxUrl: state.sandboxUrl,
    sandboxRefreshKey: state.sandboxRefreshKey,
    setSandboxUrl: (v: string | null) => setState((s) => ({ ...s, sandboxUrl: v })),
    sendAuthSync: noop as unknown as (token: string, uid: string, refreshToken?: string) => void,
    liveTranscript: state.liveTranscript,
    sessionId: state.sessionId,
    lastError: state.lastError,
    // Demo-specific exports for presenter UI
    scenePhase,
    scene,
    advanceScene,
    totalScenes: 3 as const,
  };
}
