import { useState, useRef, useCallback, useEffect } from "react";
import { toast } from "@/hooks/use-toast";

const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

async function tauriInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauri()) {
    throw new Error(`[Voco] Not running inside Tauri — cannot invoke "${cmd}". Open via Tauri desktop app.`);
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(cmd, args);
}

const WS_URL = "ws://localhost:8001/ws/voco-stream";

export interface TerminalOutput {
  command: string;
  output: string;
  isLoading: boolean;
  scope: "local" | "web" | "hybrid";
  error?: string;
}

export interface SearchResult {
  id: string;
  scope: string;
  localResults?: string;
  webResults?: string;
}

export interface Proposal {
  proposal_id: string;
  action: "create_file" | "edit_file";
  file_path: string;
  content?: string;
  diff?: string;
  description: string;
  project_root: string;
  status: "pending" | "approved" | "rejected";
}

export interface LedgerNode {
  id: string;
  iconType: string;
  title: string;
  description: string;
  status: "completed" | "active" | "pending" | "failed";
  execution_output?: string;
}

export interface LedgerState {
  domain: string;
  nodes: LedgerNode[];
}

export interface CommandProposal {
  command_id: string;
  command: string;
  description: string;
  project_path: string;
  status: "pending" | "approved" | "rejected";
}

/** A long-running tool dispatched to the background queue (Milestone 11). */
export interface BackgroundJob {
  job_id: string;
  tool_name: string;
  status: "running" | "completed" | "failed";
}

export function useVocoSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [bargeInActive, setBargeInActive] = useState(false);
  const ttsActiveRef = useRef(false);
  const [terminalOutput, setTerminalOutput] = useState<TerminalOutput | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [commandProposals, setCommandProposals] = useState<CommandProposal[]>([]);
  const [ledgerState, setLedgerState] = useState<LedgerState | null>(null);
  const [backgroundJobs, setBackgroundJobs] = useState<BackgroundJob[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingRequests = useRef<Map<string, { resolve: (value: unknown) => void; reject: (reason?: unknown) => void }>>(new Map());

  const sendAudioChunk = useCallback((bytes: Uint8Array) => {
    // Suppress mic input while TTS is playing to prevent echo/feedback loop
    if (ttsActiveRef.current) return;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(bytes.buffer);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // --- Native Rust audio (bypasses webview entirely) ---

  const playNativeAudio = useCallback(async (pcm: Uint8Array) => {
    if (!pcm.length) return;
    try {
      await tauriInvoke("play_native_audio", { audioBytes: Array.from(pcm) });
    } catch (err) {
      console.error("[NativeAudio] Playback failed:", err);
    }
  }, []);

  const haltNativeAudio = useCallback(async () => {
    try {
      await tauriInvoke("halt_native_audio");
    } catch (err) {
      console.error("[NativeAudio] Halt failed:", err);
    }
  }, []);

  const sendJsonRpcResponse = useCallback((id: string, result: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ jsonrpc: "2.0", id, result }));
    }
  }, []);

  const sendJsonRpcError = useCallback((id: string, code: number, message: string, data?: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        jsonrpc: "2.0",
        id,
        error: { code, message, data }
      }));
    }
  }, []);

  const handleLocalSearch = useCallback(async (msg: { id: string; params: { pattern: string; project_path: string } }) => {
    const { id, params } = msg;

    setTerminalOutput({
      command: `$ rg --pattern "${params.pattern}" ${params.project_path}`,
      output: "",
      isLoading: true,
      scope: "local"
    });

    try {
      const result = await tauriInvoke<string>("search_project", {
        pattern: params.pattern,
        projectPath: params.project_path
      });

      setTerminalOutput({
        command: `$ rg --pattern "${params.pattern}" ${params.project_path}`,
        output: result || "No matches found",
        isLoading: false,
        scope: "local"
      });

      setSearchResults({ id, scope: "local", localResults: result });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      setTerminalOutput({
        command: `$ rg --pattern "${params.pattern}" ${params.project_path}`,
        output: "",
        isLoading: false,
        scope: "local",
        error: errorMsg
      });

      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleExecuteCommand = useCallback(async (msg: { id: string; params: { command: string; project_path: string } }) => {
    const { id, params } = msg;

    setTerminalOutput({
      command: `$ ${params.command}`,
      output: "",
      isLoading: true,
      scope: "local",
    });

    try {
      const result = await tauriInvoke<string>("execute_command", {
        command: params.command,
        projectPath: params.project_path,
      });

      setTerminalOutput({
        command: `$ ${params.command}`,
        output: result || "(no output)",
        isLoading: false,
        scope: "local",
      });

      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      setTerminalOutput({
        command: `$ ${params.command}`,
        output: "",
        isLoading: false,
        scope: "local",
        error: errorMsg,
      });

      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleWriteFile = useCallback(async (msg: { id: string; params: { file_path: string; content: string; project_root: string } }) => {
    const { id, params } = msg;
    try {
      const result = await tauriInvoke<string>("write_file", {
        filePath: params.file_path,
        content: params.content,
        projectRoot: params.project_root,
      });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleWebDiscovery = useCallback(async (msg: { id: string; params: { query: string } }) => {
    const { id, params } = msg;

    setTerminalOutput({
      command: `$ webmcp --query "${params.query}"`,
      output: "",
      isLoading: true,
      scope: "web"
    });

    try {
      if (typeof navigator !== "undefined" && navigator.modelContext) {
        const results = await navigator.modelContext.callTool({
          name: "web_search",
          input: { query: params.query }
        });

        setTerminalOutput({
          command: `$ webmcp --query "${params.query}"`,
          output: JSON.stringify(results, null, 2),
          isLoading: false,
          scope: "web"
        });

        setSearchResults({ id, scope: "web", webResults: JSON.stringify(results) });
        sendJsonRpcResponse(id, results);
      } else {
        const errorMsg = "WebMCP not available in this context";
        setTerminalOutput({
          command: `$ webmcp --query "${params.query}"`,
          output: "",
          isLoading: false,
          scope: "web",
          error: errorMsg
        });
        sendJsonRpcError(id, -32001, errorMsg);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);

      setTerminalOutput({
        command: `$ webmcp --query "${params.query}"`,
        output: "",
        isLoading: false,
        scope: "web",
        error: errorMsg
      });

      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const submitProposalDecisions = useCallback((decisions: Array<{ proposal_id: string; status: "approved" | "rejected" }>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "proposal_decision",
        decisions,
      }));
    }
    setProposals([]);
  }, []);

  const submitCommandDecisions = useCallback((decisions: Array<{ command_id: string; status: "approved" | "rejected" }>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "command_decision",
        decisions,
      }));
    }
    setCommandProposals([]);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }
    disconnect();

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setIsConnected(true);
      console.log("[VocoSocket] Connected to", WS_URL);
    };

    ws.onmessage = async (event) => {
      // Handle binary TTS audio frames → pipe directly to Rust native audio
      if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
        const buf = event.data instanceof Blob ? new Uint8Array(await event.data.arrayBuffer()) : new Uint8Array(event.data);
        playNativeAudio(buf);
        return;
      }

      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "control") {
          if (msg.action === "halt_audio_playback") {
            haltNativeAudio();
            setBargeInActive(true);
            console.log("[Barge-in] Halting native audio!");
          } else if (msg.action === "turn_ended") {
            setBargeInActive(false);
          } else if (msg.action === "tts_start") {
            ttsActiveRef.current = true;
            console.log("[TTS] Active — mic suppressed to prevent echo");
          } else if (msg.action === "tts_end") {
            // Delay mic resume slightly so tail-end audio doesn't trigger VAD
            setTimeout(() => {
              ttsActiveRef.current = false;
              console.log("[TTS] Ended — mic resumed");
            }, 600);
          }
        } else if (msg.type === "background_job_start") {
          // A new async tool was dispatched to the background queue.
          setBackgroundJobs((prev) => [
            ...prev,
            { job_id: msg.job_id, tool_name: msg.tool_name, status: "running" },
          ]);
          console.log(`[VocoSocket] Background job started: ${msg.job_id} (${msg.tool_name})`);
        } else if (msg.type === "background_job_complete") {
          // Mark the job done and auto-remove after 4 s so the UI stays clean.
          setBackgroundJobs((prev) =>
            prev.map((j) =>
              j.job_id === msg.job_id ? { ...j, status: "completed" } : j
            )
          );
          toast({ title: "Background task complete", description: msg.tool_name });
          setTimeout(() => {
            setBackgroundJobs((prev) => prev.filter((j) => j.job_id !== msg.job_id));
          }, 4000);
          console.log(`[VocoSocket] Background job complete: ${msg.job_id}`);
        } else if (msg.type === "ledger_update") {
          setLedgerState(msg.payload);
        } else if (msg.type === "ledger_clear") {
          // Clear the transient pipeline state but preserve active background jobs.
          setLedgerState(null);
        } else if (msg.type === "command_proposal") {
          setCommandProposals((prev) => [
            ...prev,
            {
              command_id: msg.command_id,
              command: msg.command,
              description: msg.description,
              project_path: msg.project_path,
              status: "pending",
            },
          ]);
        } else if (msg.type === "proposal") {
          setProposals((prev) => [
            ...prev,
            {
              proposal_id: msg.proposal_id,
              action: msg.action,
              file_path: msg.file_path,
              content: msg.content,
              diff: msg.diff,
              description: msg.description,
              project_root: msg.project_root,
              status: "pending",
            },
          ]);
        } else if (msg.type === "screen_capture_request") {
          // Phase 3: Voco Eyes — capture recent screen frames and send back
          const requestId: string = msg.id ?? "";
          try {
            const frames = await tauriInvoke<string[]>("get_recent_frames");
            ws.send(JSON.stringify({
              type: "screen_frames",
              id: requestId,
              frames,
              media_type: "image/jpeg",
            }));
            console.log(`[VocoEyes] Sent ${frames.length} frame(s) to Python.`);
          } catch (err) {
            // Send an empty frames array so Python can respond gracefully
            ws.send(JSON.stringify({ type: "screen_frames", id: requestId, frames: [], media_type: "image/jpeg" }));
            console.warn("[VocoEyes] get_recent_frames failed:", err);
          }
        } else if (msg.type === "scan_security_request") {
          // Phase 4: Voco Auto-Sec — run local security scan via Rust and send findings back
          const requestId: string = msg.id ?? "";
          const projectPath: string = msg.project_path ?? "";
          try {
            const raw = await tauriInvoke<string>("scan_security", { projectPath });
            const findings = JSON.parse(raw);
            ws.send(JSON.stringify({
              type: "scan_security_result",
              id: requestId,
              findings,
            }));
            console.log("[AutoSec] Security scan complete, findings sent to Python.");
          } catch (err) {
            ws.send(JSON.stringify({
              type: "scan_security_result",
              id: requestId,
              findings: { error: String(err) },
            }));
            console.warn("[AutoSec] scan_security failed:", err);
          }
        } else if (msg.jsonrpc === "2.0" && msg.method) {
          if (msg.method === "local/search_project") {
            await handleLocalSearch(msg);
          } else if (msg.method === "local/execute_command") {
            await handleExecuteCommand(msg);
          } else if (msg.method === "local/write_file") {
            await handleWriteFile(msg);
          } else if (msg.method === "web/discovery") {
            await handleWebDiscovery(msg);
          }
        } else if (msg.jsonrpc === "2.0" && msg.id) {
          const pending = pendingRequests.current.get(msg.id);
          if (pending) {
            if (msg.error) {
              pending.reject(msg.error);
            } else {
              pending.resolve(msg.result);
            }
            pendingRequests.current.delete(msg.id);
          }
        }
      } catch (err) {
        // Non-JSON frame or parse error — ignore
        console.warn("[VocoSocket] Message parse error:", err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setLedgerState(null);
      console.log("[VocoSocket] Disconnected");
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, [disconnect, playNativeAudio, haltNativeAudio, handleLocalSearch, handleExecuteCommand, handleWriteFile, handleWebDiscovery]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return {
    isConnected,
    bargeInActive,
    sendAudioChunk,
    connect,
    disconnect,
    terminalOutput,
    searchResults,
    proposals,
    commandProposals,
    setTerminalOutput,
    setSearchResults,
    submitProposalDecisions,
    submitCommandDecisions,
    ledgerState,
    backgroundJobs,
    wsRef,
  };
}
