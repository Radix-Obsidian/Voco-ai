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

// ---------------------------------------------------------------------------
// Scene 4 — "Build Me an App" → MVP Builder → Live Sandbox
// ---------------------------------------------------------------------------

export const SCENE4_TRANSCRIPT = "Build me a task tracker app with dark mode";

export const SCENE4_UPDATE_TRANSCRIPT = "Add a priority column with color tags";

export const SCENE4_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "ui",
    nodes: [
      { id: "s4-1", iconType: "FileCode2", title: "Domain", description: "UI/Frontend", status: "completed" },
      { id: "s4-2", iconType: "FileCode2", title: "Generate", description: "Building MVP…", status: "active" },
      { id: "s4-3", iconType: "HardDrive", title: "Sandbox", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "ui",
    nodes: [
      { id: "s4-1", iconType: "FileCode2", title: "Domain", description: "UI/Frontend", status: "completed" },
      { id: "s4-2", iconType: "FileCode2", title: "Generate", description: "Complete", status: "completed" },
      { id: "s4-3", iconType: "HardDrive", title: "Sandbox", description: "Live preview", status: "active" },
    ],
  },
  {
    domain: "ui",
    nodes: [
      { id: "s4-1", iconType: "FileCode2", title: "Domain", description: "UI/Frontend", status: "completed" },
      { id: "s4-2", iconType: "FileCode2", title: "Generate", description: "Complete", status: "completed" },
      { id: "s4-3", iconType: "HardDrive", title: "Sandbox", description: "Live", status: "completed" },
    ],
  },
];

export const SCENE4_SANDBOX_HTML = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Task Tracker</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-950 text-white min-h-screen p-8">
<div class="max-w-2xl mx-auto space-y-6">
  <h1 class="text-3xl font-bold">Task Tracker</h1>
  <div class="bg-white/5 rounded-2xl ring-1 ring-white/10 p-6 space-y-4">
    <div class="flex gap-3">
      <input type="text" placeholder="Add a task…" class="flex-1 bg-white/5 rounded-xl px-4 py-2 text-sm ring-1 ring-white/10 focus:ring-emerald-500 outline-none" />
      <button class="bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl px-4 py-2 text-sm font-medium transition">Add</button>
    </div>
    <ul class="space-y-2">
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10">
        <input type="checkbox" class="accent-emerald-500" />
        <span>Design landing page mockup</span>
      </li>
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10">
        <input type="checkbox" class="accent-emerald-500" />
        <span>Set up CI/CD pipeline</span>
      </li>
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10 opacity-50 line-through">
        <input type="checkbox" checked class="accent-emerald-500" />
        <span>Initialize project repo</span>
      </li>
    </ul>
  </div>
</div>
</body></html>`;

export const SCENE4_UPDATED_HTML = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Task Tracker</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-950 text-white min-h-screen p-8">
<div class="max-w-2xl mx-auto space-y-6">
  <h1 class="text-3xl font-bold">Task Tracker</h1>
  <div class="bg-white/5 rounded-2xl ring-1 ring-white/10 p-6 space-y-4">
    <div class="flex gap-3">
      <input type="text" placeholder="Add a task…" class="flex-1 bg-white/5 rounded-xl px-4 py-2 text-sm ring-1 ring-white/10 focus:ring-emerald-500 outline-none" />
      <button class="bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl px-4 py-2 text-sm font-medium transition">Add</button>
    </div>
    <ul class="space-y-2">
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10">
        <input type="checkbox" class="accent-emerald-500" />
        <span class="flex-1">Design landing page mockup</span>
        <span class="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 ring-1 ring-red-500/30">High</span>
      </li>
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10">
        <input type="checkbox" class="accent-emerald-500" />
        <span class="flex-1">Set up CI/CD pipeline</span>
        <span class="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30">Medium</span>
      </li>
      <li class="flex items-center gap-3 bg-white/5 rounded-xl px-4 py-3 ring-1 ring-white/10 opacity-50 line-through">
        <input type="checkbox" checked class="accent-emerald-500" />
        <span class="flex-1">Initialize project repo</span>
        <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30">Low</span>
      </li>
    </ul>
  </div>
</div>
</body></html>`;

// ---------------------------------------------------------------------------
// Scene 5 — "Analyze This YouTube Tutorial" → Video MCP / Synapse
// ---------------------------------------------------------------------------

export const SCENE5_TRANSCRIPT =
  "Analyze this YouTube tutorial and extract the React code — youtube.com/watch?v=demo123";

export const SCENE5_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "code_search",
    nodes: [
      { id: "s5-1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "s5-2", iconType: "Terminal", title: "Video Download", description: "Downloading…", status: "active" },
      { id: "s5-3", iconType: "FileCode2", title: "Gemini Analysis", description: "Awaiting", status: "pending" },
      { id: "s5-4", iconType: "FileCode2", title: "Results", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "s5-1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "s5-2", iconType: "Terminal", title: "Video Download", description: "Complete", status: "completed" },
      { id: "s5-3", iconType: "FileCode2", title: "Gemini Analysis", description: "Analyzing with gemini-1.5-pro…", status: "active" },
      { id: "s5-4", iconType: "FileCode2", title: "Results", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "s5-1", iconType: "Database", title: "Domain", description: "code_search", status: "completed" },
      { id: "s5-2", iconType: "Terminal", title: "Video Download", description: "Complete", status: "completed" },
      { id: "s5-3", iconType: "FileCode2", title: "Gemini Analysis", description: "Complete", status: "completed" },
      { id: "s5-4", iconType: "FileCode2", title: "Results", description: "Code extracted", status: "completed" },
    ],
  },
];

export const SCENE5_TERMINAL_STAGES: string[] = [
  `[synapse] Downloading video: youtube.com/watch?v=demo123
[synapse] Format: 720p mp4 (12.4 MB)
[synapse] Progress: ██████████░░░░░░ 62%`,

  `[synapse] Download complete (12.4 MB)
[synapse] Uploading to Gemini File API...
[synapse] File state: PROCESSING
[synapse] Analyzing with gemini-1.5-pro...`,

  `[synapse] Analysis complete!
[synapse] Extracted 3 React components, 2 custom hooks
[synapse] Output:

\`\`\`tsx
// Component: TaskBoard.tsx
import { useState } from "react";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";

interface Task {
  id: string;
  title: string;
  status: "todo" | "in-progress" | "done";
}

export function TaskBoard() {
  const [tasks, setTasks] = useState<Task[]>([
    { id: "1", title: "Design system setup", status: "todo" },
    { id: "2", title: "API integration", status: "in-progress" },
    { id: "3", title: "Unit tests", status: "done" },
  ]);

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      {["todo", "in-progress", "done"].map((status) => (
        <Droppable key={status} droppableId={status}>
          {(provided) => (
            <div ref={provided.innerRef} {...provided.droppableProps}>
              {tasks.filter((t) => t.status === status).map((task, i) => (
                <Draggable key={task.id} draggableId={task.id} index={i}>
                  {(provided) => (
                    <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}>
                      {task.title}
                    </div>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
            </div>
          )}
        </Droppable>
      ))}
    </DragDropContext>
  );
}
\`\`\``,
];

// ---------------------------------------------------------------------------
// Scene 6 — "Deep Codebase Exploration" — All 4 Search Primitives
// ---------------------------------------------------------------------------

export const SCENE6_TRANSCRIPT =
  "Show me the project structure, find all route files, then read the auth middleware";

export const SCENE6_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "code_search",
    nodes: [
      { id: "s6-1", iconType: "Database", title: "Domain", description: "API", status: "completed" },
      { id: "s6-2", iconType: "FileCode2", title: "List Directory", description: "Scanning structure…", status: "active" },
      { id: "s6-3", iconType: "FileCode2", title: "Glob Find", description: "Awaiting", status: "pending" },
      { id: "s6-4", iconType: "FileCode2", title: "Read File", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "s6-1", iconType: "Database", title: "Domain", description: "API", status: "completed" },
      { id: "s6-2", iconType: "FileCode2", title: "List Directory", description: "Complete", status: "completed" },
      { id: "s6-3", iconType: "FileCode2", title: "Glob Find", description: "Searching…", status: "active" },
      { id: "s6-4", iconType: "FileCode2", title: "Read File", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "s6-1", iconType: "Database", title: "Domain", description: "API", status: "completed" },
      { id: "s6-2", iconType: "FileCode2", title: "List Directory", description: "Complete", status: "completed" },
      { id: "s6-3", iconType: "FileCode2", title: "Glob Find", description: "4 files found", status: "completed" },
      { id: "s6-4", iconType: "FileCode2", title: "Read File", description: "Reading…", status: "active" },
    ],
  },
  {
    domain: "code_search",
    nodes: [
      { id: "s6-1", iconType: "Database", title: "Domain", description: "API", status: "completed" },
      { id: "s6-2", iconType: "FileCode2", title: "List Directory", description: "Complete", status: "completed" },
      { id: "s6-3", iconType: "FileCode2", title: "Glob Find", description: "4 files found", status: "completed" },
      { id: "s6-4", iconType: "FileCode2", title: "Read File", description: "Complete", status: "completed" },
    ],
  },
];

export const SCENE6_TERMINAL_STAGES: TerminalOutput[] = [
  {
    command: "$ list_directory ./src --depth 3",
    output: `src/
  middleware/
    auth.ts
    rate-limiter.ts
    cors.ts
  routes/
    api.ts
    admin.ts
    health.ts
    webhooks.ts
  utils/
    logger.ts
    config.ts
  index.ts
  server.ts`,
    isLoading: false,
    scope: "local",
  },
  {
    command: '$ glob_find "*.route.ts" ./src',
    output: `src/routes/api.route.ts
src/routes/admin.route.ts
src/routes/health.route.ts
src/routes/webhooks.route.ts

4 files found`,
    isLoading: false,
    scope: "local",
  },
  {
    command: "$ read_file src/middleware/auth.ts:1-35",
    output: `import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";

interface AuthPayload {
  userId: string;
  role: "admin" | "user";
  iat: number;
  exp: number;
}

export function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    return res.status(401).json({ error: "Missing or invalid Authorization header" });
  }

  const token = header.split("Bearer ")[1];
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET!) as AuthPayload;
    req.user = decoded;
    next();
  } catch (err) {
    if (err instanceof jwt.TokenExpiredError) {
      return res.status(401).json({ error: "Token expired" });
    }
    return res.status(401).json({ error: "Invalid token" });
  }
}

// Rate limit config per role
const RATE_LIMITS: Record<string, number> = {
  admin: 1000,
  user: 100,
};`,
    isLoading: false,
    scope: "local",
  },
];
