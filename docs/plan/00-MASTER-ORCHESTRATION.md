# MASTER ORCHESTRATION — Scratly execution plan

> **Version:** 2026-09-29 · **Status:** Phase 1 ready · **Entry point for every Devin agent working on this repo.**
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
| **1** | [01-fix-current-system.md](01-fix-current-system.md) — A2 exposure caps, A14 dedup, A18 options/research, completion, latency, hygiene (ruff/mypy/CI) | — | **READY** |
| **2** | [02-frontend-ui-foundation.md](02-frontend-ui-foundation.md) — Tailwind v4 + shadcn/ui + Motion migration, tokens, a11y contract, frontend AGENTS.md + skills | Phase 1 | pending |
| **3** | [03-modules-learning.md](03-modules-learning.md) — learning schema, content model, slide player, module path, automatic tracking | Phase 2 | pending |
| **4** | [04-quiz-gating.md](04-quiz-gating.md) — 5-item quizzes, 4/5 + critical-objective pass rule, remediation, BKT mastery | Phase 3 | pending |
| **5** | [05-progress-coaching.md](05-progress-coaching.md) — check-in scheduler, advice/intervention ladder, retention cards, dashboard | Phase 4 | pending |
| **6** | [06-integration-eval.md](06-integration-eval.md) — chat routing, contracts, migrations 013–017, learning eval scenarios, staged rollout | Phases 2–5 | pending |

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
