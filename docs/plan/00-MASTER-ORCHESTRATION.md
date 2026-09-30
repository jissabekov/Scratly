# MASTER ORCHESTRATION — Scratly execution plan

> **Version:** 2026-09-29 · **Status:** Phase 4 done (W4.1–W4.6) · Phase 1 leftovers open · **Entry point for every Devin agent working on this repo.**
> Read this file first; each phase has its own detailed plan file. Update the status column as work completes — this file is the single source of truth for sequencing.

## 0. Ground rules (apply to every phase)

- Read root `AGENTS.md` (hard rules, commands) + `apps/web/AGENTS.md` for frontend work.
- **Architecture Note first** (5–10 lines) before any code — global rule.
- Hard gates before "done": compileall + pytest (79 baseline, grows) + `npm --prefix apps/web run build` when web changed. Use `/verify`.
- Policy/conversation changes require eval proof via `/eval-suite` (partial `--only` for targeted, full 21 for stage/elicitation/repetition/matching).
- Never weaken assertions or thresholds to pass ("fake green"). Migrations append-only. Prompts versioned. Secrets only in `.env`.
- Subagents for research/mapping (`/research` skill); keep main context clean.

## 1. Phase order (strict; each phase gates the next)

| Phase | Plan file | Scope | Depends on | Status |
|---|---|---|---|---|
| **1** | [01-fix-current-system.md](01-fix-current-system.md) — A2 exposure caps, A14 dedup, A18 options/research, completion, latency, hygiene (ruff/mypy/CI) | — | **DONE (code + T3 live proof)** — W1.1/W1.2/W1.3/W1.4/W1.5/W1.6 landed; all 3 adaptive sims green at T3 (`2026-09-30-phase1-t3c`, `AssertionViolations=0`); single T4 gate run at `eval/traces/2026-09-30-phase1-final`. See plan 01 §T4 |
| **2** | [02-frontend-ui-foundation.md](02-frontend-ui-foundation.md) — Tailwind v4 + shadcn/ui + Motion migration, tokens, a11y contract, frontend AGENTS.md + skills | Phase 1 | **DONE — W2.1–W2.5 landed with build + 5/5 Playwright + axe + AA-contrast proof (see plan 02 §2.9); Phase 1 leftovers (W1.4 completion, latency, 3 sim A18s) remain open in plan 01** |
| **3** | [03-modules-learning.md](03-modules-learning.md) — learning schema, content model, slide player, module path, automatic tracking | Phase 2 | **DONE — W3.1–W3.5 landed (migration `017_learning_content.sql`, week-2 module authored end-to-end, hub + player + xAPI tracking); gates green (compileall · pytest 125 · ruff+mypy · web build · 9/9 Playwright incl. axe). See plan 03 §3.6** |
| **4** | [04-quiz-gating.md](04-quiz-gating.md) — 5-item quizzes, 4/5 + critical-objective pass rule, remediation, BKT mastery | Phase 3 | **DONE — W4.1–W4.6 landed (migrations `018`+`019`, 3-form bank for the real module, alternate-form remediation, attempt caps + handoff, BKT mastery + replay); gates green (compileall · pytest 151 · ruff+mypy · web build · 11/11 Playwright incl. axe); math verified via mathcheck. See plan 04 §4.7** |
| **5** | [05-progress-coaching.md](05-progress-coaching.md) — check-in scheduler, advice/intervention ladder, retention cards, dashboard | Phase 4 | **IN PROGRESS — W5.1/W5.2/W5.3/W5.4 landed (migration `020`, seeded `checkins.json`, deterministic engines + API + widget/dashboard); W5.5 phrasing boundary implemented; W5.6 e2e authored. See plan 05 §5.7** |
| **6** | [06-integration-eval.md](06-integration-eval.md) — chat routing, contracts, migrations, learning eval scenarios, staged rollout | Phases 2–5 | **READY — execution prompt in §6.7** (migration numbers corrected: next free is `022`; `learning_enabled` and the `learning_*` / `progress_checkin` enum values do not exist yet) |

**Rule:** no phase starts until the previous phase's acceptance criteria are met and verified. Content (module text/slides/quiz items) is provided by the user later — build the schema, player, and gating with placeholder seed content first.

## 2. Phase summaries

- **Phase 1 — Fix current system** (`01`): W1.1 exposure caps (A2) → W1.2 dedup ring buffer (A14) → W1.3 catalog-first matching + research abstraction (A18) → W1.5 stage monotonicity (A15) → W1.4 completion path → W1.6 hygiene (ruff/mypy/CI, Makefile Windows paths). Done = full 21-scenario suite green A1–A18 in a NEW trace dir + baseline diff.
- **Phase 2 — UI foundation** (`02`): Tailwind v4 (CSS-first, keeps existing tokens), shadcn/ui primitives, Motion, lucide; server-components-first refactor; fix frontend debt (`lib/types.ts` missing kinds, `next lint` deprecation); a11y contract; `apps/web/AGENTS.md` + frontend skills (already authored).
- **Phase 3 — Modules** (`03`): `learning` schema + content-in-repo + seed script; module hub (Duolingo-path), slide player (one idea/slide, typed blocks, keyboard, focus mgmt); idempotent slide-completion tracking via xAPI-shaped `learning_events`.
- **Phase 4 — Quizzes** (`04`): 5-item quiz per module, **pass = 4/5 AND every critical objective ≥1 correct**; alternate-form retakes; attempt caps; BKT mastery per objective; unlock projection.
- **Phase 5 — Coaching** (`05`): deterministic check-in scheduler (caps/budgets), BKT mastery states, SM-2-lite retention cards, advice escalation ladder (hint → re-teach → re-quiz → handoff), progress dashboard.
- **Phase 6 — Integration** (`06`): parallel-track architecture (assessment `complete` stays terminal), chat routing intercept, contracts, migrations, eval extension (A19+), staged rollout behind `learning_enabled`.

## 3. Verification gates (per phase, run — never claimed)

```bash
# Backend gates (every phase)
.venv/Scripts/python -m compileall -q apps/api/app
.venv/Scripts/python -m pytest apps/api/tests -q

# Frontend gates (Phases 2+)
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e        # needs API+DB running

# Live proof (Phase 1, and Phase 6 acceptance)
PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/<date-label>
.venv/Scripts/python eval/analyze_post_fix.py <date-label>
```

## 4. Agent orchestration (who runs what)

| Work | Devin setup |
|---|---|
| Backend fixes/policy | root `AGENTS.md` rules + `/verify` + `/eval-suite` |
| Frontend/UI work | `apps/web/AGENTS.md` (auto-loaded) + `/frontend-ui` skill + `/web-e2e` skill |
| Research spikes | `/research <topic>` (parallel web + GitHub subagents) |
| Status reporting | `/state-report` |
| DB checks | `postgres` MCP (restricted mode, `.devin/mcp_config.json`) |

**Instructing agents (copy-paste prompts):**
- "Work Phase 1 W1.1 per docs/plan/01-fix-current-system.md; run /verify; prove with /eval-suite --only …"
- "Execute Phase 2 per docs/plan/02…; follow apps/web/AGENTS.md and the /frontend-ui skill; run /web-e2e before claiming done."
- "Execute Phase 6 per docs/plan/06-integration-eval.md **§6.7** (the full execution prompt); it supersedes §6.2's stale migration numbers."
- "Research first with /research <topic> before implementing <feature>."

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Repetition fix changes conversation feel | eval diff + human transcript review (2 transcripts per PR, per repo convention) |
| Quiz gating feels punitive for teens | 4/5 threshold + immediate feedback + remediation re-teach (never identical re-quiz); attempt caps with handoff |
| Check-ins annoying | deterministic budget (≤1/10min, ≤3/session, dismissible with cooldown ×2) |
| Scope creep in UI rewrite | Phase 2 is foundation-only; new features land in Phases 3–5 on top of it |
| Eval runtime (~65–80 min) | `--only` for targeted proofs; full suite only at phase boundaries; CI job manual-trigger |
| Minor-data privacy | Plan 05 §5.5 constraints baked into schema + prompts |

## 6. Definition of done (whole program)

1. Phase 1: full 21-scenario suite A1–A18 green; before/after metric rows committed.
2. Phases 2–5: each workstream's unit + E2E proofs green; `/verify` gate green.
3. Phase 6: learning eval scenarios + assertions green; one human-reviewed full journey; reproducible seeds + traces for every result (reproducibility contract).
