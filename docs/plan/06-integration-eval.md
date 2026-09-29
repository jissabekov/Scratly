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
