# Plan 04 — 5-question quizzes with pass-to-advance gating (Phase 4)

> **Status: READY (after Phase 3)** · Owner: Devin (full-stack) · Depends on: Plan 03 (modules, objectives, slide content)
> **Goal:** each module ends in a **5-question quiz that must be passed to unlock the next module**, with automatic tracking, fair thresholds, and a remediation loop that teaches instead of punishing.

## 4.1 Gating rules (evidence-based)

- **Pass = ≥4/5 correct AND ≥1 correct item on every critical objective.** (80% criterion — with n=5, SEM ≈ ±1 item, so 4/5 is the smallest defensible cut; 5/5 produces ~41% false-fails for true masters. Per-critical-objective coverage prevents passing while missing a whole concept.)
- Threshold shown up front ("get 4/5 to unlock").
- **Immediate per-question feedback** (correct/incorrect + 1–2 sentence explanation — the quiz teaches), pass/fail computed at the end; failure screen lists missed questions with "review slide n" deep links.
- **Remediation loop (deterministic):** fail → re-show only slides for missed objectives + a worked example → cooldown (≥10 min or next session) → **re-quiz from alternate item forms** (`form_id` 2/3), never identical items.
- **Attempt caps (anti wheel-spinning):** fail ×2 → intervention level 3 (scaffolded walkthrough); fail ×3 → level 4 handoff card (teacher/mentor) + optional provisional pass if BKT P(mastery) ≥ 0.8 across module objectives — no wheel-spinning dead-ends.
- Items are **concept variations** (Brilliant: 20+ problems per concept), banked 3 forms × 5 items per module, tagged to objectives with author-estimated difficulty updated from data (poor-man's IRT: p̂ = fraction correct).

## 4.2 Data model (migration `015_quiz_gating.sql`)

```sql
learning.quiz_items(id, module_id, objective_id, form_id, kind,   -- mcq|select_all|short
                    stem, options jsonb, answer jsonb,
                    difficulty float, hint_text,
                    feedback_correct, feedback_wrong, is_critical bool)
learning.quiz_attempts(id, student_id, module_id, attempt_no, form_id,
                       item_ids jsonb, started_at, submitted_at,
                       score int, passed bool,
                       UNIQUE(student_id, module_id, attempt_no))
learning.quiz_responses(id, attempt_id, item_id, response jsonb,
                        correct bool, latency_ms,
                        UNIQUE(attempt_id, item_id))
```

- Reuse the `ElicitationSpec`-style payload pattern for the API contract (StrictModel `extra="forbid"` → web+API change together).
- Quiz answers are **learning evidence, not assessment evidence** — they never write `assessment.evidence` (hard rules 2/4).

## 4.3 Mastery model (deterministic, ~30 lines)

- **BKT per learning objective** (P(L0)=0.25, P(T)=0.15, P(G)=0.25 MCQ / 0.15 select-all, P(S)=0.10) updated by every scored event: quiz items (weight 1.0) + check-in mini-exercises (weight 0.5, Plan 05).
  `P(L|correct) = P(L)(1−P(S)) / (P(L)(1−P(S)) + (1−P(L))P(G))` (+ mirrored wrong-update, then `P(L) += (1−P(L))·P(T)`).
- `mastered` when P(L) ≥ 0.95 **or** module quiz passed (pass sets P(L)=1 for its critical objectives).
- Objective states: `unseen → learning → mastered → decaying` (retention lapse, Plan 05).
- Elo shadow rating per objective for item-difficulty calibration analytics (display-only).
- All pure functions of the append-only `learning_events` stream; `mastery_states` is a projection — replayable, explainable ("you've mastered 3 of 4 objectives").

## 4.4 API

| Endpoint | Behavior |
|---|---|
| `GET …/modules/{mid}/quiz` | draw 5 items: ≥1 per critical objective, current `form_id`, no repeats of recently-missed identical items |
| `POST …/quiz-attempts` | idempotent by `request_id`; scores deterministically; updates BKT + rollups; returns `{passed, score, missed[{item_id, slide_ref, explanation}]}` |
| Unlock rule | `passed=true` → module `passed`, next module `available` (`progress_rollups`), unlock event traced |

## 4.5 UX (QuizRunner)

- One question at a time (`?q=` param), fieldset/legend + Radix RadioGroup, keys 1–4, focus moves to question heading, "Question 2 of 5" live region.
- Immediate feedback block (`aria-live=polite`); correct → CTA becomes "Next".
- Result screen: pass → unlock animation + confetti + CTA to next module; fail → missed list + "Review slide" deep links + encouragement (strategy-focused phrasing, never ability judgments).

## 4.6 Acceptance

- Unit: gating matrix (4/5 + critical coverage; 3/5 fails; critical-miss fails despite 4/5), alternate-form draw, attempt caps, BKT update math (property test vs hand-computed), unlock projection replay from `learning_events`.
- E2E: fail → remediation path shown → re-quiz (form 2) → pass → next module unlocked; attempt 3 fail → handoff card.
- Eval extension (Plan 06): A19 quiz-gating assertions (no unlock without pass; form rotation; cap respected).
