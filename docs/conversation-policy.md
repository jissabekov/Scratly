# Conversation policy

Priority is fixed: contradictions; required hard variables; project-critical unknowns; provisional dimensions; project discrimination; profile validation. The model only personalizes the selected seeded intent; failures use its fallback template (parameterized for contradictions so options are named).

## Stages

Application state advances through discovery, measurement, gap-resolution, profile-review, project-matching, and complete.

Stage inputs:

- `coverage_established` = required dims with status `established` / required total
- `coverage_touched` = required dims with status ≠ `unknown` / required total (UI + early pacing)
- `contradictions` = count of **open** true contradictions

Policy:

- `projects_ready ∧ reviewed` → complete
- `reviewed` → project_matching
- `coverage_established ≥ 0.9 ∧ contradictions == 0` → profile_review
- `contradictions > 0 ∧ coverage_established ≥ 0.5` → gap_resolution
- else if `coverage_touched ≥ 0.4` → measurement
- else → discovery

Early open conflicts no longer force gap_resolution while coverage is only contested/touched.

## Memory

Compaction is attempted after roughly eight student responses or the token threshold. Each snapshot uses all raw messages through its sequence boundary, never a prior summary. Failure is non-fatal: retain the preceding snapshot and recent raw messages. Writer input is bounded recent context plus the latest memory snapshot. Extractor/reducer never consume memory as evidence.

## Reading a decision trace

The trace reason codes mirror the fixed priority and stage policies. `priority_*` explains why a target won; `stage_*` explains the derived application stage; grounding events aggregate rejected evidence by stable rejection reason; `contradiction_resolved` records close reasons; `question_quality_gate` records seeded overrides; and `writer_failure` proves that seeded fallback wording was used. Counts and entity IDs are stored, but student text is not duplicated in audit events. Successful Azure calls should link `llm_run_id` on extract/write events.
