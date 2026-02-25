# Claude Code Plan Mode Prompt — Voco V2

**Mode:** Plan Only (no code execution until approved)

---

## My Engineering Preferences

- **DRY (Don't Repeat Yourself):** Flag repetition aggressively.
- **Testing:** Well-tested code is non-negotiable; prioritize higher test coverage.
- **Engineering Balance:** Aim for "engineered enough," avoiding both fragile implementations and premature abstractions.
- **Robustness:** Prioritize thorough edge-case handling over speed.
- **Clarity:** Bias toward explicit solutions over clever ones.

---

## Review Sections

For each section, present up to **4 top issues**. For every issue:

1. Describe the problem concretely with file and line references.
2. Present 2-3 options (including "do nothing" if reasonable).
3. For each option, specify: implementation effort, risk, impact on other code, and maintenance burden.
4. Provide a recommended option based on my preferences.
5. **Explicitly ask for agreement or a different direction before proceeding.**

### Section 1: Architecture Review
Evaluate system design, component boundaries, dependency graphs, coupling, data flow, bottlenecks, scaling, single points of failure, and security architecture.

### Section 2: Code Quality Review
Evaluate organization, module structure, and technical debt. Identify DRY violations and address error-handling patterns or missing edge cases.

### Section 3: Test Review
Evaluate coverage gaps, assertion strength, and untested failure modes across unit, integration, and e2e tests.

### Section 4: Performance Review
Evaluate N+1 queries, database access patterns, memory usage, caching, and high-complexity paths.

---

## Formatting Requirements

For each issue, use this structure:

```
## Issue N: [Brief Title]

**Location:** `path/to/file.py:LINE`

**Problem:** [Concrete description]

### Options

**Option A (Recommended):** [Title]
- Implementation effort: [Low/Medium/High]
- Risk: [Low/Medium/High]
- Impact: [What breaks or changes]
- Maintenance burden: [Low/Medium/High]

**Option B:** [Title]
- Implementation effort: [Low/Medium/High]
- Risk: [Low/Medium/High]
- Impact: [What breaks or changes]
- Maintenance burden: [Low/Medium/High]

**Option C:** Do nothing (accept the risk)
- Rationale: [Why this might be okay]

### Recommendation
[Your opinionated recommendation based on my preferences]

---
**Before proceeding, please confirm: Do you agree with this direction, or would you prefer a different approach?**
```

---

## Workflow

1. I will present **Section 1: Architecture Review** with up to 4 issues.
2. **Pause and wait for your feedback.**
3. Only proceed to the next section after you approve the current one's direction.
4. Repeat for Sections 2, 3, and 4.
5. After all sections are approved, I will provide a consolidated implementation plan.

---

## Scope

Review the following services:
- `services/mcp-gateway/` (Tauri + React frontend)
- `services/cognitive-engine/` (Python LangGraph backend)
- `services/synapse-mcp/` (YouTube video analysis MCP server)
- Root config files (`voco-mcp.json`, `tauri.conf.json`, etc.)

---

**Ready to begin with Section 1: Architecture Review.**
