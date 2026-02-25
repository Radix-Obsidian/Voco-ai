import type {
  TerminalOutput,
  Proposal,
  LedgerState,
  CommandProposal,
} from "@/hooks/use-voco-socket";

// ---------------------------------------------------------------------------
// Scene 0 — "Connect Existing Repo" → Project scan → File tree
// ---------------------------------------------------------------------------

export const SCENE0_TRANSCRIPT = "Connect my e-commerce project at projects slash shopwave";

export const SCENE0_LEDGER_STAGES: LedgerState[] = [
  {
    domain: "project",
    nodes: [
      { id: "s0-1", iconType: "FolderSync", title: "Connect", description: "Scanning project…", status: "active" },
      { id: "s0-2", iconType: "FileCode2", title: "Index", description: "Awaiting", status: "pending" },
      { id: "s0-3", iconType: "Database", title: "Ready", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "project",
    nodes: [
      { id: "s0-1", iconType: "FolderSync", title: "Connect", description: "142 files found", status: "completed" },
      { id: "s0-2", iconType: "FileCode2", title: "Index", description: "Building AST map…", status: "active" },
      { id: "s0-3", iconType: "Database", title: "Ready", description: "Awaiting", status: "pending" },
    ],
  },
  {
    domain: "project",
    nodes: [
      { id: "s0-1", iconType: "FolderSync", title: "Connect", description: "142 files found", status: "completed" },
      { id: "s0-2", iconType: "FileCode2", title: "Index", description: "AST indexed", status: "completed" },
      { id: "s0-3", iconType: "Database", title: "Ready", description: "Project connected", status: "completed" },
    ],
  },
];

export const SCENE0_TERMINAL: TerminalOutput = {
  command: "$ voco connect ~/projects/shopwave",
  output: `Scanning ~/projects/shopwave …

shopwave/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── (shop)/
│   │       ├── products/page.tsx
│   │       ├── cart/page.tsx
│   │       └── checkout/page.tsx
│   ├── components/
│   │   ├── ProductCard.tsx
│   │   ├── CartDrawer.tsx
│   │   ├── Header.tsx
│   │   └── ui/ (12 files)
│   ├── lib/
│   │   ├── stripe.ts
│   │   ├── db.ts
│   │   └── auth.ts
│   └── middleware.ts
├── prisma/
│   └── schema.prisma
├── package.json  (next 14.2, prisma, stripe, tailwind)
├── tsconfig.json
└── .env.local

142 files · 18 components · 3 API routes · Prisma + Stripe detected
✓ Project indexed and ready`,
};

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

export const SCENE4_TRANSCRIPT = "Build me an AI chat interface with streaming responses";

export const SCENE4_UPDATE_TRANSCRIPT = "Add a conversation history sidebar and dark light toggle";

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
<title>NeuralChat</title>
<script src="https://cdn.tailwindcss.com"><\/script>
<style>
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
  .cursor-blink::after { content:'\\25AE'; animation:blink 0.7s infinite; margin-left:2px; }
  ::-webkit-scrollbar{width:6px} ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#333;border-radius:3px}
<\/style></head>
<body class="bg-gray-950 text-white h-screen flex flex-col overflow-hidden">
<!-- Header -->
<div class="flex items-center justify-between px-5 py-3 border-b border-white/10">
  <div class="flex items-center gap-3">
    <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-400 flex items-center justify-center text-sm font-bold">N<\/div>
    <span class="font-semibold text-sm">NeuralChat<\/span>
  </div>
  <select id="modelPicker" class="bg-white/5 text-xs text-zinc-400 rounded-lg px-3 py-1.5 border border-white/10 outline-none cursor-pointer">
    <option>GPT-4o</option><option>Claude 3.5</option><option>Gemini Pro</option><option>Llama 3.1</option>
  <\/select>
</div>
<!-- Messages -->
<div id="msgs" class="flex-1 overflow-y-auto px-5 py-4 space-y-4"><\/div>
<!-- Input -->
<div class="px-5 py-3 border-t border-white/10">
  <div class="flex gap-3 items-end">
    <textarea id="chatInput" rows="1" placeholder="Send a message…"
      class="flex-1 bg-white/5 rounded-xl px-4 py-2.5 text-sm ring-1 ring-white/10 focus:ring-violet-500 outline-none resize-none max-h-32"><\/textarea>
    <button id="sendBtn" class="bg-gradient-to-r from-violet-500 to-cyan-400 hover:opacity-90 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition flex-shrink-0">Send<\/button>
  </div>
</div>
<script>
  const msgs = [
    {role:"assistant",text:"Hello! I'm NeuralChat, your AI assistant. How can I help you today?"},
    {role:"user",text:"Explain how transformers work in deep learning"},
    {role:"assistant",text:"Transformers are a neural network architecture introduced in the 2017 paper \\"Attention Is All You Need.\\" They revolutionized NLP by replacing recurrence with **self-attention mechanisms**.\\n\\nKey components:\\n\\n1. **Self-Attention** \u2014 Each token attends to every other token, computing relevance scores\\n2. **Multi-Head Attention** \u2014 Multiple attention heads capture different relationship patterns in parallel\\n3. **Positional Encoding** \u2014 Since there's no recurrence, position information is injected via sinusoidal embeddings\\n4. **Feed-Forward Networks** \u2014 Each layer includes a position-wise FFN for non-linear transformation\\n\\nThe key breakthrough: O(1) sequential operations vs O(n) for RNNs, enabling massive parallelization during training."},
  ];
  const el = (tag,cls,html) => { const e=document.createElement(tag); if(cls)e.className=cls; if(html)e.innerHTML=html; return e; };
  function md(t){ return t.replace(/\\*\\*(.+?)\\*\\*/g,'<strong class="text-white">$1<\\/strong>').replace(/\\n/g,'<br>'); }
  function renderAll(){
    const c=document.getElementById("msgs"); c.innerHTML="";
    msgs.forEach(m=>{ c.appendChild(bubble(m)); });
    c.scrollTop=c.scrollHeight;
  }
  function bubble(m){
    const isUser=m.role==="user";
    const wrap=el("div","flex gap-3 "+(isUser?"justify-end":""));
    if(!isUser){
      const av=el("div","w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-cyan-400 flex-shrink-0 flex items-center justify-center text-[10px] font-bold","N");
      wrap.appendChild(av);
    }
    const bub=el("div","max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed "
      +(isUser?"bg-violet-600/30 text-violet-100 rounded-br-md":"bg-white/5 text-zinc-300 rounded-bl-md ring-1 ring-white/5"),
      md(m.text));
    wrap.appendChild(bub);
    return wrap;
  }
  function streamReply(text){
    const c=document.getElementById("msgs");
    const wrap=el("div","flex gap-3");
    const av=el("div","w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-cyan-400 flex-shrink-0 flex items-center justify-center text-[10px] font-bold","N");
    const bub=el("div","max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-white/5 text-zinc-300 rounded-bl-md ring-1 ring-white/5 cursor-blink","");
    wrap.appendChild(av); wrap.appendChild(bub); c.appendChild(wrap);
    let i=0;
    const iv=setInterval(()=>{
      i++; bub.innerHTML=md(text.slice(0,i));
      c.scrollTop=c.scrollHeight;
      if(i>=text.length){ clearInterval(iv); bub.classList.remove("cursor-blink"); msgs.push({role:"assistant",text:text}); }
    },12);
  }
  const replies=["That's a great question! Let me think about that...\\n\\nBased on my analysis, there are several approaches you could take. The most effective would be to start with a clear problem definition, then iterate rapidly with user feedback.\\n\\nWould you like me to go deeper on any specific aspect?","Here's a quick implementation:\\n\\n\`\`\`python\\ndef process(data):\\n    results = [transform(x) for x in data]\\n    return aggregate(results)\\n\`\`\`\\n\\nThis uses list comprehension for clean, readable code. The **transform** and **aggregate** functions handle the heavy lifting."];
  let ri=0;
  function send(){
    const inp=document.getElementById("chatInput");
    const v=inp.value.trim(); if(!v)return;
    msgs.push({role:"user",text:v}); inp.value=""; renderAll();
    setTimeout(()=>{ streamReply(replies[ri%replies.length]); ri++; },600);
  }
  document.getElementById("sendBtn").addEventListener("click",send);
  document.getElementById("chatInput").addEventListener("keydown",(e)=>{ if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();} });
  renderAll();
<\/script>
</body></html>`;

export const SCENE4_UPDATED_HTML = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NeuralChat</title>
<script src="https://cdn.tailwindcss.com"><\/script>
<style>
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
  .cursor-blink::after { content:'\\25AE'; animation:blink 0.7s infinite; margin-left:2px; }
  ::-webkit-scrollbar{width:6px} ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#555;border-radius:3px}
  .light { --bg:#ffffff; --bg2:#f9fafb; --fg:#111827; --fg2:#6b7280; --border:#e5e7eb; --card:#f3f4f6; --accent-from:#7c3aed; --accent-to:#06b6d4; }
  .dark  { --bg:#030712; --bg2:#0a0a0a; --fg:#f9fafb; --fg2:#9ca3af; --border:rgba(255,255,255,0.1); --card:rgba(255,255,255,0.03); --accent-from:#7c3aed; --accent-to:#06b6d4; }
  body { background:var(--bg); color:var(--fg); transition:background 0.3s,color 0.3s; }
  .sb-item { border-color:var(--border); background:var(--card); color:var(--fg2); }
  .sb-item:hover,.sb-item.active { background:rgba(124,58,237,0.1); color:var(--fg); }
<\/style></head>
<body class="dark h-screen flex overflow-hidden">
<!-- Sidebar -->
<div id="sidebar" class="w-64 flex-shrink-0 flex flex-col border-r" style="border-color:var(--border);background:var(--bg2)">
  <div class="p-3 border-b" style="border-color:var(--border)">
    <button id="newChat" class="w-full text-left text-xs px-3 py-2 rounded-lg sb-item font-medium" style="border:1px solid var(--border)">+ New Chat<\/button>
  </div>
  <div id="convList" class="flex-1 overflow-y-auto p-2 space-y-1"><\/div>
  <div class="p-3 border-t flex items-center justify-between" style="border-color:var(--border)">
    <span class="text-[10px]" style="color:var(--fg2)">Theme<\/span>
    <button id="themeBtn" class="text-xs px-2.5 py-1 rounded-lg sb-item" style="border:1px solid var(--border)">Light<\/button>
  </div>
</div>
<!-- Main -->
<div class="flex-1 flex flex-col">
  <div class="flex items-center justify-between px-5 py-3 border-b" style="border-color:var(--border)">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-400 flex items-center justify-center text-sm font-bold text-white">N<\/div>
      <span class="font-semibold text-sm" id="chatTitle">NeuralChat<\/span>
    </div>
    <select id="modelPicker" class="text-xs rounded-lg px-3 py-1.5 outline-none cursor-pointer" style="background:var(--card);color:var(--fg2);border:1px solid var(--border)">
      <option>GPT-4o</option><option>Claude 3.5</option><option>Gemini Pro</option><option>Llama 3.1</option>
    <\/select>
  </div>
  <div id="msgs" class="flex-1 overflow-y-auto px-5 py-4 space-y-4"><\/div>
  <div class="px-5 py-3 border-t" style="border-color:var(--border)">
    <div class="flex gap-3 items-end">
      <textarea id="chatInput" rows="1" placeholder="Send a message…"
        class="flex-1 rounded-xl px-4 py-2.5 text-sm outline-none resize-none max-h-32" style="background:var(--card);color:var(--fg);border:1px solid var(--border)"><\/textarea>
      <button id="sendBtn" class="bg-gradient-to-r from-violet-500 to-cyan-400 hover:opacity-90 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition flex-shrink-0">Send<\/button>
    </div>
  </div>
</div>
<script>
  const convs=[
    {id:1,title:"Transformers explained",msgs:[
      {role:"assistant",text:"Hello! I'm NeuralChat, your AI assistant. How can I help you today?"},
      {role:"user",text:"Explain how transformers work in deep learning"},
      {role:"assistant",text:"Transformers are a neural network architecture introduced in the 2017 paper \\"Attention Is All You Need.\\" They revolutionized NLP by replacing recurrence with **self-attention mechanisms**.\\n\\nKey components:\\n\\n1. **Self-Attention** \u2014 Each token attends to every other token\\n2. **Multi-Head Attention** \u2014 Multiple heads capture different patterns\\n3. **Positional Encoding** \u2014 Sinusoidal embeddings inject position info\\n4. **Feed-Forward Networks** \u2014 Position-wise FFN for non-linear transforms\\n\\nThe breakthrough: O(1) sequential ops vs O(n) for RNNs."},
    ]},
    {id:2,title:"React optimization",msgs:[
      {role:"assistant",text:"Hello! What would you like to know?"},
      {role:"user",text:"How do I optimize React re-renders?"},
      {role:"assistant",text:"Key strategies:\\n\\n1. **React.memo** \u2014 Wrap pure components\\n2. **useMemo / useCallback** \u2014 Memoize expensive computations and callbacks\\n3. **Key prop** \u2014 Stable keys prevent unnecessary unmount/remount\\n4. **Virtualization** \u2014 Use react-window for long lists\\n5. **Code splitting** \u2014 React.lazy + Suspense"},
    ]},
    {id:3,title:"Database indexing",msgs:[
      {role:"assistant",text:"Hi there! Ask me anything about databases."},
    ]},
  ];
  let activeId=1, isDark=true;
  const el=(tag,cls,html)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(html)e.innerHTML=html;return e;};
  function md(t){return t.replace(/\\*\\*(.+?)\\*\\*/g,'<strong style="color:var(--fg)">$1<\\/strong>').replace(/\\n/g,'<br>');}
  function renderSidebar(){
    const list=document.getElementById("convList"); list.innerHTML="";
    convs.forEach(c=>{
      const btn=el("button","sb-item w-full text-left text-xs px-3 py-2 rounded-lg truncate"+(c.id===activeId?" active":""),c.title);
      btn.style.cssText="border:none;cursor:pointer";
      btn.addEventListener("click",()=>{activeId=c.id;renderAll();});
      list.appendChild(btn);
    });
  }
  function getActive(){return convs.find(c=>c.id===activeId);}
  function bubble(m){
    const isUser=m.role==="user";
    const wrap=el("div","flex gap-3 "+(isUser?"justify-end":""));
    if(!isUser){const av=el("div","w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-cyan-400 flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-white","N");wrap.appendChild(av);}
    const bub=el("div","max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed "
      +(isUser?"rounded-br-md":"rounded-bl-md"),
      md(m.text));
    bub.style.cssText=isUser?"background:rgba(124,58,237,0.2);color:var(--fg)":"background:var(--card);color:var(--fg2);border:1px solid var(--border)";
    wrap.appendChild(bub); return wrap;
  }
  function renderMsgs(){
    const conv=getActive(); if(!conv)return;
    const c=document.getElementById("msgs"); c.innerHTML="";
    conv.msgs.forEach(m=>c.appendChild(bubble(m)));
    c.scrollTop=c.scrollHeight;
    document.getElementById("chatTitle").textContent=conv.title;
  }
  function renderAll(){renderSidebar();renderMsgs();}
  function streamReply(text){
    const c=document.getElementById("msgs");
    const wrap=el("div","flex gap-3");
    const av=el("div","w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-cyan-400 flex-shrink-0 flex items-center justify-center text-[10px] font-bold text-white","N");
    const bub=el("div","max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed cursor-blink","");
    bub.style.cssText="background:var(--card);color:var(--fg2);border:1px solid var(--border);border-bottom-left-radius:0.375rem";
    wrap.appendChild(av);wrap.appendChild(bub);c.appendChild(wrap);
    let i=0;
    const iv=setInterval(()=>{
      i++;bub.innerHTML=md(text.slice(0,i));c.scrollTop=c.scrollHeight;
      if(i>=text.length){clearInterval(iv);bub.classList.remove("cursor-blink");getActive().msgs.push({role:"assistant",text});}
    },12);
  }
  const replies=["Great question! Let me break that down...\\n\\nThe most effective approach combines **incremental delivery** with tight feedback loops. Start small, validate early, and scale what works.\\n\\nWant me to elaborate on any part?","Here's a concise implementation:\\n\\n\`\`\`python\\ndef process(data):\\n    return aggregate([transform(x) for x in data])\\n\`\`\`\\n\\nClean, readable, and the **transform** + **aggregate** pattern handles the complexity."];
  let ri=0;
  function send(){
    const inp=document.getElementById("chatInput");const v=inp.value.trim();if(!v)return;
    getActive().msgs.push({role:"user",text:v});inp.value="";renderMsgs();
    setTimeout(()=>{streamReply(replies[ri%replies.length]);ri++;},600);
  }
  document.getElementById("sendBtn").addEventListener("click",send);
  document.getElementById("chatInput").addEventListener("keydown",(e)=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});
  document.getElementById("newChat").addEventListener("click",()=>{
    const id=convs.length+1;convs.unshift({id,title:"New Chat",msgs:[{role:"assistant",text:"Hello! How can I help?"}]});activeId=id;renderAll();
  });
  document.getElementById("themeBtn").addEventListener("click",()=>{
    isDark=!isDark;document.body.className=(isDark?"dark":"light")+" h-screen flex overflow-hidden";
    document.getElementById("themeBtn").textContent=isDark?"Light":"Dark";
  });
  renderAll();
<\/script>
</body></html>`;

// ---------------------------------------------------------------------------
// Scene 5 — "Analyze This YouTube Tutorial" → Video MCP / Synapse
// ---------------------------------------------------------------------------

export const SCENE5_TRANSCRIPT =
  "Analyze this YouTube tutorial and extract the React code — youtube.com/watch?v=bTMPwUgLZf0";

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
  `[synapse] Downloading video: youtube.com/watch?v=bTMPwUgLZf0
[synapse] Format: 720p mp4 (48.7 MB)
[synapse] Progress: ██████████░░░░░░ 62%`,

  `[synapse] Download complete (48.7 MB)
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
