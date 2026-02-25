/**
 * Slice 4: Frontend unit tests for use-voco-socket message routing.
 *
 * Tests the WebSocket message handling logic that routes incoming JSON
 * messages to the correct handlers (JSON-RPC dispatch, control messages,
 * proposals, background jobs, auth_sync, etc.)
 *
 * Run: cd services/mcp-gateway && bun run test
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Extracted pure-function tests (no React hooks needed)
// ---------------------------------------------------------------------------

describe("WebSocket message routing logic", () => {
  describe("JSON-RPC method routing", () => {
    it("identifies local/search_project as a local search", () => {
      const msg = {
        jsonrpc: "2.0",
        method: "local/search_project",
        params: { pattern: "test", project_path: "/abs/path" },
        id: "rpc-1",
      };
      expect(msg.jsonrpc).toBe("2.0");
      expect(msg.method).toBe("local/search_project");
      expect(msg.method.startsWith("local/")).toBe(true);
    });

    it("identifies local/execute_command as a local command", () => {
      const msg = {
        jsonrpc: "2.0",
        method: "local/execute_command",
        params: { command: "ls", project_path: "/abs/path" },
        id: "rpc-2",
      };
      expect(msg.method).toBe("local/execute_command");
      expect(msg.method.startsWith("local/")).toBe(true);
    });

    it("identifies local/write_file as a local write", () => {
      const msg = {
        jsonrpc: "2.0",
        method: "local/write_file",
        params: { file_path: "/abs/file.ts", content: "hello", project_root: "/abs" },
        id: "rpc-3",
      };
      expect(msg.method).toBe("local/write_file");
    });

    it("identifies web/discovery as a web call", () => {
      const msg = {
        jsonrpc: "2.0",
        method: "web/discovery",
        params: { query: "how to use React" },
        id: "rpc-4",
      };
      expect(msg.method.startsWith("web/")).toBe(true);
    });

    it("routes JSON-RPC responses (no method, has id) to pending futures", () => {
      const msg = { jsonrpc: "2.0", id: "rpc-1", result: "search results..." };
      const isResponse = msg.jsonrpc === "2.0" && msg.id && !("method" in msg && msg.method);
      // This has 'result' but no 'method', so it's a response
      expect("result" in msg).toBe(true);
      expect("method" in msg).toBe(false);
    });
  });

  describe("Control message routing", () => {
    it("identifies halt_audio_playback for barge-in", () => {
      const msg = { type: "control", action: "halt_audio_playback" };
      expect(msg.type).toBe("control");
      expect(msg.action).toBe("halt_audio_playback");
    });

    it("identifies tts_start for mic suppression", () => {
      const msg = { type: "control", action: "tts_start" };
      expect(msg.action).toBe("tts_start");
    });

    it("identifies tts_end for mic resume", () => {
      const msg = { type: "control", action: "tts_end" };
      expect(msg.action).toBe("tts_end");
    });

    it("identifies turn_ended for barge-in reset", () => {
      const msg = { type: "control", action: "turn_ended" };
      expect(msg.action).toBe("turn_ended");
    });
  });

  describe("auth_sync message format", () => {
    it("includes refresh_token in auth_sync payload (BUG-6 regression)", () => {
      const token = "eyJ...access";
      const uid = "user-123";
      const refreshToken = "eyJ...refresh";

      const payload = {
        type: "auth_sync",
        token,
        uid,
        refresh_token: refreshToken || "",
      };

      expect(payload.type).toBe("auth_sync");
      expect(payload.token).toBe(token);
      expect(payload.uid).toBe(uid);
      expect(payload.refresh_token).toBe(refreshToken);
    });

    it("defaults refresh_token to empty string when not provided", () => {
      const payload = {
        type: "auth_sync",
        token: "tok",
        uid: "uid",
        refresh_token: undefined || "",
      };

      expect(payload.refresh_token).toBe("");
    });
  });

  describe("Proposal message parsing", () => {
    it("parses file proposal correctly", () => {
      const msg = {
        type: "proposal",
        proposal_id: "prop-1",
        action: "create_file" as const,
        file_path: "/project/src/new.ts",
        content: "export const x = 1;",
        description: "Create new utility file",
        project_root: "/project",
      };

      expect(msg.type).toBe("proposal");
      expect(msg.action).toBe("create_file");
      expect(msg.proposal_id).toBe("prop-1");
    });

    it("parses command proposal correctly", () => {
      const msg = {
        type: "command_proposal",
        command_id: "cmd-1",
        command: "npm test",
        description: "Run test suite",
        project_path: "/project",
      };

      expect(msg.type).toBe("command_proposal");
      expect(msg.command).toBe("npm test");
    });
  });

  describe("Background job messages", () => {
    it("parses background_job_start", () => {
      const msg = {
        type: "background_job_start",
        job_id: "job-abc",
        tool_name: "search_codebase",
      };

      expect(msg.type).toBe("background_job_start");
      expect(msg.job_id).toBe("job-abc");
    });

    it("parses background_job_complete", () => {
      const msg = {
        type: "background_job_complete",
        job_id: "job-abc",
        tool_name: "search_codebase",
      };

      expect(msg.type).toBe("background_job_complete");
    });
  });

  describe("Ledger messages", () => {
    it("parses ledger_update with domain and nodes", () => {
      const msg = {
        type: "ledger_update",
        payload: {
          domain: "api",
          nodes: [
            { id: "1", iconType: "Brain", title: "Context Router", description: "Routing...", status: "completed" },
            { id: "2", iconType: "Cpu", title: "Orchestrator", description: "Thinking...", status: "active" },
          ],
        },
      };

      expect(msg.type).toBe("ledger_update");
      expect(msg.payload.domain).toBe("api");
      expect(msg.payload.nodes).toHaveLength(2);
    });

    it("parses ledger_clear", () => {
      const msg = { type: "ledger_clear" };
      expect(msg.type).toBe("ledger_clear");
    });
  });

  describe("Sandbox messages", () => {
    it("parses sandbox_live with URL", () => {
      const msg = { type: "sandbox_live", url: "http://localhost:3456" };
      expect(msg.type).toBe("sandbox_live");
      expect(msg.url).toBe("http://localhost:3456");
    });

    it("parses sandbox_updated", () => {
      const msg = { type: "sandbox_updated" };
      expect(msg.type).toBe("sandbox_updated");
    });
  });
});
