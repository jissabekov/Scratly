# Conversation policy

Machine rules for **what to ask next** and **which stage** the session is in. The model only personalizes the selected intent; it does not choose priority or stage.

Product tone and anti-patterns: [conversation-quality.md](conversation-quality.md).  
Conflict math: [scoring-rules.md](scoring-rules.md).  
Index: [README.md](README.md).

---

## Question priority

Fixed order (`question_policy.PRIORITY`):

1. `contradiction` — open true conflict (engine v2)
2. `required_hard_variable` — required dim still `unknown` **or** missing location (`constraints:geo`)
3. `project_critical_unknown` — `topics` or `work_mode` still `unknown`
4. `provisional_dimension` — dim is `provisional`
5. `project_discrimination` — discriminate among options (prefer provisional dims; avoid hammering established `work_mode`)
6. `profile_validation` — reflect summary back for confirmation

`select_next` picks the candidate with the best (priority index, then `key`). Seeded intents and fallback templates live in `assessment.question_intents` (including `elicitation` and `location_constraint`).

### How candidates are built

| Source | Candidate |
|---|---|
| Open contradiction rows | `contradiction` + dimension key; fallback names concrete sides when known |
| Required + `unknown` | `required_hard_variable` |
| Location not established | `required_hard_variable` + key `constraints:geo` |
| `topics` / `work_mode` + `unknown` | `project_critical_unknown` |
| Any `provisional` | `provisional_dimension` |
| ≥2 established dims | `project_discrimination` (provisional key if any; else `work_mode` at most twice) |
| Always | `profile_validation` / `profile` |

Contradiction fallbacks are parameterized in code, e.g.:

> For work mode, do you lean more toward small group or independent — or both in different situations?

The generic DB string *“I heard two different preferences…”* is a last resort and is blocked by the quality gate when sides are known.

---

## Stages

Stage enum:

`discovery` → `measurement` → `gap_resolution` → `profile_review` → `project_matching` → `complete`

### Inputs

| Input | Definition |
|---|---|
| `coverage_established` | (# required dims with status `established`) / (# required) |
| `coverage_touched` | (# required dims with status ≠ `unknown`) / (# required) |
| `contradictions` | Count of **open** contradictions |
| `reviewed` | Latch: `core.sessions.profile_reviewed`, or already in matching/complete |
| `projects_ready` | Latch: already `complete` / `matching_completed` (matching does not auto-complete) |
| `location_ready` | At least one accepted geo constraint value (region or place) |

With four required dimensions: `0.5` established ⇒ ≥2 established; `0.9` ⇒ essentially all four established.

### Derivation (`derive_stage`)

```text
if projects_ready and reviewed     → complete
if reviewed and not location_ready → profile_review   (hold matching)
if reviewed and location_ready     → project_matching
if coverage_established ≥ 0.9
   and contradictions == 0         → profile_review
if contradictions > 0
   and coverage_established ≥ 0.5  → gap_resolution
if coverage_touched ≥ 0.4          → measurement
else                               → discovery
```

Constants: `GAP_RESOLUTION_ESTABLISHED = 0.5`, `PROFILE_REVIEW_ESTABLISHED = 0.9`, `MEASUREMENT_TOUCHED = 0.4`.

**Why this matters:** contested/touched coverage no longer counts as “fully known.” Early multi-value evidence stays in discovery/measurement instead of jumping straight into a gap-resolution loop. Reviewed sessions without geography stay in `profile_review` until location is established.

Even outside `gap_resolution`, open true contradictions remain the highest *question* priority — but writer tone and clarification caps keep early chat from becoming pure adjudication.

---

## Location readiness

Project matching requires established geography on `constraints` via value keys such as
`seattle_metro`, `bay_area`, `austin_metro`, `nyc_metro`, `remote_ok`, or place keys
(`seattle`, `austin`, …). See [student-model.md](student-model.md).

Missing location surfaces as `required_hard_variable` with key `constraints:geo`.
Event: `location_readiness_checked` (`location_ready` / `location_missing`).

---

## Thin-answer elicitation

When an assessment contribution is thin (`idk`, very short token count, and/or zero accepted evidence),
policy may override the next target to `elicitation` with 2–3 concrete options (max **2**
attempts per target). Exhaustion soft-skips to the next priority **without** writing oppose evidence for “idk”.

Events: `answer_thinness_evaluated` → `elicitation_selected` or `elicitation_exhausted`.  
Quality gate reason `elicitation_missing_options` forces the seeded option template.

---

## Student questions

`turn_intent` classifies `student_question` / `mixed` / `assessment_contribution` (LLM + heuristic).
Heuristic **out-of-scope** (homework / general tutoring) always wins over a soft LLM miss.

| Topic | Behavior |
|---|---|
| `process` / `profile` / `project` | Answer briefly (citations must be real); resume with one assessment question |
| `out_of_scope` | Refuse; still ask the next assessment question |
| Cap | ≥2 consecutive student questions → short redirect |

Pure student questions skip evidence extraction (`evidence_extraction_skipped`).  
Events: `student_answer_written` / `student_answer_refused`.

---

## Memory compaction

Wired at the end of a successful turn (`MemoryCompactor`):

| Trigger | Default |
|---|---|
| Student responses since last snapshot | ≥ **8** (`MEMORY_RESPONSE_INTERVAL`) |
| Uncompacted token estimate | ≥ **6000** (`MEMORY_TOKEN_THRESHOLD`) |

Rules:

1. Always regenerate from **raw** messages with `sequence ≤ boundary_sequence`.
2. Never feed a prior summary into the compactor or the extractor/reducer.
3. Failure is non-fatal — keep the previous snapshot and recent raw window.
4. Writer context = recent messages (about **8**) **plus** latest memory snapshot fields.
5. Snapshots are unique per `(session_id, boundary_sequence)` (idempotent retries do not duplicate).

---

## Question quality gate

After the writer (or seeded fallback), `question_quality.apply_question_quality_gate` may rewrite the text:

| Outcome | Typical reason |
|---|---|
| `passed` | OK |
| `seeded_override` | Generic contradiction wording, near-duplicate (≥0.92 overlap), leaked template, or elicitation missing options |
| `regenerated` | Stacked questions trimmed to the first `?` (not applied to elicitation) |

Overrides emit `question_quality_gate` on the decision trace.

---

## Project matching (when stage allows)

On `project_matching` with `location_ready`:

1. Deterministic `opportunity_matcher` ranks curated `matching.opportunities` (geo is a hard fail unless `remote_ok`).
2. Bounded web research (Responses API `web_search`) stores URL findings; failure is non-fatal (`web_search_unconfigured` / `research_failed`).
3. `project_composer` drafts 1–3 offers; `project_citation_gate` rejects anything without valid opportunity/finding IDs.
4. Admin `project-fit` shows fits, generated projects + citations, and research URLs.

See [scoring-rules.md](scoring-rules.md).

---

## Reading a decision trace

`GET /v1/admin/sessions/{session_id}/decision-trace`

| Reason pattern | Meaning |
|---|---|
| `intent_*` | Turn intent classification |
| `topic_*` / `out_of_scope_*` / `consecutive_question_cap` | Student answer / refuse |
| `skipped_no_assessment_content` | No evidence extract on pure Q |
| `thin` / `substantive` | Thin-answer evaluation |
| `thin_answer_elicitation` / `elicitation_cap_reached` | Elicitation path |
| `location_ready` / `location_missing` | Geo gate |
| `priority_*` | Why this question target won |
| `stage_*` | Derived stage |
| `grounding_checks_applied` | Accept/reject counts (+ rejection reason histogram) |
| `explicit_newest` / `dismissed_not_conflict` / `unresolved_after_clarification` | Contradiction close |
| `structured_writer_succeeded` / `writer_failure` | Azure wording vs seeded fallback |
| Gate reasons | Quality override |
| `deterministic_opportunity_rank` / `findings_persisted` / `projects_persisted` | Matching |
| `turn_committed` | Persist succeeded |

Successful Azure extract/write events should carry a non-null `llm_run_id` into `audit.llm_runs` (metadata only — no student text).
