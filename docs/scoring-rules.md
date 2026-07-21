# Scoring rules

The reducer consumes accepted evidence only. At confidence **0.70** a dimension becomes `established`; below that it remains `provisional`.

## Contradiction engine v2

Conflicts remain explicit and are never averaged. A dimension is contested only when:

1. the same `value_key` has both **support** and **oppose**, or
2. the dimension is `single_choice` with ≥2 competing supports, or
3. a pair is listed in the sparse incompatibility table, or
4. the student explicitly prefers X and negates rival Y (`preference_negation`).

`multi_value` / `structured` dimensions (topics, motivation, capability, constraints, collaboration, work_mode) allow coexisting supports.

## Resolution

Open contradictions resolve by **newer explicit evidence** from a clarification turn (`explicit_newest`), by engine re-evaluation that proves the open was not a true conflict (`dismissed_not_conflict`), or by dismissal after repeated failed clarifications (`unresolved_after_clarification`). Strengths are never averaged.

## Project fit

Project fit is `0.40 × topic + 0.40 × work mode + 0.20 × motivation`. Hard constraints are independent pass/fail gates. Capability gaps produce scope and scaffold suggestions.
