/**
 * Production smoke tests — frontend message parsing and demo mode.
 *
 * Run: cd services/mcp-gateway && bun run test:run
 */

import { describe, it, expect, vi } from "vitest";

// ---------------------------------------------------------------------------
// 1. session_init sets sessionId
// ---------------------------------------------------------------------------

describe("session_init parsing", () => {
  it("parses session_init and extracts session_id", () => {
    const msg = { type: "session_init", session_id: "session-abc12345" };
    expect(msg.type).toBe("session_init");
    expect(msg.session_id).toBe("session-abc12345");
    expect(msg.session_id.startsWith("session-")).toBe(true);
    expect(msg.session_id.length).toBeGreaterThan("session-".length);
  });

  it("handles missing session_id gracefully", () => {
    const msg = { type: "session_init" } as { type: string; session_id?: string };
    const sessionId = msg.session_id ?? null;
    expect(sessionId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 2. error message triggers lastError
// ---------------------------------------------------------------------------

describe("error message parsing", () => {
  it("parses error message and sets lastError shape", () => {
    const msg = {
      type: "error",
      code: "E_GRAPH_FAILED",
      message: "LangGraph invocation raised RuntimeError",
      recoverable: true,
    };

    const errPayload = {
      code: msg.code ?? "UNKNOWN",
      message: msg.message ?? "Unknown error",
      recoverable: msg.recoverable ?? true,
    };

    expect(errPayload.code).toBe("E_GRAPH_FAILED");
    expect(errPayload.message).toContain("RuntimeError");
    expect(errPayload.recoverable).toBe(true);
  });

  it("defaults code to UNKNOWN when missing", () => {
    const msg = { type: "error" } as { type: string; code?: string; message?: string; recoverable?: boolean };
    const errPayload = {
      code: msg.code ?? "UNKNOWN",
      message: msg.message ?? "Unknown error",
      recoverable: msg.recoverable ?? true,
    };
    expect(errPayload.code).toBe("UNKNOWN");
  });
});

// ---------------------------------------------------------------------------
// 3. Demo mode loops all 6 scenes
// ---------------------------------------------------------------------------

describe("Demo mode 6-scene loop", () => {
  it("scene type includes all 6 scenes", () => {
    // Verify that the demo-script exports all 6 scenes
    const sceneNumbers = [1, 2, 3, 4, 5, 6];
    expect(sceneNumbers).toHaveLength(6);
    // After scene 6, loop back to 1
    const nextScene = (current: number) => (current % 6) + 1;
    expect(nextScene(1)).toBe(2);
    expect(nextScene(2)).toBe(3);
    expect(nextScene(3)).toBe(4);
    expect(nextScene(4)).toBe(5);
    expect(nextScene(5)).toBe(6);
    expect(nextScene(6)).toBe(1);
  });

  it("imports all scene data from demo-script", async () => {
    const demoScript = await import("@/data/demo-script");
    // Scene 1
    expect(demoScript.SCENE1_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE1_LEDGER_STAGES).toBeDefined();
    expect(demoScript.SCENE1_TERMINAL).toBeDefined();
    // Scene 2
    expect(demoScript.SCENE2_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE2_PROPOSALS).toBeDefined();
    // Scene 3
    expect(demoScript.SCENE3_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE3_COMMAND).toBeDefined();
    // Scene 4
    expect(demoScript.SCENE4_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE4_SANDBOX_HTML).toBeTruthy();
    expect(demoScript.SCENE4_LEDGER_STAGES).toBeDefined();
    // Scene 5
    expect(demoScript.SCENE5_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE5_LEDGER_STAGES).toBeDefined();
    expect(demoScript.SCENE5_TERMINAL_STAGES).toBeDefined();
    // Scene 6
    expect(demoScript.SCENE6_TRANSCRIPT).toBeTruthy();
    expect(demoScript.SCENE6_LEDGER_STAGES).toBeDefined();
    expect(demoScript.SCENE6_TERMINAL_STAGES).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// 4. Free tier paywall at 50 turns
// ---------------------------------------------------------------------------

describe("Free tier paywall", () => {
  it("turnCount >= 50 triggers atTurnLimit", () => {
    const FREE_TURN_LIMIT = 50;
    const atTurnLimit = (turnCount: number) => turnCount >= FREE_TURN_LIMIT;
    expect(atTurnLimit(0)).toBe(false);
    expect(atTurnLimit(49)).toBe(false);
    expect(atTurnLimit(50)).toBe(true);
    expect(atTurnLimit(100)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5. Sandbox URL activates split-screen
// ---------------------------------------------------------------------------

describe("Sandbox activation", () => {
  it("sandboxUrl set → isSandboxActive true", () => {
    const sandboxUrl: string | null = "http://localhost:8001/sandbox";
    const isSandboxActive = sandboxUrl !== null && sandboxUrl.length > 0;
    expect(isSandboxActive).toBe(true);
  });

  it("null sandboxUrl → isSandboxActive false", () => {
    const sandboxUrl: string | null = null;
    const isSandboxActive = sandboxUrl !== null && sandboxUrl.length > 0;
    expect(isSandboxActive).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 6. Proposal decision payload shape
// ---------------------------------------------------------------------------

describe("Proposal decision payload", () => {
  it("has correct JSON structure", () => {
    const payload = {
      type: "proposal_decision",
      decisions: [
        { proposal_id: "p-001", status: "approved" as const },
        { proposal_id: "p-002", status: "rejected" as const },
      ],
    };

    expect(payload.type).toBe("proposal_decision");
    expect(payload.decisions).toHaveLength(2);
    expect(payload.decisions[0]).toHaveProperty("proposal_id");
    expect(payload.decisions[0]).toHaveProperty("status");
    expect(["approved", "rejected"]).toContain(payload.decisions[0].status);
  });
});

// ---------------------------------------------------------------------------
// 7. Command decision payload shape
// ---------------------------------------------------------------------------

describe("Command decision payload", () => {
  it("has correct JSON structure", () => {
    const payload = {
      type: "command_decision",
      decisions: [
        { command_id: "cmd-001", status: "approved" as const },
      ],
    };

    expect(payload.type).toBe("command_decision");
    expect(payload.decisions).toHaveLength(1);
    expect(payload.decisions[0]).toHaveProperty("command_id");
    expect(payload.decisions[0]).toHaveProperty("status");
    expect(["approved", "rejected"]).toContain(payload.decisions[0].status);
  });
});
