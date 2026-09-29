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

## 4.2 Data model (migration `018_quiz_gating.sql` + `019_quiz_provisional_pass.sql`)

> **Correction (2026-09-29):** `015` was already taken
> (`015_catalog_persona_coverage.sql`). The quiz schema shipped as
> `018_quiz_gating.sql`, with `019_quiz_provisional_pass.sql` adding the
> `provisional` column that the attempt-cap rule needs. Quiz item ids are uuid5
> of `(module, form, seq)`, so reseeding never orphans an attempt.

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
| `POST …/quiz-attempts/{aid}/responses` | **added in implementation:** check one answer server-side → `{correct, feedback, correct_answer}`. Needed so per-question feedback (§4.5) never requires shipping the answer bank to the browser. |
| Unlock rule | `passed=true` → module `passed`, next module `available` (`progress_rollups`), unlock event traced |

## 4.5 UX (QuizRunner)

- One question at a time (`?q=` param), fieldset/legend + Radix RadioGroup, keys 1–4, focus moves to question heading, "Question 2 of 5" live region.
- Immediate feedback block (`aria-live=polite`); correct → CTA becomes "Next".
- Result screen: pass → unlock animation + confetti + CTA to next module; fail → missed list + "Review slide" deep links + encouragement (strategy-focused phrasing, never ability judgments).

## 4.6 Acceptance

- Unit: gating matrix (4/5 + critical coverage; 3/5 fails; critical-miss fails despite 4/5), alternate-form draw, attempt caps, BKT update math (property test vs hand-computed), unlock projection replay from `learning_events`.
- E2E: fail → remediation path shown → re-quiz (form 2) → pass → next module unlocked; attempt 3 fail → handoff card.
- Eval extension (Plan 06): A19 quiz-gating assertions (no unlock without pass; form rotation; cap respected).

## 4.7 Per-workstream status (2026-09-29)

Environment: Postgres up with `018` + `019` applied, content reseeded
(`modules=10 objectives=30 lessons=25 slides=85 quiz_items=125`, idempotent),
API on :8000 (repo `.env`, `LEARNING_QUIZ_COOLDOWN_SECONDS=0` for the e2e run),
web built and served for e2e.

| # | Workstream | Status | Evidence |
|---|---|---|---|
| W4.1 | Quiz schema | **DONE** | `migrations/018_quiz_gating.sql` (`learning.quiz_items/quiz_attempts/quiz_responses/mastery_states/item_stats`, one-open-attempt partial unique index, global-unique `request_id`) + `019` (`provisional`). |
| W4.2 | Content + engine | **DONE** | `content/modules/**/quiz.json` (3 forms for the real Week-2 module, 2 for each placeholder), validated against each module (critical-objective coverage, slide refs, `is_critical` agreement) and seeded with stable uuid5 ids. Pure engine `learning_quiz_engine.py`: BKT, scoring (≥4/5 **and** ≥1 correct per critical objective), deterministic form rotation, retry ladder, `replay_mastery`. |
| W4.3 | API | **DONE** | `GET …/modules/{mid}/quiz` (draw/resume, gate states `available/cooldown/handoff/passed/unavailable`), `POST …/quiz-attempts` (idempotent by `request_id`; one transaction; scores, updates BKT + item stats + mastery, appends xAPI `attempted/answered/passed|failed` events), `POST …/quiz-attempts/{aid}/responses` (per-item feedback). Answers never leave the server on a draw. |
| W4.4 | Unlock wiring | **DONE** | Hub/module-detail read `passed OR provisional`; `derive_module_states` flips the module to `passed` and the next to `available`; `quiz_gate_locked` and `QuizGate` reflect reality. |
| W4.5 | Quiz UI | **DONE** | `app/modules/[moduleId]/quiz/page.tsx` (server) + `components/learn/QuizRunner.tsx` (client, `?q=`, keys 1–4, Enter, focus-to-question, "Question x of 5" live region, immediate per-question feedback) + `QuizResult.tsx` (pass → unlock CTA; fail → missed list with "Review slide n" deep links, re-teach list, retry/walkthrough/handoff copy). Hub node and the module-completion panel link to the quiz. |
| W4.6 | E2E + tests | **DONE** | `e2e/quiz.spec.ts`: fail → remediation → alternate form → pass → next module unlocked (server state asserted); 3 fails → handoff card with no 4th attempt. axe WCAG 2.2 AA on the player and the result/gate screens. Unit: gating matrix (4/5 pass, critical-miss fail, 3/5 fail), rotation, retry ladder, BKT hand-computed values, replay-from-events, content invariants. |

**Gates (run in-session):** `compileall` OK · `pytest apps/api/tests -q` → **151 passed** (was 125; +26) · `ruff check`/`format --check apps/api` clean · `mypy` success (46 files) · `npm --prefix apps/web run build` green · `npm --prefix apps/web run test:e2e` → **11/11** (2 new quiz + 4 learning + 5 existing).

**Math verification (global rule 4, `mathcheck` MCP, seed `20260929`):**
- BKT implementation: model P(correct) forecasts reproduce hand-computed **Brier 0.200245** (`verify_brier`, match at 1e-6, n=40); BKT converges (5 correct → 0.9981 ≥ 0.95 mastered; 5 wrong → 0.1731); calibration **ECE 0.075** (`verify_reliability`, 5 bins, n=40, 1 empty bin).
- Threshold: `verify_sample_size(n=5, minimum=10)` → **below** the bar (deficit 5) — an explicit limitation; the per-critical-objective coverage rule carries the correctness guarantee, not the item count. False-fail for true masters at per-item accuracy 0.73 = **38.1%** (`verify_wilson_ci` 95% CI **36.0–40.2%**, n=2000); the plan's "~41%" corresponds to p≈0.74.
- Assumptions: item independence within a form; per-item accuracy as the mastery signal; BKT params P(L0)=0.25, P(T)=0.15, P(G)=0.25 mcq / 0.15 select-all, P(S)=0.10.

**Deliberate deviations (recorded):**
1. `short` items are not authored (the enum value remains); grading fuzzy text adds risk with no Phase-4 benefit.
2. Per-question feedback needed a small extra endpoint so answers stay server-side (see §4.4).
3. The 10-minute cooldown is a settings value (`LEARNING_QUIZ_COOLDOWN_SECONDS`, default 600). The quiz e2e launches the API with `0` so the promised immediate retry is testable; the default is unchanged and the spec asserts the precondition explicitly.
4. The draw is persisted as an open attempt on `GET` (auditable form rotation and attempt numbering), rather than re-drawing on submit.
5. `attempt 3` provisional pass (BKT ≥ 0.8 on every critical objective) is unit-tested; with the current 5-item forms it is not reachable through three pure-fail attempts, so the live path lands on `handoff`.
