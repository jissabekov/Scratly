# Scoring rules

Deterministic rules for profile reduction, contradictions, and project fit. Models never average conflicts or invent coverage.

Related: [student-model.md](student-model.md) · [conversation-policy.md](conversation-policy.md) · [docs index](README.md)

---

## Profile reducer (v1)

Input: **accepted** evidence only (rejected proposals never affect the profile).

For each dimension:

1. Score each `value_key` as `±strength` by polarity (`support` adds, `oppose` subtracts).
2. Pick the value with the maximum score.
3. Confidence = that score clamped to `[0, 1]`.
4. Status = `established` if confidence **≥ 0.70**, else `provisional`.

Rows without a `value_key` are skipped for scoring. Empty score maps yield `provisional` with `value = null`.

The reducer **does not** set `contested`. That status is applied by contradiction sync when engine v2 opens a true conflict.

---

## Contradiction engine (v2)

Code: `apps/api/app/services/contradiction_engine.py` (`ENGINE_VERSION = "v2"`).

### What is *not* a conflict

Compatible multi-valued signals coexist. Examples that must **not** open a contradiction:

- motivation: `curiosity` + `impact`
- topics: `neighborhood_data` + `science_projects`
- capability: `python_basics` + `spreadsheets` + oppose(`full_web_app`)
- collaboration nuance: small group for brainstorming, solo for coding

### When a conflict opens

A dimension is contested when any of these holds:

| Reason code | Condition |
|---|---|
| `support_oppose_same_value` | Same `value_key` has both support and oppose |
| `preference_negation` | Support X and oppose Y where they are rivals **or** the dim is `single_choice` |
| `declared_incompatible_pair` | Two supported values appear in the sparse incompatibility table |
| `single_choice_competing_supports` | `single_choice` dim has ≥2 distinct support values |

### Incompatibility table (sparse)

Default is compatible. Only these pairs are true rivals today:

| Dimension | Pair |
|---|---|
| `work_mode` | `large_group` ↔ `solo_only` |
| `collaboration` | `large_group_only` ↔ `solo_only` |
| `challenge` | `avoid_hard` ↔ `seek_hard` |

Cardinality defaults: `challenge` is `single_choice`; most others are `multi_value` or `structured` (see [student-model.md](student-model.md)).

### Resolution (never average)

Open contradictions close by later append-only updates (never edits of history):

| Resolution | Status | When |
|---|---|---|
| `explicit_newest` | `resolved` | Clarifying turn supplies accepted evidence that picks a side (newest wins) |
| `dismissed_not_conflict` | `resolved` | Re-evaluation shows the open was not a true conflict under v2 |
| `unresolved_after_clarification` | `dismissed` | ≥ **2** clarification attempts with no usable evidence |

Resolve triggers on a turn when:

1. the previous assistant question targeted this contradiction, **or**
2. the dimension was already open and this turn added accepted evidence, **or**
3. this turn is an explicit preference (support one value and oppose another).

After resolve/dismiss, coverage is restored from the latest profile snapshot (contested → provisional/established).

### Reopen rules

After `explicit_newest`, `unresolved_after_clarification`, or `compatible_merge`, the same dimension reopens only if **new** evidence after the resolution cutoff:

- opposes the winning value, **or**
- supports an incompatible rival, **or**
- adds a competing support on a `single_choice` dimension.

Mere restatements of the winning side do not reopen the fight.

Decision event: `contradiction_resolved` with the resolution as `reason_code`, plus entity refs to contradiction and evidence IDs.

---

## Project fit

### Curated opportunities (primary path)

When the session reaches `project_matching` with location established, `opportunity_matcher.py` ranks
seeded `matching.opportunities`:

```text
score = 0.40 × topic_overlap + 0.40 × work_mode_overlap + 0.20 × motivation_overlap
```

- **Geo** is a hard eligibility gate: student `geo_regions` / `geo_places` must intersect the
  opportunity’s regions/places, **or** the opportunity (or student) allows `remote_ok`.
- Other **hard_constraints** on the opportunity are independent pass/fail gates.
- **Capability gaps** do not block eligibility; they produce scope/scaffold suggestions
  (e.g. `scaffold:code`).
- Results persist in `matching.project_fits` with `opportunity_id` and `algorithm_version`.

Bounded web research may add URL-grounded rows in `matching.research_findings`.
`project_composer` may then draft 1–3 student-facing offers; each must cite at least one
existing opportunity ID and/or research finding ID or it is rejected (`project_citation_rejected`).

Admin `project-fit` shows opportunity ranks, generated projects + citations, research URLs,
or the catalog when no fits have been computed yet.

### Legacy archetypes

`project_matcher.py` still scores older `matching.project_archetypes` with the same 40/40/20
weights for unit tests and backward compatibility. Live matching prefers opportunities.
