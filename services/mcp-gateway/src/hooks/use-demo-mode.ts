import { useState, useEffect, useCallback, useRef } from "react";
import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
  BackgroundJob,
} from "@/hooks/use-voco-socket";
import {
  SCENE0_TRANSCRIPT,
  SCENE0_LEDGER_STAGES,
  SCENE0_TERMINAL,
  SCENE1_TRANSCRIPT,
  SCENE1_LEDGER_STAGES,
  SCENE1_TERMINAL,
  SCENE2_TRANSCRIPT,
  SCENE2_LEDGER_STAGES,
  SCENE2_PROPOSALS,
  SCENE4_TRANSCRIPT,
  SCENE4_UPDATE_TRANSCRIPT,
  SCENE4_LEDGER_STAGES,
  SCENE4_SANDBOX_HTML,
  SCENE4_UPDATED_HTML,
  SCENE6_TRANSCRIPT,
  SCENE6_LEDGER_STAGES,
  SCENE6_TERMINAL_STAGES,
} from "@/data/demo-script";

type DemoScene = 1 | 2 | 3 | 4 | 5;
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
 * Hardcoded demo mode hook that mimics useVocoSocket output
 * with scripted scenes and timed transitions.
 */
export function useDemoMode() {
  const [scene, setScene] = useState<DemoScene>(1);
  const [scenePhase, setScenePhase] = useState<ScenePhase>("playing");
  const sandboxSubPhase = useRef<1 | 2>(1);
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
  const blobUrls = useRef<string[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    blobUrls.current.forEach((u) => URL.revokeObjectURL(u));
    blobUrls.current = [];
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

  // ── Scene 1: Connect Existing Repo ──
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

    typeTranscript(SCENE0_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE0_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE0_LEDGER_STAGES[1] }));
    }, 3500);

    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE0_LEDGER_STAGES[2],
        terminalOutput: SCENE0_TERMINAL,
      }));
    }, 5000);

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null }));
      setScenePhase("waiting");
    }, 8500);
  }, [typeTranscript, schedule]);

  // ── Scene 2: Voice Search ──
  const runScene2 = useCallback(() => {
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

    typeTranscript(SCENE1_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[1] }));
    }, 4000);

    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE1_LEDGER_STAGES[2],
        terminalOutput: SCENE1_TERMINAL,
      }));
    }, 5500);

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null }));
      setScenePhase("waiting");
    }, 9000);
  }, [typeTranscript, schedule]);

  // ── Scene 3: Code Generation (HITL — presenter approves) ──
  const runScene3 = useCallback(() => {
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

    typeTranscript(SCENE2_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE2_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE2_LEDGER_STAGES[1] }));
    }, 5000);

    // Show proposals — presenter must approve/reject via ReviewDeck
    schedule(() => {
      setState((s) => ({ ...s, proposals: SCENE2_PROPOSALS }));
      setScenePhase("hitl");
    }, 6000);
  }, [typeTranscript, schedule]);

  // ── Scene 4: AI Chat Builder → Live Sandbox ──
  // Sub-phase 1: build initial app, wait for presenter to explore
  // Sub-phase 2: follow-up voice update, wait again
  const runScene4 = useCallback(() => {
    setScenePhase("playing");
    sandboxSubPhase.current = 1;
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      commandProposals: [],
      ledgerState: null,
      sandboxUrl: null,
      liveTranscript: "",
    }));

    typeTranscript(SCENE4_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE4_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE4_LEDGER_STAGES[1] }));
    }, 4500);

    // Sandbox goes live — presenter can interact before advancing
    schedule(() => {
      const blob = new Blob([SCENE4_SANDBOX_HTML], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      blobUrls.current.push(url);
      setState((s) => ({
        ...s,
        ledgerState: SCENE4_LEDGER_STAGES[2],
        sandboxUrl: url,
        sandboxRefreshKey: s.sandboxRefreshKey + 1,
      }));
      setScenePhase("waiting");
    }, 6000);
  }, [typeTranscript, schedule]);

  // Scene 4 follow-up: type update transcript, swap to enhanced HTML
  const runScene4Update = useCallback(() => {
    setScenePhase("playing");
    sandboxSubPhase.current = 2;

    typeTranscript(SCENE4_UPDATE_TRANSCRIPT, 0, () => {
      const blob = new Blob([SCENE4_UPDATED_HTML], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      blobUrls.current.push(url);
      setState((s) => ({
        ...s,
        liveTranscript: "",
        sandboxUrl: url,
        sandboxRefreshKey: s.sandboxRefreshKey + 1,
      }));
      setScenePhase("waiting");
    });
  }, [typeTranscript]);

  // ── Scene 5: Deep Codebase Exploration (All 4 Search Primitives) ──
  const runScene5 = useCallback(() => {
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

    typeTranscript(SCENE6_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE6_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    schedule(() => {
      setState((s) => ({ ...s, terminalOutput: SCENE6_TERMINAL_STAGES[0] }));
    }, 4000);

    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE6_LEDGER_STAGES[1],
        terminalOutput: SCENE6_TERMINAL_STAGES[1],
      }));
    }, 7500);

    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE6_LEDGER_STAGES[2],
        terminalOutput: SCENE6_TERMINAL_STAGES[2],
      }));
    }, 11000);

    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE6_LEDGER_STAGES[3] }));
      setScenePhase("waiting");
    }, 14000);
  }, [typeTranscript, schedule]);

  // ── Presenter controls ──

  // Advance to next scene (or sub-phase within scene 4)
  const advanceScene = useCallback(() => {
    // Scene 4 sub-phase 1 → trigger follow-up update
    if (scene === 4 && sandboxSubPhase.current === 1) {
      clearTimers();
      runScene4Update();
      return;
    }
    clearTimers();
    if (scene < 5) {
      setScene((s) => (s + 1) as DemoScene);
    } else {
      setScene(1);
    }
  }, [scene, clearTimers, runScene4Update]);

  // HITL: presenter approves/rejects proposals → clear and advance
  const handleProposalDecisions = useCallback(() => {
    setState((s) => ({ ...s, proposals: [], ledgerState: null }));
    setTimeout(() => advanceScene(), 300);
  }, [advanceScene]);

  const handleCommandDecisions = useCallback(() => {
    setState((s) => ({ ...s, commandProposals: [], ledgerState: null }));
    setTimeout(() => advanceScene(), 300);
  }, [advanceScene]);

  // Run the current scene
  useEffect(() => {
    clearTimers();
    if (scene === 1) runScene1();
    else if (scene === 2) runScene2();
    else if (scene === 3) runScene3();
    else if (scene === 4) runScene4();
    else if (scene === 5) runScene5();
    return clearTimers;
  }, [scene, runScene1, runScene2, runScene3, runScene4, runScene5, clearTimers]);

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
    totalScenes: 5 as const,
  };
}
