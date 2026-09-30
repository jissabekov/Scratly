# MASTER ORCHESTRATION — Scratly execution plan

> **Version:** 2026-09-30 · **Status:** Phases 1–4 and 6 done · Phase 5 in progress · Plan 07 (conversation quality) is in implementation and stays outside this table · **Phase 10 done** · **Phases 8–9 planned** (learning-surface track) · **Entry point for every agent working on this repo.**
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
| **6** | [06-integration-eval.md](06-integration-eval.md) — chat routing, contracts, migrations, learning eval scenarios, staged rollout | Phases 2–5 | **DONE — W6.1–W6.6 landed and gated**: migration `022` (progress_checkin, 10 `learning_*` events, `learning_enabled` default false, `turn_id` nullable); terminal chat routing + `learning` payload; turn-less learning trace recorder; 3 teacher views; harness extended to 28 scenarios + A19–A23. Gates green: compileall · pytest 245 · ruff+mypy · web build · seed · Playwright 20/20 · mobile 390px (0 overflow/0 axe) · T3 subsets 5/5 · **T4 `eval/traces/2026-09-30-phase6-final` 28/28 clean, Findings=0, AssertionViolations=0** (3 variance re-runs preserved at `…-final-violations1`). See plan 06 §6.8 |

**Rule:** no phase starts until the previous phase's acceptance criteria are met and verified. Content (module text/slides/quiz items) is provided by the user later — build the schema, player, and gating with placeholder seed content first.

[Plan 07](07-conversation-quality.md) (planner directive v2 + writer turn-contract) is already in implementation. It is not a row in the table above. Do not renumber it. Phases 8–10 continue the numbering after it.

### 1b. Learning-surface track (Phases 8–10)

These phases do not mutate assessment policy, prompts, or migrations. They are not blocked on the open Phase 5 leftovers or on Plan 07. Inside this track the order is strict: **10 → 8 → 9**.

| Phase | Plan file | Scope | Depends on | Harness | Status |
|---|---|---|---|---|---|
| **10** | [10-skills-and-harnesses.md](10-skills-and-harnesses.md) | Acquire UI skills; extend `/frontend-ui` and `/web-e2e` | Phase 2 skills already in `.devin/skills/` | `create-skill` storage rules; `npx skills add` (project, `-a cursor`, no `-g`); no app code | **DONE — W10.1–W10.4:** `npx skills add -a cursor` (skills CLI 1.7.0) wrote `.agents/skills/` (Cursor project path; no `.cursor/skills/` copy): `frontend-design`, `web-design-guidelines`, `vercel-react-best-practices`, `shadcn`. `migrate-radix-to-base` absent. `/frontend-ui`, `/web-e2e`, and `/eval-suite` (28 scenarios, A1–A23) updated. No app/content/migration diff. compileall + pytest 263 passed. |
| **8** | [08-ui-navigation-and-type.md](08-ui-navigation-and-type.md) | Back on every non-root route, visible buttons, diagram rendering, loaded type | Phase 10 | `/frontend-ui` + acquired design skills; `/web-e2e`; `cursor-ide-browser` at 1280px and 390px; `/verify` | **PLANNED** |
| **9** | [09-lesson-explanations.md](09-lesson-explanations.md) | Expand shared slide explanations from week markdown | Phase 3 schema + Phase 8 for acceptance screenshots | `seed_learning_content.py --dry-run`; `test_learning_content.py`; `/verify`; browser read-through. No `/eval-suite` | **PLANNED** |

Phase 10 is the gate for implementation of 8 and 9. Skills are installed in `.agents/skills/` (see plan 10). Phases 8 and 9 stay planned.

## 2. Phase summaries

- **Phase 1 — Fix current system** (`01`): W1.1 exposure caps (A2) → W1.2 dedup ring buffer (A14) → W1.3 catalog-first matching + research abstraction (A18) → W1.5 stage monotonicity (A15) → W1.4 completion path → W1.6 hygiene (ruff/mypy/CI, Makefile Windows paths). Done = full 21-scenario suite green A1–A18 in a NEW trace dir + baseline diff.
- **Phase 2 — UI foundation** (`02`): Tailwind v4 (CSS-first, keeps existing tokens), shadcn/ui primitives, Motion, lucide; server-components-first refactor; fix frontend debt (`lib/types.ts` missing kinds, `next lint` deprecation); a11y contract; `apps/web/AGENTS.md` + frontend skills (already authored).
- **Phase 3 — Modules** (`03`): `learning` schema + content-in-repo + seed script; module hub (Duolingo-path), slide player (one idea/slide, typed blocks, keyboard, focus mgmt); idempotent slide-completion tracking via xAPI-shaped `learning_events`.
- **Phase 4 — Quizzes** (`04`): 5-item quiz per module, **pass = 4/5 AND every critical objective ≥1 correct**; alternate-form retakes; attempt caps; BKT mastery per objective; unlock projection.
- **Phase 5 — Coaching** (`05`): deterministic check-in scheduler (caps/budgets), BKT mastery states, SM-2-lite retention cards, advice escalation ladder (hint → re-teach → re-quiz → handoff), progress dashboard.
- **Phase 6 — Integration** (`06`): parallel-track architecture (assessment `complete` stays terminal), chat routing intercept, contracts, migrations, eval extension (A19+), staged rollout behind `learning_enabled`.
- **Phase 8 — Navigation, buttons, type** (`08`): a real Back control from every student and teacher destination; first-slide action-bar Back leaves the flow; diagrams stop rendering a raw asset slug; a loaded display/body/utility type pair on the existing token palette.
- **Phase 9 — Lesson explanations** (`09`): shared `module.json` slides teach the mechanism that the week markdown already explains. Punchline callouts stay short. Objective codes, quiz banks, and slide `seq` values stay put.
- **Phase 10 — Skills and harnesses** (`10`): done. UI skills are in `.agents/skills/` (`frontend-design`, `web-design-guidelines`, `vercel-react-best-practices`, `shadcn`). `.devin/skills/frontend-ui` and `.devin/skills/web-e2e` point at them and keep the a11y contract.

## 3. Verification gates (per phase, run — never claimed)

```bash
# Backend gates (every phase)
.venv/Scripts/python -m compileall -q apps/api/app
.venv/Scripts/python -m pytest apps/api/tests -q

# Frontend gates (Phases 2+)
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e        # needs API+DB running

# Live proof (Phase 1, and Phase 6 acceptance — not Phases 8–10)
PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/<date-label>
.venv/Scripts/python eval/analyze_post_fix.py <date-label>

# Learning content (Phase 9, and any reseed)
.venv/Scripts/python scripts/seed_learning_content.py --dry-run
.venv/Scripts/python scripts/seed_learning_content.py
```

## 4. Agent orchestration (who runs what)

| Work | Devin setup |
|---|---|
| Backend fixes/policy | root `AGENTS.md` rules + `/verify` + `/eval-suite` |
| Frontend/UI work | `apps/web/AGENTS.md` (auto-loaded) + `/frontend-ui` skill + `/web-e2e` skill. From Phase 10 on, also read the acquired `frontend-design`, `web-design-guidelines`, and `shadcn` skills before changing visual UI. Browser-verify with the `cursor-ide-browser` MCP (click the route, confirm Back, desktop and 390px). |
| Lesson copy | Phase 9. `/verify` + `seed_learning_content.py --dry-run` + `apps/api/tests/test_learning_content.py`. No `/eval-suite` unless a prompt or assertion changes. |
| Research spikes | `/research <topic>` (parallel web + GitHub subagents) |
| Status reporting | `/state-report` at the end of a phase, not on every edit |
| DB checks | `postgres` MCP (restricted mode, `.devin/mcp_config.json`) when that server is attached. It is not in the Cursor session that authored Phases 8–10. |
| Origin / app-control / subscriptions MCP | Not part of Phases 8–10. `cursor-origin-readonly` only sees Origin-hosted repos. |

**Instructing agents (copy-paste prompts):**
- "Work Phase 1 W1.1 per docs/plan/01-fix-current-system.md; run /verify; prove with /eval-suite --only …"
- "Execute Phase 2 per docs/plan/02…; follow apps/web/AGENTS.md and the /frontend-ui skill; run /web-e2e before claiming done."
- "Execute Phase 6 per docs/plan/06-integration-eval.md **§6.7** (the full execution prompt); it supersedes §6.2's stale migration numbers."
- "Research first with /research <topic> before implementing <feature>."
- "Execute Phase 10 per docs/plan/10-skills-and-harnesses.md before any Phase 8 visual edit. Do not install theme-factory, webapp-testing, or migrate-radix-to-base."
- "Execute Phase 8 per docs/plan/08-ui-navigation-and-type.md; follow /frontend-ui and /web-e2e; verify Back in the browser at 1280px and 390px."
- "Execute Phase 9 per docs/plan/09-lesson-explanations.md; expand text from docs/AI_Course_Weeks_02-11; do not renumber slide seq; dry-run the seed before writing."

## 5. Risk register

| Risk | Mitigation |
|---|---|
| Repetition fix changes conversation feel | eval diff + human transcript review (2 transcripts per PR, per repo convention) |
| Quiz gating feels punitive for teens | 4/5 threshold + immediate feedback + remediation re-teach (never identical re-quiz); attempt caps with handoff |
| Check-ins annoying | deterministic budget (≤1/10min, ≤3/session, dismissible with cooldown ×2) |
| Scope creep in UI rewrite | Phase 2 is foundation-only; new features land in Phases 3–5 on top of it |
| Eval runtime (~65–80 min) | `--only` for targeted proofs; full suite only at phase boundaries; CI job manual-trigger |
| Minor-data privacy | Plan 05 §5.5 constraints baked into schema + prompts |
| Renumbering slide `seq` while expanding lessons | `slide_id` is uuid5 of lesson id + seq (`learning_content.py`). The seed deletes slides whose ids fall out of the set, and `slide_completions.slide_id` is `ON DELETE CASCADE`. Phase 9 expands text in place or appends a new seq. |
| A third-party skill overrides canon tokens or localStorage rules | Phase 10 lists the conflicts. `apps/web/AGENTS.md` wins. |
| `npx skills add -g` writes into the user profile | Phase 10 installs into the project only (`-a cursor`, no `-g`). |

## 6. Definition of done (whole program)

1. Phase 1: full 21-scenario suite A1–A18 green; before/after metric rows committed.
2. Phases 2–5: each workstream's unit + E2E proofs green; `/verify` gate green.
3. Phase 6: learning eval scenarios + assertions green; one human-reviewed full journey; reproducible seeds + traces for every result (reproducibility contract).
4. Phases 8–10: skills installed in-repo; every non-root route has a working Back control verified in the browser and in Playwright; shared lesson slides teach from the week markdown with seed `--dry-run` and `test_learning_content.py` green. `/eval-suite` stays the gate for policy changes only.
