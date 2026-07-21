# Scratly documentation

Scratly runs an **explainable assessment conversation**: a teen student answers questions; the system builds a structured preference profile; teachers can see *why* every claim, stage, and next question happened.

## How to read these docs

| Doc | What it explains |
|---|---|
| [architecture.md](architecture.md) | Hard rules, system topology, sole turn write path, decision tracing |
| [student-model.md](student-model.md) | Eight dimensions, coverage statuses, evidence fields, cardinality modes |
| [scoring-rules.md](scoring-rules.md) | Profile reducer, contradiction engine v2, resolution, project fit |
| [conversation-policy.md](conversation-policy.md) | Question priority, stage derivation, memory compaction, reading traces |
| [conversation-quality.md](conversation-quality.md) | Tone, good/bad questions, stage experience (product quality bar) |
| [local-development.md](local-development.md) | Run Compose/host API, Azure Entra, tests, sim harness, troubleshooting |
| [conversation-quality-fix-plan.md](conversation-quality-fix-plan.md) | Historical design record of the quality fixes (implemented) |

## Mental model (one paragraph)

Azure OpenAI may **propose** grounded evidence and **phrase** a question. Deterministic application code **validates** quotes, **reduces** the profile, **opens/closes** only true contradictions, **chooses** the next question target and stage, **gates** question quality, and writes an **append-only** decision trace. Raw messages are the source of truth; memory snapshots are disposable aids for the writer only.

## Typical student journey

```text
discovery  →  measurement  →  (gap_resolution if true conflicts)  →  profile_review  →  project_matching  →  complete
```

1. Student text arrives on `POST /v1/sessions/{id}/turns`.
2. Extractor proposes evidence; grounding accepts or rejects with a reason.
3. Reducer updates coverage; contradiction engine v2 opens only real conflicts.
4. Policy selects one question target; writer personalizes it (or seeded fallback).
5. Quality gate blocks generic/duplicate questions.
6. Stage advances from **established** coverage (not merely “touched”).
7. Teachers inspect transcript, evidence, contradictions, and decision-trace in the web console.

## Key code entry points

| Concern | Path |
|---|---|
| Sole turn orchestration | `apps/api/app/services/turn_processor.py` |
| Evidence grounding | `apps/api/app/services/grounding_validator.py` |
| Profile reduction | `apps/api/app/services/profile_reducer.py` |
| Contradictions | `apps/api/app/services/contradiction_engine.py` |
| Question/stage policy | `apps/api/app/services/question_policy.py` |
| Question quality gate | `apps/api/app/services/question_quality.py` |
| Persistence / candidates | `apps/api/app/repository/assessment.py` |
| Live sim harness | `scripts/sim_assessment_conversation.py` |
