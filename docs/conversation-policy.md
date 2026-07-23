# Conversation policy (V2: planner-controlled interview)

## Control boundary

The system has two separate responsibilities and only one owns subject selection:

`answer → evidence extractor → student/coverage/evidence maps → deterministic planner → question writer`

The planner emits `{action, target, reason, avoid_topics, phase}`. Its actions are
`FOLLOW_UP`, `SWITCH`, `BRIDGE`, `CLARIFY`, `VERIFY`, and `GATE`. The writer decides only
how to express that intention naturally. It must not replace the target, add another probe,
or remain on the prior subject for continuity. The decision and its factors are traced.

## Five phases

1. **Conversation contract** (1–2 turns): explain the project-matching purpose, say the
   conversation will bounce around, and do not request account data already known.
2. **Breadth scan** (about 10–15 questions): touch interests, social context, natural
   competence, friction, school/work behavior, online attention, outside activities, and
   local exposure. Ask one or two questions per area; breadth outranks continuity.
3. **Selective verification** (about 4–7 questions): test only useful tentative patterns
   in an unrelated context, or use a balanced project tradeoff. A behavior is tentative;
   corroboration across contexts makes it supported; repeated behavior plus an explicit
   preference can make it strong. Never infer a personality verdict from one behavior.
4. **Hard feasibility**: directly collect time, tools, transportation, privacy, outreach,
   visibility, skills, people/organization access, and location/community access.
5. **Reflection**: summarize supported evidence, clearly label tentative and unknown areas,
   and ask the student what is wrong before matching projects.

## Coverage and evidence maps

Coverage tracks interests; investigate/build/organize/communicate; rewards; persistence;
ambiguity; outreach; visibility; social/community context; capabilities; local exposure;
assets/access; and constraints. Each is `unknown`, `provisional`, `supported`, or
`contradicted`. **Unknown is never low or zero.** Evidence stores its concrete behavior,
context, source, count, and status rather than a personality probability. Cross-context
evidence is required to promote a behavioral pattern.

## Hard saturation and friction rules

`DEFAULT_MAX_TOPIC_DEPTH = 2`; `ABSOLUTE_MAX_TOPIC_DEPTH = 3`. A branch normally receives
one discovery question and one behavioral follow-up. A third question is allowed only for
important clarification. A fourth is invalid until breadth is complete. High saturation
plus a major uncovered area makes `FOLLOW_UP` invalid.

`no`, `not really`, and `I don't know` collapse branch utility and cause a switch unless the
field is an essential feasibility gate. Do not rephrase the same failed probe. An explicit
topic-change request blocks the current topic, adds friction, and prevents return unless the
student reopens it. Frustration or “why are you asking?” produces a transparent explanation,
reassurance that one answer decides nothing, a lighter breadth question, and a switch.

Candidate value is conceptually:

`gap × project importance × discrimination × evidence quality − redundancy − fatigue − friction − sensitivity`.

Repair and decision-changing contradictions may override ordinary scoring. In all other
cases the largest important coverage gap wins; continuity is only a small writing concern.

Machine rules for **what to ask next** and **which stage** the session is in.
The model personalizes the selected intent; it does not choose priority or stage.

Product tone: [conversation-quality.md](conversation-quality.md).  
Student model: [student-model.md](student-model.md).  
Scoring: [scoring-rules.md](scoring-rules.md).

---

## Question priority

Fixed order (`question_policy.PRIORITY`):

1. `contradiction`
2. `required_hard_variable`
3. `project_critical_unknown`
4. `provisional_dimension`
5. `project_discrimination`
6. `profile_validation`

Same-priority tie-break uses **anchor order** (`ANCHOR_KEY_ORDER`):

`topics` → `work_mode` → `motivation` → `execution` (+ facet keys) → `constraints` → `constraints:geo` → `capability` → `assets`

### Interest-depth gate

Until interest depth is ready, **do not emit** other required dims (`work_mode`,
`motivation`, `execution`, `constraints`, geo). A casual first mention stays
`provisional` / shallow and must be deepened first.

Depth is ready when `topics` is `supported`/`contradicted`, or the top interest
has score ≥ 2 with ≥ 2 evidence rows (a single mention never unlocks work-mode).

### Conversation path and seven assessment anchors

1. Human introduction: ask the student's name, then city/region and country (greetings are
   **not** thin; no chips; these social turns are not assessment dimensions)
2. Warm interests open, followed by concrete curiosity about the detail they volunteered
3. Interest depth (behavioral 0–4) — **before** work-mode
4. Contextual work-mode in the student’s activity language (not “project” by default)
5. Behavioral proof for strong self-claims
6. Motivation primary + secondary tradeoff
7. Persistence + ambiguity
8. Hard outreach / visibility / geo must-haves

After anchors: ask the unknown that **changes leading project options**.

### Thin answers and elicitation

1. **First thin** on a recoverable dimension → smaller rephrase; trace `elicitation_rephrase`; persist counter on `core.sessions`.
2. **Second thin** (same dimension family, counter not reset on planner SWITCH) → option chips if `should_offer_options` (`thin`, `insufficient`, or `thin_answer` + `attempts ≥ 2`); trace `elicitation_selected`.
3. **Third+** → `elicitation_exhausted`; soft-skip and advance.
4. Greetings and name intros before any assistant question are **never** thin.
5. Non-recoverable targets (e.g. turn-1 `social_intro`) → `elicitation_skipped_not_recoverable`.

See `elicitation_policy.py`, `thin_answer.py`, and [system-guide.md](system-guide.md) §7.

### Repetition hard-stop

`is_repetition_blocked()` excludes over-asked targets before `select_next`. Penalty `asked_count × 0.35`. Planner forces `follow_up_exhausted` after depth ≥ 3 on same key. Emits `question_target_blocked`.

`profile_validation` candidates appear only when `coverage_established ≥ 0.9` or session is already in review/matching.

### Stage gates

Two paths to `profile_review`:

- **Full inventory:** `coverage_established ≥ 0.9`, no open contradictions
- **Decision-sufficient:** `evaluate_review_eligibility()` — core three supported, execution supported/provisional, capability or assets touched, location ready, established ≥ 0.6

Every turn emits `stage_gate_evaluated` before `stage_derived`.

### Next-question decisions

Candidates are scored from uncertainty, evidence weakness, project discrimination,
continuity with the latest accepted evidence, novelty, and prior asks. The selected score and
its factors are stored with the question rationale and decision trace. Contradiction repair
still takes precedence, but questionnaire order alone does not decide ordinary turns.

---

## Stages

`discovery` → `measurement` → `gap_resolution` → `profile_review` → `project_matching` → `complete`

Coverage uses required dims (`topics`, `work_mode`, `motivation`, `constraints`, `execution`, `capability`, `assets`).
`supported` counts toward established coverage; `contradicted` counts as touched only.

**Review latch:** see `evaluate_review_eligibility` and `stage_gate_evaluated` traces ([system-guide.md](system-guide.md) §3).

`project_matching` requires profile review latch + `location_ready` (geo on constraints). Geo may be established via extractor or `geo_inferred_from_text` fallback.

---

## Student questions

Process / profile / project → brief answer, then one assessment question.
Framing pushback (“I just play — why a gaming project?”) gets a plain acknowledgment,
then returns to interest depth — not the same work-mode ask.
Out-of-scope / homework → refuse, still advance assessment.
Pure student questions skip evidence extraction.
