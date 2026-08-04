# Evaluation assessment — committed `eval/traces/latest`

> **Implementation update:** the five pre-rerun risks identified here now have code-level
> remediations described in [eval-risk-remediation-2026-07-28.md](eval-risk-remediation-2026-07-28.md).
> They still require the provider-backed 21-scenario proof run below.

**Assessed:** 2026-07-28  
**Artifact report time:** 2026-07-28 14:11:19 UTC  
**Code/eval-harness commit time:** 2026-07-28 18:46:56 UTC (`d3c7bc4`)  
**Artifacts:** `eval/suite_run_latest.log`, `eval/traces/latest/*.json`,
`suite_report.json`, and `reassessment.json`

## Executive verdict

This run is **operationally complete but product-quality failing**: all 18 scripted
scenarios completed without transport errors, yet the suite recorded **29 mandatory
assertion violations**. It must not be treated as a passing release evaluation.

It is also **not a post-`d3c7bc4` evaluation**. The report was generated about 4 hours 36
minutes before the commit that added fatigue-bounded review, the repetition hard-stop,
evidence-yield output, adolescent prompt grounding, and the three adaptive scenarios. The
run contains 18 scenarios rather than the current 21 and has none of the `sim_*` adaptive
journeys or A17/A18 end-to-end results. It is a useful baseline/bug corpus, not proof of the
latest implementation.

## Scorecard

| Area | Result | Verdict |
|---|---:|---|
| Scenario execution | 18/18 without request errors | Pass (infrastructure only) |
| Mandatory assertions | 29 violations | **Fail** |
| Review reached | 11/18 (61%) | Fail |
| Matching reached | 10/18 (56%) | Fail |
| Complete reached | 9/18 (50%) | Fail |
| Stuck-cohort review/matching | 1/4 (25%; required 75%) | **Fail** |
| Consecutive-target rule | 17/18 scenarios fail | **Fail** |
| Stage monotonicity | 3 regressions | Fail |
| Duplicate assistant messages | 67 total; 8 scenarios over threshold | **Fail** |
| Evidence acceptance | 45.5% average | Weak |
| Reported information gain | 0.0 for all scenarios | Invalid instrumentation in this run |
| Web research | 10 started, 10 failed | **Fail** |
| End-to-end adaptive journeys | 0/3 present | Not evaluated |
| Turn latency | p95 14.785 s | Poor interactive UX |

## Critical findings

### P0 — The run does not evaluate the newly committed system

The current harness defines 21 scenarios and adaptive A17/A18 gates, but this artifact has
only the original 18. Its zero information-gain values also reflect the earlier trace shape.
Do not use this report to accept or reject the new fatigue/repetition changes; rerun all 21
on the committed revision and save to a new immutable directory rather than overwriting
`latest`.

### P0 — Repetition remains the dominant conversation failure

Seventeen scenarios repeat one committed target more than twice consecutively. Runs range
from 4 to 12, including:

- `profile_review_reject_repair`: 12;
- `capability_scaffold_gaps`: 12;
- `bilingual_code_switch`: 12;
- `topic_switch_frustration`: 11;
- `execution_deep_dive` and `early_complete_attempt`: 10;
- `gamer_correction_repair`, `student_questions_and_refuse`, and
  `hostile_terse_then_open`: 9.

This is not merely a metric defect. The transcripts repeatedly ask slightly different
versions of the same capability, execution, constraint, motivation, or profile question.
It produces an interrogative experience and crowds out new decision-changing information.

### P0 — Project recommendations are largely unrelated to the students

All ten research attempts failed. Nine of ten project offers are only permutations of the
same two generic fallbacks: **Remote Open-Source Docs Sprint** and **Remote Data Journalism
Starter**. Those were offered to students focused on tamales/family recipes, chemistry
video teaching, music production, board-game playtesting, art/anatomy practice, wildlife
camera labeling, and local water testing.

The only different offer was the bike-repair scenario, which received Bay Area transit,
climate field-guide, and data-journalism directions. Geography was closer, but project
mechanism and demonstrated interest were still weakly aligned. The product currently
reaches “matching” without delivering credible personalized choices.

### P0 — Completion semantics corrupt long-conversation evaluation

Nine scenarios reach `complete`, after which the fixed scripts continue for **65 turns**.
Every later student message receives the same saved-directions acknowledgment. This causes
most of the 67 exact duplicates and means substantive later facts and questions are ignored.

This reveals two separate issues:

1. The old fixed harness should have stopped or adapted at completion.
2. The product needs an explicit post-match behavior: close input, or support refinement and
   questions without reopening assessment.

The three adaptive scenarios now stop at completion, but they were not included in this
run, so the new behavior remains unproven.

### P1 — Stage progression is inconsistent

`location_delayed_then_ready` and `organizer_communicate_mode` never reach review or
matching despite rich scripted evidence. `maya_happy_path`, `hostile_terse_then_open`, and
`topic_switch_frustration` each regress one stage. A stage machine used to control matching
must be monotonic except for an explicitly traced correction path; these regressions are
neither expected nor acceptable here.

### P1 — Evidence and information-gain reporting are not decision-quality proof

The run accepted 1,427 evidence items but only 45.5% of proposed evidence on average. The
reported information-gain ratio is 0.0 in every scenario because these traces predate the
new `outputs.accepted_evidence_count` field. Even after that instrumentation fix, accepted
evidence is only a yield proxy: it does not prove that the profile changed or that a
question reduced project-choice uncertainty. A future metric should separately report:

- accepted evidence count;
- actual profile field/status transitions;
- previously unknown decision variables resolved;
- whether the leading project set or ranking changed.

### P1 — Latency is too high for a natural teen conversation

Suite p95 is 14.785 seconds. Several scenarios have p95 above 15 seconds, including
`maya_happy_path`, `multi_value_nuance`, and `organizer_communicate_mode`. A 15–19-year-old
chat experience that pauses this long after short replies will feel broken or overly
formal. Track p50/p95 by pipeline component and set a product target for ordinary turns.

## What did work

- All 18 sessions completed without request/admin-dump errors.
- All sessions recorded decision events, LLM runs, and memory snapshots.
- Student-question handling produced two expected refusals.
- The thin-answer path finally emitted one `elicitation_selected` event, although 12
  rephrases for one selection suggests recovery remains too hard to trigger.
- Ten sessions reached project matching and did not regenerate multiple offers.
- The suite detected its failures: the console ended with
  `AssertionViolations=29`, rather than falsely returning a clean quality verdict.

These are pipeline/reliability strengths, not evidence that recommendation quality is good.

## Reassessment file limitation

`reassessment.json` is not useful for release comparison. It contains only
`info_gain_ratio: 0.0` deltas for each shared scenario; it omits the available repetition,
stage, duplication, latency, evidence-yield, and matching-quality changes. Generate a fresh
baseline comparison with the current analyzer after the 21-scenario rerun.

## Required next evaluation

Run the committed revision in a new directory, for example:

```bash
python scripts/eval_conversation_suite.py \
  --out-dir eval/traces/2026-07-28-post-d3c7bc4 \
  --baseline-report eval/traces/latest/suite_report.json
```

Release acceptance should require:

1. all 21 scenarios present, including all three `sim_*` adaptive journeys;
2. A1–A18 with zero violations;
3. each adaptive journey reaches review and receives at least two cited, persona-relevant
   options, then supplies feedback or selects/rescopes one;
4. no committed target repeated more than twice consecutively;
5. no unexplained stage regression;
6. research succeeds, or matching abstains transparently rather than returning unrelated
   generic projects;
7. post-completion fixed-script turns excluded from conversational duplication metrics;
8. evidence yield, actual profile transitions, and project-decision change reported
   separately;
9. manual review of the three adaptive transcripts for responsiveness, respect, natural
   pacing, correction repair, and fit of the final options;
10. latency reported by pipeline component, with an explicit interactive target.

Until that run exists, the correct status is: **latest implementation unevaluated; committed
18-scenario baseline fails product quality**.
