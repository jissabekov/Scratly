# Conversation quality

Product bar for how the assessment should *feel*. Machine priority and stage math live in [conversation-policy.md](conversation-policy.md). Index: [README.md](README.md).

A teacher reading the transcript should always understand **why** the next question was asked from the decision-trace alone.

---

## Qualitative bar

1. **Discover before adjudicating** — early turns gather breadth; contradiction questions only for genuine incompatibilities.
2. **One clear job per turn** — name the conflict or gap; never vague “two preferences.”
3. **Acknowledge and advance** — each student answer fills an unknown, strengthens a provisional, or closes an open contradiction.
4. **Preserve nuance** — “small group for brainstorming, alone for coding” is enrichment, not a fight.
5. **Stay coherent over time** — later questions use profile + memory + recent messages so early context is not forgotten.
6. **Exit stages deliberately** — reach `profile_review` / `project_matching` when coverage is real, location is established, and conflicts are resolved or dismissed with reason.
7. **Answer only in-scope student questions** — process / profile / project; refuse homework; resume assessment on the same turn.
8. **Elicit when answers are thin** — offer concrete “this or this” options instead of writing negative evidence for “idk”.
9. **Ground project offers** — every suggested project cites a curated opportunity and/or a stored research URL; never invent uncited orgs.

---

## Stage experience

| Stage | Student experience | System behavior |
|---|---|---|
| `discovery` | Warm, concrete, one topic at a time | Prefer required unknowns / project-critical / location; only true incompatibilities as contradictions |
| `measurement` | Deepen provisional dims with examples | Provisional + discrimination targets; elicitation on thin answers |
| `gap_resolution` | Explicit choices; allow “both, differently” | Resolve or dismiss; max **2** clarifications per contradiction |
| `profile_review` | Reflect a short accurate summary | Validation intent; corrections become new evidence; hold here until location ready |
| `project_matching` | Compare grounded fits with tradeoffs | Opportunity rank + optional research + citation-gated offers |
| `complete` | Session finished | Explicit completion latch |

---

## Good questions

- Name the conflict or gap: “For work mode, lean small group or independent — or both in different situations?”
- One question only; teen-appropriate; specific.
- Lightly acknowledge the last answer, then advance.
- For discovery: open but concrete (“What’s a recent project you enjoyed and why?”).
- For thin answers: named options (“which is closer: A, B, or C — or something else?”).
- For location: city/region or remote.

Writer prompt version: `apps/api/prompts/question_writer/v2/`.

---

## Banned patterns

Enforced by prompts **and** the application quality gate where possible:

- Asking a contradiction when values are compatible facets
- Generic “I heard two different preferences”
- Ignoring the student’s last answer
- Repeating the previous assistant question verbatim
- Jumping to projects before required dims, conflicts, **and location** are ready
- Multiple stacked assessment questions in one assistant message
- Doing homework / general tutoring mid-assessment
- Inventing project sponsors or URLs without citations

---

## Evidence extraction quality

Extractor prompt version: `apps/api/prompts/evidence_extractor/v2/`.

- Prefer **1–3** high-confidence items unless the student stated many distinct facts.
- Cap at **5** proposals per turn (`excess_proposals_trimmed`).
- Multi-value supports without implying conflict.
- `oppose` only when the student explicitly negates something.
- Map to taxonomy keys; omit inventing keys.
- Map explicit place/region talk to `constraints` geo value keys.

---

## Live verification

Use the harness:

```bash
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --conflict-probe --out sim-final-proof.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 2 --student-questions --out sim-student-q.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --thin-answer-probe --out sim-thin.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --project-matching-probe --out sim-projects.json
```

Asserts (among others): no turn-1 `gap_resolution` from false multi-value opens, no generic contradiction fallback leak, linked `llm_run_id` when Azure is live, memory snapshot after ≥8 responses, contradictions resolve instead of stalling, student homework refused, thin answers elicit options, location readiness events present for matching probes.
