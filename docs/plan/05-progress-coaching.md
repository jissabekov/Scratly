# Plan 05 — Progress tracking check-ins & advice engine (Phase 5)

> **Status: READY (after Phase 4)** · Owner: Devin (full-stack) · Depends on: Plan 03/04 (objectives, mastery model)
> **Goal:** while the student progresses through modules, the system asks lightweight **check-in questions** to track development progress and offers **advice when needed** — deterministic triggers and scoring, LLM only phrases and classifies.

## 5.1 Check-in scheduler (deterministic triggers, LLM only phrases)

**Global budget:** ≤1 per 10 min of activity, ≤3 per session, none during a quiz, none within 5 min of the last check-in; a "not now" doubles the cooldown (autonomy support). Streak unit = "one step counts" (a check-in or a module step), not time.

| Trigger (deterministic) | Check-in type mix |
|---|---|
| slide section completed | comprehension mini-exercise 60% / self-explain 25% / Likert 15% on that objective |
| milestone (module passed) | confidence self-report + one **retention item** from a prior module whose retention card is due |
| error burst (≥3 fast-wrong events) | "everything OK?" + optional hint offer |
| inactivity ≥72h | re-engagement + easiest due retention item |
| streak day | light praise + optional challenge item |

- `CheckinIntent{objective_id, item_form, trigger_reason}` emitted by the deterministic scheduler; LLM **phrases** it conversationally and classifies free-text into the item's rubric; scoring/state stays deterministic.
- Mix: applied mini-exercises (real BKT evidence, weight 0.5) > self-explanation prompts > Likert self-report (sparingly — calibration drift).
- Retention: on module pass create SM-2-lite cards (1d→3d→7d→16d); failed retention item → objective `decaying` → offer refresher slide, **never re-lock** the module.

## 5.2 Advice / intervention ladder (deterministic, priority-ordered)

| Condition | Intervention |
|---|---|
| Quiz fail ×1 | targeted re-teach (missed objectives only) + encouragement |
| Quiz fail ×2 same module | worked example + Socratic hint thread; suggest break |
| Quiz fail ×3 / BKT stagnant ≥8 evidence events | handoff card ("ask a teacher/mentor") + provisional-pass option |
| Fast-wrong streak (median <2.5s & wrong ×3) | slow-down nudge + explain-it-back prompt |
| Inactivity ≥72h | re-engagement + easy-win item |
| Confidence ≤2 twice on same objective | offer refresher before quiz |
| Retention lapse | refresher slide + interval reset |

**Escalation ladder per objective:** hint (Socratic, never the answer) → targeted re-teach → alternate-form re-quiz → scaffolded walkthrough / teacher handoff. Every intervention row: `level, trigger_rule, content, resolved_at`.

**Phrasing rules for the LLM (teen-appropriate, SDT-informed):** strategy-focused not ability-focused; always offer a choice (autonomy); celebrate progress toward mastery ("3 of 4 objectives"); no shame on streak breaks; no diagnosis.

## 5.3 Data model (migration `016_checkins_advice.sql`)

```sql
learning.checkin_items(id, objective_id, kind, payload jsonb)     -- likert|mcq|mini_exercise|self_explain
learning.checkin_events(id, student_id, checkin_item_id, trigger_reason,
                        scheduled_at, delivered_at, responded_at, response jsonb,
                        score float, latency_ms, dismissed bool)
learning.mastery_states(student_id, objective_id, p_mastery, elo,
                        state_enum, evidence_count, updated_at,
                        UNIQUE(student_id, objective_id))          -- derived projection
learning.interventions(id, student_id, objective_id, level, trigger_rule,
                       content jsonb, created_at, resolved_at)
learning.retention_cards(student_id, objective_id, ease, interval_days,
                         due_at, reps, lapses)
```

`learning_events` stays the append-only source of truth; mastery/rollups replay from it.

## 5.4 Surfaces

- **In-module:** `CheckInWidget` card at section boundaries (non-modal, dismissible).
- **In-chat:** post-completion routing in `turn_processor` (terminal fast path) may deliver a conversational check-in/advice as `message_kind="progress_checkin"` — requires new enum value + `lib/types.ts` + `MessageBubble` label/CSS + relaxing the `stage==='complete'` input gate (integration map: StudentChat L137).
- **Progress dashboard:** mastery grid (Khan-style squares), streak chip, Recharts client island (mastery-over-time, quiz scores) behind route-level code-split.

## 5.5 Privacy (minors)

- Data minimization; pseudonymous student ids in logs and **LLM payloads** (send objective ids + rubric, never chat PII); retention limits + export/delete endpoints; Azure OpenAI configured with no-training-on-data; check-in content avoids sensitive categories.

## 5.6 Acceptance

- Unit: scheduler budget/caps; BKT update math; SM-2 interval math; intervention escalation matrix; retention decay path.
- E2E: check-in appears at section boundary, dismissible with cooldown; advice card after 2 quiz fails; retention card due → appears at next milestone.
- Eval: check-in response rate >60% target; no check-in during quiz; deterministic pipeline p95 <100ms.

---

## 5.7 Per-workstream status (implemented)

| # | Workstream | Status | Evidence |
|---|---|---|---|
| W5.1 | Schema + content + seed | **DONE** | `migrations/020_checkins_advice.sql` (`checkin_items`, `checkin_events`, `interventions`, `retention_cards`, `mastery_states` extended with `elo`/`evidence_count`/`last_evidence_at`); `checkins.json` authored for all 6 modules; `scripts/seed_learning_content.py --dry-run` prints `checkin_items=120`; applied + verified via psql (30 items per kind) |
| W5.2 | Deterministic engines | **DONE** | `services/learning_checkin_engine.py` (pure, injected `now`) + 31 unit tests (`test_learning_checkin_engine.py`) covering budget/caps, trigger priority, kind mix, scoring, SM-2-lite interval math, lapse/decay, intervention matrix, escalation ladder, streak |
| W5.3 | API | **DONE** | `repository/learning_checkin.py` + `routes/learning_checkins.py` (`GET/POST/PATCH /v1/sessions/{id}/learning/checkins[/{cid}]`, `GET .../learning/summary`); idempotent by `request_id`; appends xAPI `learning_events` + updates the `mastery_states` projection; **never writes `assessment.evidence`** |
| W5.4 | Surfaces | **DONE** | `components/learn/CheckInWidget.tsx` (non-modal, dismissible, `aria-live`, keys 1–5, focus mgmt, reduced-motion) wired at lesson section boundaries in `LessonPlayer`; `app/progress/page.tsx` + `components/progress/MasteryGrid.tsx` (mastery grid incl. `decaying`, streak chip, due-retention list, advice list); `npm --prefix apps/web run build` green |
| W5.5 | LLM phrasing boundary | **DONE (opt-in)** | `prompts/checkin_phrasing/v1/system.txt` + `services/learning_checkin_phrasing.py` with server-side rubric validation and a deterministic fallback; 5 unit tests. **Deliberate deviation:** the default check-in path does not call the LLM (deterministic authored prompt), so scoring stays reproducible and the pipeline adds no latency — consistent with D1 (chat pipeline untouched). |
| W5.6 | E2E + measurable claims | **DONE** | `apps/web/e2e/checkins.spec.ts` (section-boundary check-in + dismiss + dashboard + axe; no check-in during a quiz; hub → dashboard link). Full Playwright suite: **14/14 green** (`npm --prefix apps/web run test:e2e`, baseline was 11/11). Claims measured by `.venv/Scripts/python scripts/measure_checkin_claims.py` (`verify_percentile` numpy-linear, `verify_wilson_ci` z=1.96). Deterministic pipeline p95 **0.0089 ms** (n=2000, target <100). Stored response rate **43/64 = 0.672** (Wilson 95% **0.550–0.774**); point estimate clears >0.60, the lower bound does not. Check-ins delivered during an open quiz: **0**. Live `deliver()` p95 **40.03 ms** (n=40), also under 100 ms; those samples were rolled back and did not change the 43/64 counts. |

**Fix recorded during W5.6:** the section-complete trigger originally matched a
`experienced` verb and the streak counter matched short verb ids, but the slide
tracker writes full xAPI URIs with `completed` / `slide:<id>` objects. Both now
match the real statements, which is what makes the widget appear at a section
boundary (proven by the e2e test).

### W5.6 measurement (2026-09-30)

Command: `.venv/Scripts/python scripts/measure_checkin_claims.py`

| Claim | Result | How |
|---|---|---|
| Deterministic pipeline p95 < 100 ms | **0.0089 ms** (p50 0.0066 ms, n=2000, 156 unique) | `verify_percentile` q=0.95, empirical numpy linear, over seeded `checkin_gate` → trigger → kind → item → score calls. Warmup 50 excluded. No LLM, no DB. |
| No check-in during a quiz | **0 / 286** seeded engine samples, **0 / 10** live `deliver()` samples with an open attempt, **0** stored events overlapping an open quiz attempt | Gate returns before an item is chosen. |
| Check-in response rate > 60% | point **0.672** (43 answered / 64 delivered, 9 dismissed, 12 still open) | `verify_wilson_ci`, Wilson score, z=1.96, 95% CI **0.550–0.774**. Point estimate is above 0.60. The lower bound is not. |
| Live deliver path | p95 **40.03 ms**, p50 **23.56 ms**, n=40 | `CheckinRepository.deliver` after a section-complete event. 3 warmup calls excluded. Assessment evidence + profile snapshots written: **0**. Stored 43/64 unchanged after the run. |

Population: every `learning.checkin_events` row already in local Postgres (sessions with no `external_ref`, written by earlier local API use). This run did not insert answered check-ins. Dismissed and still-open deliveries count as non-responses. Independence is approximate because several events share a session. n=64 is why the interval still reaches below 60%.

### Corrections applied to this plan (per task §6)

- Migration number: `016_checkins_advice.sql` → **`020_checkins_advice.sql`** (016 taken by the Phase 1 catalog work).
- `mastery_states` already existed (Phase 4, keyed `(session_id, objective_id)`): **extended** with `elo` / `evidence_count` / `last_evidence_at` rather than recreated with a `(student_id, objective_id)` key. Session↔student is 1:1 in this product; documented in the migration.
- Reuse: `learning.learning_events` stays the append-only source of truth; `mastery_states` stays a replayable projection; `bkt_update` / `objective_state` / `xapi_statement` / `compute_streak_days` reused from Phases 3–4.
- The `routes/learning_checkins.py` 501 stub is replaced.
- All time-dependent logic is a pure function of an injected `now` (72 h inactivity, 5/10 min cooldowns, retention due dates).
- **No new dependencies** were added: the dashboard hand-rolls the mastery grid with the existing tokens instead of pulling in Recharts (D2).

### Decisions recorded

- **D1 — Phase 5 in-chat delivery:** `turn_processor` was **left untouched** in Phase 5 (in-module widget + dashboard only). Endpoint shapes are ready for a Plan 06 chat integration.
- **D2 — Recharts:** not added; the mastery grid is hand-rolled with the token system.
- **D3 — mastery key:** kept `(session_id, objective_id)`; session↔student 1:1 documented.
- **D4 — second full eval run:** not taken; exactly one T4 run was used.
