# Student model

The assessment profile is a structured view of a student’s preferences and constraints across eight dimensions. Numeric internals (confidence scores) are teacher-facing; the writer and student see labels and statuses only.

Related: [scoring-rules.md](scoring-rules.md) · [conversation-policy.md](conversation-policy.md) · [docs index](README.md)

---

## Dimensions

Seeded in `assessment.dimensions` (ordinal order):

| Key | Label | Required | Cardinality mode | Role |
|---|---|---|---|---|
| `topics` | Topic interests | yes | `multi_value` | What to work on |
| `work_mode` | Work mode | yes | `structured` | Solo / small group / process style |
| `motivation` | Motivation | yes | `multi_value` | Why the work matters |
| `capability` | Capabilities | no | `multi_value` | Skills and gaps (scaffolding, not eligibility) |
| `constraints` | Constraints | yes | `multi_value` | Non-negotiable limits (time, tools, group size, …) |
| `collaboration` | Collaboration | no | `structured` | Who to work with, in which situations |
| `challenge` | Challenge appetite | no | `single_choice` | Seek hard vs avoid hard (true rivals possible) |
| `impact` | Desired impact | no | `multi_value` | What “useful” looks like |

**Required dimensions (4):** `topics`, `work_mode`, `motivation`, `constraints`.  
Coverage math uses this denominator — see [conversation-policy.md](conversation-policy.md).

Location for project matching is expressed as **constraint value keys** (not a separate dimension): geo regions such as `seattle_metro` / `bay_area` / `remote_ok`, and places such as `seattle` / `austin`. Matching will not enter `project_matching` until at least one geo value is established.

### Cardinality modes

| Mode | Meaning |
|---|---|
| `multi_value` | Several support values coexist (e.g. curiosity + impact). Not a conflict. |
| `structured` | Faceted / situational values coexist (e.g. brainstorming in a small group, coding alone). |
| `single_choice` | Competing supports may be a true conflict when the student must pick one primary answer. |

Full conflict rules: [scoring-rules.md](scoring-rules.md).

### Motivation vocabulary

Allowed motivation `value_key`s come from `assessment.motivation_values`:

`mastery` · `impact` · `autonomy` · `recognition` · `belonging` · `curiosity`

Unknown motivation keys are rejected with `taxonomy_value_not_allowed`. Other dimensions map free text to closest keys via the extractor prompt (omit if nothing fits).

---

## Coverage status

Each `(session, dimension)` row in `assessment.coverage` has one status:

| Status | Meaning |
|---|---|
| `unknown` | No accepted evidence yet |
| `provisional` | Accepted evidence, confidence **&lt; 0.70** |
| `established` | Accepted evidence, confidence **≥ 0.70** |
| `contested` | A **true** open contradiction exists for this dimension (engine v2) |

The reducer only emits `provisional` / `established`. Contested is applied by contradiction sync after reduce. When a contradiction resolves or is dismissed, coverage is restored from the latest profile snapshot.

---

## Evidence

Every claim about the student is an evidence row. Proposals must include:

| Field | Rule |
|---|---|
| `dimension_key` | Must exist in taxonomy |
| `value_key` | Optional but preferred; motivation must be in vocabulary |
| `polarity` | `support` or `oppose` |
| `strength` | 0–1 (clamped) |
| `source_message_ids` | Must be owned by this session |
| `exact_source_quote` | Verbatim substring of an owned message |
| `rationale` | Model explanation (not stored as profile truth) |

Lifecycle status: `proposed` → `accepted` | `rejected` (with reason) · later `superseded` if needed.

### Grounding rejection reasons

| Reason | When |
|---|---|
| `source_message_unavailable_or_not_owned` | Message ID not in session |
| `exact_quote_not_found` | Quote not a substring of owned content |
| `empty_quote` | Blank quote |
| `excess_proposals_trimmed` | Beyond 5 proposals in one turn |
| `taxonomy_value_not_allowed` | Illegal motivation key |
| `unknown_dimension_key` | Dimension not in taxonomy |

Capabilities change **scope and scaffolding**, not hard eligibility for projects.

---

## Profile snapshots

Each successful reduce writes:

- `assessment.profile_snapshots` — versioned state + `reducer_version`
- `assessment.profile_changes` — why the transition happened

Teachers browse these via admin `profile` / `profile-history`. Students never see raw confidence numbers in the writer context — only public labels/statuses/values.
