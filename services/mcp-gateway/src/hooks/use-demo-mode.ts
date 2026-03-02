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
  SCENE4_COMMAND,
  SCENE4_TERMINAL,
  SCENE4_LEDGER_STAGES,
} from "@/data/demo-script";

type DemoScene = 1 | 2 | 3 | 4;
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
 * Hardcoded demo: "DraftClaw Spreads Market" — real feature addition.
 *
 * Scene 1 — THE ASK:  Voice → 4-node intent ledger animates
 * Scene 2 — THE PLAN: ReviewDeck with 3 edit proposals (HITL)
 * Scene 3 — THE SHIP: CommandApproval → terminal streams test + commit
 * Scene 4 — THE PR:   CommandApproval → terminal streams PR creation
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

    // Type out the DraftClaw voice command
    typeTranscript(SCENE1_TRANSCRIPT, 500, () => {
      // Transcript done → ledger stage 0: "Parse Intent — Analyzing voice…"
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    // Ledger stage 1: "Search Codebase — Finding analysis files…"
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[1] }));
    }, 8500);

    // Ledger stage 2: "Plan Changes — Mapping dependencies…"
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[2] }));
    }, 11000);

    // Ledger stage 3: "Generate Diffs — Review ready"
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[3] }));
    }, 13500);

    // Show proposals (ReviewDeck) — presenter must approve
    schedule(() => {
      setState((s) => ({ ...s, proposals: SCENE2_PROPOSALS }));
      setScenePhase("hitl");
    }, 15000);
  }, [typeTranscript, schedule]);

  // ── Scene 2: THE PLAN — show command approval for test+commit ──
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

  // ── Scene 3: THE SHIP — Terminal execution: test + commit ──
  const runScene3 = useCallback(() => {
    setScenePhase("playing");
    setState((s) => ({
      ...s,
      commandProposals: [],
      proposals: [],
      liveTranscript: "",
      ledgerState: SCENE3_LEDGER_STAGES[0],
    }));

    // Tests passed, creating branch
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE3_LEDGER_STAGES[1],
        terminalOutput: { ...SCENE3_TERMINAL, isLoading: true },
      }));
    }, 1500);

    // Commit done — show full terminal output
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE3_LEDGER_STAGES[2],
        terminalOutput: SCENE3_TERMINAL,
      }));
    }, 4000);

    // Show Scene 4 command approval (PR) — presenter must approve
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: null,
        commandProposals: [SCENE4_COMMAND],
      }));
      setScenePhase("hitl");
    }, 6500);
  }, [schedule]);

  // ── Scene 4: THE PR — Terminal execution: push + PR creation ──
  const runScene4 = useCallback(() => {
    setScenePhase("playing");
    setState((s) => ({
      ...s,
      commandProposals: [],
      proposals: [],
      liveTranscript: "",
      terminalOutput: null,
      ledgerState: SCENE4_LEDGER_STAGES[0],
    }));

    // Branch pushed
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE4_LEDGER_STAGES[1],
        terminalOutput: { ...SCENE4_TERMINAL, isLoading: true },
      }));
    }, 1500);

    // PR created — show full terminal output
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE4_LEDGER_STAGES[2],
        terminalOutput: SCENE4_TERMINAL,
      }));
    }, 4000);

    // Done — final ledger stays visible, waiting for presenter to loop
    schedule(() => {
      setScenePhase("waiting");
    }, 7000);
  }, [schedule]);

  // ── Presenter controls ──

  const advanceScene = useCallback(() => {
    clearTimers();
    if (scene < 4) {
      setScene((s) => (s + 1) as DemoScene);
    } else {
      // Loop back to Scene 1
      setScene(1);
    }
  }, [scene, clearTimers]);

  // HITL: presenter approves proposals → move to next scene (command approval)
  const handleProposalDecisions = useCallback(() => {
    setState((s) => ({ ...s, proposals: [], ledgerState: null }));
    setTimeout(() => {
      clearTimers();
      setScene(2);
    }, 300);
  }, [clearTimers]);

  // HITL: presenter approves command → advance to next scene
  const handleCommandDecisions = useCallback(() => {
    setState((s) => ({ ...s, commandProposals: [], ledgerState: null }));
    setTimeout(() => {
      clearTimers();
      setScene((prev) => (prev + 1) as DemoScene);
    }, 300);
  }, [clearTimers]);

  // Run the current scene
  useEffect(() => {
    clearTimers();
    if (scene === 1) runScene1();
    else if (scene === 2) runScene2();
    else if (scene === 3) runScene3();
    else if (scene === 4) runScene4();
    return clearTimers;
  }, [scene, runScene1, runScene2, runScene3, runScene4, clearTimers]);

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
    totalScenes: 4 as const,
  };
}
