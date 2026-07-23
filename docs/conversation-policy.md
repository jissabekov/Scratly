# Conversation policy (V1)

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

### Seven anchors

1. Warm interests open (greetings are **not** thin; no chips on turn 1)
2. Interest depth (behavioral 0–4)
3. Contextual work-mode A/B/C/D in the student’s domain
4. Behavioral proof for strong self-claims
5. Motivation primary + secondary tradeoff
6. Persistence + ambiguity
7. Hard outreach / visibility / geo must-haves

After anchors: ask the unknown that **changes leading project options**.

### Thin answers

`idk` / ultra-short mid-assessment answers may switch to elicitation chips.
Social openers (`hello`, name intros) before any assistant question are **never** thin.

---

## Stages

`discovery` → `measurement` → `gap_resolution` → `profile_review` → `project_matching` → `complete`

Coverage uses required dims (`topics`, `work_mode`, `motivation`, `constraints`, `execution`).
`supported` counts toward established coverage; `contradicted` counts as touched only.

`project_matching` requires profile review latch + `location_ready` (geo on constraints).

---

## Student questions

Process / profile / project → brief answer, then one assessment question.
Out-of-scope / homework → refuse, still advance assessment.
Pure student questions skip evidence extraction.
