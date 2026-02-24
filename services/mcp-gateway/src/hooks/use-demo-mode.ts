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
  SCENE1_TERMINAL,
  SCENE2_TRANSCRIPT,
  SCENE2_LEDGER_STAGES,
  SCENE2_PROPOSALS,
  SCENE3_TRANSCRIPT,
  SCENE3_LEDGER_STAGES,
  SCENE3_COMMAND,
  SCENE3_TERMINAL_STAGES,
} from "@/data/demo-script";

type DemoScene = 1 | 2 | 3;

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
}

/**
 * Hardcoded demo mode hook that mimics useVocoSocket output
 * with scripted scenes and timed transitions.
 */
export function useDemoMode() {
  const [scene, setScene] = useState<DemoScene>(1);
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

  // ── Scene 1: Voice Search ──
  const runScene1 = useCallback(() => {
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      commandProposals: [],
      ledgerState: null,
      liveTranscript: "",
    }));

    // Type transcript
    typeTranscript(SCENE1_TRANSCRIPT, 500, () => {
      // Ledger stage 1
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    // Ledger stage 2
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE1_LEDGER_STAGES[1] }));
    }, 4000);

    // Terminal output + ledger stage 3
    schedule(() => {
      setState((s) => ({
        ...s,
        ledgerState: SCENE1_LEDGER_STAGES[2],
        terminalOutput: SCENE1_TERMINAL,
      }));
    }, 5500);

    // Clear ledger, advance scene
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null }));
    }, 9000);

    schedule(() => setScene(2), 10000);
  }, [typeTranscript, schedule]);

  // ── Scene 2: Code Generation ──
  const runScene2 = useCallback(() => {
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      commandProposals: [],
      ledgerState: null,
      liveTranscript: "",
    }));

    typeTranscript(SCENE2_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE2_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    // Code generated
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: SCENE2_LEDGER_STAGES[1] }));
    }, 5000);

    // Show proposals
    schedule(() => {
      setState((s) => ({ ...s, proposals: SCENE2_PROPOSALS }));
    }, 6000);

    // Auto-approve after delay
    schedule(() => {
      setState((s) => ({
        ...s,
        proposals: s.proposals.map((p) => ({ ...p, status: "approved" as const })),
      }));
    }, 9000);

    // Clear and advance
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null, proposals: [] }));
    }, 11000);

    schedule(() => setScene(3), 12000);
  }, [typeTranscript, schedule]);

  // ── Scene 3: Terminal Execution ──
  const runScene3 = useCallback(() => {
    setState((s) => ({
      ...s,
      terminalOutput: null,
      proposals: [],
      commandProposals: [],
      ledgerState: null,
      liveTranscript: "",
    }));

    typeTranscript(SCENE3_TRANSCRIPT, 500, () => {
      setState((s) => ({ ...s, ledgerState: SCENE3_LEDGER_STAGES[0], liveTranscript: "" }));
    });

    // Show command proposal for HITL
    schedule(() => {
      setState((s) => ({ ...s, commandProposals: [SCENE3_COMMAND] }));
    }, 3500);

    // Auto-approve command
    schedule(() => {
      setState((s) => ({
        ...s,
        commandProposals: [],
        terminalOutput: {
          command: `$ ${SCENE3_COMMAND.command}`,
          output: SCENE3_TERMINAL_STAGES[0],
          isLoading: true,
          scope: "local",
        },
        ledgerState: SCENE3_LEDGER_STAGES[0],
      }));
    }, 6000);

    // Streaming terminal stage 2
    schedule(() => {
      setState((s) => ({
        ...s,
        terminalOutput: {
          command: `$ ${SCENE3_COMMAND.command}`,
          output: SCENE3_TERMINAL_STAGES[1],
          isLoading: true,
          scope: "local",
        },
        ledgerState: SCENE3_LEDGER_STAGES[1],
      }));
    }, 8000);

    // Final terminal output
    schedule(() => {
      setState((s) => ({
        ...s,
        terminalOutput: {
          command: `$ ${SCENE3_COMMAND.command}`,
          output: SCENE3_TERMINAL_STAGES[2],
          isLoading: false,
          scope: "local",
        },
        ledgerState: SCENE3_LEDGER_STAGES[2],
      }));
    }, 10000);

    // Clear and loop back to scene 1
    schedule(() => {
      setState((s) => ({ ...s, ledgerState: null, terminalOutput: null }));
    }, 14000);

    schedule(() => setScene(1), 15000);
  }, [typeTranscript, schedule]);

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
    submitProposalDecisions: noop,
    submitCommandDecisions: noop,
    ledgerState: state.ledgerState,
    backgroundJobs: state.backgroundJobs,
    wsRef: { current: null } as React.MutableRefObject<WebSocket | null>,
    sandboxUrl: state.sandboxUrl,
    sandboxRefreshKey: state.sandboxRefreshKey,
    setSandboxUrl: (v: string | null) => setState((s) => ({ ...s, sandboxUrl: v })),
    sendAuthSync: noop as unknown as (token: string, uid: string) => void,
    liveTranscript: state.liveTranscript,
  };
}
