# Scoring rules (V1)

Deterministic rules for profile reduction, contradictions, and project fit.
Models never average conflicts or invent coverage from silence.

Related: [student-model.md](student-model.md) · [conversation-policy.md](conversation-policy.md)

---

## Profile reducer (v2)

Input: **accepted** evidence only.

### Interests (`topics`)

- Group by `value_key` (topic).
- Prefer `score_band` (0–4); else derive from `strength` via `round(strength * 4)`.
- `evidence_count` = accepted supports; `examples` = short quotes.
- Status: `supported` with repeated strong evidence; else `provisional`.
- Never invent a topic that was never mentioned.

### Work modes / execution facets

- Facets start as `null` / `unknown` (UNKNOWN ≠ 0).
- Update only facets with accepted evidence.
- Oppose on a facet can push toward 0 when explicit avoidance is evidenced.

### Motivation

- Rank reward keys by support strength.
- Top → `primary`, second → `secondary` (five-reward vocabulary only).

### Capabilities

- Level 0–3 from `score_band` (clamped) or derived strength.
- Oppose → capability gap for scaffolding only.

### Assets

- Freeform list; no numeric score.

### Compatibility dimensions view

Reducer also emits a flat `dimensions[]` view for coverage sync (`supported` / `provisional` / `unknown`).
`contradicted` is applied by contradiction sync, not the reducer.

---

## Contradiction engine (v2)

True conflicts only:

- Same `value_key` with both support and oppose
- Declared incompatible pairs (sparse; V1 has no collab/challenge rivals)

Compatible multi-value supports coexist (multiple interests, multiple assets).

---

## Project / opportunity fit

```text
score = 0.40 × topic_overlap
      + 0.40 × work_mode_alignment
      + 0.20 × motivation_alignment
```

**Execution gates (PASS/FAIL):** if opportunity `hard_constraints` requires
`outreach_willingness >= 3` (etc.) and the student score is known and lower → fail.
If the facet is `null` / unknown → **do not fail**.

**Geo:** still a hard filter via constraint geo keys / `remote_ok`.

**Capabilities:** produce `scaffold:…` adjustments only — never eligibility failure.
