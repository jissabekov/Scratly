# Scratly documentation

Scratly runs an **explainable assessment conversation**: a teen student answers questions; the system builds a structured preference profile; teachers can see *why* every claim, stage, and next question happened.

## Start here

| Doc | What it explains |
|---|---|
| **[system-guide.md](system-guide.md)** | **End-to-end current system** — turn pipeline, policy, stages, elicitation, geo, matching, eval |
| [architecture.md](architecture.md) | Hard rules, topology, sole write path, schemas, tracing |
| [conversation-policy.md](conversation-policy.md) | Planner, anchors, repetition, stages, elicitation |
| [student-model.md](student-model.md) | V1 profile dimensions and evidence semantics |
| [scoring-rules.md](scoring-rules.md) | Reducer v2, contradictions, matching weights |
| [eval-suite.md](eval-suite.md) | 18-persona live regressor, assertions, proof workflow |
| [eval-findings-and-fix-plan.md](eval-findings-and-fix-plan.md) | 2026-07-23 eval findings, fix plan, proof status |
| [conversation-quality.md](conversation-quality.md) | Tone and UX quality bar |
| [local-development.md](local-development.md) | Compose, Azure Entra, tests, troubleshooting |

## Mental model (one paragraph)

Azure OpenAI may **propose** grounded evidence, **classify** turn intent, **phrase** questions or in-scope student answers, and **compose** citation-linked project offers. Deterministic application code **validates** quotes and citations, **reduces** the profile, **opens/closes** only true contradictions, **chooses** the next question target and stage (including thin-answer elicitation and location gates), **gates** question quality, ranks **curated opportunities**, and writes an **append-only** decision trace. Raw messages are the source of truth; memory snapshots and research findings are disposable aids — never profile truth.

## Typical student journey

```text
discovery  →  measurement  →  (gap_resolution if true conflicts)
  →  profile_review  →  project_matching (needs location)  →  complete
```

1. Student text arrives on `POST /v1/sessions/{id}/turns`.
2. Intent classifier + heuristic safety: process/profile/project questions are answered (or homework refused); then assessment resumes.
3. Extractor proposes evidence (skipped for pure student questions); grounding accepts or rejects with a reason.
4. Reducer updates coverage; contradiction engine v2 opens only real conflicts.
5. Thin answers may trigger option-style elicitation instead of inventing negative evidence.
6. Policy selects one question target; writer personalizes it (or seeded fallback); quality gate applies.
7. Stage advances from **supported** coverage; `project_matching` also requires reviewed + location.
8. Matching ranks curated opportunities, optionally runs bounded web research, and persists only citation-grounded projects.
9. Students chat at `/`; teachers inspect transcript, evidence, contradictions, project-fit, and decision-trace at `/teacher`.

## Key code entry points

| Concern | Path |
|---|---|
| Sole turn orchestration | `apps/api/app/services/turn_processor.py` |
| Turn intent / student answers | `turn_intent_classifier.py`, `student_answerer.py` |
| Thin-answer elicitation | `thin_answer.py`, `elicitation_policy.py` |
| Location readiness | `location_policy.py` |
| Evidence grounding | `apps/api/app/services/grounding_validator.py` |
| Profile reduction | `apps/api/app/services/profile_reducer.py` |
| Contradictions | `apps/api/app/services/contradiction_engine.py` |
| Question/stage policy | `apps/api/app/services/question_policy.py` |
| Question quality gate | `apps/api/app/services/question_quality.py` |
| Opportunity match / research / compose | `opportunity_matcher.py`, `web_research_client.py`, `project_composer.py`, `project_citation_gate.py` |
| Persistence / candidates | `apps/api/app/repository/assessment.py` |
| Live sim harness | `scripts/sim_assessment_conversation.py` |
| **Live eval regressor (18 personas)** | `scripts/eval_conversation_suite.py` · [eval-suite.md](eval-suite.md) |
