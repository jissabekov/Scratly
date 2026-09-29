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
