# Scratly architecture

Explainable student discovery and project matching. Models propose; the application owns state and policy.

> **HARD RULE 1 — No direct LLM profile mutation.** Models may propose grounded evidence or phrase an application-selected question. Only the versioned deterministic reducer changes the profile.
>
> **HARD RULE 2 — No derived summary is a source of truth.** Raw messages are authoritative. Memory snapshots are disposable conversation aids regenerated from the complete bounded raw transcript.
>
> **HARD RULE 3 — Complete backward explainability.** Every profile transition has a versioned snapshot, change record, reducer version, and accepted evidence linked to exact quotes in owned raw messages.

Related: [student-model.md](student-model.md) · [scoring-rules.md](scoring-rules.md) · [conversation-policy.md](conversation-policy.md) · [docs index](README.md)

---

## System boundaries

```text
Teacher console (Next.js :3000)
        │  HTTP /v1
        ▼
   FastAPI API (:8000)
        │
        ├── Azure OpenAI (Entra)  — extract, write, compact (optional)
        └── PostgreSQL 16         — sole state store
```

| Layer | Responsibility |
|---|---|
| `apps/web` | Teacher UI: create sessions, submit turns, inspect admin views + decision trace |
| `apps/api` | Sole assessment write path, policy, grounding, reduction, audit |
| `migrations/` | Ordered SQL schemas: `core`, `conversation`, `assessment`, `matching`, `audit` |
| Azure OpenAI | Structured outputs only; never selects stage, priority, or mutates profile |
| Blob / App Insights | Azure topology sketches only; not required for local |

No Cosmos DB, Redis, vectors, agent framework, MCP, or Service Bus.

---

## Sole write path: `process_student_turn`

Ordinary assessment state changes go through one transactional workflow
(`apps/api/app/services/turn_processor.py`). Concurrent retries are guarded by
`UNIQUE(session_id, idempotency_key)` on `conversation.turns`.

| # | Step | Decision event | Notes |
|---|---|---|---|
| 0 | Idempotent replay if turn already completed | — | Returns prior assistant message |
| 1 | Create turn + student message; bind LLM audit context | `turn_started` | Reason `new_idempotency_key` |
| 2 | Note pending contradiction target (last Q was contradiction?) | — | Used for resolve-on-answer |
| 3 | Extractor proposes evidence (prompt **v2**) | `evidence_proposed` | Links `llm_run_id` when Azure succeeds |
| 4 | Ground + persist evidence | `evidence_validated` | Rejection reason counts in outputs |
| 5 | Reduce profile; sync contradictions; write snapshot | `profile_reduced` | Reducer version on snapshot |
| 6 | Close non-conflicts / resolve clarifying answers | `contradiction_resolved` | See [scoring-rules.md](scoring-rules.md) |
| 7 | Recount open contradictions | `contradiction_evaluated` | Engine **v2** |
| 8 | Select next question target | `question_target_selected` | Reason `priority_{kind}` |
| 9 | Derive conversation stage | `stage_derived` | Reason `stage_{stage}` |
| 10 | Write / fallback question (prompt **v2**) | `question_written` or `question_fallback_used` | |
| 11 | Quality gate | `question_quality_gate` | Only if outcome ≠ `passed` |
| 12 | Persist assistant message, stage, complete turn | — | |
| 13 | Maybe compact memory (non-fatal) | — | Never feeds extractor |
| 14 | Commit | `turn_completed` | Reason `turn_committed` |

Public API:

- `POST /v1/sessions` — create student + session (stage `discovery`)
- `GET /v1/sessions/{id}` — resume metadata
- `POST /v1/sessions/{id}/turns` — `{ idempotency_key, text }` → `{ turn_id, assistant_message, stage }`

---

## Component map

| Component | File | May do | Must not do |
|---|---|---|---|
| Evidence extractor | `evidence_extractor.py` | Propose `EvidencePacket` | Mutate profile/stage |
| Grounding validator | `grounding_validator.py` | Accept/reject with reason | Invent quotes |
| Profile reducer | `profile_reducer.py` | Compute dimension states from accepted evidence | Average conflicts |
| Contradiction engine | `contradiction_engine.py` | Detect/resolve true conflicts (v2) | Treat multi-value supports as fights |
| Question policy | `question_policy.py` | Priority + stage derivation | Call the LLM |
| Question quality gate | `question_quality.py` | Override generic/duplicate questions | Change profile |
| Context builder | `context_builder.py` | Bounded extractor/writer/memory contexts | Pass full uncontrolled transcript to writer |
| Memory compactor | `memory_compactor.py` | Summarize raw msgs through boundary | Become evidence source |
| Project matcher | `project_matcher.py` | Score archetypes 40/40/20 | Soften hard constraints |
| Decision trace | `decision_trace.py` | Append privacy-safe events | Store student text |
| Turn processor | `turn_processor.py` | Orchestrate the sole write transaction | Bypass reducer |

Repository orchestration and SQL live in `apps/api/app/repository/assessment.py`.

---

## Data model (schemas)

| Schema | Owns |
|---|---|
| `core` | Students, sessions (`stage` enum) |
| `conversation` | Idempotent turns, ordered raw messages, memory snapshots |
| `assessment` | Dimensions, motivation values, intents, evidence, coverage, profile snapshots/changes, contradictions, questions |
| `matching` | Project archetypes, project-fit rows |
| `audit` | Metadata-only `llm_runs`, append-only `decision_events` |

Migrations (lexical apply on first Postgres volume):

1. `001_initial.sql` — core model + seeds
2. `002_decision_tracing.sql` — decision events + immutability trigger
3. `003_contradiction_resolution.sql` — `contradiction_resolved` / `question_quality_gate` enums, `clarification_attempts`

---

## Decision tracing and incident diagnosis

Every normal turn gets a `correlation_id` and ordered `audit.decision_events`. Each event records:

- component + component version
- stable `reason_code`
- privacy-safe `inputs` / `outputs` (no student text keys)
- `entity_refs` (message, evidence, snapshot, contradiction IDs)
- optional `llm_run_id` → `audit.llm_runs` (deployment, prompt version, response id, usage, error)

Teacher query: `GET /v1/admin/sessions/{session_id}/decision-trace` (optional `correlation_id`).

**Diagnosis recipe:** take the failed turn’s correlation ID → find the first unexpected reason code → follow `entity_refs` into evidence / profile history → open `llm_run_id` for model metadata. Events cannot be updated or deleted; corrections are later events.

Admin inspect views (`GET /v1/admin/sessions/{id}/{view}`):

`transcript` · `evidence` · `profile` · `profile-history` · `contradictions` · `question-history` · `why-next-question` · `project-fit`

---

## Operational topology (Azure)

Two Container Apps with managed identities; PostgreSQL Flexible Server; Application Insights + Log Analytics for ops telemetry. Azure OpenAI deployments are configuration. Local Compose uses loopback Postgres (+ optional host-run API with `az login`). See [local-development.md](local-development.md).
