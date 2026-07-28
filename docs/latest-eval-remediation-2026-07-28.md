# Latest eval remediation — 2026-07-28

Source artifacts: `eval/suite_run_latest.log`, `eval/traces/latest/` (18 scenarios,
353 turns), `suite_report.json`, and `reassessment.json`.

## Shortcomings found

1. **Target loops are systemic:** 17 scenarios violate the maximum consecutive-target
   assertion, with runs from 4 to 12. When all candidates were repetition-blocked, the
   processor used `filtered_candidates or candidates`, silently restoring every blocked
   candidate. Profile, execution, capability, and constraints loops followed.
2. **Stage progression is unreliable:** only 11/18 reached review, 10/18 matching, and
   9/18 complete. The stuck cohort reached review/matching in only 1/4 cases; three stage
   regressions occurred. A tentative preference could hold the entire interview hostage.
3. **Terminal replies repeat:** 67 assistant messages are exact duplicates. Seven scenarios
   exceed the 10% duplicate threshold, mostly because the scripted evaluator continues to
   send turns after completion and the terminal response is intentionally idempotent.
4. **Reported information gain is falsely zero:** all 18 sessions report 0.0 because
   `profile_reduced` put the accepted count in trace inputs while the analyzer reads
   `outputs.change_count`. Evidence acceptance itself is only 45.5%, so extraction quality
   remains a separate real concern.
5. **Conversation quality is uneven:** questions over-mine a narrow behavioral example,
   offer forced choices too readily, return to rejected topics, and sometimes advance to
   generic projects poorly related to the student's demonstrated interest. Location is
   asked more than once in some traces even though it should be only a feasibility input.
6. **Project research failed in all 10 matching runs.** The fallback directions are generic
   (for example, open-source docs/data journalism) and can mismatch art, cooking, or local
   science interests. This is a deployment/provider issue as well as a composition issue;
   project claims must remain grounded and citation-gated rather than invented.
7. **Latency is high:** p95 is 14.8 seconds, with many turns taking 8–15 seconds. Three LLM
   calls per ordinary turn and research failure/fallback paths are visible contributors.
8. **Eval completeness gaps:** duplicate terminal behavior dominates some scenarios;
   `reassessment.json` contains only the broken information-gain delta; and the analyzer
   does not judge project relevance, autonomy, age-appropriate voice, or whether each ask
   could actually change the recommendation.

## Changes in this remediation

- Blocked candidates can no longer re-enter selection when the filtered pool is empty.
- A fatigue-bounded review allows supported topics plus exhausted tentative work-mode and
  motivation fields to be reviewed without promoting tentative evidence. Location,
  execution, and capability/assets safeguards still apply.
- Question-writer policy now specifies a respectful adolescent stance: calm adult voice,
  no slang performance, concrete behavior, low burden, student autonomy, no diagnosis,
  and no hobby-to-career/project leap.
- The context sent to the writer carries the same stance as structured rules.
- `profile_reduced.outputs.accepted_evidence_count` now makes the eval evidence-yield proxy
  visible without falsely claiming that every accepted item changed the reduced profile.
- Unit coverage proves fatigue-bounded review keeps tentative fields tentative.

## Still requires a live rerun

The full suite depends on the configured database, Azure model, and web-research provider.
It must be rerun to quantify stage reach, repetition, research success, project relevance,
and latency. A passing unit suite proves policy invariants, not conversational quality.
Terminal post-completion turns should be evaluated separately from assessment turns rather
than hidden: either the product closes input, or a dedicated post-match refinement flow
must respond to feedback naturally without reopening assessment.
