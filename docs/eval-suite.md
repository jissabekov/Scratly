# Live conversation eval suite

The eval suite is Scratly's **self-proving regressor**: 18 designed student personas run against a live API + Azure OpenAI + Postgres, producing full decision traces and mandatory assertions.

Related: [eval-findings-and-fix-plan.md](eval-findings-and-fix-plan.md) · [system-guide.md](system-guide.md)

---

## Quick start

```bash
# API + Postgres must be running (see local-development.md)
.venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/post-fix

# Partial run
.venv/Scripts/python scripts/eval_conversation_suite.py \
  --only maya_happy_path,thin_elicitation_loop \
  --out-dir eval/traces/proof

# Rebuild report from existing dumps
.venv/Scripts/python scripts/eval_conversation_suite.py \
  --analyze-only --out-dir eval/traces/post-fix

# Summary analysis helper
.venv/Scripts/python eval/analyze_post_fix.py post-fix-v2
```

**Windows:** `$env:PYTHONIOENCODING='utf-8'` before running (scenario titles use Unicode).

**Timing:** ~326–353 turns × ~8–25s/turn + admin dumps ≈ **65–80 minutes** full serial run.

---

## What each run produces

Per scenario (`eval/traces/<out-dir>/<scenario_id>.json`):

| Artifact | Contents |
|---|---|
| `turns[]` | Request/response per turn, latency, stage, `message_kind` |
| `admin_views` | transcript, evidence, profile, history, contradictions, project-fit |
| `decision_trace.events` | Full audit chain (limit 1000) |
| `metrics` | Aggregated analysis from `analyze_dump()` |
| `errors` | Turn or admin failures |

Suite-level: `suite_report.json` with cross-scenario totals and findings.

---

## 18 scenarios

| ID | Stress surface |
|---|---|
| `maya_happy_path` | Happy path → review → matching |
| `gamer_correction_repair` | Interest inflation pushback |
| `thin_elicitation_loop` | idk / thin → elicitation chips |
| `student_questions_and_refuse` | Process Q + homework refuse |
| `true_contradiction_resolve` | Real contradiction repair |
| `multi_value_nuance` | Multi-value without false conflicts |
| `hostile_terse_then_open` | Terse/hostile warm-up |
| `location_delayed_then_ready` | Geo late in script |
| `topic_switch_frustration` | Topic rejection |
| `execution_deep_dive` | Execution facets + Nashville geo |
| `profile_review_reject_repair` | Profile correction |
| `slang_uncertain_hedging` | Slang / hedging |
| `organizer_communicate_mode` | Organize/communicate work mode |
| `capability_scaffold_gaps` | Capability gaps |
| `greeting_slow_warm_up` | Slow warm-up |
| `mixed_intent_answer_plus_evidence` | Answer + evidence same turn |
| `early_complete_attempt` | Rush to project (anti-rush gate) |
| `bilingual_code_switch` | Code-switch / bilingual |

Scripts are inline in `scripts/eval_conversation_suite.py` → `SCENARIOS`.

---

## Metrics (`analyze_dump`)

- `stage_path`, `final_stage`, review/matching flags
- `target_key_counts` — **policy-only** `question_target_selected` (component `question_policy`)
- Evidence accepted/rejected totals, dimensions touched
- `assistant_leak_hits`, elicitation event counts
- `llm_runs`, `memory_snapshots` from Postgres

---

## Mandatory assertions (`assert_suite`)

| ID | Rule |
|---|---|
| A1 | All run scenarios `completed` with `errors=[]` |
| A2 | `max(target_key frequency) ≤ 4` for sessions ≥15 turns |
| A3 | `thin_elicitation_loop` has `elicitation_selected` |
| A4 | `thin_elicitation_loop` has `response.elicitation` |
| A5 | Stuck cohort ≥75% reach `profile_review` or `project_matching` |
| A6 | `multi_value_nuance` open contradictions = 0 |
| A7 | `student_questions_and_refuse` refuse + extract skip |
| A8 | `assistant_leak_hits = 0` |
| A9 | Long sessions have llm_runs + memory_snapshots |
| A10 | `early_complete_attempt` no matching before turn 8 |
| A11 | (Manual) zero Postgres FK violations during suite |
| A12 | No null `target_kind` on `question_target_selected` |

Partial runs skip scenario-specific checks (A3/A4/A5/A7/A10) when those scenarios are not in the batch.

Exit code 1 if any assertion fails or any scenario errors.

---

## Proof workflow (PR / release)

1. Run affected `--only` scenarios after policy changes
2. Run full 18 when touching stage/elicitation/repetition
3. Attach `suite_report.json` diff or `eval/analyze_post_fix.py` output
4. Quote one decision-trace excerpt per closed finding
5. Run unit tests: `test_determinism`, `test_student_ux`, `test_reliability_regressions`

---

## Trace excerpts (teacher verification)

```http
GET /v1/admin/sessions/{session_id}/decision-trace?limit=1000
GET /v1/admin/sessions/{session_id}/why-next-question
GET /v1/admin/sessions/{session_id}/profile
GET /v1/admin/sessions/{session_id}/question-history
```

Forensic one-liner:

```bash
.venv/Scripts/python -c "import json;d=json.load(open('eval/traces/post-fix/location_delayed_then_ready.json',encoding='utf-8'));print([(e['reason_code'],e.get('outputs')) for e in d['decision_trace']['events'] if e['event_type']=='stage_gate_evaluated'][-1:])"
```
