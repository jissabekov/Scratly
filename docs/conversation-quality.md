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
6. **Exit stages deliberately** — reach `profile_review` / `project_matching` when coverage is real and conflicts are resolved or dismissed with reason.

---

## Stage experience

| Stage | Student experience | System behavior |
|---|---|---|
| `discovery` | Warm, concrete, one topic at a time | Prefer required unknowns / project-critical; only true incompatibilities as contradictions |
| `measurement` | Deepen provisional dims with examples | Provisional + discrimination targets |
| `gap_resolution` | Explicit choices; allow “both, differently” | Resolve or dismiss; max **2** clarifications per contradiction |
| `profile_review` | Reflect a short accurate summary | Validation intent; corrections become new evidence |
| `project_matching` | Compare fits with tradeoffs | Discrimination + constraints gates |
| `complete` | Session finished | Explicit completion latch |

---

## Good questions

- Name the conflict or gap: “For work mode, lean small group or independent — or both in different situations?”
- One question only; teen-appropriate; specific.
- Lightly acknowledge the last answer, then advance.
- For discovery: open but concrete (“What’s a recent project you enjoyed and why?”).

Writer prompt version: `apps/api/prompts/question_writer/v2/`.

---

## Banned patterns

Enforced by prompts **and** the application quality gate where possible:

- Asking a contradiction when values are compatible facets
- Generic “I heard two different preferences”
- Ignoring the student’s last answer
- Repeating the previous assistant question verbatim
- Jumping to projects before required dims are established and conflicts cleared
- Multiple questions in one assistant message

---

## Evidence extraction quality

Extractor prompt version: `apps/api/prompts/evidence_extractor/v2/`.

- Prefer **1–3** high-confidence items unless the student stated many distinct facts.
- Cap at **5** proposals per turn (`excess_proposals_trimmed`).
- Multi-value supports without implying conflict.
- `oppose` only when the student explicitly negates something.
- Map to taxonomy keys; omit inventing keys.

---

## Live verification

Use the harness:

```bash
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --conflict-probe --out sim-final-proof.json
```

Asserts (among others): no turn-1 `gap_resolution` from false multi-value opens, no generic contradiction fallback leak, linked `llm_run_id` when Azure is live, memory snapshot after ≥8 responses, contradictions resolve instead of stalling.
