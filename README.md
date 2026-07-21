# Scratly

Explainable student discovery and project matching.

Start here for how the system works:

- [`docs/README.md`](docs/README.md) — documentation index and mental model
- [`docs/architecture.md`](docs/architecture.md) — hard rules, turn path, tracing
- [`docs/conversation-policy.md`](docs/conversation-policy.md) — priority, stages, student Q&A, elicitation, location, matching
- [`docs/local-development.md`](docs/local-development.md) — run Compose/host API, Azure Entra, tests, sims

## Quick local start

```bash
cp .env.example .env
make local-db
```

Without Make (for example on Windows):

```bash
cp .env.example .env
docker compose up -d --wait postgres
```

For a production-style local build of PostgreSQL, API, and web:

```bash
make local-up
# or: docker compose --profile full up -d --build --wait
```

The default local URLs are:

- Web: `http://127.0.0.1:3000`
- API documentation: `http://127.0.0.1:8000/docs`
- API liveness: `http://127.0.0.1:8000/health`
- API/database readiness: `http://127.0.0.1:8000/health/ready`

Apply migrations in numeric order (`001`–`004`). On an existing Postgres volume after pulling new SQL, run `make local-reset` (or recreate the volume).

## Tracing a decision

Query `GET /v1/admin/sessions/{session_id}/decision-trace`. Supply a
`correlation_id` query parameter to isolate one turn. Each append-only event
identifies the policy component and version, a stable reason code, safe inputs
and outputs, domain entity references, and an LLM run reference where relevant.
Raw student text remains in the conversation schema and is not copied into the
audit trace.

Useful reason patterns: `intent_*`, `thin` / `elicitation_*`, `location_*`,
`priority_*`, `stage_*`, `projects_persisted`.
