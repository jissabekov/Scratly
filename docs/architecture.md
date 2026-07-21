# Scratly frozen architecture

> **HARD RULE 1 — No direct LLM profile mutation.** Models may propose grounded evidence or phrase an application-selected question; only the versioned deterministic reducer changes the profile.
>
> **HARD RULE 2 — No derived summary is a source of truth.** Raw messages are authoritative. Memory snapshots are disposable conversation aids and are regenerated from the complete bounded raw transcript.
>
> **HARD RULE 3 — Complete backward explainability.** Every profile transition has a versioned snapshot, change record, reducer version, and accepted evidence linked to exact quotes in owned raw messages.

## Boundaries
The Next.js teacher console calls FastAPI. PostgreSQL owns core, conversation, assessment, matching, and audit state. Blob Storage is files-only. Azure OpenAI Responses API performs bounded structured extraction, wording, compaction, review narrative, and project drafting. It never selects policy or stage.

`process_student_turn` is the only ordinary write workflow. Its transaction creates the student message, validates proposed evidence, reduces state, records changes/snapshots and contradictions, derives coverage/stage, selects a target, persists the assistant question, and completes the turn. The database uniqueness constraint on session and idempotency key protects concurrent retries.

## Operational topology
Two Container Apps use managed identities. PostgreSQL Flexible Server stores state; Application Insights and Log Analytics collect telemetry. Azure deployment names are environment configuration. No Cosmos DB, search, Redis, vectors, agent framework, MCP, Service Bus, or separate memory service is part of the design.

## Decision tracing and incident diagnosis
Every normal turn receives a correlation ID and an ordered, append-only series of `audit.decision_events`. Events show the component and version, stable reason code, privacy-safe decision inputs and outputs, referenced domain entity IDs, timing, and the related `audit.llm_runs` ID when a model participated. The trace records extraction counts, grounding rejection reasons, reducer execution, explicit contradiction handling, deterministic target priority, application-derived stage, writer success or fallback, and completion. It deliberately references raw messages and evidence by ID rather than copying student text into audit storage.

Teachers and operators can query `GET /v1/admin/sessions/{session_id}/decision-trace`, optionally filtering by `correlation_id`. Start with a failed turn's correlation ID, locate the first unexpected reason code, follow `entity_refs` into the evidence ledger or profile history, and use `llm_run_id` to inspect deployment, prompt version, response ID, usage, and error code. Audit events cannot be updated or deleted; a correction is a later event, preserving the original diagnosis trail.

Application Insights and Log Analytics provide operational telemetry for container failures and latency. PostgreSQL decision events provide the durable domain explanation. Neither replaces the raw conversation, evidence ledger, or versioned profile history as the source of truth.
