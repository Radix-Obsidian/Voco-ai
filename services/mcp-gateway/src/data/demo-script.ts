import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
} from "@/hooks/use-voco-socket";

// ---------------------------------------------------------------------------
// Scene 1 — Voice Search → ripgrep results
// ---------------------------------------------------------------------------

export const SCENE1_TRANSCRIPT = "Search for authentication middleware in the Express routes";

export const SCENE1_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "code_search",
    nodes: [
      { id: "n1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "n2", iconType: "FileCode2", title: "Local Search", description: "ripgrep scanning…", status: "active" },
      { id: "n3", iconType: "Terminal", title: "Results", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "n1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "n2", iconType: "FileCode2", title: "Local Search", description: "3 files matched", status: "completed" },
      { id: "n3", iconType: "Terminal", title: "Results", description: "Rendering…", status: "active" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "n1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "n2", iconType: "FileCode2", title: "Local Search", description: "3 files matched", status: "completed" },
      { id: "n3", iconType: "Terminal", title: "Results", description: "Complete", status: "completed" },
    ],
  },
];

export const SCENE1_TERMINAL: TerminalOutput = {
  command: '$ rg --pattern "auth.*middleware" ./src',
  output: `src/middleware/auth.ts:12:export function authMiddleware(req: Request, res: Response, next: NextFunction) {
src/middleware/auth.ts:24:  const token = req.headers.authorization?.split("Bearer ")[1];
src/middleware/auth.ts:31:  jwt.verify(token, process.env.JWT_SECRET!, (err, decoded) => {
src/routes/api.ts:5:import { authMiddleware } from "../middleware/auth";
src/routes/api.ts:8:router.use("/protected", authMiddleware);
src/routes/admin.ts:3:import { authMiddleware } from "../middleware/auth";

3 files matched · 6 lines found`,
  isLoading: false,
  scope: "local",
};

// ---------------------------------------------------------------------------
// Scene 2 — Code Generation → ReviewDeck diff
// ---------------------------------------------------------------------------

export const SCENE2_TRANSCRIPT = "Create a rate limiter middleware with a sliding window algorithm";

export const SCENE2_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "code_generation",
    nodes: [
      { id: "g1", iconType: "Database", title: "Domain", description: "code_generation", status: "completed" },
      { id: "g2", iconType: "FileCode2", title: "Generate", description: "Writing code…", status: "active" },
      { id: "g3", iconType: "HardDrive", title: "Propose", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_generation",
    nodes: [
      { id: "g1", iconType: "Database", title: "Domain", description: "code_generation", status: "completed" },
      { id: "g2", iconType: "FileCode2", title: "Generate", description: "Complete", status: "completed" },
      { id: "g3", iconType: "HardDrive", title: "Propose", description: "Awaiting approval", status: "active" },
    ],
  },
];

export const SCENE2_PROPOSALS: Proposal[] = [
  {
    proposal_id: "demo-p1",
    action: "create_file",
    file_path: "src/middleware/rate-limiter.ts",
    content: `import { Request, Response, NextFunction } from "express";

interface SlidingWindow {
  timestamps: number[];
  count: number;
}

const windows = new Map<string, SlidingWindow>();
const WINDOW_MS = 60_000; // 1 minute
const MAX_REQUESTS = 100;

export function rateLimiter(req: Request, res: Response, next: NextFunction) {
  const key = req.ip ?? "unknown";
  const now = Date.now();
  let window = windows.get(key) ?? { timestamps: [], count: 0 };

  // Slide: remove expired timestamps
  window.timestamps = window.timestamps.filter((t) => now - t < WINDOW_MS);
  window.count = window.timestamps.length;

  if (window.count >= MAX_REQUESTS) {
    return res.status(429).json({
      error: "Too many requests",
      retryAfter: Math.ceil((window.timestamps[0] + WINDOW_MS - now) / 1000),
    });
  }

  window.timestamps.push(now);
  window.count++;
  windows.set(key, window);

  res.setHeader("X-RateLimit-Remaining", MAX_REQUESTS - window.count);
  next();
}`,
    description: "New file: sliding-window rate limiter middleware",
    project_root: "/home/user/project",
    status: "pending",
  },
];

// ---------------------------------------------------------------------------
// Scene 3 — Terminal Execution → streaming output
// ---------------------------------------------------------------------------

export const SCENE3_TRANSCRIPT = "Run the test suite for the auth module";

export const SCENE3_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "terminal_execution",
    nodes: [
      { id: "t1", iconType: "Database", title: "Domain", description: "terminal_execution", status: "completed" },
      { id: "t2", iconType: "Terminal", title: "Execute", description: "Running command…", status: "active" },
      { id: "t3", iconType: "FileCode2", title: "Report", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "terminal_execution",
    nodes: [
      { id: "t1", iconType: "Database", title: "Domain", description: "terminal_execution", status: "completed" },
      { id: "t2", iconType: "Terminal", title: "Execute", description: "Complete", status: "completed" },
      { id: "t3", iconType: "FileCode2", title: "Report", description: "Summarizing", status: "active" },
    ],
  },
  {
    domain: "terminal_execution",
    nodes: [
      { id: "t1", iconType: "Database", title: "Domain", description: "terminal_execution", status: "completed" },
      { id: "t2", iconType: "Terminal", title: "Execute", description: "Complete", status: "completed" },
      { id: "t3", iconType: "FileCode2", title: "Report", description: "All passed", status: "completed" },
    ],
  },
];

export const SCENE3_COMMAND: CommandProposal = {
  command_id: "demo-cmd1",
  command: "npm test -- --grep auth",
  description: "Run auth module test suite",
  project_path: "/home/user/project",
  status: "pending",
};

export const SCENE3_TERMINAL_STAGES: string[] = [
  `> project@1.0.0 test
> jest --grep auth

 RUNS  src/middleware/__tests__/auth.test.ts`,

  `> project@1.0.0 test
> jest --grep auth

 PASS  src/middleware/__tests__/auth.test.ts
  authMiddleware
    ✓ rejects requests without token (12 ms)
    ✓ rejects expired tokens (8 ms)
    ✓ passes valid tokens through (5 ms)
    ✓ handles malformed Authorization header (3 ms)`,

  `> project@1.0.0 test
> jest --grep auth

 PASS  src/middleware/__tests__/auth.test.ts
  authMiddleware
    ✓ rejects requests without token (12 ms)
    ✓ rejects expired tokens (8 ms)
    ✓ passes valid tokens through (5 ms)
    ✓ handles malformed Authorization header (3 ms)

 PASS  src/routes/__tests__/api.test.ts
  Protected routes
    ✓ returns 401 without auth (6 ms)
    ✓ returns 200 with valid auth (4 ms)

Test Suites: 2 passed, 2 total
Tests:       6 passed, 6 total
Time:        1.247 s
Ran all test suites matching /auth/i.`,
];
