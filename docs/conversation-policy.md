# Conversation policy
Priority is fixed: contradictions; required hard variables; project-critical unknowns; provisional dimensions; project discrimination; profile validation. Application state advances through discovery, measurement, gap-resolution, profile-review, project-matching, and complete. The model only personalizes the selected seeded intent; failures use its fallback template.

Compaction is attempted after roughly eight student responses or the token threshold. Each snapshot uses all raw messages through its sequence boundary, never a prior summary. Failure is non-fatal: retain the preceding snapshot and recent raw messages. Writer input is bounded recent context rather than an uncontrolled transcript.

## Reading a decision trace
The trace reason codes mirror the fixed priority and stage policies. `priority_*` explains why a target won; `stage_*` explains the derived application stage; grounding events aggregate rejected evidence by stable rejection reason; and `writer_failure` proves that seeded fallback wording was used. Counts and entity IDs are stored, but student text is not duplicated in audit events.
