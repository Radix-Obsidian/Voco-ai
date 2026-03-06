import { useState, useEffect, useCallback, useRef } from "react";
import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
  BackgroundJob,
  ClaudeCodeDelegation,
  ChatMessage,
} from "@/hooks/use-voco-socket";
import {
  SCENE1_LEDGER_STAGES,
  SCENE2_PROPOSALS,
  SCENE3_COMMAND,
  SCENE3_TERMINAL,
  SCENE3_LEDGER_STAGES,
  SCENE4_COMMAND,
  SCENE4_TERMINAL,
  SCENE4_LEDGER_STAGES,
} from "@/data/demo-script";

/**
 * Live demo mode: real mic → real STT → scripted AI responses.
 *
 * Connects to the real cognitive-engine WebSocket. Your voice is captured
 * and transcribed by Deepgram normally. But instead of letting Claude
 * respond, we intercept `turn_ended` and inject the scripted ledger,
 * proposals, commands, and terminal output.
 *
 * Flow:
 *   1. You speak into the mic (real orb animation, real transcript)
 *   2. Backend transcribes via Deepgram, sends `transcript` messages
 *   3. When VAD detects silence → backend sends `turn_ended`
 *   4. We suppress all backend AI responses and inject our scripted sequence
 *   5. You manually click HITL approvals (real ReviewDeck / CommandApproval)
 *   6. Each approval advances to the next scripted scene
 *
 * Activate: pass `?demo` in the URL. Requires the cognitive-engine running.
 */

type DemoPhase =
  | "idle"            // Waiting — mic on, ready for voice
  | "listening"       // User is speaking (real transcript flowing)
  | "scene1_ledger"   // Injecting ledger animation after voice
  | "scene2_hitl"     // ReviewDeck proposals visible, waiting for approval
  | "scene3_hitl"     // CommandApproval for test+commit, waiting for approval
  | "scene3_terminal" // Terminal animation for test+commit
  | "scene4_hitl"     // CommandApproval for PR, waiting for approval
  | "scene4_terminal" // Terminal animation for push+PR
  | "done";           // Demo complete — ledger stays, presenter can restart

const WS_URL = import.meta.env.VITE_COGNITIVE_ENGINE_WS
  ?? localStorage.getItem("voco-ws-url")
  ?? "ws://localhost:8001/ws/voco-stream";

export function useDemoMode() {
  const [isConnected, setIsConnected] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [ledgerState, setLedgerState] = useState<LedgerState | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [commandProposals, setCommandProposals] = useState<CommandProposal[]>([]);
  const [terminalOutput, setTerminalOutput] = useState<TerminalOutput | null>(null);
  const [backgroundJobs] = useState<BackgroundJob[]>([]);
  const [sandboxUrl, setSandboxUrl] = useState<string | null>(null);
  const [sandboxRefreshKey] = useState(0);
  const [claudeCodeDelegation] = useState<ClaudeCodeDelegation | null>(null);
  const [messages] = useState<ChatMessage[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const phaseRef = useRef<DemoPhase>("idle");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const suppressBackend = useRef(false);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const schedule = useCallback((fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  }, []);

  // ── Scene injectors ──

  const injectScene1Ledger = useCallback(() => {
    phaseRef.current = "scene1_ledger";
    suppressBackend.current = true;
    setLiveTranscript("");

    // Staggered ledger animation — feels like real processing
    setLedgerState(SCENE1_LEDGER_STAGES[0]);

    schedule(() => setLedgerState(SCENE1_LEDGER_STAGES[1]), 2500);
    schedule(() => setLedgerState(SCENE1_LEDGER_STAGES[2]), 5000);
    schedule(() => setLedgerState(SCENE1_LEDGER_STAGES[3]), 7500);

    // Show proposals — transition to HITL
    schedule(() => {
      setProposals(SCENE2_PROPOSALS);
      phaseRef.current = "scene2_hitl";
    }, 9500);
  }, [schedule]);

  const injectScene3Terminal = useCallback(() => {
    phaseRef.current = "scene3_terminal";
    setCommandProposals([]);
    setLedgerState(SCENE3_LEDGER_STAGES[0]);

    schedule(() => {
      setLedgerState(SCENE3_LEDGER_STAGES[1]);
      setTerminalOutput({ ...SCENE3_TERMINAL, isLoading: true });
    }, 1800);

    schedule(() => {
      setLedgerState(SCENE3_LEDGER_STAGES[2]);
      setTerminalOutput(SCENE3_TERMINAL);
    }, 4500);

    // Show PR command approval
    schedule(() => {
      setLedgerState(null);
      setCommandProposals([SCENE4_COMMAND]);
      phaseRef.current = "scene4_hitl";
    }, 7000);
  }, [schedule]);

  const injectScene4Terminal = useCallback(() => {
    phaseRef.current = "scene4_terminal";
    setCommandProposals([]);
    setTerminalOutput(null);
    setLedgerState(SCENE4_LEDGER_STAGES[0]);

    schedule(() => {
      setLedgerState(SCENE4_LEDGER_STAGES[1]);
      setTerminalOutput({ ...SCENE4_TERMINAL, isLoading: true });
    }, 1800);

    schedule(() => {
      setLedgerState(SCENE4_LEDGER_STAGES[2]);
      setTerminalOutput(SCENE4_TERMINAL);
    }, 4500);

    schedule(() => {
      phaseRef.current = "done";
    }, 7000);
  }, [schedule]);

  // ── HITL handlers (you click these manually) ──

  const submitProposalDecisions = useCallback(() => {
    setProposals([]);
    setLedgerState(null);
    // Short beat before command approval appears
    schedule(() => {
      setTerminalOutput(null);
      setCommandProposals([SCENE3_COMMAND]);
      phaseRef.current = "scene3_hitl";
    }, 400);
  }, [schedule]);

  const submitCommandDecisions = useCallback(() => {
    clearTimers();
    if (phaseRef.current === "scene3_hitl") {
      injectScene3Terminal();
    } else if (phaseRef.current === "scene4_hitl") {
      injectScene4Terminal();
    }
  }, [clearTimers, injectScene3Terminal, injectScene4Terminal]);

  // ── WebSocket connection (real backend, intercepted responses) ──

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setIsConnected(true);
      phaseRef.current = "idle";
      suppressBackend.current = false;
      console.log(`[Demo] Connected to ${WS_URL}`);
    };

    ws.onmessage = async (event) => {
      // Binary = TTS audio — suppress in demo mode after first turn
      if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
        if (suppressBackend.current) return;
        return;
      }

      try {
        const msg = JSON.parse(event.data);

        // Always allow these through
        if (msg.type === "session_init") {
          console.log(`[Demo] Session: ${msg.session_id}`);
          return;
        }
        if (msg.type === "heartbeat") return;

        // Real transcript from Deepgram — always show
        if (msg.type === "transcript") {
          setLiveTranscript(msg.text ?? "");
          return;
        }

        // turn_ended = STT silence detected → inject our scripted response
        if (msg.type === "control" && msg.action === "turn_ended") {
          if (phaseRef.current === "idle" || phaseRef.current === "listening") {
            injectScene1Ledger();
          }
          return;
        }

        // Suppress all other backend messages once demo takes over
        if (suppressBackend.current) return;

        // Before demo starts, let tts_start/tts_end through for natural mic suppression
        if (msg.type === "control") return;

      } catch {
        // Ignore parse errors
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log("[Demo] Disconnected");
    };

    ws.onerror = () => {
      console.error("[Demo] WebSocket error");
    };

    wsRef.current = ws;
  }, [injectScene1Ledger]);

  const disconnect = useCallback(() => {
    clearTimers();
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, [clearTimers]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearTimers();
      wsRef.current?.close();
    };
  }, [clearTimers]);

  const sendAuthSync = useCallback((token: string, uid: string, refreshToken?: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "auth_sync", token, uid, refresh_token: refreshToken || "" }));
    }
  }, []);

  const cancelBackgroundJob = useCallback(() => {}, []);

  return {
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
    cancelBackgroundJob,
    wsRef,
    sandboxUrl,
    sandboxRefreshKey,
    setSandboxUrl,
    sendAuthSync,
    claudeCodeDelegation,
    // V2.5 chat state
    messages,
    sendMessage: () => {},
    isThinking: false,
    requestTTS: () => {},
    stopTTS: () => {},
    isTTSPlaying: false,
  };
}
