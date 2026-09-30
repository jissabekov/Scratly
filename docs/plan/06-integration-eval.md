# Plan 06 — Integration, contracts & evaluation (Phase 6)

> **Status: READY (after Phases 1–5)** · Owner: Devin (full-stack) · Depends on: Plans 01–05
> **Goal:** wire the learning journey into the existing system without violating any hard rule, and extend the self-proving eval harness to cover it.

## 6.1 Architectural decision: parallel track, not a new assessment stage

The integration map shows `conversation.stage` is terminal at `complete`, `STAGE_RANK`/A15 assume monotonicity, and `completed_at` is set at `complete`. Therefore:

- **Assessment stage stays `complete`.** The learning journey lives in the new `learning` schema with its own state machine (`hub → module_in_progress → quiz_gate → module_passed → …`), keyed by `student_id` + `project_archetype`.
- **Chat routing:** in `turn_processor`'s terminal fast path (L93–125), intercept **before** `_post_match_reply`: if the student has an active learning journey, route conversational check-ins/advice (`message_kind="progress_checkin"`); otherwise fall back to post-match feedback. Relax the web input gate (`StudentChat` L137) accordingly.
- **Structured learning interactions (slides, quiz submissions, check-in answers) use dedicated REST endpoints** (`routes/learning.py`), NOT `process_student_turn` — they are not assessment turns. Each write: idempotent `request_id`, one transaction, append-only `learning_events`, trace `learning_*` decision events for auditability.

## 6.2 Migrations (ordered, append-only)

| Migration | Contents |
|---|---|
| `013_exposure_control.sql` | Plan 01 W1.1: dim exposure counters + `exposure_cap` event enum value |
| `014_learning_content.sql` | `learning` schema: modules, learning_objectives, lessons, slides |
| `015_quiz_gating.sql` | quiz_items, quiz_attempts, quiz_responses |
| `016_checkins_advice.sql` | checkin_items/events, mastery_states, interventions, retention_cards |
| `017_learning_trace_events.sql` | `audit.decision_event_type` += `learning_*` values; `conversation.assistant_message_kind` += `progress_checkin` |

## 6.3 Contracts (StrictModel `extra="forbid"` — web + API change together)

- `TurnResponse` unchanged except optional `learning` payload for conversational check-ins (mirrors `elicitation` pattern).
- New `learning` contracts: `LearningHubResponse`, `ModuleDetail`, `QuizAttemptRequest/Response`, `CheckInSubmission`.
- Frontend `lib/types.ts`: add missing `matching_unavailable`/`post_match_feedback` kinds (existing debt) + new kinds.

## 6.4 Eval harness extensions

- New scripted + adaptive **learning scenarios**: happy path (module → quiz pass → unlock), quiz-fail remediation loop (re-teach → form-2 re-quiz → pass), check-in cadence/budget, retention card due, advice escalation to handoff, inactivity re-engagement.
- New assertions: **A19** no module unlock without a passed quiz; **A20** quiz attempts idempotent under replayed request_ids; **A21** check-in budget respected (≤3/session, none during quiz); **A22** mastery projections replay exactly from `learning_events` (reproducibility contract); **A23** no PII in LLM payloads for learning turns.
- `analyze_dump` extensions: module completion rate, first-attempt pass rate, check-in response/dismissal rates, intervention counts.
- Teacher console: new admin views `learning-progress`, `quiz-history`, `interventions` (admin route pattern already supports view dispatch).

## 6.5 Constraints checklist (from integration map — every PR must respect)

1. Sole write path per domain: assessment = `process_student_turn`; learning = learning endpoints; never cross.
2. `audit.decision_events` is append-only (trigger-enforced) — corrections are new events.
3. Enum additions only via `ALTER TYPE … ADD VALUE IF NOT EXISTS` in new migrations; never edit applied SQL.
4. Quiz/check-in answers never write `assessment.evidence` (hard rules 2/4).
5. New prompts = new version dirs (`prompts/<name>/vN/system.txt`).
6. `completed_turn` replay must reconstruct any new replay-relevant payload kind (pattern: elicitation rebuild).
7. `asked_count` accounting: learning turns must not reuse assessment `target_key`s (would trip `is_repetition_blocked`).

## 6.6 Rollout & release gate

1. Phase 1 rerun green (Plan 01) → release baseline.
2. Learning features ship behind a session flag (`core.sessions.learning_enabled`) for staged rollout.
3. Final acceptance: full assessment suite green **+** learning scenarios green + human review of one full journey (chat → project → modules → quizzes → check-ins) on mobile viewport.

---

## 6.7 Execution prompt (copy-paste for the Phase 6 agent)

> **Status: READY after Phases 1–5.** HEAD `9a77659` (`main == origin/main`, tree clean):
> 209 pytest, ruff/mypy clean, web build green, Playwright **14/14**. Phase 1 release
> baseline = `eval/traces/2026-09-30-phase1-final` (21/21 clean, `AssertionViolations=2`,
> both A2 — fixed in code and proven in `eval/traces/2026-09-30-phase1-a2`).

### 0. Read first, in this order, before any code

1. `AGENTS.md` (root) — hard rules, Windows commands, change discipline.
2. `docs/plan/00-MASTER-ORCHESTRATION.md` — sequencing; update the Phase 6 status column.
3. **This file**, §6.1–§6.6, then §6.7 (corrected numbers below — §6.2's migration list is stale).
4. `docs/architecture.md` (hard rules 1–6) and `apps/web/AGENTS.md` (binding for `apps/web/`).
5. `docs/plan/01-fix-current-system.md` §T4 — the baseline you must not regress.
6. `docs/plan/05-progress-coaching.md` §5.7 — what Phase 5 actually shipped.

**Architecture Note first (global rule 1):** 5–10 lines (objective, modules touched, data
dependencies, exact verification commands) before any code.

### 1. Verified starting state — do not re-derive, do not trust §6.2's numbers

| Fact | Value |
|---|---|
| HEAD | `9a77659`, `main == origin/main`, working tree clean |
| Migrations applied | `001`–`021`; **next free = `022`**. §6.2's `013`–`017` are all taken/renamed |
| Schemas | `core`, `conversation`, `assessment`, `matching`, `learning`, `audit` |
| `core.sessions.learning_enabled` | **does not exist** → create it in `022` |
| `conversation.assistant_message_kind` | 8 values; **no `progress_checkin`** |
| `audit.decision_event_type` | 37 values; **no `learning_*`** |
| Learning endpoints already live | `GET .../learning` (hub), `GET .../learning/modules/{id}`, `POST .../learning/slides/{id}/complete` (`routes/learning.py`); quiz (`routes/learning_quiz.py`); check-ins + `GET .../learning/summary` (`routes/learning_checkins.py`) |
| Learning repos emit traces? | **No** — `repository/learning*.py` never write `audit.decision_events` |
| Chat terminal path | `turn_processor` branch `if counters.get("matching_completed")` (≈ L224) → `_post_match_reply` |
| Web input gate | `components/chat/StudentChat.tsx` L213 `const completed = stage === 'complete'` |
| Web kinds | `lib/types.ts` L9–18 `MessageKind`; `MessageBubble` `KIND_LABELS` + class modifiers |
| Harness hooks | `SCENARIOS`, `assert_suite` (A1–A18), `analyze_dump`, `ADMIN_VIEWS`, `STUCK_STAGE_COHORT` |
| Admin view dispatch | `routes/admin.py` `handlers = {...}` dict (≈ L83) |

### 2. Efficiency doctrine — read before running anything

The live suite is a **release gate, not a debugger**. Tiered loop, cheapest first, never skip a tier:

| Tier | Cost | Proves | Command |
|---|---|---|---|
| **T0** fixture unit tests | ~2 s | assertion/analysis logic + policy pure functions | `.venv/Scripts/python -m pytest apps/api/tests -q` |
| **T1** re-analyze dumps | ~2 s | new metrics/assertions over existing evidence, zero LLM | `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --analyze-only --out-dir eval/traces/2026-09-30-phase1-final --baseline-report eval/traces/2026-09-30-phase1-final/suite_report.json` |
| **T2** deterministic server | 1–2 min | policy behaviour, no network/LLM variance | `cd apps/api && set -a && source .env && set +a && export AZURE_OPENAI_ENDPOINT= && export AZURE_OPENAI_API_KEY= && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| **T3** live subset | 2–8 min | LLM-quality behaviour, only the scenarios owning a failing assertion | `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --only <ids> --out-dir eval/traces/<label> --resume` |
| **T4** full suite | ~40–60 min | the release gate — **once per phase boundary** | see §9 |

Extend the T0 fixtures (`apps/api/tests/test_eval_assertions.py` already drives
`analyze_dump`/`assert_suite` with synthetic dumps) with **A19–A23** before touching the harness.

**Phase 6 + Phase 1 coupling:** §6.1 requires touching `turn_processor`'s terminal fast path.
That invalidates the Phase 1 gate, so the **combined full run must be the last thing you do**,
and it must be green for A1–A23 on one tree.

### 3. Workstreams (corrected)

**W6.1 — Migration `022_learning_integration.sql`** (append-only):

- `ALTER TYPE conversation.assistant_message_kind ADD VALUE IF NOT EXISTS 'progress_checkin';`
- `ALTER TYPE audit.decision_event_type ADD VALUE IF NOT EXISTS` for
  `learning_hub_viewed`, `learning_slide_completed`, `learning_quiz_drawn`,
  `learning_quiz_scored`, `learning_module_unlocked`, `learning_checkin_delivered`,
  `learning_checkin_answered`, `learning_checkin_dismissed`,
  `learning_intervention_opened`, `learning_retention_card_due`.
- `ALTER TABLE core.sessions ADD COLUMN learning_enabled boolean NOT NULL DEFAULT false;`
- **Postgres caveat:** a new enum value cannot be *used* in the same transaction that adds it.
  Keep `022` to enum additions + the column only; emit the events from code applied afterwards.
  Apply to the existing volume with
  `docker compose exec -T postgres psql -U scratly -d scratly -v ON_ERROR_STOP=1 < migrations/022_learning_integration.sql`.

**W6.2 — Chat routing (the risky one).** In the terminal fast path, before `_post_match_reply`:
if `learning_enabled` and the session has an active journey, return
`message_kind="progress_checkin"` with a deterministic (or W5.5-phrased) check-in, plus an
optional `learning` payload on `TurnResponse` (mirror the `elicitation` pattern). Relax the
`StudentChat` input gate (keep `stage === 'complete'` terminal for *assessment*; allow input when
a learning journey is active). Add `progress_checkin` to `lib/types.ts` + `MessageBubble`.
Do **not** write assessment state from this path.

**W6.3 — Learning decision tracing.** Give the learning repos the same auditability as
assessment: emit the `learning_*` events above with `entity_refs` (module/slide/quiz/check-in ids)
through a small recorder. Then add teacher-console admin views `learning-progress`,
`quiz-history`, `interventions` to `routes/admin.py`'s `handlers` dict, and extend the harness
`ADMIN_VIEWS` so dumps capture them.

**W6.4 — Eval harness.** New scenarios (scripted + adaptive) for: module → quiz pass → unlock;
quiz-fail remediation loop (re-teach → form-2 → pass); check-in cadence/budget; retention card
due; advice escalation to handoff; inactivity re-engagement. New assertions:
**A19** no module unlock without a passed quiz; **A20** quiz attempts idempotent under replayed
`request_id`; **A21** check-in budget respected (≤3/session, none during a quiz);
**A22** mastery projections replay exactly from `learning_events`; **A23** no PII in LLM payloads
for learning turns. Extend `analyze_dump`: module completion rate, first-attempt pass rate,
check-in response/dismissal rates, intervention counts.

**W6.5 — Staged rollout.** `learning_enabled` defaults **false**; document the seam used by e2e
(mirror `LEARNING_QUIZ_COOLDOWN_SECONDS` — a documented env/settings toggle, never a weakened
assertion).

**W6.6 — Final acceptance.** One combined full run green for **A1–A23**, learning scenarios
green, plus a human review of one full journey (chat → project → modules → quizzes → check-ins)
at mobile 390 px.

### 4. Skills — invoke, do not re-derive

`/state-report` (confirm baseline first) · `/verify` (hard gate) · `/eval-suite` (T3/T4 and
A19–A23 semantics) · `/frontend-ui` (before any `apps/web/` work: tokens, a11y contract, visual
polish loop at 390/1280 px) · `/web-e2e` (Playwright) · `/research <topic>` for spikes.

### 5. MCPs — and verify every number (global rule 4)

Call `mcp_list_servers` then `mcp_list_tools` before calling any server; never guess tool names.
Currently reachable: **postgres** (read-only), **mathcheck**, **memory**.
`repo`, `docs`, `devtools` were unreachable at the time of writing — verify before relying on them.

- **postgres** — schema, seed, projection and event-stream verification (e.g. `learning_events`
  replay vs `mastery_states`, enum values, `learning_enabled` default).
- **mathcheck** — mandatory for every statistics claim, with assumptions + uncertainty:
  `verify_percentile` for latency p50/p95 over **measured** per-turn ms; `verify_wilson_ci` for
  first-attempt pass rate / check-in response rate / dismissal rate; `verify_brier` +
  `verify_reliability` for BKT/retention calibration over a **seeded** simulation (report the seed);
  `verify_sample_size` for the check-in caps.
- **memory** — record Phase 6 findings/relations (workstream → evidence) so later sessions inherit them.

### 6. Orchestration — subagents, max 2 concurrent, disjoint files

- **SA1 (background, harness):** author the learning scenarios + A19–A23 in a **new** file
  `apps/api/tests/test_eval_learning_assertions.py` first (fixtures), then the harness scenario
  additions. Report assertion coverage + pytest output.
- **SA2 (background, teacher console):** the three new admin views + their web surface, after the
  main agent lands W6.1/W6.3's read models.
- **SA3 (background, read-only):** verify §6.2's integration map against the real repo and report
  every stale claim (migration numbers, line numbers, endpoint names).
- **Main agent:** migration `022`, `turn_processor` routing, contracts, `deps.py`, the T3/T4 runs —
  the coupled chat-pipeline work stays with one owner.

### 7. Hard constraints (never violate)

1. Sole write path per domain: assessment = `process_student_turn`; learning = learning endpoints.
   Never cross.
2. Quiz/check-in answers never write `assessment.evidence` (hard rules 2/4).
3. `audit.decision_events` is append-only (trigger-enforced); corrections are new events.
4. Enum additions only via `ALTER TYPE … ADD VALUE IF NOT EXISTS` in new migrations; never edit
   an applied migration.
5. New prompts = new version dirs (`prompts/<name>/vN/system.txt`).
6. `mastery_states` / rollups stay replayable projections of `learning_events` (no hidden state).
7. Learning turns must not reuse assessment `target_key`s (would trip `is_repetition_blocked`).
8. No PII in LLM payloads; pseudonymous ids only.
9. Never weaken an assertion/threshold to pass ("fake green").
10. No client-side progress persistence; token canon (`--ink/--paper/--panel/--line/--accent/--muted/--warn`).

### 8. Decisions to record in the plan status

- **D1 — chat routing:** does the terminal fast path gain `progress_checkin`? (Default: yes per §6.1.)
  If yes, the full-suite run is mandatory and must be **last**.
- **D2 — learning scenario set:** ids, scripted vs adaptive, and the `min_turns` floor for adaptive.
- **D3 — `learning_enabled` seam:** default `false`; document the single toggle e2e uses.
- **D4 — second full eval run:** write down why before running it.

### 9. Verification gates (run — never claimed)

```bash
# Backend (every change)
.venv/Scripts/python -m compileall -q apps/api/app
.venv/Scripts/python -m pytest apps/api/tests -q
.venv/Scripts/python -m ruff check apps/api
.venv/Scripts/python -m ruff format --check apps/api
.venv/Scripts/python -m mypy

# Frontend
npm --prefix apps/web run build          # stop `next dev` first — they share .next/
npm --prefix apps/web run test:e2e       # needs API on :8000 + Postgres + seeded content

# Migration + content
docker compose exec -T postgres psql -U scratly -d scratly -v ON_ERROR_STOP=1 < migrations/022_learning_integration.sql
.venv/Scripts/python scripts/seed_learning_content.py --dry-run
.venv/Scripts/python scripts/seed_learning_content.py

# Phase 6 gate (T4 — once)
PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py \
  --out-dir eval/traces/2026-09-30-phase6-final \
  --baseline-report eval/traces/2026-09-30-phase1-final/suite_report.json
.venv/Scripts/python eval/analyze_post_fix.py 2026-09-30-phase6-final
```

API for live runs:
`cd apps/api && set -a && source .env && set +a && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
(add `LEARNING_QUIZ_COOLDOWN_SECONDS=0` for quiz e2e; do **not** blank Azure for T3/T4).

### 10. Reporting

Update `docs/plan/00-MASTER-ORCHESTRATION.md` (Phase 6 column), this file (per-workstream status +
before/after metric rows), and commit + push. Every result must be reproducible: content version,
seeds, trace dirs, and the exact commands.
