# Conversation policy (V1)

The goal is minimum sufficient behavioral evidence, not a personality inventory. Priority is: repair a conversational rupture; resolve contradictions; establish a concrete behavioral anchor; gather required hard variables (including broad location); resolve project-critical unknowns; strengthen only decision-changing provisional dimensions; discriminate projects; validate the profile. Within a priority, the deterministic policy favors an unasked, continuous, high-information probe. Application state advances through discovery, measurement, gap-resolution, profile-review, project-matching, and complete. The model only personalizes the selected seeded intent; failures use its fallback template.

Every student-facing turn acknowledges or repairs before it probes, stays literal to volunteered facts, and asks one question. Recent concrete behavior is preferred to trait labels, hypotheticals, or forced-choice menus. Corrections must discard the rejected premise. Internal state and policy are never narrated to the student. Location means city/region and country at most—never an address—and is requested with a plain explanation that it keeps opportunities realistic.

Internally the orchestration is a non-rigid six-phase loop: broad discovery, behavioral evidence, preference discrimination, uncertainty/contradiction resolution, project-fit probing, and reflective validation. Curated intents define purpose, target signals, prerequisites, allowed format, avoidance rules, and whether a behavioral follow-up is required. The LLM personalizes only the selected intent.

Candidate value is a deterministic V1 proxy: 30% project discrimination, 25% uncertainty reduction, 15% evidence weakness, 15% contradiction resolution, 10% conversational relevance, and 5% novelty, minus repetition, leading, sensitivity, and fatigue penalties. Repair and open contradictions take precedence. All other questions compete on value to the project decision—not on questionnaire order. The system stops when required constraints are known, contradictions that could change the decision are resolved, and one project mode reaches the configured confidence threshold.

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

### Thin answers

`idk` first receives a smaller open rephrase on the same subject. Only a repeated explicit
insufficient answer may switch to optional elicitation choices; ordinary short answers never
trigger a forced-choice menu. A third failed attempt advances rather than badgering.
Social openers (`hello`, name intros) before any assistant question are **never** thin.

### Next-question decisions

Candidates are scored from uncertainty, evidence weakness, project discrimination,
continuity with the latest accepted evidence, novelty, and prior asks. The selected score and
its factors are stored with the question rationale and decision trace. Contradiction repair
still takes precedence, but questionnaire order alone does not decide ordinary turns.

---

## Stages

`discovery` → `measurement` → `gap_resolution` → `profile_review` → `project_matching` → `complete`

Coverage uses required dims (`topics`, `work_mode`, `motivation`, `constraints`, `execution`).
`supported` counts toward established coverage; `contradicted` counts as touched only.

`project_matching` requires profile review latch + `location_ready` (geo on constraints).

---

## Student questions

Process / profile / project → brief answer, then one assessment question.
Framing pushback (“I just play — why a gaming project?”) gets a plain acknowledgment,
then returns to interest depth — not the same work-mode ask.
Out-of-scope / homework → refuse, still advance assessment.
Pure student questions skip evidence extraction.
