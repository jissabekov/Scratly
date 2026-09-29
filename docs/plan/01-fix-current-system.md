# Plan 01 — Fix the current system (Phase 1)

> **Status: READY TO EXECUTE** · Owner: Devin (backend) · Depends on: nothing
> **Goal:** take the committed Aug 4 eval state (`21/21 clean, AssertionViolations=46`) to a full-suite green run (A1–A18, zero violations) without weakening any assertion.

Every workstream below follows the same contract: **root cause → change → unit proof → live proof → acceptance**. A workstream is done only when its live proof (eval scenario or unit test) is committed next to the fix. Never lower a threshold to pass ("fake green" — see docs/eval-findings-and-fix-plan.md §8).

---

## W1.1 — Target repetition loops (fixes A2, worst offender: 21/21 scenarios)

**Evidence (Aug 4 run):** every scenario repeats one committed target 4–17 consecutive turns (`sim_luz` 17, `sim_nia` 16, `profile_review_reject_repair` 14). The `repetition_hard_stop` (PR #4/#5 era) reduced repeats vs baseline but loops persist under live LLM variance.

**Forensic result (committed 2026-09-29, from `eval/traces/latest/*.json`):** the hypothesized causes (a) blocked-pool fallback, (b) planner FOLLOW_UP override, (c) value score still highest are all **ruled out**. The actual mechanism, identical in all 3 worst scenarios: a **`profile_validation` fallback loop**. Every streak turn selects the pseudo-target `profile` (kind `profile_validation`, reason `priority_profile_validation`) with `inputs.candidates=[]`, `candidate_count: 0`, `planner_action: null`, constant `decision_value: 0.175`, and `asked_count: 0` that never increments — so neither a consecutive nor a total exposure cap can bind to it. Each streak turn also runs `research_started` → `research_failed(RuntimeError)` → `project_matching_abstained(no_relevant_opportunity, findings=0)` → identical `matching_unavailable` message. Trace inconsistency: during streaks, `question_target_blocked.outputs.chosen_instead` (e.g. `work_mode`) disagrees with the actually selected `target_key: "profile"`.

| scenario | streak length | streak turns | streak target | (a) blocked-pool | (b) planner FOLLOW_UP | (c) value-highest | (d) other | blocked events |
|---|---|---|---|---|---|---|---|---|
| sim_luz_bilingual_food | 17 (t8–t24) | 17 | `profile`/`profile_validation` | 0 | 0 | 0 | 16 | 18 |
| sim_nia_creative_community | 16 (t9–t24) | 16 | `profile` | 0 | 0 | 0 | 15 | 2 |
| profile_review_reject_repair | 14 (t7–t20) | 14 | `profile` | 0 | 0 | 0 | 13 | 1 |

Suite-wide corroboration: all 21 scenarios show the same signature (`profile`/`profile_validation` fallback streaks 4–17 turns); `research_started=225`, `research_failed=225` (100% failure, `RuntimeError`), `project_matching_abstained=224`; `question_target_blocked(repetition_hard_stop)` fires only against real dims (e.g. `work_mode` at `asked_count=2, status=supported`) and its `chosen_instead` disagrees with the actual selection during streaks.

**Fix (deterministic, code-owned — CAT item-exposure control):**
- New per-dimension exposure state on `core.sessions` (migration `013_learning_foundations.sql` or a dedicated `013_exposure_control.sql`):
  - `dim_ask_counts` (jsonb): `{dim: {total, consecutive, last_asked_turn}}`
  - updated in `process_student_turn` at question-commit time, inside the sole write path.
- Hard rule in `question_policy.select_next` / planner:
  - `consecutive_count >= 2` → dimension **ineligible** for selection, regardless of decision value (exceptions: `contradiction` repair, explicit student correction, essential gate).
  - `total >= 3` on a dim whose status is `supported/established` → hard-excluded (extends existing `is_repetition_blocked`).
- Emit `question_target_blocked` with new reason `exposure_cap` (migration: new enum value).
- LLM may rank questions *within* the chosen dimension; it never chooses the dimension.

**Unit proof:** candidate list where `execution` has `consecutive=2` vs fresh `assets` → must select `assets`; contradiction target still selectable at `consecutive=2`.
**Live proof:** `--only sim_luz_bilingual_food,sim_nia_creative_community,profile_review_reject_repair` → A2 clean; then full suite.
**Files:** `question_policy.py`, `turn_processor.py`, `repository/assessment.py`, new migration, `eval_conversation_suite.py` (assertion stays at ≤2).

## W1.2 — Duplicate assistant messages (A14, ~20 scenarios, ratios 25–74%)

**Fix (two layers):**
1. **Outgoing dedup ring buffer** (deterministic): keep last 8 assistant texts per session (new `conversation.assistant_recent` table or session jsonb column); normalize (casefold, strip punct/whitespace); on exact match or Jaccard ≥ 0.7 for short replies → regenerate once with an injected steering note; if still near-dup → substitute a templated transition line from a small bank. Trace event `assistant_duplicate_rewritten`.
2. **Post-completion turns:** scripted scenarios keep sending turns after `complete`; the terminal fast path (PR #7) returns contextual-but-often-identical replies. Keep `post_match_feedback` contextual variety (≥4 distinct templates by intent: selection/rescope/question/note) **and** exclude post-completion turns from the conversational dup metric in the harness (metrics split: `assessment` vs `post_match` turns) — this is an instrumentation fix, not threshold lowering; A14 stays at ≤10% for assessment turns.

**Unit proof:** ring-buffer fixture (8 replies, inject duplicate → rewritten); post-match template variety test.
**Live proof:** `--only early_complete_attempt,mixed_intent_answer_plus_evidence,sim_luz_bilingual_food` → A14 pass.

## W1.3 — Adaptive options never presented (A18, 0/3 sim personas; 1 offer in whole suite)

**Root cause chain:** research fails (Responses API unavailable on this resource — see Plan 01 §W1.5) → zero findings → citation gate + topic-overlap gate reject everything → offer abstains → `options_presented=0` → A18 fails on `options_presented/options_are_grounded/options_fit_persona/feedback_after_options`.

**Fix (two parts):**
1. **Research path that works on this resource:** provider abstraction in `web_research_client.py` — Responses-API path kept when available; new default path = direct search API (Bing/Brave/Tavily — config-driven, key in `.env`) + bounded page fetch + quote extraction, feeding the *same* `ResearchFindingPacket` shape so the citation gate is unchanged. Concurrent queries, 12s bound, partial success retained (pattern already in `web_research_client.py`).
2. **Catalog-first matching:** curated `matching.opportunities` get topic tags + geo; `rank_opportunities` already gates on topic overlap + min fit (PR #7) — extend the catalog with enough spread (per archetype × geo bucket) that ≥2 grounded persona-relevant options exist for the 3 sim personas *without* web research. Offer only when ≥2 survive; abstain otherwise (keep).

**Unit proof:** rank_opportunities returns ≥2 for each sim persona profile from catalog alone; citation gate still rejects topic-mismatched entries.
**Live proof:** full suite → A18 checks `options_presented, options_are_grounded, options_fit_persona, feedback_after_options` all pass; ≥1 `complete`.

## W1.4 — Completion rate (1/21 reached `complete`)

- Diagnose via traces: where do sessions stall at `project_matching` (abstention loop? feedback never requested?).
- Add traced path: after offer + student feedback/selection → `complete` (already exists for bilingual scenario; find why others never compose).
- Acceptance: ≥15/21 reach `complete` in the rerun; abstention only on genuine research failure with `project_matching_abstained`.

## W1.5 — Latency (p95 ~7–13.5s → target: p50 ≤3s, p95 ≤8s)

1. **Prompt-prefix discipline:** byte-stable system prompts per component (already versioned files) + session-stable prefix; volatile state appended last → Azure prompt caching. Measure TTFT before/after.
2. **Model routing:** intent (already deterministic), extraction, dedup-check → analyzer deployment; only writer/compose on writer deployment. Verify both deployments exist (`gpt-5.4-mini` confirmed working).
3. **Component timings** already traced (PR #7) — after W1.1/W1.2 land, produce a per-component p50/p95 table from the rerun and set the product target per stage.
4. Stream assistant text when writer is the only remaining call (UI change, coordinate with Plan 02).

## W1.5 — Stage regressions & completion semantics (A15)

- `organizer_communicate_mode` had 1 regression: make `derive_stage` monotonic except the explicit traced correction path; unit-test the regression matrix; assert A15 in every partial run.

## W1.6 — Engineering hygiene (gates for everything above)

- Add `ruff` (format+lint) and `mypy` (or pyright) config; wire into `make check` equivalent for Windows (`.venv/Scripts/...`); fix Makefile paths.
- CI (GitHub Actions): compileall + pytest on every PR; eval-suite job manual-trigger (`workflow_dispatch`) with `--only` support.
- Prompt-version discipline: any prompt change = new version dir + eval rerun.

---

## Execution order & verification

| # | Workstream | Unblocks | Est. risk |
|---|---|---|---|
| 1 | W1.1 exposure caps | all | Medium |
| 2 | W1.2 dedup ring buffer | A14 | Low |
| 3 | W1.3 catalog-first matching + research abstraction | A18, P4 | High |
| 4 | W1.5 stage monotonicity | A15 | Low |
| 5 | W1.4 completion path | complete-rate | Medium |
| 6 | W1.6 hygiene (ruff/mypy/CI) | all | Low |
| 7 | Full 21-scenario rerun (new dir + baseline diff) | release gate | — |

**Verification commands (every workstream):**
```bash
.venv/Scripts/python -m compileall -q apps/api/app
.venv/Scripts/python -m pytest apps/api/tests -q
PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/<date-label>
.venv/Scripts/python eval/analyze_post_fix.py <date-label>
```

**Definition of done (from docs/eval-findings-and-fix-plan.md §8, unchanged):** full 21-scenario suite green A1–A18, before/after metric rows per finding, one live session ID per fix with proving events quoted, zero FK/UTF8/concurrent-audit failures, human teacher check on 2 transcripts.
