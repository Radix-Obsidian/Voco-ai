import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
} from "@/hooks/use-voco-socket";

// ═══════════════════════════════════════════════════════════════════════════
// DEMO: "DraftClaw Spreads Market" — Real Feature Addition (2:30 screencast)
//
// Scene 1 — THE ASK:  Voice → ledger animates → intent parsed → codebase searched
// Scene 2 — THE PLAN: ReviewDeck with 3 edit proposals (HITL approve)
// Scene 3 — THE SHIP: Command approval → terminal streams test + commit
// Scene 4 — THE PR:   Command approval → terminal streams PR creation
// ═══════════════════════════════════════════════════════════════════════════

// ---------------------------------------------------------------------------
// Scene 1 — "The Ask" — Voice → Intent Ledger
// ---------------------------------------------------------------------------

export const SCENE1_TRANSCRIPT =
  "Add spreads market support to DraftClaw's EV analysis. Right now it only does moneyline and totals — spreads is the biggest market and we're leaving edge on the table.";

export const SCENE1_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "code_generation",
    nodes: [
      { id: "s1", iconType: "Database", title: "Parse Intent", description: "Analyzing voice…", status: "active" },
      { id: "s2", iconType: "FileCode2", title: "Search Codebase", description: "Awaiting", status: "pending" },
      { id: "s3", iconType: "Terminal", title: "Plan Changes", description: "Awaiting", status: "pending" },
      { id: "s4", iconType: "HardDrive", title: "Generate Diffs", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_generation",
    nodes: [
      { id: "s1", iconType: "Database", title: "Parse Intent", description: "Spread market support", status: "completed" },
      { id: "s2", iconType: "FileCode2", title: "Search Codebase", description: "Finding analysis files…", status: "active" },
      { id: "s3", iconType: "Terminal", title: "Plan Changes", description: "Awaiting", status: "pending" },
      { id: "s4", iconType: "HardDrive", title: "Generate Diffs", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_generation",
    nodes: [
      { id: "s1", iconType: "Database", title: "Parse Intent", description: "Spread market support", status: "completed" },
      { id: "s2", iconType: "FileCode2", title: "Search Codebase", description: "3 files found", status: "completed" },
      { id: "s3", iconType: "Terminal", title: "Plan Changes", description: "Mapping dependencies…", status: "active" },
      { id: "s4", iconType: "HardDrive", title: "Generate Diffs", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "code_generation",
    nodes: [
      { id: "s1", iconType: "Database", title: "Parse Intent", description: "Spread market support", status: "completed" },
      { id: "s2", iconType: "FileCode2", title: "Search Codebase", description: "3 files found", status: "completed" },
      { id: "s3", iconType: "Terminal", title: "Plan Changes", description: "3 files, 4 edits", status: "completed" },
      { id: "s4", iconType: "HardDrive", title: "Generate Diffs", description: "Review ready", status: "active" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Scene 2 — "The Plan" — ReviewDeck with 3 real DraftClaw edits (HITL)
// ---------------------------------------------------------------------------

export const SCENE2_PROPOSALS: Proposal[] = [
  {
    proposal_id: "dc-p1",
    action: "edit_file",
    file_path: "extensions/draft-claw/src/types.ts",
    content: `export interface Outcome {
  name: string;
  price: number;
  point?: number;
}

export interface Market {
  key: string;
  last_update: string;
  outcomes: Outcome[];
}

export interface Bookmaker {
  key: string;
  title: string;
  last_update: string;
  markets: Market[];
}

export type Recommendation =
  | "Bet Home"
  | "Bet Away"
  | "Bet Over"
  | "Bet Under"
  | "Bet Spread";

export type Confidence = "High" | "Medium" | "Low";`,
    description: 'Add "Bet Spread" to the Recommendation union type',
    project_root: "~/dev/DraftClaw",
    status: "pending",
  },
  {
    proposal_id: "dc-p2",
    action: "edit_file",
    file_path: "extensions/draft-claw/src/analysis.ts",
    content: `// ── Add "spreads" to market loop (was: ["h2h", "totals"]) ──
for (const marketKey of ["h2h", "spreads", "totals"]) {
  const sharpProbs = getSharpProbabilities(event.bookmakers, marketKey);
  if (!sharpProbs) continue;

  for (const softBook of softBooks) {
    const market = softBook.markets.find((m) => m.key === marketKey);
    if (!market) continue;

    for (const outcome of market.outcomes) {
      // ... existing EV calculation ...

      // ── New: spread-specific recommendation ──
      let recommendation: Recommendation;
      if (marketKey === "h2h") {
        recommendation = isHomeTeam ? "Bet Home" : "Bet Away";
      } else if (marketKey === "spreads") {
        recommendation = "Bet Spread";
      } else {
        recommendation = outcome.name.toLowerCase().includes("over")
          ? "Bet Over" : "Bet Under";
      }

      // ── New: spread reasoning ──
      if (marketKey === "spreads" && outcome.point !== undefined) {
        const spread = outcome.point;
        if (spread > 0) {
          parts.push(
            \`Getting +\${spread} pts with \${edge.toFixed(1)}% edge — \` +
            \`sharp consensus \${(trueProb * 100).toFixed(0)}% vs implied \${(impliedProb * 100).toFixed(0)}%\`
          );
        } else {
          parts.push(
            \`Laying \${Math.abs(spread)} pts but \${edge.toFixed(1)}% edge justifies — \` +
            \`sharp \${(trueProb * 100).toFixed(0)}% vs market \${(impliedProb * 100).toFixed(0)}%\`
          );
        }
      }
    }
  }
}`,
    description: "Add spreads to market loop + spread recommendation handler + spread-specific reasoning",
    project_root: "~/dev/DraftClaw",
    status: "pending",
  },
  {
    proposal_id: "dc-p3",
    action: "edit_file",
    file_path: "extensions/draft-claw/index.ts",
    content: `const ClawSheetOutputSchema = z.object({
  timestamp: z.string(),
  mode: z.enum(["mock", "live"]),
  analyses: z.array(
    z.object({
      game: z.string(),
      market: z.string(),
      recommendation: z.enum([
        "Bet Home",
        "Bet Away",
        "Bet Over",
        "Bet Under",
        "Bet Spread",
      ]),
      impliedProbability: z.number(),
      clawProbability: z.number(),
      edge: z.number(),
      confidence: z.enum(["High", "Medium", "Low"]),
      reasoning: z.string(),
      deepLink: z.string(),
    })
  ),
  summary: z.object({
    totalGames: z.number(),
    opportunitiesFound: z.number(),
    highConfidence: z.number(),
  }),
});`,
    description: 'Add "Bet Spread" to Zod validation schema for ClawSheet output',
    project_root: "~/dev/DraftClaw",
    status: "pending",
  },
];

// ---------------------------------------------------------------------------
// Scene 3 — "The Ship" — Command Approval + Terminal (test + commit)
// ---------------------------------------------------------------------------

export const SCENE3_COMMAND: CommandProposal = {
  command_id: "dc-cmd1",
  command:
    'cd extensions/draft-claw && pnpm test && git checkout -b feat/spreads-market && git add -A && git commit -m "feat: add spreads market EV analysis"',
  description: "Run tests, create feature branch, and commit all changes",
  project_path: "~/dev/DraftClaw",
  status: "pending",
};

export const SCENE3_TERMINAL: TerminalOutput = {
  command:
    '$ cd extensions/draft-claw && pnpm test && git checkout -b feat/spreads-market && git add -A && git commit -m "feat: add spreads market EV analysis"',
  output: `> draft-claw@0.4.2 test
> vitest run

 ✓ src/__tests__/analysis.test.ts (12 tests) 340ms
   ✓ analyzes h2h markets correctly
   ✓ analyzes totals markets correctly
   ✓ analyzes spreads markets correctly
   ✓ detects positive EV on spread with sharp edge
   ✓ skips negative EV spreads
   ✓ builds spread reasoning for underdog getting points
   ✓ builds spread reasoning for favorite laying points
   ✓ validates Recommendation union type
   ✓ handles missing odds gracefully
   ✓ respects minEdgePercentage threshold
   ✓ returns correct market keys
   ✓ Zod schema validates "Bet Spread"

 ✓ src/__tests__/bookmakers.test.ts (4 tests) 28ms

 Test Files  2 passed (2)
      Tests  16 passed (16)
   Start at  14:32:07
   Duration  1.84s

Switched to a new branch 'feat/spreads-market'

[feat/spreads-market 3a1f9cb] feat: add spreads market EV analysis
 3 files changed, 47 insertions(+), 3 deletions(-)`,
  isLoading: false,
  scope: "local",
};

export const SCENE3_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "ship",
    nodes: [
      { id: "t1", iconType: "Terminal", title: "Tests", description: "Running vitest…", status: "active" },
      { id: "t2", iconType: "GitBranch", title: "Branch", description: "Awaiting", status: "pending" },
      { id: "t3", iconType: "HardDrive", title: "Commit", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "ship",
    nodes: [
      { id: "t1", iconType: "Terminal", title: "Tests", description: "16 passed", status: "completed" },
      { id: "t2", iconType: "GitBranch", title: "Branch", description: "Creating branch…", status: "active" },
      { id: "t3", iconType: "HardDrive", title: "Commit", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "ship",
    nodes: [
      { id: "t1", iconType: "Terminal", title: "Tests", description: "16 passed", status: "completed" },
      { id: "t2", iconType: "GitBranch", title: "Branch", description: "feat/spreads-market", status: "completed" },
      { id: "t3", iconType: "HardDrive", title: "Commit", description: "3a1f9cb", status: "completed" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Scene 4 — "The PR" — Command Approval + Terminal (push + PR)
// ---------------------------------------------------------------------------

export const SCENE4_COMMAND: CommandProposal = {
  command_id: "dc-cmd2",
  command:
    'git push -u origin feat/spreads-market && gh pr create --title "feat: add spreads market EV analysis" --body "Adds spread betting support to the EV analysis pipeline.\n\n- Spread market loop + reasoning\n- Zod schema + type updates\n- 16/16 tests passing"',
  description: "Push branch and open pull request on GitHub",
  project_path: "~/dev/DraftClaw",
  status: "pending",
};

export const SCENE4_TERMINAL: TerminalOutput = {
  command:
    '$ git push -u origin feat/spreads-market && gh pr create --title "feat: add spreads market EV analysis" --body "..."',
  output: `Enumerating objects: 9, done.
Counting objects: 100% (9/9), done.
Delta compression using up to 10 threads
Compressing objects: 100% (5/5), done.
Writing objects: 100% (5/5), 1.83 KiB | 1.83 MiB/s, done.
Total 5 (delta 3), reused 0 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (3/3), completed with 3 local objects.
remote:
remote: Create a pull request for 'feat/spreads-market' on GitHub by visiting:
remote:   https://github.com/Radix-Obsidian/DraftClaw/pull/new/feat/spreads-market
remote:
To github.com:Radix-Obsidian/DraftClaw.git
 * [new branch]      feat/spreads-market -> feat/spreads-market
branch 'feat/spreads-market' set up to track 'origin/feat/spreads-market'.

Creating pull request for feat/spreads-market into main in Radix-Obsidian/DraftClaw

https://github.com/Radix-Obsidian/DraftClaw/pull/42`,
  isLoading: false,
  scope: "local",
};

export const SCENE4_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "pull_request",
    nodes: [
      { id: "pr1", iconType: "GitBranch", title: "Push", description: "Pushing to origin…", status: "active" },
      { id: "pr2", iconType: "Github", title: "PR", description: "Awaiting", status: "pending" },
      { id: "pr3", iconType: "HardDrive", title: "Done", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "pull_request",
    nodes: [
      { id: "pr1", iconType: "GitBranch", title: "Push", description: "Branch pushed", status: "completed" },
      { id: "pr2", iconType: "Github", title: "PR", description: "Opening PR #42…", status: "active" },
      { id: "pr3", iconType: "HardDrive", title: "Done", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "pull_request",
    nodes: [
      { id: "pr1", iconType: "GitBranch", title: "Push", description: "Branch pushed", status: "completed" },
      { id: "pr2", iconType: "Github", title: "PR", description: "PR #42 opened", status: "completed" },
      { id: "pr3", iconType: "HardDrive", title: "Done", description: "Ship it!", status: "completed" },
    ],
  },
];
