# Voco V3 Ideas — Backlog for Post-PMF

> **Rule:** Nothing in this file gets built until a paying user mentions the problem unprompted.
> Threshold to greenlight any item: ≥20% of paying users report the pain in feedback.

---

## 1. Cross-Model Memory Layer — "Model Amnesia Cure"

**The Problem:**
When a power user switches between Claude, Gemini, and ChatGPT for different tasks, each model starts blind. It doesn't know what the previous model did, why it made its decisions, or what changed in the codebase. No existing product solves this.

**The Research:**
- RedMonk (Dec 2025): "Persistent Memory" is #2 developer priority for 2026. Developers want "a living system of record that captures not just code but **reasoning**."
- Mem0 paper (arXiv:2504.19413, Apr 2025): Cross-session memory achieves 26% improvement over OpenAI's native memory, 91% lower p95 latency, 90% token savings vs full-context replay.
- Every existing solution (OpenAI Memory, Anthropic Projects, Windsurf Memories, Claude Code) is **siloed by vendor**. Zero cross-model solutions exist.

**The Voco Advantage:**
The Logic Ledger already captures architectural intent. V3 adds one input layer:

```
Today:     Voco Claude reasoning → Logic Ledger
V3:        ANY model session (Cursor/GPT/Gemini) → Logic Ledger via MCP observer
```

**Example interaction:**
> "Gemini rewrote your auth middleware 3 days ago — it switched from JWT to session cookies because of XSS concerns. Want me to read you the rationale before you continue?"

**Why MCP makes this possible:**
MCP became the fastest-adopted dev standard RedMonk has ever tracked. Adopted by OpenAI, Google DeepMind, Microsoft, and AWS by end of 2025. A Voco MCP server could passively observe and record decisions from any MCP-connected tool.

**What needs to be built:**
- Voco MCP observer server that hooks into IDE events (Cursor, Windsurf, VS Code)
- Decision extraction layer: parse model output → structured rationale → write to Ledger
- Voice recall: "What did the last AI session do in this file?"
- Cross-model diff: "Here's what Claude would do differently than what GPT-4 suggested"

**Competitive moat:**
Zero-to-one by Thiel's definition. No product does this. Voice + cross-model memory + local-first execution = entirely new category.

**Greenlight signal:** ≥20% of V2 paying users mention multi-model confusion in feedback unprompted.

---

## 2. Predictable Pricing Transparency

**The Problem:**
RedMonk (Dec 2025): "Pricing turbulence and rug pulls of 2025 left developers frustrated. Cursor's shift to usage-based pricing caught users off guard. Claude Code users reported restrictive limits inconsistent with their Max subscriptions."

**The Voco angle:**
Show users exactly what each voice turn costs — token count, model cost, total session spend — inline in the UI. Kiro (2025) pioneered this and it became an expectation.

**Greenlight signal:** Any billing complaint from V2 users.

---

## 3. Background Agent Mode — "Overnight PRs"

**The Problem:**
RedMonk #1: "Developers want to queue up tasks, let agents work in the background or even overnight, and return to review completed pull requests."

**The Voco angle:**
Voice-queue a task before leaving your desk. Voco runs it overnight using the LangGraph background worker, presents a voice summary when you return: "I refactored the auth module, ran the tests (12/12 pass), and created a draft PR. Review?"

**Dependencies:** Requires robust HITL + approval flow (already in V2) + GitHub automation (already in V2 tools).

**Greenlight signal:** Users ask "can Voco keep working while I sleep?"

---

## 4. Rollback-by-Voice

**The Problem:**
RedMonk #9: "Developers want Git-native undo for AI actions."

**The Voco angle:**
Every approved Voco action auto-creates a Git commit. Voice command: "Voco, undo the last 3 changes." Voco speaks the diff, asks for confirmation, then `git revert`.

**Greenlight signal:** Users express fear of committing AI changes.

---

## 5. Multi-Model Orchestration (Router Mode)

**The Problem:**
Different models have different strengths. Claude is best for reasoning, Gemini for long context, GPT-4o for multimodal. Switching manually is friction.

**The Voco angle:**
Voco's ContextRouter intelligently dispatches to the right model per task — silently. "Search the repo" → local ripgrep. "Explain this 200k-token codebase" → Gemini. "Generate the PR description" → Claude.

**Dependencies:** LiteLLM gateway already handles multi-model routing. This is UI + routing logic only.

**Greenlight signal:** Users complain about model selection friction.

---

## Notes

- **Don't pre-optimize.** Every item above starts as a 1-sentence mention in user feedback before it becomes a sprint.
- **Logic Ledger is the foundation** for ideas #1, #3, #4. Every V3 feature builds on the Ledger — protect its integrity in V2.
- **MCP is the integration layer** for ideas #1, #2, #5. V2's MCP gateway is the right foundation.

*Last updated: Feb 2026 — after V2 beta launch decision.*
