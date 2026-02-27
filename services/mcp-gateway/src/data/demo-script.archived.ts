import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
} from "@/hooks/use-voco-socket";

// ═══════════════════════════════════════════════════════════════════════════
// DEMO: "Microservice Extraction" — Single Killer Flow (1:45 screencast)
//
// Scene 1 — THE ASK:  Speak architecture → ledger animates → intent parsed
// Scene 2 — THE PLAN: ReviewDeck with 4 diff proposals (HITL approve)
// Scene 3 — THE YES:  Command approval → terminal streams file creation
// ═══════════════════════════════════════════════════════════════════════════

// ---------------------------------------------------------------------------
// Scene 1 — "The Ask" — Voice → Intent Ledger
// ---------------------------------------------------------------------------

export const SCENE1_TRANSCRIPT =
  "Extract the auth module into its own microservice with JWT validation, rate limiting, and a shared proto contract";

export const SCENE1_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "architecture",
    nodes: [
      { id: "a1", iconType: "Database", title: "Parse Intent", description: "Analyzing voice…", status: "active" },
      { id: "a2", iconType: "FileCode2", title: "Plan Arch", description: "Awaiting", status: "pending" },
      { id: "a3", iconType: "Terminal", title: "Gen Diffs", description: "Awaiting", status: "pending" },
      { id: "a4", iconType: "HardDrive", title: "Propose", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "architecture",
    nodes: [
      { id: "a1", iconType: "Database", title: "Parse Intent", description: "Auth extraction", status: "completed" },
      { id: "a2", iconType: "FileCode2", title: "Plan Arch", description: "Mapping deps…", status: "active" },
      { id: "a3", iconType: "Terminal", title: "Gen Diffs", description: "Awaiting", status: "pending" },
      { id: "a4", iconType: "HardDrive", title: "Propose", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "architecture",
    nodes: [
      { id: "a1", iconType: "Database", title: "Parse Intent", description: "Auth extraction", status: "completed" },
      { id: "a2", iconType: "FileCode2", title: "Plan Arch", description: "4 files planned", status: "completed" },
      { id: "a3", iconType: "Terminal", title: "Gen Diffs", description: "Writing code…", status: "active" },
      { id: "a4", iconType: "HardDrive", title: "Propose", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "architecture",
    nodes: [
      { id: "a1", iconType: "Database", title: "Parse Intent", description: "Auth extraction", status: "completed" },
      { id: "a2", iconType: "FileCode2", title: "Plan Arch", description: "4 files planned", status: "completed" },
      { id: "a3", iconType: "Terminal", title: "Gen Diffs", description: "Complete", status: "completed" },
      { id: "a4", iconType: "HardDrive", title: "Propose", description: "Review ready", status: "active" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Scene 2 — "The Plan" — ReviewDeck with 4 diffs (HITL)
// ---------------------------------------------------------------------------

export const SCENE2_PROPOSALS: Proposal[] = [
  {
    proposal_id: "ms-p1",
    action: "create_file",
    file_path: "auth-service/src/index.ts",
    content: `import express from "express";
import { authRouter } from "./routes";
import { rateLimiter } from "./rate-limiter";
import { loadProtoDefinitions } from "./proto";

const app = express();
const PORT = process.env.AUTH_SERVICE_PORT ?? 4001;

// Middleware
app.use(express.json());
app.use(rateLimiter);

// gRPC service definitions
const proto = loadProtoDefinitions();

// Routes
app.use("/auth", authRouter);

// Health check
app.get("/health", (_req, res) => res.json({ status: "ok", service: "auth" }));

app.listen(PORT, () => {
  console.log(\`[auth-service] Running on :\${PORT}\`);
});`,
    description: "New microservice entry point — Express + rate limiter + gRPC proto loader",
    project_root: "/home/user/shopwave",
    status: "pending",
  },
  {
    proposal_id: "ms-p2",
    action: "create_file",
    file_path: "auth-service/src/rate-limiter.ts",
    content: `import { Request, Response, NextFunction } from "express";

interface Window { timestamps: number[]; count: number; }

const windows = new Map<string, Window>();
const WINDOW_MS = 60_000;

const ROLE_LIMITS: Record<string, number> = {
  admin: 1000,
  user: 100,
  anonymous: 20,
};

export function rateLimiter(req: Request, res: Response, next: NextFunction) {
  const key = req.ip ?? "anonymous";
  const role = (req as any).user?.role ?? "anonymous";
  const limit = ROLE_LIMITS[role] ?? ROLE_LIMITS.anonymous;
  const now = Date.now();

  let win = windows.get(key) ?? { timestamps: [], count: 0 };
  win.timestamps = win.timestamps.filter((t) => now - t < WINDOW_MS);
  win.count = win.timestamps.length;

  if (win.count >= limit) {
    return res.status(429).json({
      error: "Rate limit exceeded",
      retryAfter: Math.ceil((win.timestamps[0] + WINDOW_MS - now) / 1000),
    });
  }

  win.timestamps.push(now);
  win.count++;
  windows.set(key, win);

  res.setHeader("X-RateLimit-Limit", limit);
  res.setHeader("X-RateLimit-Remaining", limit - win.count);
  next();
}`,
    description: "Sliding-window rate limiter with per-role limits (admin: 1000, user: 100, anon: 20)",
    project_root: "/home/user/shopwave",
    status: "pending",
  },
  {
    proposal_id: "ms-p3",
    action: "create_file",
    file_path: "proto/auth.proto",
    content: `syntax = "proto3";

package auth;

service AuthService {
  rpc ValidateToken (TokenRequest) returns (TokenResponse);
  rpc RefreshToken  (RefreshRequest) returns (TokenResponse);
  rpc RevokeToken   (RevokeRequest) returns (RevokeResponse);
}

message TokenRequest {
  string token = 1;
}

message TokenResponse {
  bool   valid   = 1;
  string user_id = 2;
  string role    = 3;
  int64  exp     = 4;
}

message RefreshRequest {
  string refresh_token = 1;
}

message RevokeRequest {
  string token = 1;
}

message RevokeResponse {
  bool revoked = 1;
}`,
    description: "Shared gRPC contract — ValidateToken, RefreshToken, RevokeToken",
    project_root: "/home/user/shopwave",
    status: "pending",
  },
  {
    proposal_id: "ms-p4",
    action: "edit_file",
    file_path: "src/middleware/auth.ts",
    content: `import { credentials } from "@grpc/grpc-js";
import { AuthServiceClient } from "../proto/auth_grpc_pb";

const authClient = new AuthServiceClient(
  process.env.AUTH_SERVICE_URL ?? "localhost:4001",
  credentials.createInsecure()
);

export async function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.split("Bearer ")[1];
  if (!token) return res.status(401).json({ error: "Missing token" });

  const response = await authClient.validateToken({ token });
  if (!response.valid) return res.status(401).json({ error: "Invalid token" });

  req.user = { userId: response.user_id, role: response.role };
  next();
}`,
    description: "Replaced 35-line JWT logic with 2-line gRPC call to auth-service",
    project_root: "/home/user/shopwave",
    status: "pending",
  },
];

// ---------------------------------------------------------------------------
// Scene 3 — "The Yes" — Command Approval + Terminal Execution
// ---------------------------------------------------------------------------

export const SCENE3_COMMAND: CommandProposal = {
  command_id: "ms-cmd1",
  command:
    "mkdir -p auth-service/src proto && cp src/middleware/auth.ts auth-service/src/ && protoc --ts_out=. proto/auth.proto",
  description: "Create auth-service directory, copy files, compile proto contract",
  project_path: "/home/user/shopwave",
  status: "pending",
};

export const SCENE3_TERMINAL: TerminalOutput = {
  command:
    "$ mkdir -p auth-service/src proto && cp src/middleware/auth.ts auth-service/src/ && protoc --ts_out=. proto/auth.proto",
  output: `Creating auth-service/src/ …
Creating proto/ …

✓ auth-service/src/index.ts         created  (28 lines)
✓ auth-service/src/rate-limiter.ts  created  (42 lines)
✓ proto/auth.proto                  created  (31 lines)
✓ src/middleware/auth.ts            updated  (35 → 16 lines)

Compiling proto/auth.proto …
✓ proto/auth_grpc_pb.ts generated
✓ proto/auth_pb.ts generated

4 files changed · 1 service extracted · 0 errors`,
  isLoading: false,
  scope: "local",
};

export const SCENE3_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "terminal_execution",
    nodes: [
      { id: "e1", iconType: "Terminal", title: "Execute", description: "Creating files…", status: "active" },
      { id: "e2", iconType: "FileCode2", title: "Compile", description: "Awaiting", status: "pending" },
      { id: "e3", iconType: "HardDrive", title: "Done", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "terminal_execution",
    nodes: [
      { id: "e1", iconType: "Terminal", title: "Execute", description: "4 files written", status: "completed" },
      { id: "e2", iconType: "FileCode2", title: "Compile", description: "protoc running…", status: "active" },
      { id: "e3", iconType: "HardDrive", title: "Done", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "terminal_execution",
    nodes: [
      { id: "e1", iconType: "Terminal", title: "Execute", description: "4 files written", status: "completed" },
      { id: "e2", iconType: "FileCode2", title: "Compile", description: "Proto compiled", status: "completed" },
      { id: "e3", iconType: "HardDrive", title: "Done", description: "Service extracted", status: "completed" },
    ],
  },
];

