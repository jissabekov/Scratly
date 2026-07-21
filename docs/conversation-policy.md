# Conversation policy

Machine rules for **what to ask next** and **which stage** the session is in. The model only personalizes the selected intent; it does not choose priority or stage.

Product tone and anti-patterns: [conversation-quality.md](conversation-quality.md).  
Conflict math: [scoring-rules.md](scoring-rules.md).  
Index: [README.md](README.md).

---

## Question priority

Fixed order (`question_policy.PRIORITY`):

1. `contradiction` — open true conflict (engine v2)
2. `required_hard_variable` — required dim still `unknown`
3. `project_critical_unknown` — `topics` or `work_mode` still `unknown`
4. `provisional_dimension` — dim is `provisional`
5. `project_discrimination` — discriminate among options (prefer provisional dims; avoid hammering established `work_mode`)
6. `profile_validation` — reflect summary back for confirmation

`select_next` picks the candidate with the best (priority index, then `key`). Seeded intents and fallback templates live in `assessment.question_intents`.

### How candidates are built

| Source | Candidate |
|---|---|
| Open contradiction rows | `contradiction` + dimension key; fallback names concrete sides when known |
| Required + `unknown` | `required_hard_variable` |
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
| `reviewed` | Latch: reached matching/complete, or profile_review after a `profile_validation` ask |
| `projects_ready` | Latch: already `complete` (matching does not auto-complete) |

With four required dimensions: `0.5` established ⇒ ≥2 established; `0.9` ⇒ essentially all four established.

### Derivation (`derive_stage`)

```text
if projects_ready and reviewed     → complete
if reviewed                        → project_matching
if coverage_established ≥ 0.9
   and contradictions == 0         → profile_review
if contradictions > 0
   and coverage_established ≥ 0.5  → gap_resolution
if coverage_touched ≥ 0.4          → measurement
else                               → discovery
```

Constants: `GAP_RESOLUTION_ESTABLISHED = 0.5`, `PROFILE_REVIEW_ESTABLISHED = 0.9`, `MEASUREMENT_TOUCHED = 0.4`.

**Why this matters:** contested/touched coverage no longer counts as “fully known.” Early multi-value evidence stays in discovery/measurement instead of jumping straight into a gap-resolution loop.

Even outside `gap_resolution`, open true contradictions remain the highest *question* priority — but writer tone and clarification caps keep early chat from becoming pure adjudication.

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
| `seeded_override` | Generic contradiction wording, near-duplicate of previous assistant (≥0.92 token overlap), or leaked template with known sides |
| `regenerated` | Stacked questions trimmed to the first `?` |

Overrides emit `question_quality_gate` on the decision trace.

---

## Reading a decision trace

`GET /v1/admin/sessions/{session_id}/decision-trace`

| Reason pattern | Meaning |
|---|---|
| `priority_*` | Why this question target won |
| `stage_*` | Derived stage |
| `grounding_checks_applied` | Accept/reject counts (+ rejection reason histogram) |
| `explicit_newest` / `dismissed_not_conflict` / `unresolved_after_clarification` | Contradiction close |
| `structured_writer_succeeded` / `writer_failure` | Azure wording vs seeded fallback |
| Gate reasons | Quality override |
| `turn_committed` | Persist succeeded |

Successful Azure extract/write events should carry a non-null `llm_run_id` into `audit.llm_runs` (metadata only — no student text).
