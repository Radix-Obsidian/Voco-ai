# Demo 001 — Microservice Extraction (1:45)

> **One flow:** Speak a new microservice architecture → Voco plans + diffs → spoken "Yes" → files update.
> **Target:** Tired senior engineer scrolling LinkedIn at 11pm. Peer-to-peer tone. No hype.

---

## Pre-Production Checklist

| Item | Pre-record or Live? | Notes |
|------|---------------------|-------|
| Voco desktop app open on a monolith Express codebase | **Live** (hardcoded demo mode) | `?demo=true` in Tauri devUrl |
| Voiceover | **Pre-record** in OBS, splice in post | Record in quiet room, one take per section |
| Text overlays | **Post-production** (OBS or DaVinci) | Big, bold, 3-sec max per card |
| Terminal output & diffs | **Hardcoded** in `demo-script.ts` | No real backend needed — Dropbox-style "perfect flow" |
| Orb animation + transcript typing | **Live** from demo mode | Already implemented in app |

---

## Why This Works (Dropbox-Style Honesty)

Everything shown is **real UI running real code paths** — the data is hardcoded, but the components (VisualLedger, GhostTerminal, ReviewDeck, CommandApproval) are the actual production components. We're showing the real product experience with scripted data. No mock screenshots, no Figma prototypes.

---

## Second-by-Second Script

### ACT 1 — THE HOOK (0:00 – 0:08)

| Time | Screen | Voiceover | Overlay |
|------|--------|-----------|---------|
| 0:00 | Black screen, fade in | — | **"You think at 150 wpm."** |
| 0:02 | — | — | **"You type at 40."** |
| 0:04 | Voco app fades in — dark UI, orb idle, monolith codebase connected. Header shows "shopwave" project. | — | — |
| 0:06 | — | "What if your IDE could keep up with your brain?" | — |
| 0:08 | Orb starts subtle pulse | — | **CUT** to Act 2 |

> **Edit note:** Hard cut. No fade. Keeps energy up.

### ACT 2 — THE ASK (0:08 – 0:28)

| Time | Screen | Voiceover | Overlay |
|------|--------|-----------|---------|
| 0:08 | Orb pulses green — "listening" state | "I've got a Next.js monolith. Auth is tangled into everything." | — |
| 0:12 | Transcript types out character by character: *"Extract the auth module into its own microservice with JWT validation, rate limiting, and a shared proto contract"* | *(same voice, natural pace)* "Extract the auth module into its own microservice. JWT validation, rate limiting, shared proto contract." | — |
| 0:22 | Transcript finishes. Orb shifts to "thinking" cyan pulse. | — | — |
| 0:24 | **Visual Ledger appears** — 4-node pipeline: `Parse Intent → Plan Architecture → Generate Diffs → Propose` | "Voco doesn't just autocomplete. It plans." | **"INTENT → PLAN → DIFFS"** |
| 0:28 | Ledger nodes animate: Parse ✓, Plan ✓, Generate spinning… | — | **CUT** |

> **Edit note:** Speed up the ledger animation by ~1.5x if it feels slow. The audience should feel "this thing is fast."

### ACT 3 — THE PLAN (0:28 – 0:58)

| Time | Screen | Voiceover | Overlay |
|------|--------|-----------|---------|
| 0:28 | Generate ✓. **ReviewDeck slides in** with 4 diff cards. | "Four file changes. Real diffs. Not a chat message — actual code." | — |
| 0:32 | Camera zooms into first diff: `auth-service/src/index.ts` — new Express microservice entry point with JWT middleware | "New service entry point. JWT validation middleware baked in." | — |
| 0:38 | Second diff: `auth-service/src/rate-limiter.ts` — sliding window rate limiter | "Sliding window rate limiter. Per-role limits." | — |
| 0:42 | Third diff: `proto/auth.proto` — gRPC contract | "Shared proto contract so the monolith and service speak the same language." | **"ZERO DRIFT"** |
| 0:48 | Fourth diff: `src/middleware/auth.ts` — original file replaced with thin gRPC client | "The old monolith auth? Now a two-line gRPC call." | — |
| 0:52 | Presenter hovers over "Approve All" button | "I see exactly what changes before anything touches my code." | **"YOU APPROVE. ALWAYS."** |
| 0:56 | **Click "Approve All"** — ReviewDeck slides away. | — | — |

> **Edit note:** Use slow zoom on each diff card (Ken Burns style). Makes 30 seconds feel rich, not rushed.

### ACT 4 — THE YES (0:58 – 1:22)

| Time | Screen | Voiceover | Overlay |
|------|--------|-----------|---------|
| 0:58 | **CommandApproval overlay appears** — terminal command: `mkdir -p auth-service/src && cp src/middleware/auth.ts auth-service/src/ && ...` | "Now it needs to execute. But nothing runs without my say-so." | — |
| 1:04 | — | "This is zero-trust. The AI proposes. You decide." | **"ZERO TRUST"** |
| 1:08 | Presenter clicks **Approve** (or says "Yes" — voice flows through) | "Yes." | — |
| 1:10 | **GhostTerminal slides in** — streaming output. Files being created, moved, proto compiled. | — | — |
| 1:14 | Terminal shows: `✓ auth-service/src/index.ts created` `✓ auth-service/src/rate-limiter.ts created` `✓ proto/auth.proto created` `✓ src/middleware/auth.ts updated` | "Four files. Ten seconds. Done." | — |
| 1:18 | Terminal completes. All green checkmarks. | — | **"SHIPPED."** |
| 1:22 | Terminal fades. Clean app UI. Orb idle. | — | **CUT** |

> **Edit note:** Terminal output should stream line-by-line (already implemented). If real timing is >3s, speed up 2x in post.

### ACT 5 — THE CLOSE (1:22 – 1:45)

| Time | Screen | Voiceover | Overlay |
|------|--------|-----------|---------|
| 1:22 | App UI, calm. Orb breathing. | "No context window. No copy-paste. No babysitting." | — |
| 1:26 | — | "You spoke an architecture. Voco planned it. You said yes. Files updated." | — |
| 1:32 | Screen dims slightly | "That's it. That's the product." | — |
| 1:35 | **CTA card** — centered on screen | — | **"50 FOUNDING SEATS"** |
| 1:37 | — | "Fifty founding seats. Voice-native coding." | **"vocohq.com"** |
| 1:40 | — | "Link in bio." | — |
| 1:42 | Fade to black | — | **Voco icon** |
| 1:45 | Black | — | — |

---

## Post-Production Notes

### Editing Cuts
- **0:00–0:08:** Jump cuts on text overlays. No transitions.
- **0:08–0:28:** Single continuous shot. Let the typing animation carry the pacing.
- **0:28–0:58:** Slow Ken Burns zoom on each diff card. Cut between cards on voiceover beats.
- **0:58–1:22:** Continuous shot. Terminal streaming is the action.
- **1:22–1:45:** Slow fade between beats. Let it breathe.

### Audio
- Background: Very subtle dark ambient (like Stripe's product videos). No music with beats.
- Voice: Natural pace. Record each act separately, splice in post.
- SFX: Subtle "tick" on each ledger node completion. Quiet terminal keystroke sounds.

### Text Overlay Style
- Font: Inter Bold or SF Pro Display Bold
- Size: 48–72px
- Color: White on dark, voco-cyan (#00FFB2) accent
- Duration: 3 seconds max per card
- Animation: Fade in 200ms, hold, fade out 200ms

---

## A/B Testing Variants

| Variant | Change | Hypothesis |
|---------|--------|------------|
| **A (this one)** | Full 1:45, peer tone | Baseline |
| **B** | 60-second cut (skip Act 1, compress Act 3) | Higher completion rate on LinkedIn |
| **C** | Same flow but open with pain point text: "Context drift kills velocity" | Hook engineers who feel the pain |
| **D** | End with waitlist count instead of "50 seats" | Social proof > scarcity |
