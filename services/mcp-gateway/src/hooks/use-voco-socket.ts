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

const WS_URL = import.meta.env.VITE_COGNITIVE_ENGINE_WS
  ?? localStorage.getItem("voco-ws-url")
  ?? "ws://localhost:8001/ws/voco-stream";

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

/** A long-running tool dispatched to the background queue. */
export interface BackgroundJob {
  job_id: string;
  tool_name: string;
  status: "running" | "completed" | "failed";
}

/** Claude Code delegation progress. */
export interface ClaudeCodeDelegation {
  job_id: string;
  task_description: string;
  status: "running" | "completed" | "failed";
  messages: string[];
}

/** A single message in the chat thread. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: number;
}

export function useVocoSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState<TerminalOutput | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [commandProposals, setCommandProposals] = useState<CommandProposal[]>([]);
  const [ledgerState, setLedgerState] = useState<LedgerState | null>(null);
  const [backgroundJobs, setBackgroundJobs] = useState<BackgroundJob[]>([]);
  const [claudeCodeDelegation, setClaudeCodeDelegation] = useState<ClaudeCodeDelegation | null>(null);
  const [sandboxUrl, setSandboxUrl] = useState<string | null>(null);
  const [sandboxRefreshKey, setSandboxRefreshKey] = useState(0);
  const [orgoSandbox, setOrgoSandbox] = useState<{
    computerId: string;
    status: "booting" | "running" | "stopped";
    vncUrl: string | null;
    vncPassword: string | null;
    commandHistory: Array<{ command: string; output: string; timestamp: number }>;
  } | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lastError, setLastError] = useState<{ code: string; message: string; recoverable: boolean } | null>(null);
  const [turnCount, setTurnCount] = useState(0);
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);
  // Chat messages — the core UI state for V2.5
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingRequests = useRef<Map<string, { resolve: (value: unknown) => void; reject: (reason?: unknown) => void }>>(new Map());

  // Reconnect state
  const [isReconnecting, setIsReconnecting] = useState(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalCloseRef = useRef(false);
  const MAX_RECONNECT_ATTEMPTS = 10;
  const BASE_RECONNECT_DELAY_MS = 1000;

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptRef.current = 0;
    setIsReconnecting(false);
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

  const handleLocalSearch = useCallback(async (msg: { id: string; params: { pattern: string; project_path: string; max_count?: number; file_glob?: string; context_lines?: number } }) => {
    const { id, params } = msg;
    setTerminalOutput({ command: `$ rg --pattern "${params.pattern}" ${params.project_path}`, output: "", isLoading: true, scope: "local" });
    try {
      const invokeArgs: Record<string, unknown> = { pattern: params.pattern, projectPath: params.project_path };
      if (params.max_count) invokeArgs.maxCount = params.max_count;
      if (params.file_glob) invokeArgs.fileGlob = params.file_glob;
      if (params.context_lines) invokeArgs.contextLines = params.context_lines;
      const result = await tauriInvoke<string>("search_project", invokeArgs);
      setTerminalOutput({ command: `$ rg --pattern "${params.pattern}" ${params.project_path}`, output: result || "No matches found", isLoading: false, scope: "local" });
      setSearchResults({ id, scope: "local", localResults: result });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ rg --pattern "${params.pattern}" ${params.project_path}`, output: "", isLoading: false, scope: "local", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleReadFile = useCallback(async (msg: { id: string; params: { file_path: string; project_root: string; start_line?: number; end_line?: number } }) => {
    const { id, params } = msg;
    const lineRange = params.start_line ? `:${params.start_line}${params.end_line ? `-${params.end_line}` : ""}` : "";
    setTerminalOutput({ command: `$ read_file ${params.file_path}${lineRange}`, output: "", isLoading: true, scope: "local" });
    try {
      const invokeArgs: Record<string, unknown> = { filePath: params.file_path, projectRoot: params.project_root };
      if (params.start_line) invokeArgs.startLine = params.start_line;
      if (params.end_line) invokeArgs.endLine = params.end_line;
      const result = await tauriInvoke<string>("read_file", invokeArgs);
      setTerminalOutput({ command: `$ read_file ${params.file_path}${lineRange}`, output: result || "(empty file)", isLoading: false, scope: "local" });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ read_file ${params.file_path}${lineRange}`, output: "", isLoading: false, scope: "local", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleListDirectory = useCallback(async (msg: { id: string; params: { dir_path: string; project_root: string; max_depth?: number } }) => {
    const { id, params } = msg;
    setTerminalOutput({ command: `$ list_directory ${params.dir_path} --depth ${params.max_depth ?? 3}`, output: "", isLoading: true, scope: "local" });
    try {
      const result = await tauriInvoke<string>("list_directory", { dirPath: params.dir_path, projectRoot: params.project_root, maxDepth: params.max_depth ?? 3 });
      setTerminalOutput({ command: `$ list_directory ${params.dir_path} --depth ${params.max_depth ?? 3}`, output: result || "(empty directory)", isLoading: false, scope: "local" });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ list_directory ${params.dir_path}`, output: "", isLoading: false, scope: "local", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleGlobFind = useCallback(async (msg: { id: string; params: { pattern: string; project_path: string; file_type?: string; max_results?: number } }) => {
    const { id, params } = msg;
    setTerminalOutput({ command: `$ glob_find "${params.pattern}" ${params.project_path}`, output: "", isLoading: true, scope: "local" });
    try {
      const result = await tauriInvoke<string>("glob_find", { pattern: params.pattern, projectPath: params.project_path, fileType: params.file_type ?? "file", maxResults: params.max_results ?? 50 });
      setTerminalOutput({ command: `$ glob_find "${params.pattern}" ${params.project_path}`, output: result || "No files found", isLoading: false, scope: "local" });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ glob_find "${params.pattern}" ${params.project_path}`, output: "", isLoading: false, scope: "local", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleExecuteCommand = useCallback(async (msg: { id: string; params: { command: string; project_path: string } }) => {
    const { id, params } = msg;
    setTerminalOutput({ command: `$ ${params.command}`, output: "", isLoading: true, scope: "local" });
    try {
      const result = await tauriInvoke<string>("execute_command", { command: params.command, projectPath: params.project_path });
      setTerminalOutput({ command: `$ ${params.command}`, output: result || "(no output)", isLoading: false, scope: "local" });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ ${params.command}`, output: "", isLoading: false, scope: "local", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleWriteFile = useCallback(async (msg: { id: string; params: { file_path: string; content: string; project_root: string } }) => {
    const { id, params } = msg;
    try {
      const result = await tauriInvoke<string>("write_file", { filePath: params.file_path, content: params.content, projectRoot: params.project_root });
      sendJsonRpcResponse(id, result);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const handleWebDiscovery = useCallback(async (msg: { id: string; params: { query: string } }) => {
    const { id, params } = msg;
    setTerminalOutput({ command: `$ webmcp --query "${params.query}"`, output: "", isLoading: true, scope: "web" });
    try {
      if (typeof navigator !== "undefined" && navigator.modelContext) {
        const results = await navigator.modelContext.callTool({ name: "web_search", input: { query: params.query } });
        setTerminalOutput({ command: `$ webmcp --query "${params.query}"`, output: JSON.stringify(results, null, 2), isLoading: false, scope: "web" });
        setSearchResults({ id, scope: "web", webResults: JSON.stringify(results) });
        sendJsonRpcResponse(id, results);
      } else {
        const errorMsg = "WebMCP not available in this context";
        setTerminalOutput({ command: `$ webmcp --query "${params.query}"`, output: "", isLoading: false, scope: "web", error: errorMsg });
        sendJsonRpcError(id, -32001, errorMsg);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      setTerminalOutput({ command: `$ webmcp --query "${params.query}"`, output: "", isLoading: false, scope: "web", error: errorMsg });
      sendJsonRpcError(id, -32000, errorMsg);
    }
  }, [sendJsonRpcResponse, sendJsonRpcError]);

  const submitProposalDecisions = useCallback((decisions: Array<{ proposal_id: string; status: "approved" | "rejected" }>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "proposal_decision", decisions }));
      setProposals([]);
    } else {
      toast({ title: "Connection lost", description: "Reconnecting — your proposals are preserved. Please resubmit after reconnection.", variant: "destructive" });
    }
  }, []);

  const sendAuthSync = useCallback((token: string, uid: string, refreshToken?: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "auth_sync", token, uid, refresh_token: refreshToken || "" }));
      console.log(`[VocoSocket] auth_sync sent for uid=${uid}`);
    }
  }, []);

  const cancelBackgroundJob = useCallback((jobId: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "cancel_job", job_id: jobId }));
    }
    setBackgroundJobs((prev) => prev.filter((j) => j.job_id !== jobId));
  }, []);

  const submitCommandDecisions = useCallback((decisions: Array<{ command_id: string; status: "approved" | "rejected" }>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "command_decision", decisions }));
      setCommandProposals([]);
    } else {
      toast({ title: "Connection lost", description: "Reconnecting — your commands are preserved. Please resubmit after reconnection.", variant: "destructive" });
    }
  }, []);

  /** Send a text message to the AI. Adds it to chat immediately. */
  const sendMessage = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!text.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
    // Add user message to chat
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: text.trim(),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);
    ws.send(JSON.stringify({ type: "text_input", text: text.trim() }));
  }, []);

  /** Request TTS playback of text (on-demand "Read aloud"). */
  const requestTTS = useCallback((text: string) => {
    const ws = wsRef.current;
    if (!text.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "tts_request", text: text.trim() }));
  }, []);

  /** Stop TTS playback. */
  const stopTTS = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "tts_stop" }));
    }
    haltNativeAudio();
    setIsTTSPlaying(false);
  }, [haltNativeAudio]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }
    disconnect();

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setIsConnected(true);
      setIsReconnecting(false);
      reconnectAttemptRef.current = 0;
      intentionalCloseRef.current = false;
      console.log(`[VocoSocket] Connected to ${WS_URL}`);
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

        if (msg.type === "heartbeat") {
          // No-op
        } else if (msg.type === "session_init") {
          setSessionId(msg.session_id ?? null);
        } else if (msg.type === "error") {
          const errPayload = { code: msg.code ?? "UNKNOWN", message: msg.message ?? "Unknown error", recoverable: msg.recoverable ?? true };
          setLastError(errPayload);
          setIsThinking(false);
          toast({ title: errPayload.code, description: errPayload.message, variant: "destructive" });
        } else if (msg.type === "ai_response") {
          // AI response text — add to chat thread
          const aiMsg: ChatMessage = {
            id: `ai-${Date.now()}`,
            role: "assistant",
            text: msg.text ?? "",
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, aiMsg]);
          setIsThinking(false);
        } else if (msg.type === "transcript") {
          // Server echoing back the transcript — can be used for confirmation
          console.log("[VocoSocket] Transcript confirmed:", msg.text);
        } else if (msg.type === "control") {
          if (msg.action === "halt_audio_playback") {
            haltNativeAudio();
            setIsTTSPlaying(false);
          } else if (msg.action === "turn_ended") {
            const serverCount = typeof msg.turn_count === "number" ? msg.turn_count : undefined;
            setTurnCount((prev) => {
              const next = prev + 1;
              if (serverCount !== undefined && serverCount !== next) {
                console.warn(`[TurnCount] Client/server mismatch: client=${next} server=${serverCount}`);
              }
              return serverCount ?? next;
            });
          } else if (msg.action === "tts_start") {
            setIsTTSPlaying(true);
          } else if (msg.action === "tts_end") {
            setIsTTSPlaying(false);
          }
        } else if (msg.type === "background_job_start") {
          setBackgroundJobs((prev) => [
            ...prev,
            { job_id: msg.job_id, tool_name: msg.tool_name, status: "running" },
          ]);
        } else if (msg.type === "background_job_complete") {
          setBackgroundJobs((prev) =>
            prev.map((j) =>
              j.job_id === msg.job_id ? { ...j, status: "completed" } : j
            )
          );
          toast({ title: "Background task complete", description: msg.tool_name });
          setTimeout(() => {
            setBackgroundJobs((prev) => prev.filter((j) => j.job_id !== msg.job_id));
          }, 4000);
        } else if (msg.type === "ledger_update") {
          setLedgerState(msg.payload);
        } else if (msg.type === "ledger_clear") {
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
        } else if (msg.type === "user_info") {
          const tier = msg.tier ?? "free";
          localStorage.setItem("voco-tier", tier);
          window.dispatchEvent(new StorageEvent("storage", { key: "voco-tier", newValue: tier }));
        } else if (msg.type === "screen_capture_request") {
          const requestId: string = msg.id ?? "";
          try {
            const frames = await tauriInvoke<string[]>("get_recent_frames");
            ws.send(JSON.stringify({ type: "screen_frames", id: requestId, frames, media_type: "image/jpeg" }));
          } catch (err) {
            ws.send(JSON.stringify({ type: "screen_frames", id: requestId, frames: [], media_type: "image/jpeg" }));
            console.warn("[VocoEyes] get_recent_frames failed:", err);
          }
        } else if (msg.type === "cowork_edit") {
          setProposals((prev) => [
            ...prev,
            {
              proposal_id: msg.proposal_id,
              action: msg.action ?? "edit_file",
              file_path: msg.file_path,
              content: msg.content,
              diff: msg.diff,
              description: msg.description,
              project_root: msg.project_root,
              status: "pending",
            },
          ]);
        } else if (msg.type === "claude_code_start") {
          setClaudeCodeDelegation({
            job_id: msg.job_id,
            task_description: msg.task_description ?? "",
            status: "running",
            messages: [],
          });
        } else if (msg.type === "claude_code_progress") {
          setClaudeCodeDelegation((prev) => {
            if (!prev || prev.job_id !== msg.job_id) return prev;
            const updated = [...prev.messages, msg.message ?? ""].slice(-20);
            return { ...prev, messages: updated };
          });
        } else if (msg.type === "claude_code_complete") {
          setClaudeCodeDelegation((prev) => {
            if (!prev || prev.job_id !== msg.job_id) return prev;
            return { ...prev, status: msg.success ? "completed" : "failed" };
          });
          toast({
            title: msg.success ? "Claude Code finished" : "Claude Code failed",
            description: (msg.summary as string)?.slice(0, 120) ?? "",
          });
          const completedJobId = msg.job_id;
          setTimeout(() => {
            setClaudeCodeDelegation((prev) => prev?.job_id === completedJobId ? null : prev);
          }, 10000);
        } else if (msg.type === "sandbox_live") {
          setSandboxUrl(msg.url as string);
          setSandboxRefreshKey((prev) => prev + 1);
        } else if (msg.type === "sandbox_updated") {
          setSandboxRefreshKey((prev) => prev + 1);
        } else if (msg.type === "orgo_sandbox_live") {
          setOrgoSandbox({
            computerId: msg.computer_id as string,
            status: "running",
            vncUrl: (msg.vnc_url as string) || null,
            vncPassword: (msg.vnc_password as string) || null,
            commandHistory: [],
          });
          // Close any existing HTML sandbox
          setSandboxUrl(null);
        } else if (msg.type === "orgo_command_output") {
          setOrgoSandbox((prev) => {
            if (!prev) return prev;
            const newHistory = [
              ...prev.commandHistory,
              {
                command: msg.command as string,
                output: (msg.output as string) || "",
                timestamp: Date.now(),
              },
            ].slice(-50); // Keep last 50 entries
            return { ...prev, commandHistory: newHistory };
          });
        } else if (msg.type === "orgo_sandbox_stopped") {
          setOrgoSandbox(null);
        } else if (msg.type === "scan_security_request") {
          const requestId: string = msg.id ?? "";
          const projectPath: string = msg.project_path ?? "";
          try {
            const raw = await tauriInvoke<string>("scan_security", { projectPath });
            const findings = JSON.parse(raw);
            ws.send(JSON.stringify({ type: "scan_security_result", id: requestId, findings }));
          } catch (err) {
            ws.send(JSON.stringify({ type: "scan_security_result", id: requestId, findings: { error: String(err) } }));
          }
        } else if (msg.jsonrpc === "2.0" && msg.method) {
          if (msg.method === "local/search_project") {
            await handleLocalSearch(msg);
          } else if (msg.method === "local/read_file") {
            await handleReadFile(msg);
          } else if (msg.method === "local/list_directory") {
            await handleListDirectory(msg);
          } else if (msg.method === "local/glob_find") {
            await handleGlobFind(msg);
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
        console.warn("[VocoSocket] Message parse error:", err);
      }
    };

    ws.onclose = (ev) => {
      setIsConnected(false);
      setLedgerState(null);
      setIsThinking(false);

      // Auto-reconnect with exponential backoff
      if (!intentionalCloseRef.current && reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const attempt = reconnectAttemptRef.current;
        const delay = Math.min(BASE_RECONNECT_DELAY_MS * Math.pow(2, attempt), 30000);
        const jitter = Math.random() * delay * 0.3;
        const totalDelay = Math.round(delay + jitter);
        reconnectAttemptRef.current = attempt + 1;
        setIsReconnecting(true);
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          connect();
        }, totalDelay);
      } else if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setIsReconnecting(false);
        toast({ title: "Connection Lost", description: "Could not reconnect to Voco engine. Click Connect to retry.", variant: "destructive" });
      }
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, [disconnect, playNativeAudio, haltNativeAudio, handleLocalSearch, handleReadFile, handleListDirectory, handleGlobFind, handleExecuteCommand, handleWriteFile, handleWebDiscovery]);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  return {
    isConnected,
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
    cancelBackgroundJob,
    wsRef,
    sendAuthSync,
    sandboxUrl,
    sandboxRefreshKey,
    setSandboxUrl,
    orgoSandbox,
    setOrgoSandbox,
    sessionId,
    lastError,
    isReconnecting,
    turnCount,
    claudeCodeDelegation,
    // V2.5 chat state
    messages,
    sendMessage,
    isThinking,
    // V2.5 optional TTS
    requestTTS,
    stopTTS,
    isTTSPlaying,
  };
}
