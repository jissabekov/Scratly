# Pre-rerun risk remediation — 2026-07-28

This change closes the five known implementation risks identified after assessment of the
committed 18-scenario baseline. A provider-backed 21-scenario rerun is still the proof gate.

## 1. Exhausted candidate pool

When repetition filtering leaves no usable candidate, policy now forces a single profile
review checkpoint instead of constructing an apparently fresh `profile_validation` probe
on every turn. Open contradictions and social-introduction turns remain exempt. This makes
the transition explicit and testable without promoting tentative evidence.

## 2. Post-completion conversation

Completed sessions take an early terminal fast path before intent classification, evidence
extraction, question writing, memory compaction, or research. The response is contextual to
the saved project title and distinguishes selection, rescoping, questions, and final notes.
It records `post_match_feedback_handled` and uses `post_match_feedback` message kind rather
than returning the same receipt for every input.

## 3. Research and recommendation relevance

- Independent web queries run concurrently with a 12-second bound and retain partial
  successes if another query fails.
- Catalog opportunities require topic overlap and a minimum fit score in addition to hard
  feasibility.
- Research findings can seed citation-grounded, topic-tagged directions when no catalog
  opportunity fits.
- The citation gate rejects generated projects whose topic keys do not overlap the profile.
- The product presents an offer only when at least two grounded choices survive. Otherwise
  it says that it could not verify relevant options and asks whether to broaden or pause;
  it never fills the gap with generic remote projects.

## 4. Latency

- Obvious assessment contributions and unambiguous questions use deterministic intent
  classification, removing one model round trip from most turns. Mixed/unclear messages
  retain model classification.
- Research queries execute concurrently rather than serially.
- Completed sessions avoid the entire assessment pipeline.
- Traces now report intent, extraction, writer, matching, and total turn durations plus
  whether intent classification used a model call. The rerun can therefore locate remaining
  latency rather than relying only on HTTP p95.

## 5. True information gain

Profile reduction now loads the prior snapshot and stores a real `before_state`, the new
`after_state`, and IDs of evidence accepted on that turn. Its trace output separates:

- `accepted_evidence_count` (extractor/grounding yield);
- `change_count` and `changed_paths` (actual profile state changes);
- `status_transitions` (for example unknown → provisional);
- `resolved_unknown_keys` (decision variables newly learned).

The eval analyzer calculates information-gain turns only from actual changes and separately
reports total profile changes, resolved unknowns, opportunity-ranking evaluations, and
ranking changes. It no longer treats accepted evidence as synonymous with information gain.

## Rerun acceptance

Run all 21 scenarios in a new directory. In addition to A1–A18, inspect:

1. no repeated `profile` fallback after `question_target_blocked` exhausts the pool;
2. `post_match_feedback` responses are contextual and terminal-fast-path duration is low;
3. irrelevant catalog entries carry `topic_mismatch` or `low_fit_score` and no generic offer
   is shown;
4. partial web success persists findings, while total failure produces
   `project_matching_abstained`;
5. `profile_reduced` has nonempty state-change fields only when the state truly changed;
6. ordinary-turn p50/p95 improves, with trace component timings explaining any residual
   outliers.
