# Scratly architecture

Explainable student discovery and project matching. Models propose; the application owns state and policy.

> **HARD RULE 1 — No direct LLM profile mutation.** Models may propose grounded evidence or phrase an application-selected question. Only the versioned deterministic reducer changes the profile.
>
> **HARD RULE 2 — No derived summary is a source of truth.** Raw messages are authoritative. Memory snapshots are disposable conversation aids regenerated from the complete bounded raw transcript.
>
> **HARD RULE 3 — Complete backward explainability.** Every profile transition has a versioned snapshot, change record, reducer version, and accepted evidence linked to exact quotes in owned raw messages.
>
> **HARD RULE 4 — Student answers never write profile state.** They may only quote already-accepted evidence / public profile fields.
>
> **HARD RULE 5 — Research findings are derived artifacts** (like memory): useful for matching, never override evidence.
>
> **HARD RULE 6 — Project text without citation links** to stored opportunities/findings is rejected like ungrounded evidence.

Related: [student-model.md](student-model.md) · [scoring-rules.md](scoring-rules.md) · [conversation-policy.md](conversation-policy.md) · [docs index](README.md)

Truth hierarchy:

```text
1. RAW STUDENT MESSAGE
2. ACCEPTED GROUNDED EVIDENCE
3. DETERMINISTIC PROFILE STATE
4. PROFILE SNAPSHOT
5. CONVERSATION SUMMARY / RESEARCH FINDINGS  (aids only)
```

Curated `matching.opportunities` are application catalog data, not student truth.

---

## System boundaries

```text
Student chat (Next.js :3000/)  ──public /v1──┐
Teacher console (:3000/teacher) ─admin /v1──┤
                                            ▼
                                       FastAPI API (:8000)
                                            │
        ├── Azure OpenAI (Entra)  — extract, intent, answer, write, compact, web_search, compose
        └── PostgreSQL 16         — sole state store
```

| Layer | Responsibility |
|---|---|
| `apps/web` | Student chat at `/` (public session/messages/turns/projects); teacher inspect at `/teacher` |
| `apps/api` | Sole assessment write path, policy, grounding, reduction, matching, audit |
| `migrations/` | Ordered SQL schemas: `core`, `conversation`, `assessment`, `matching`, `audit` |
| Azure OpenAI | Structured outputs (+ optional Responses `web_search`); never selects stage/priority or mutates profile |
| Blob / App Insights | Azure topology sketches only; not required for local |

No Cosmos DB, Redis, vectors, Agent Service framework, MCP, or Service Bus.

---

## Sole write path: `process_student_turn`

Ordinary assessment state changes go through one transactional workflow
(`apps/api/app/services/turn_processor.py`). Concurrent retries are guarded by
`UNIQUE(session_id, idempotency_key)` on `conversation.turns`.

| # | Step | Decision event | Notes |
|---|---|---|---|
| 0 | Idempotent replay if turn already completed | — | Returns prior assistant message |
| 1 | Create turn + student message; bind LLM audit context | `turn_started` | Reason `new_idempotency_key` |
| 2 | Classify turn intent (LLM + heuristic out-of-scope override) | `turn_intent_classified` | |
| 3 | In-scope student Q → answer; out-of-scope → refuse; cap consecutive Qs | `student_answer_written` / `student_answer_refused` | Prefix on assistant message |
| 4 | Pure student Q skips extract | `evidence_extraction_skipped` | Reason `skipped_no_assessment_content` |
| 5 | Else: extractor proposes evidence (prompt **v2**) | `evidence_proposed` | Links `llm_run_id` when Azure succeeds |
| 6 | Ground + persist evidence | `evidence_validated` | Rejection reason counts in outputs |
| 7 | Reduce profile; sync contradictions; write snapshot | `profile_reduced` | Reducer version on snapshot |
| 8 | Close non-conflicts / resolve clarifying answers | `contradiction_resolved` | See [scoring-rules.md](scoring-rules.md) |
| 9 | Recount open contradictions | `contradiction_evaluated` | Engine **v2** |
| 10 | Location readiness check | `location_readiness_checked` | Geo on `constraints` |
| 11 | Thin-answer evaluate → elicitation or soft-skip | `answer_thinness_evaluated`, `elicitation_*` | Max 2 attempts / target |
| 12 | Select next question target | `question_target_selected` | Reason `priority_{kind}` |
| 13 | Derive conversation stage | `stage_derived` | Includes `location_ready` |
| 14 | Optional profile-review narrative | `profile_review_completed` | Latch `profile_reviewed` |
| 15 | Write / fallback question (prompt **v2**) | `question_written` or `question_fallback_used` | |
| 16 | Quality gate (incl. elicitation options) | `question_quality_gate` | Only if outcome ≠ `passed` |
| 17 | If `project_matching` + location: research, rank, compose | `research_*`, `opportunities_matched`, `project_*` | Citations required |
| 18 | Persist assistant message (`message_kind`), stage, complete turn | — | Answer/refusal prefix + question |
| 19 | Maybe compact memory (non-fatal) | — | Never feeds extractor |
| 20 | Commit | `turn_completed` | Reason `turn_committed` |

Public API:

- `POST /v1/sessions` — create student + session (stage `discovery`)
- `GET /v1/sessions/{id}` — resume metadata
- `POST /v1/sessions/{id}/turns` — `{ idempotency_key, text }` → `{ turn_id, assistant_message, stage }`

---

## Component map

| Component | File | May do | Must not do |
|---|---|---|---|
| Turn intent classifier | `turn_intent_classifier.py` | Propose intent / topic | Mutate profile |
| Student answerer | `student_answerer.py` | Phrase in-scope answers | Invent profile facts |
| Thin-answer detector | `thin_answer.py` | Flag thin assessment replies | Call the LLM |
| Elicitation policy | `elicitation_policy.py` | Build option banks / targets | Change profile |
| Location policy | `location_policy.py` | Geo readiness helpers | Soften missing geo for matching |
| Evidence extractor | `evidence_extractor.py` | Propose `EvidencePacket` | Mutate profile/stage |
| Grounding validator | `grounding_validator.py` | Accept/reject with reason | Invent quotes |
| Profile reducer | `profile_reducer.py` | Compute dimension states from accepted evidence | Average conflicts |
| Contradiction engine | `contradiction_engine.py` | Detect/resolve true conflicts (v2) | Treat multi-value supports as fights |
| Question policy | `question_policy.py` | Priority + stage derivation | Call the LLM |
| Question quality gate | `question_quality.py` | Override generic/duplicate/elicitation misses | Change profile |
| Context builder | `context_builder.py` | Bounded extractor/writer/memory contexts | Pass full uncontrolled transcript to writer |
| Memory compactor | `memory_compactor.py` | Summarize raw msgs through boundary | Become evidence source |
| Opportunity matcher | `opportunity_matcher.py` | Geo-gated rank of curated opportunities | Soften hard geo fails |
| Web research client | `web_research_client.py` | Bounded `web_search` → URL findings | Mutate profile |
| Project composer | `project_composer.py` | Draft offers from opportunities/findings | Invent citation IDs |
| Project citation gate | `project_citation_gate.py` | Reject uncited / unknown refs | Persist rejected drafts |
| Decision trace | `decision_trace.py` | Append privacy-safe events | Store student text |
| Turn processor | `turn_processor.py` | Orchestrate the sole write transaction | Bypass reducer |

Repository orchestration and SQL live in `apps/api/app/repository/assessment.py`.

---

## Data model (schemas)

| Schema | Owns |
|---|---|
| `core` | Students, sessions (`stage`, counters, `profile_reviewed`) |
| `conversation` | Idempotent turns, ordered raw messages (`message_kind`), memory snapshots |
| `assessment` | Dimensions, motivation values, intents, evidence, coverage, profile snapshots/changes, contradictions, questions |
| `matching` | Archetypes, **opportunities**, research runs/findings, generated projects + citations, project-fit rows |
| `audit` | Metadata-only `llm_runs`, append-only `decision_events` |

Migrations (lexical apply on first Postgres volume):

1. `001_initial.sql` — core model + seeds
2. `002_decision_tracing.sql` — decision events + immutability trigger
3. `003_contradiction_resolution.sql` — `contradiction_resolved` / `question_quality_gate` enums, `clarification_attempts`
4. `004_student_ux_and_projects.sql` — student Q&A / elicitation events, opportunities, research, generated projects, location intents, session counters

---

## Decision tracing and incident diagnosis

Every normal turn gets a `correlation_id` and ordered `audit.decision_events`. Each event records:

- component + component version
- stable `reason_code`
- privacy-safe `inputs` / `outputs` (no student text keys)
- `entity_refs` (message, evidence, snapshot, contradiction, opportunity, finding IDs)
- optional `llm_run_id` → `audit.llm_runs` (deployment, prompt version, response id, usage, error)

Teacher query: `GET /v1/admin/sessions/{session_id}/decision-trace` (optional `correlation_id`).

**Diagnosis recipe:** take the failed turn’s correlation ID → find the first unexpected reason code → follow `entity_refs` into evidence / profile history / project citations → open `llm_run_id` for model metadata. Events cannot be updated or deleted; corrections are later events.

Admin inspect views (`GET /v1/admin/sessions/{id}/{view}`):

`transcript` · `evidence` · `profile` · `profile-history` · `contradictions` · `question-history` · `why-next-question` · `project-fit`

`project-fit` returns opportunity ranks, generated projects with citations, research finding URLs, or the seeded catalog when no fits exist yet.

---

## Operational topology (Azure)

Two Container Apps with managed identities; PostgreSQL Flexible Server; Application Insights + Log Analytics for ops telemetry. Azure OpenAI deployments are configuration. Bounded web research uses the Responses API `web_search` tool when the API version and entitlement allow it; otherwise matching continues on the curated catalog alone. Local Compose uses loopback Postgres (+ optional host-run API with `az login`). See [local-development.md](local-development.md).
