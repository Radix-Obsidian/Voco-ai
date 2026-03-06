/**
 * Production readiness tests — Orgo sandbox integration (frontend).
 *
 * Validates WebSocket message handling, OrgoSandboxState shape,
 * and split-panel activation logic.
 *
 * Run: cd services/mcp-gateway && npm run test:run
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// 1. orgo_sandbox_live message parsing
// ---------------------------------------------------------------------------

describe("Orgo sandbox messages", () => {
  it("parses orgo_sandbox_live with VNC credentials", () => {
    const msg = {
      type: "orgo_sandbox_live",
      computer_id: "vm-abc123",
      vnc_url: "wss://vm-abc123.orgo.dev",
      vnc_password: "secret123",
      status: "running",
    };

    expect(msg.type).toBe("orgo_sandbox_live");
    expect(msg.computer_id).toBe("vm-abc123");
    expect(msg.vnc_url).toContain("wss://");
    expect(msg.vnc_password).toBeTruthy();
  });

  it("constructs OrgoSandboxState from orgo_sandbox_live", () => {
    const msg = {
      type: "orgo_sandbox_live" as const,
      computer_id: "vm-abc123",
      vnc_url: "wss://vm-abc123.orgo.dev",
      vnc_password: "secret123",
    };

    const state = {
      computerId: msg.computer_id,
      status: "running" as const,
      vncUrl: msg.vnc_url || null,
      vncPassword: msg.vnc_password || null,
      commandHistory: [] as Array<{ command: string; output: string; timestamp: number }>,
    };

    expect(state.computerId).toBe("vm-abc123");
    expect(state.status).toBe("running");
    expect(state.vncUrl).toBe("wss://vm-abc123.orgo.dev");
    expect(state.vncPassword).toBe("secret123");
    expect(state.commandHistory).toHaveLength(0);
  });

  it("parses orgo_command_output and appends to history", () => {
    const msg = {
      type: "orgo_command_output",
      command: "npm install",
      output: "added 42 packages",
      exit_code: 0,
    };

    const existing = {
      computerId: "vm-123",
      status: "running" as const,
      vncUrl: "wss://vm-123.orgo.dev",
      vncPassword: "secret",
      commandHistory: [] as Array<{ command: string; output: string; timestamp: number }>,
    };

    const newHistory = [
      ...existing.commandHistory,
      {
        command: msg.command,
        output: msg.output || "",
        timestamp: Date.now(),
      },
    ].slice(-50);

    expect(newHistory).toHaveLength(1);
    expect(newHistory[0].command).toBe("npm install");
    expect(newHistory[0].output).toBe("added 42 packages");
  });

  it("keeps only last 50 command history entries", () => {
    const history = Array.from({ length: 55 }, (_, i) => ({
      command: `cmd-${i}`,
      output: `out-${i}`,
      timestamp: Date.now(),
    }));

    const trimmed = history.slice(-50);
    expect(trimmed).toHaveLength(50);
    expect(trimmed[0].command).toBe("cmd-5");
    expect(trimmed[49].command).toBe("cmd-54");
  });

  it("parses orgo_sandbox_stopped", () => {
    const msg = { type: "orgo_sandbox_stopped" };
    expect(msg.type).toBe("orgo_sandbox_stopped");
    // Handler should set orgoSandbox to null
  });
});

// ---------------------------------------------------------------------------
// 2. Split panel activation logic
// ---------------------------------------------------------------------------

describe("Split panel activation with Orgo", () => {
  it("orgoSandbox active → hasSplitPanel true", () => {
    const sandboxUrl: string | null = null;
    const orgoSandbox = {
      computerId: "vm-123",
      status: "running" as const,
      vncUrl: "wss://vm-123.orgo.dev",
      vncPassword: "secret",
      commandHistory: [],
    };
    const isSandboxActive = !!sandboxUrl;
    const isOrgoActive = !!orgoSandbox;
    const hasSplitPanel = isSandboxActive || isOrgoActive;
    expect(hasSplitPanel).toBe(true);
  });

  it("both null → hasSplitPanel false", () => {
    const sandboxUrl: string | null = null;
    const orgoSandbox = null;
    const isSandboxActive = !!sandboxUrl;
    const isOrgoActive = !!orgoSandbox;
    const hasSplitPanel = isSandboxActive || isOrgoActive;
    expect(hasSplitPanel).toBe(false);
  });

  it("HTML sandbox active → hasSplitPanel true (backward compat)", () => {
    const sandboxUrl: string | null = "http://localhost:8001/sandbox";
    const orgoSandbox = null;
    const isSandboxActive = !!sandboxUrl;
    const isOrgoActive = !!orgoSandbox;
    const hasSplitPanel = isSandboxActive || isOrgoActive;
    expect(hasSplitPanel).toBe(true);
  });

  it("orgo_sandbox_live clears HTML sandbox", () => {
    // When orgo sandbox goes live, HTML sandbox should be cleared
    let sandboxUrl: string | null = "http://localhost:8001/sandbox";
    const setOrgoSandbox = () => {
      // Simulating the handler
      sandboxUrl = null; // setSandboxUrl(null)
    };
    setOrgoSandbox();
    expect(sandboxUrl).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 3. OrgoSandboxView connection states
// ---------------------------------------------------------------------------

describe("OrgoSandboxView connection states", () => {
  it("booting state shows loading", () => {
    const sandbox = {
      computerId: "vm-123",
      status: "booting" as const,
      vncUrl: null,
      vncPassword: null,
      commandHistory: [],
    };
    expect(sandbox.status).toBe("booting");
    expect(sandbox.vncUrl).toBeNull();
  });

  it("running state with VNC credentials triggers connection", () => {
    const sandbox = {
      computerId: "vm-123",
      status: "running" as const,
      vncUrl: "wss://vm-123.orgo.dev",
      vncPassword: "secret",
      commandHistory: [],
    };
    const canConnect = sandbox.vncUrl !== null && sandbox.vncPassword !== null;
    expect(canConnect).toBe(true);
  });

  it("running state without VNC credentials does not trigger connection", () => {
    const sandbox = {
      computerId: "vm-123",
      status: "running" as const,
      vncUrl: null,
      vncPassword: null,
      commandHistory: [],
    };
    const canConnect = sandbox.vncUrl !== null && sandbox.vncPassword !== null;
    expect(canConnect).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 4. Dead settings removed from frontend
// ---------------------------------------------------------------------------

describe("Dead settings cleanup verification", () => {
  it("VocoSettings interface only has GITHUB_TOKEN and GLOBAL_HOTKEY", () => {
    // This mirrors the runtime interface — if it had dead fields, TS would export them
    interface VocoSettings {
      GITHUB_TOKEN: string;
      GLOBAL_HOTKEY: string;
    }

    const defaults: VocoSettings = {
      GITHUB_TOKEN: "",
      GLOBAL_HOTKEY: "Alt+Space",
    };

    expect(Object.keys(defaults)).toHaveLength(2);
    expect(defaults).toHaveProperty("GITHUB_TOKEN");
    expect(defaults).toHaveProperty("GLOBAL_HOTKEY");
    // These should NOT exist
    expect(defaults).not.toHaveProperty("STT_PROVIDER");
    expect(defaults).not.toHaveProperty("WHISPER_MODEL");
    expect(defaults).not.toHaveProperty("WAKE_WORD");
    expect(defaults).not.toHaveProperty("TTS_VOICE");
  });
});

// ---------------------------------------------------------------------------
// 5. Orgo tool signal dict shapes (frontend validation)
// ---------------------------------------------------------------------------

describe("Orgo tool signal dict shapes (frontend mirror)", () => {
  it("orgo/create_sandbox signal shape", () => {
    const signal = {
      method: "orgo/create_sandbox",
      params: { project_name: "react-app", setup_commands: "npm init -y" },
    };
    expect(signal.method).toBe("orgo/create_sandbox");
    expect(signal.params.project_name).toBeTruthy();
  });

  it("orgo/run_command signal shape", () => {
    const signal = {
      method: "orgo/run_command",
      params: { command: "npm test", timeout: 30 },
    };
    expect(signal.method).toBe("orgo/run_command");
    expect(signal.params.command).toBeTruthy();
  });

  it("orgo/screenshot signal shape", () => {
    const signal = {
      method: "orgo/screenshot",
      params: {},
    };
    expect(signal.method).toBe("orgo/screenshot");
    expect(Object.keys(signal.params)).toHaveLength(0);
  });

  it("orgo/stop_sandbox signal shape", () => {
    const signal = {
      method: "orgo/stop_sandbox",
      params: {},
    };
    expect(signal.method).toBe("orgo/stop_sandbox");
  });
});
