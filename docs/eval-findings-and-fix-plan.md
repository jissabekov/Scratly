# Scratly Conversation Eval — Findings Report & Self-Proving Fix Plan

**Implementation status (2026-07-23):** Workstreams W1–W6 landed in code. See [system-guide.md](system-guide.md) for how the current system works and [eval-suite.md](eval-suite.md) for running proofs. Post-fix traces: `eval/traces/post-fix/`, `eval/traces/post-fix-v2/`. Full suite still fails some assertions (A2 repetition, A5 stuck cohort, occasional client timeouts) — see §Definition of done below.

**Date:** 2026-07-23  
**Suite:** `scripts/eval_conversation_suite.py` · 18 scenarios · 353 turns  
**Artifacts:** `eval/traces/*.json` · `eval/traces/suite_report.json`  
**Canvas summary:** [chatbot-eval-report](../../.cursor/projects/c-Users-jissabekov-Scratly/canvases/chatbot-eval-report.canvas.tsx) (optional UI companion)

This document is the durable engineering record. Every finding cites **session IDs + decision-trace events**. Every fix defines **proof probes** that must pass before the work is considered done. The suite itself is the regressor.

---

## 1. Executive verdict

| Layer | Verdict |
|---|---|
| **Recording / explainability** | Strong — full decision traces, LLM run linkage, memory snapshots on all 18 sessions |
| **Person-model growth** | Real early; stalls mid-session via target repetition |
| **Next-question policy** | Auditable but over-rewards continuity / discrimination on already-supported keys |
| **Stage progression** | Broken for majority — 11/18 never leave `measurement` because `coverage_established` caps below 0.9 |
| **Elicitation UX** | Effectively dead — thin detected, options never selected |
| **Reliability (pre-fix)** | Three production bugs aborted turns mid-suite (fixed during eval; must stay covered) |

**Headline:** Teachers can already answer “what did we record?” from traces. Students still feel like they are answering the same question. Matching is gated behind a coverage threshold the system rarely reaches.

---

## 2. Suite inventory (proof corpus)

| # | Scenario ID | Session ID | Turns | Events | Accepted / Rejected evidence | Final stage | Max re-ask |
|---|---|---|---:|---:|---|---|---|
| 1 | `maya_happy_path` | *(see dump)* | 18 | 270 | 71 / 140 | `project_matching` | capability×5 |
| 2 | `gamer_correction_repair` | `ea82af0b-5a0f-4771-b06e-f57e163bbc20` | 18 | 250 | 72 / 98 | `measurement` | execution×10 |
| 3 | `thin_elicitation_loop` | *(see dump)* | 20 | 317 | 64 / 31 | `project_matching` | capability×7 |
| 4 | `student_questions_and_refuse` | *(see dump)* | 20 | 274 | 61 / 44 | `measurement` | capability×6 |
| 5 | `true_contradiction_resolve` | *(see dump)* | 18 | 317 | 84 / 101 | `project_matching` | profile×9 |
| 6 | `multi_value_nuance` | *(see dump)* | 19 | 263 | 82 / 166 | `measurement` | motivation×6 |
| 7 | `hostile_terse_then_open` | `9918e1f6-e89a-42be-a024-8b79bf32a203` | 20 | 278 | 77 / 78 | `measurement` | constraints×10 |
| 8 | `location_delayed_then_ready` | `ee89ca7c-06a5-4f8b-ae3b-12fb46bf11d0` | 20 | 282 | 92 / 149 | `measurement` | execution×8 |
| 9 | `topic_switch_frustration` | *(see dump)* | 19 | 264 | 80 / 98 | `measurement` | execution×9 |
| 10 | `execution_deep_dive` | `8fbae04f-6655-4f6d-af59-6db28281f064` | 20 | 278 | 93 / 154 | `measurement` | constraints×7 |
| 11 | `profile_review_reject_repair` | *(see dump)* | 20 | 278 | 77 / 128 | `measurement` | capability×6 |
| 12 | `slang_uncertain_hedging` | *(see dump)* | 20 | 316 | 78 / 119 | `project_matching` | profile×8 |
| 13 | `organizer_communicate_mode` | `ba667dcc-206e-4513-a778-6f2e1a4cc324` | 19 | 265 | 86 / 130 | `measurement` | capability×8 |
| 14 | `capability_scaffold_gaps` | `dac2b74b-55fe-4060-a4f8-86ae5afaf0ce` | 20 | 286 | 92 / 117 | `measurement` | execution×4 |
| 15 | `greeting_slow_warm_up` | `83262a44-738f-434e-b004-fbd0fb953bb2` | 21 | 328 | 57 / 72 | `project_matching` | profile×12 |
| 16 | `mixed_intent_answer_plus_evidence` | *(see dump)* | 19 | 342 | 80 / 89 | `project_matching` | capability×9 |
| 17 | `early_complete_attempt` | `f4ed2cb0-f94a-44f6-bec4-b7085d2e6f34` | 22 | 368 | 75 / 77 | `project_matching` | profile×14 |
| 18 | `bilingual_code_switch` | `02527eec-df20-4841-9e28-6bfe6933cc38` | 20 | 279 | 74 / 170 | `measurement` | execution×12 |

**Aggregate recording health**

| Metric | Value |
|---|---:|
| Decision events | 5,255 |
| Questions recorded | 353 |
| Accepted evidence | 1,395 |
| Rejected evidence | 1,961 (~58% reject) |
| Sessions with `audit.llm_runs` | 18 / 18 |
| Sessions with memory snapshots | 18 / 18 |
| Policy-leak assistant hits | 0 |
| Open contradictions at end | 0 |
| Reached `profile_review` | 5 / 18 |
| Reached `project_matching` | 7 / 18 |
| Reached `complete` | 0 / 18 |
| Elicitation UI responses | 0 / 18 |
| `elicitation_selected` events | 0 |
| Mean turn latency | ~9.6 s |

Session IDs for every dump are in `eval/traces/<id>.json` → `session.session_id`.

---

## 3. Findings (with trace proofs)

### F1 — Question target repetition (P0)

**Symptom.** Across 18–22 turns, sessions typically use only 5–9 unique `target_key`s. The same key is re-selected 7–14 times.

**Proof.**

| Scenario | Session | Dominant key | Count | Dominant reason codes |
|---|---|---|---:|---|
| `bilingual_code_switch` | `02527eec-…` | `execution` | 12 | `priority_project_discrimination`×13, `largest_coverage_gap`×10, `one_high_value_behavioral_follow_up`×7 |
| `early_complete_attempt` | `f4ed2cb0-…` | `profile` | 14 | `priority_profile_validation`×14 |
| `greeting_slow_warm_up` | `83262a44-…` | `profile` | 12 | `priority_profile_validation`×12 |
| `hostile_terse_then_open` | `9918e1f6-…` | `constraints` | 10 | `largest_coverage_gap` / `priority_project_discrimination` |
| `gamer_correction_repair` | `ea82af0b-…` | `execution` | 10 | discrimination + coverage gap |

**Mechanism (code).**

- `question_policy.question_value()` applies `min(asked_count * 0.15, 0.6)` — capped, so after ~4 asks penalty stops growing.
- Continuity / `FOLLOW_UP` (`one_high_value_behavioral_follow_up`) and `project_discrimination` keep winning even when the dimension is already supported.
- `profile_validation` is always a candidate → floods late turns with `profile`.

**Impact.** Information gain plateaus; student experience feels stuck; stage cannot advance because the system keeps probing the same incomplete facet instead of establishing remaining dims (esp. `assets`, deeper `capability`).

---

### F2 — Stage stall below `profile_review` (P0)

**Symptom.** 11/18 sessions end in `measurement` despite rich evidence (60–93 accepted items) and often `location_ready=true`.

**Proof (decision-trace `stage_derived` inputs).**

| Scenario | `coverage_touched` | `coverage_established` | `location_ready` | `reviewed` | Resulting stage |
|---|---:|---:|---|---|---|
| `location_delayed_then_ready` | 1.0 | **0.8** | true | false | `measurement` |
| `organizer_communicate_mode` | 1.0 | **0.8** | true | false | `measurement` |
| `gamer_correction_repair` | 1.0 | **0.8** | true | false | `measurement` |
| `capability_scaffold_gaps` | 1.0 | **0.6** | true | false | `measurement` |
| `bilingual_code_switch` | 1.0 | **0.6** | true | false | `measurement` |
| `execution_deep_dive` | 0.8 | **0.8** | **false** | false | `measurement` |

**Mechanism (code).**

```text
PROFILE_REVIEW_ESTABLISHED = 0.9   # question_policy.py
derive_stage: if established >= 0.9 and contradictions == 0 → profile_review
```

Sessions repeatedly top out at **0.6–0.8 established**. Touched hits 1.0, but established never crosses the review latch. Without `reviewed=true`, `project_matching` is unreachable even when location is ready.

**Secondary gate:** `execution_deep_dive` also never establishes geo (`location_ready=false`) despite a scripted Nashville answer — location extraction/readiness path needs its own probe.

---

### F3 — Elicitation path is dead (P0)

**Symptom.** Product bar requires option chips after repeated thin answers. Suite: **0** `elicitation` message kinds, **0** `elicitation_selected` events, **0** non-null `TurnResponse.elicitation`.

**Proof.** `thin_elicitation_loop` detects thin repeatedly:

```text
answer_thinness_evaluated reason=thin
outputs.is_thin=true
reason_codes includes idk_or_minimal_pattern / short_token_count
```

…but turns 1–4 still return `message_kind=assessment_question` with `elicitation=null`.

**Mechanism (code) — two bugs compound:**

1. First thin on a recoverable target only increments counters (`attempts == 1` branch) — no options yet. That is intentional.
2. Options require `should_offer_options(reply_signal, attempts)`:

```python
# elicitation_policy.py
return reply_signal == "insufficient" and attempts == 2
```

So options fire **only** when reply signal is exactly `insufficient` **and** attempt counter is exactly 2 on the **same** target key.

Failures observed:

- Many thin replies classify as `thin_answer` (short token count), not `insufficient` → options never unlock even at attempt 2.
- Policy often **switches target key** between thin turns → attempt counter resets to 1 forever.
- `can_recover` excludes `social_intro`, `profile_validation`, `behavioral_anchor` — early discovery thins never enter the elicitation machine.

---

### F4 — Extractor grounding yield is poor (P1)

**Symptom.** 1,961 rejected vs 1,395 accepted (~58% reject).

**Proof.** Per-scenario reject counts in §2; common rejection reasons in evidence admin view include `exact_quote_not_found`, `source_message_unavailable_or_not_owned`, taxonomy misses.

**Impact.** Profile under-establishes (feeds F2). LLM spend is high for low accepted yield.

**Related reliability bug (fixed during eval, must stay tested):** rejected proposals still attempted `evidence_sources` inserts with hallucinated message IDs → turn-aborting FK errors. Fix: only link owned IDs for accepted evidence (`assessment.py`).

---

### F5 — Dimension coverage skew (P1)

**Symptom.** Every session touches `topics`, `work_mode`, `motivation`, `execution`. Only **9/18** touch `capability`, **5/18** touch `assets`.

**Proof.** `suite_report.json` → `dimensions_touched_across_scenarios`.

**Impact.** Project scaffolding and asset-aware matching are under-informed; discrimination loops on execution/capability instead of collecting missing hard vars.

---

### F6 — Trace schema inconsistency (P2)

**Symptom.** 147 `question_target_selected` events have `target_kind: null` in suite aggregation.

**Proof.** Planner events (`conversation_planner`) emit `action` / `target_key` but not always `target_kind`; policy events emit `kind`/`key` under different shapes. Teacher “why-next” still works, but automated eval of kind mix is incomplete.

---

### F7 — Infra / reliability defects found mid-suite (P0, fixed — must lock)

| Defect | Failure mode | Fix landed | Proof required |
|---|---|---|---|
| Shared LLM singleton race | Concurrent turns wrote foreign `llm_run_id` → `decision_events` FK abort | `contextvars` for audit / turn / last_run_id in `azure_openai.py` | Concurrent 2-session smoke; no FK in postgres logs |
| Rejected evidence source IDs | Hallucinated `message_id` → `evidence_sources` FK abort | Filter to owned IDs; skip sources on reject | Unit + live turn with bad proposed ID still completes |
| NUL bytes in quotes | Postgres `CharacterNotInRepertoireError` → 500 | Strip `\x00` before evidence insert | Fixture quote with NUL persists as cleaned text |
| Decision-trace `limit=2000` | Admin dump 422 | Eval harness uses `limit=1000` | Harness dump succeeds |

---

### F8 — What already works (do not regress)

Keep these as permanent green assertions:

| Behavior | Proof from suite |
|---|---|
| Full decision pipeline per turn | 353× `turn_started`/`turn_completed`/`stage_derived`/… |
| Student process Q + homework refuse | `student_questions_and_refuse`: refusals + `evidence_extraction_skipped` |
| No false multi-value contradictions left open | `multi_value_nuance` open_c=0; suite-wide open_c=0 |
| No internal policy leakage in assistant text | `assistant_leak_hits=0` |
| Stage gating resists “just give me a project” | `early_complete_attempt` stays discovery/measurement until substance, then matches |
| LLM + memory audit present on long chats | llm_runs & memory_snapshots on all 18 |

---

## 4. Root-cause map

```text
                    ┌──────────────────────────────┐
                    │ Thin "idk" / short replies   │
                    └──────────────┬───────────────┘
                                   │
           reply_signal=thin ──────┤────── attempts reset on target switch
           (not insufficient)      │
                                   ▼
                    ┌──────────────────────────────┐
                    │ elicitation_selected NEVER   │  ← F3
                    └──────────────────────────────┘

 High continuity + capped ask penalty
 + always-on profile_validation
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Same target_key re-selected  │  ← F1
                    │ 7–14× per session            │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Remaining dims never become  │  ← F5
                    │ established (assets, etc.)   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ coverage_established ≤ 0.8   │  ← F2
                    │ PROFILE_REVIEW needs 0.9     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                         Stuck in measurement
                         (11/18 sessions)
```

---

## 5. Fix plan (workstreams)

Each workstream has: **code locus**, **change**, **trace events to emit**, **unit proof**, **live suite proof**, **scrutinize / anti-cheat**.

### W1 — Hard-stop target repetition (closes F1, helps F2/F5)

**Code**

- `apps/api/app/services/question_policy.py` — `question_value`, `select_next`, planner FOLLOW_UP
- `apps/api/app/repository/assessment.py` — `question_candidates` asked_count / status
- Optional: persist last N `(kind,key)` outcomes on session counters

**Change**

1. Raise uncapped ask penalty, e.g. `asked_count * 0.35` with hard exclude when `asked_count >= 2` **and** coverage status ∈ `{supported, established}` (unless contradiction / repair / explicit student correction).
2. Demote `profile_validation` until `coverage_established >= 0.9` or student asks for summary / stage is review.
3. After two non-advancing FOLLOW_UPs on same key (no new accepted evidence on that dim), force SWITCH to highest-value **unasked or unknown** anchor.
4. Emit decision event:

```text
event_type: question_target_blocked
reason_code: repetition_hard_stop | follow_up_exhausted
outputs: { blocked_key, asked_count, status, chosen_instead }
```

**Unit proof**

- Fixture: candidate list with `execution` asked_count=3 status=supported vs `assets` unknown → must select `assets`.
- Fixture: FOLLOW_UP twice with zero accepted evidence on dim → third turn SWITCH.

**Live suite proof (self-proving)**

```bash
.venv/Scripts/python scripts/eval_conversation_suite.py \
  --only bilingual_code_switch,early_complete_attempt,hostile_terse_then_open,gamer_correction_repair \
  --out-dir eval/traces/w1
```

Assertions (add to harness):

- `max(target_key frequency) <= 4` for sessions ≥ 15 turns
- `unique target_keys >= 8` for rich scripts (≥18 turns with multi-dim answers)
- At least one `question_target_blocked` with `repetition_hard_stop` in bilingual/hostile dumps

**Scrutinize**

- Must not block contradiction clarification.
- Must not block first deepening of provisional topics.
- Diff teacher transcript: no sudden topic whiplash >1 consecutive SWITCH without bridge template.

---

### W2 — Make established coverage reachable + review latch honest (closes F2)

**Code**

- `question_policy.derive_stage` / `PROFILE_REVIEW_ESTABLISHED`
- Coverage status updates in reducer / `stage_inputs()`
- Geo readiness: `location_policy.py` + constraints evidence for places like “Nashville”

**Change**

1. **Diagnose first (forensic script):** for each stuck session, dump per-dimension status that keeps established at 0.6–0.8. Commit that table into the PR description.
2. Prefer **decision-sufficient review** over inventory completion:
   - Enter `profile_review` when: no open contradictions AND location_ready AND core anchors `{topics, work_mode, motivation, execution}` are supported AND (≥1 of capability/assets OR explicit soft-skip) AND expected value of next question < threshold.
   - Keep 0.9 path as alternate “full establish” route.
3. Fix geo miss on `execution_deep_dive`-class answers (city name in free text must set `location_ready`).
4. Emit:

```text
event_type: stage_gate_evaluated
outputs: {
  coverage_established, coverage_touched,
  missing_established_keys[],
  location_ready, review_eligible, reason_code
}
```

**Unit proof**

- `derive_stage` matrix: established 0.8 + core-four supported + location_ready + reviewed false → `profile_review` under new rule.
- Geo parse: “I'm in Nashville.” → `location_ready=true`.

**Live suite proof**

```bash
.venv/Scripts/python scripts/eval_conversation_suite.py \
  --only location_delayed_then_ready,organizer_communicate_mode,execution_deep_dive,gamer_correction_repair,bilingual_code_switch,maya_happy_path \
  --out-dir eval/traces/w2
```

Assertions:

- ≥ 5/6 of the previously stuck scenarios reach `profile_review` or `project_matching`
- Final `stage_derived.inputs.coverage_established` either ≥ 0.9 **or** `reason_code=decision_sufficient_review`
- `execution_deep_dive` ends with `location_ready=true` after Nashville turn
- Maya still reaches matching (no regression)

**Scrutinize**

- Do not enter review with empty interests.
- `early_complete_attempt` must still refuse matching on turn 1–4 (anti-rush preserved).
- Compare profile snapshot at review: every claimed supported dim has ≥1 accepted evidence ID in entity_refs.

---

### W3 — Repair elicitation (closes F3)

**Code**

- `elicitation_policy.should_offer_options`
- `turn_processor` thin branch (`attempts`, `can_recover`)
- Reply signal alignment with `thin_answer.evaluate_thin_answer`

**Change**

1. Offer options when:

```text
(thin.is_thin OR reply_signal in {insufficient, thin_answer})
AND attempts >= 2
AND same elicitation_target_key (or same dimension family)
AND not greeting-only open
```

2. Expand `can_recover` to include mid-assessment targets actually selected in discovery/measurement (`project_critical_unknown`, topics depth, etc.) — still **exclude** pure `social_intro` on turn 1.
3. If policy switches question target but student was thin on previous target, **keep** elicitation counter for the unanswered dim (don’t reset on planner SWITCH).
4. Always emit one of: `elicitation_selected` | `elicitation_rephrase` | `elicitation_exhausted` | `elicitation_skipped_not_recoverable` (today’s silent attempts==1 path must become `elicitation_rephrase`).

**Unit proof**

- `idk` then `idk` on same recoverable dim → second response `message_kind=elicitation` with options.
- `whatever` (thin, not insufficient) twice → still elicitation.
- Greeting `hi` → never elicitation chips.

**Live suite proof**

```bash
.venv/Scripts/python scripts/eval_conversation_suite.py \
  --only thin_elicitation_loop,hostile_terse_then_open \
  --out-dir eval/traces/w3
```

Assertions:

- `thin_elicitation_loop`: ≥1 turn with `response.elicitation.options` length ≥ 2
- ≥1 `elicitation_selected` event
- After options exhausted / answered, session still progresses (no stuck loop)
- Hostile scenario: if ≥2 consecutive thin, either elicitation or traced `elicitation_exhausted`

**Scrutinize**

- Options must not appear on greetings (existing UX tests).
- Choosing an option must produce accepted evidence or an explicit skip event — never silent no-op.
- UNKNOWN≠0: soft-skip must not write oppose polarity.

---

### W4 — Extractor yield + safe persistence (closes F4, locks F7)

**Code**

- Extractor prompt `apps/api/prompts/…`
- `grounding_validator.py`
- `validate_and_record_evidence` (already filters sources; add metrics)

**Change**

1. Prompt: only cite `allowed_source_messages[].id`; verbatim substrings only.
2. Pre-validate in extractor post-process: drop proposals with unknown IDs before DB.
3. Trace:

```text
evidence_validated.outputs.rejection_reason_counts  # already exists — assert in suite
evidence_yield: accepted/proposed ratio per turn
```

4. Keep NUL strip + owned-ID source linking; add regression tests.

**Unit proof**

- Proposal with random UUID source → rejected, turn still commits.
- Quote containing `\x00` → stored without NUL; turn 200.

**Live suite proof**

- Suite-wide accepted/proposed ≥ 0.50 (up from ~0.42) on Maya + bilingual + multi_value
- Zero postgres FK errors during full 18-run
- Concurrent smoke: 2 parallel 5-turn sessions, zero `decision_events_llm_run_id_fkey`

**Scrutinize**

- Do not loosen grounding to “fuzzy quote contains” — that reintroduces hallucination into profile.
- Yield gains must come from better proposals, not weaker validators (compare rejection_reason_counts before/after).

---

### W5 — Trace contract completeness (closes F6)

**Code**

- `turn_processor` planner + policy `question_target_selected` payloads
- `contracts/tracing.py` if schemas exist

**Change**

Normalize every `question_target_selected` to:

```json
{
  "target_kind": "...",
  "target_key": "...",
  "decision_value": 0.0,
  "planner_action": "follow_up|switch|...",
  "asked_count": 0,
  "candidate_count": 0
}
```

**Proof**

- Eval aggregator: `target_kind null count == 0`
- Admin `why-next-question` still human-readable

---

### W6 — Permanent self-proving harness (closes the loop)

**Code**

- Extend `scripts/eval_conversation_suite.py` assertions
- Optional CI job: nightly or on PR labeled `conversation`

**Mandatory suite assertions (fail build if violated)**

| ID | Assertion |
|---|---|
| A1 | All scenarios `completed` and `errors=[]` |
| A2 | `max_target_key_frequency <= 4` for turns≥15 |
| A3 | `elicitation_selected >= 1` in `thin_elicitation_loop` |
| A4 | `thin_elicitation_loop` has ≥1 `response.elicitation` |
| A5 | Stuck cohort (`location_delayed`, `organizer`, `gamer`, `bilingual`) → ≥75% reach `profile_review` or `project_matching` |
| A6 | `multi_value_nuance.open_contradictions == 0` |
| A7 | `student_questions_and_refuse` has refuse + extract skip |
| A8 | `assistant_leak_hits == 0` |
| A9 | `llm_runs > 0` and `memory_snapshots >= 1` for turns≥8 |
| A10 | `early_complete_attempt` does not enter `project_matching` before turn 8 |
| A11 | Postgres log: zero FK violations during suite window |
| A12 | `target_kind` null rate == 0 on new traces |

**Self-scrutinization ritual (every PR)**

1. Run affected `--only` scenarios; attach `suite_report.json` diff (before/after metrics table).
2. For each closed finding, paste **one** decision-trace excerpt proving the new event/reason_code.
3. Run full 18 when touching policy/stage/elicitation.
4. Explicit “what could still be fake-green?” note in PR (e.g. threshold lowered without collecting assets).
5. Teacher read of 2 transcripts (Maya + thin) — human checkbox in PR template.

---

## 6. Implementation order

| Order | Workstream | Depends on | Est. risk |
|---|---|---|---|
| 0 | Lock F7 regressions as unit tests | — | Low |
| 1 | W3 elicitation | — | Medium (UX) |
| 2 | W1 repetition hard-stop | — | Medium (pacing) |
| 3 | W2 stage / established / geo | W1 helps | High (stage math) |
| 4 | W4 extractor yield | W2 benefits | Medium |
| 5 | W5 trace contract | — | Low |
| 6 | W6 harness assertions in CI | W1–W5 | Low |

Do **not** lower `PROFILE_REVIEW_ESTABLISHED` alone without W1 — that manufactures review on shallow profiles (fake green).

---

## 7. Proof commands (copy/paste)

```bash
# Full regressor after policy changes
.venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/post-fix

# Targeted proofs
.venv/Scripts/python scripts/eval_conversation_suite.py --only thin_elicitation_loop --out-dir eval/traces/proof-elicit
.venv/Scripts/python scripts/eval_conversation_suite.py --only bilingual_code_switch,hostile_terse_then_open --out-dir eval/traces/proof-reask
.venv/Scripts/python scripts/eval_conversation_suite.py --only location_delayed_then_ready,execution_deep_dive,organizer_communicate_mode --out-dir eval/traces/proof-stage

# Unit / contract
.venv/Scripts/python -m pytest apps/api/tests/test_student_ux.py apps/api/tests/test_determinism.py apps/api/tests/test_decision_trace.py -q

# Forensic: stage gates from a dump
.venv/Scripts/python -c "import json;d=json.load(open('eval/traces/location_delayed_then_ready.json',encoding='utf-8'));\
print([ (e['reason_code'], e.get('inputs'), e.get('outputs')) for e in d['decision_trace']['events'] if e['event_type']=='stage_derived'][-3:])"
```

Teacher verification for any session:

```text
GET /v1/admin/sessions/{session_id}/decision-trace?limit=1000
GET /v1/admin/sessions/{session_id}/why-next-question
GET /v1/admin/sessions/{session_id}/profile
GET /v1/admin/sessions/{session_id}/question-history
```

---

## 8. Definition of done

The findings in this report are **closed** only when:

1. Full 18-scenario suite is green under the new assertions A1–A12.
2. Each of F1–F7 has a before/after metric row in the PR (not just narrative).
3. At least one live session ID per fix is linked with the proving events quoted.
4. No new FK / UTF8 / concurrent LLM audit failures in postgres logs during the suite.
5. Human teacher check: Maya + thin transcripts feel progressive (no 5× same ask; thin gets choices).

Until then, treat stage-matching demos as **partial** — recording is trustworthy; pacing and elicitation are not.

---

## 9. Appendix — key code references

| Area | Path |
|---|---|
| Turn pipeline | `apps/api/app/services/turn_processor.py` |
| Stage + value + reply signals | `apps/api/app/services/question_policy.py` |
| Elicitation | `apps/api/app/services/elicitation_policy.py` |
| Thin detection | `apps/api/app/services/thin_answer.py` |
| Evidence persist | `apps/api/app/repository/assessment.py` (`validate_and_record_evidence`) |
| LLM audit isolation | `apps/api/app/services/azure_openai.py` |
| Eval harness | `scripts/eval_conversation_suite.py` |
| Baseline dumps | `eval/traces/*.json` |

---

*Generated from the 2026-07-23 live Azure eval corpus. Re-run the suite to refresh proofs; do not treat this markdown as a substitute for fresh traces after code changes.*
