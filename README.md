# Scratly

Explainable student discovery and project matching. See
[`docs/architecture.md`](docs/architecture.md) for hard boundaries and
[`docs/local-development.md`](docs/local-development.md) for the complete
implementation inventory, readiness limitations, and local testing guide.

## Quick local start

```bash
cp .env.example .env
make local-db
```

For a production-style local build of PostgreSQL, API, and web:

```bash
make local-up
```

The default local URLs are:

- Web: `http://127.0.0.1:3000`
- API documentation: `http://127.0.0.1:8000/docs`
- API liveness: `http://127.0.0.1:8000/health`
- API/database readiness: `http://127.0.0.1:8000/health/ready`

## Tracing a decision

Apply migrations in numeric order, then query
`GET /v1/admin/sessions/{session_id}/decision-trace`. Supply a
`correlation_id` query parameter to isolate one turn. Each append-only event
identifies the policy component and version, a stable reason code, safe inputs
and outputs, domain entity references, and an LLM run reference where relevant.
Raw student text remains in the conversation schema and is not copied into the
audit trace.
