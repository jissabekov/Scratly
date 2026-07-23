# Conversation quality (V1)

Product bar for how the assessment should *feel*. Machine priority and stage math live in [conversation-policy.md](conversation-policy.md). Index: [README.md](README.md).

A teacher reading the transcript should always understand **why** the next question was asked from the decision-trace alone.

---

## Qualitative bar

1. **Discover before adjudicating** — early turns gather interest breadth and depth.
2. **One clear job per turn** — never vague “two preferences.”
3. **Acknowledge and advance** — each answer fills an unknown or strengthens a provisional.
4. **UNKNOWN ≠ 0** — never treat silence as avoidance.
5. **Stay coherent over time** — later questions use profile + recent messages.
6. **Exit stages deliberately** — reach `profile_review` / `project_matching` when coverage is real, location is ready, and conflicts are resolved.
7. **Answer only in-scope student questions** — process / profile / project; refuse homework.
8. **Elicit when answers are thin mid-assessment** — never quiz chips on a greeting.
9. **Ground project offers** — cite curated opportunities / research URLs.

---

## Stage experience

| Stage | Student experience |
|---|---|
| `discovery` | Warm interest open → depth → contextual work-mode |
| `measurement` | Motivation tradeoff, execution behavioral proof |
| `gap_resolution` | Explicit choices only for true conflicts |
| `profile_review` | Reflect V1 profile for confirm |
| `project_matching` | Grounded fits with execution gates |
| `complete` | Session finished |

Writer prompt: `apps/api/prompts/question_writer/v3/`.
