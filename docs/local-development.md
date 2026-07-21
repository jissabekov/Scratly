# Scratly implementation guide and local testing

This document describes what exists in the repository, the architectural boundaries it enforces, and how to run every currently runnable component on a local workstation. It is intentionally candid about scaffolding that is not yet wired end to end.

## 1. Current implementation

### Monorepo layout

- `apps/api/` is a Python 3.12 FastAPI service with configuration loading, async SQLAlchemy connectivity, public/admin route surfaces, deterministic assessment services, Azure OpenAI access, and production container packaging.
- `apps/web/` is a Node.js 22 / Next.js 15 teacher inspection console with a production standalone container image.
- `migrations/` contains ordered PostgreSQL 16 migrations. PostgreSQL is the only state database.
- `infra/bicep/` describes the future Azure topology.
- `docs/` freezes the architecture, student model, scoring rules, conversation policy, and this local workflow.

### API contracts and deterministic assessment

Strict Pydantic models describe proposed and validated evidence, question output, memory snapshots, profile reviews, generated projects, turns, and decision traces. Evidence proposals must include owned source-message IDs and an exact source quote.

The service boundaries are:

1. `evidence_extractor.py` may propose evidence but cannot mutate profile state.
2. `grounding_validator.py` checks session ownership and exact quote containment and keeps rejection reasons.
3. `profile_reducer.py` reads accepted evidence only and records a reducer version.
4. `contradiction_engine.py` exposes conflicts rather than averaging them away.
5. `question_policy.py` deterministically chooses the next intent and derives the conversation stage.
6. `context_builder.py` supplies task-specific, bounded contexts and prevents the writer from receiving an uncontrolled transcript.
7. `memory_compactor.py` regenerates from bounded raw messages and treats model failure as non-fatal.
8. `project_matcher.py` applies 40% topic, 40% work-mode, and 20% motivation scoring; hard constraints gate eligibility while capability gaps produce scaffolding.
9. `turn_processor.py` is designed as the sole normal transaction path and records a correlated decision trace.

Azure OpenAI uses Microsoft Entra tokens (service principal or `az login` via Azure CLI credential) and structured outputs. With `AZURE_OPENAI_API_VERSION=2024-12-01-preview` the client uses chat.completions structured parse; at `2025-03-01-preview` or later it uses the Responses API. Deployment names are configuration. It does not use the Assistants API or ordinary free-form JSON mode.

### PostgreSQL model

`001_initial.sql` creates:

- `core`: students and sessions.
- `conversation`: idempotent turns, ordered raw messages, and bounded memory snapshots.
- `assessment`: dimensions, motivation values, question intents, evidence/source links, coverage, profile snapshots, profile changes, contradictions, and question history.
- `matching`: seeded project archetypes and reproducible project-fit results.
- `audit`: metadata-only LLM runs.

The database uniqueness constraint on `(session_id, idempotency_key)` is the concurrency-safe idempotency guard. Seed data includes eight dimensions, motivation values, six prioritized question intents with fallback templates, and initial project archetypes.

`002_decision_tracing.sql` adds an append-only decision-event ledger. A trace contains correlation and sequence IDs, component/version, stable reason code, safe inputs/outputs, entity references, optional LLM-run linkage, and timing. A database trigger blocks updates and deletes. Raw student text remains in `conversation.messages` and is not duplicated into audit events.

### Teacher UI and infrastructure

The teacher page loads live admin data: profile, evidence ledger, conversation, timeline, contradictions, question history, next-question rationale, project ranking, and decision trace. It can create sessions and submit turns against the local API (`NEXT_PUBLIC_API_BASE_URL`).

The Bicep file sketches two Container Apps, PostgreSQL Flexible Server, Blob Storage for files, Application Insights, Log Analytics, managed identities, and Blob RBAC. It is not required for local testing and should not be deployed as production infrastructure until its database connection, networking, registry access, Azure OpenAI RBAC, and secret references are completed. Blob and App Insights stay out of the local compose path.

## 2. Honest readiness status

Session/turn persistence, admin inspection queries, and the teacher console are wired for a local end-to-end assessment journey:

1. `POST /v1/sessions` creates a student + session in PostgreSQL.
2. `POST /v1/sessions/{id}/turns` runs `process_student_turn()` (evidence → grounding → reduce → stage → question → decision trace).
3. Teacher UI at `:3000` lists sessions, submits turns, and loads live admin views + decision trace.

Azure OpenAI is optional: with `AZURE_OPENAI_ENDPOINT` set and `az login` (host) or SP env vars (container), the extractor/writer use the Responses API. Without it, the extractor returns no evidence and the writer uses seeded fallback question templates — the persistence path still works.

Azure Blob Storage and Application Insights are **not** part of the local path (Bicep sketches only).

### Remaining gaps

- `audit.llm_runs` is not yet linked from every Azure call inside the turn transaction.
- Project-fit ranking is not computed on each turn (admin shows archetypes until fits exist).
- Memory compaction is not yet scheduled inside the turn path.
- Production Bicep (networking, OpenAI RBAC, secrets) remains incomplete.

## 3. Prerequisites

Use Linux, macOS, or WSL2 with:

- Git
- Docker Engine with Docker Compose v2
- Python 3.12 for host-run API/tests
- Node.js 22 and npm for host-run web development
- Optional PostgreSQL `psql` client for manual inspection
- Optional Azure CLI for real Azure OpenAI calls

No locally installed PostgreSQL server is needed; Compose runs PostgreSQL 16 in a container.

## 4. Local configuration

From the repository root:

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
```

The checked-in defaults are disposable local values. Do not reuse `scratly_local_only` outside a developer workstation.

There are two different database hostnames by design:

- An API process running on the host uses `localhost` from `apps/api/.env`.
- The API container uses `postgres`, the Compose service name, injected by `compose.yaml`.

The root `.env` controls Compose ports and PostgreSQL initialization. The API `.env` controls a host-run Uvicorn process. Both files are ignored by Git.

### Azure OpenAI (Entra)

Set in the shell or both relevant `.env` files:

```dotenv
AZURE_OPENAI_ENDPOINT=https://pcoding.cognitiveservices.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_ANALYZER_DEPLOYMENT=gpt-5.4-mini
AZURE_OPENAI_WRITER_DEPLOYMENT=gpt-5.4-mini
AZURE_OPENAI_SUMMARY_DEPLOYMENT=gpt-5.4-mini
```

Leave `AZURE_OPENAI_ENDPOINT` empty to exercise DB/UI without LLM calls (seeded question fallbacks).

Do not add an API key. Auth is Entra via service principal (containers) or Azure CLI (`az login` on the host):

| How you run the API | Auth |
|---------------------|------|
| Host (`make api-run` / uvicorn) | `az login` on the host |
| Compose `api` container | Set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` — containers cannot use the host `az login` cache |

`2024-12-01-preview` uses chat.completions structured outputs. Set `AZURE_OPENAI_API_VERSION` to `2025-03-01-preview` or later to use the Responses API instead.

Blob Storage and Application Insights are intentionally absent from local compose.

## 5. Fastest start: local PostgreSQL only

```bash
cp .env.example .env
make local-db
```

On the first creation of the named volume, the official PostgreSQL image applies every file in `migrations/` in lexical order. Confirm it is healthy:

```bash
docker compose ps

docker compose exec postgres \
  psql -U scratly -d scratly -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('core','conversation','assessment','matching','audit') ORDER BY 1;"
```

Inspect seed data and tracing tables:

```bash
docker compose exec postgres \
  psql -U scratly -d scratly -c "TABLE assessment.dimensions;"

docker compose exec postgres \
  psql -U scratly -d scratly -c "\\d audit.decision_events"
```

Migration initialization only occurs for an empty PostgreSQL volume. After changing a migration during local development, reset the disposable database:

```bash
make local-reset
```

This deletes all local database data.

## 6. Run API and web on the host

Create the API virtual environment and install dependencies:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
```

Start PostgreSQL and API:

```bash
make local-db
make api-run
```

In another terminal, verify both process and database readiness:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/health/ready
```

Install and start the web app:

```bash
npm --prefix apps/web install
make web-run
```

Open `http://127.0.0.1:3000`.

## 7. Run the production-style containers locally

To build and start PostgreSQL, API, and web together:

```bash
cp .env.example .env
docker compose --profile full config
make local-up
```

On Windows without GNU Make, use Compose directly:

```bash
cp .env.example .env
docker compose --profile full up -d --build --wait
```

Then open:

- Web: `http://127.0.0.1:3000`
- API OpenAPI: `http://127.0.0.1:8000/docs`
- API health: `http://127.0.0.1:8000/health`
- API database readiness: `http://127.0.0.1:8000/health/ready`

Compose waits on service healthchecks (`postgres` via `pg_isready`, `api` via `/health`, `web` via HTTP). Follow logs or stop the stack:

```bash
make local-logs
make local-down
```

Or:

```bash
docker compose --profile full logs -f
docker compose --profile full down
```

The services bind to `127.0.0.1`, not all network interfaces, to keep the disposable local database and applications off the LAN by default. Optional LAN-publish overrides live in `compose.override.example.yaml`.

## 8. Run checks

With the virtual environment and web dependencies installed:

```bash
make check
```

Or run checks individually:

```bash
.venv/bin/python -m compileall -q apps/api/app
.venv/bin/python -m pytest -q
npm --prefix apps/web run build
docker compose config --quiet
docker compose --profile full config --quiet
```

Build the images independently:

```bash
docker build -t scratly-api:local apps/api
docker build -t scratly-web:local apps/web
```

## 9. End-to-end assessment smoke test

Prefer host-run API when using `az login` (containers need a service principal).

```bash
# Terminal A: Postgres
docker compose up -d --wait postgres

# Terminal B: API (from repo root, venv active)
cd apps/api && ../../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal C: Web
npm --prefix apps/web install
npm --prefix apps/web run dev
```

Or full compose (LLM only if SP env vars are set):

```bash
docker compose --profile full up -d --build --wait
```

### curl path

```bash
curl --fail -X POST http://127.0.0.1:8000/v1/sessions
# → {"session_id":"...","student_id":"...","stage":"discovery"}

SESSION_ID=<paste session_id>

curl --fail -X POST \
  "http://127.0.0.1:8000/v1/sessions/$SESSION_ID/turns" \
  -H 'content-type: application/json' \
  -d '{"idempotency_key":"local-test-0001","text":"I like building small science projects with neighborhood data."}'
# → turn_id, assistant_message, stage

curl --fail "http://127.0.0.1:8000/v1/admin/sessions/$SESSION_ID/transcript"
curl --fail "http://127.0.0.1:8000/v1/admin/sessions/$SESSION_ID/decision-trace"
curl --fail "http://127.0.0.1:8000/v1/admin/sessions"
```

### UI path

1. Open `http://127.0.0.1:3000`
2. Click **New session**
3. Edit the student turn text and click **Submit turn**
4. Confirm Conversation, Question history, and Decision trace panels populate

Idempotent retries: repeat the same `idempotency_key` and you get the same completed turn.
## 10. Inspect and reset local state

Open a SQL shell:

```bash
docker compose exec postgres psql -U scratly -d scratly
```

Useful queries:

```sql
SELECT * FROM conversation.turns ORDER BY created_at DESC;
SELECT * FROM assessment.evidence ORDER BY created_at DESC;
SELECT * FROM assessment.profile_changes ORDER BY created_at DESC;
SELECT * FROM audit.llm_runs ORDER BY created_at DESC;
SELECT * FROM audit.decision_events ORDER BY created_at, turn_id, sequence;
```

Stop while retaining the database:

```bash
make local-down
```

Delete the database and reapply migrations:

```bash
make local-reset
```

Delete everything and leave it stopped:

```bash
docker compose --profile full down -v
```

## 11. Troubleshooting

### Port already allocated

Change `POSTGRES_PORT`, `API_PORT`, or `WEB_PORT` in root `.env`. If the host-run API uses a non-default PostgreSQL port, update `apps/api/.env` as well.

### Migration was edited but nothing changed

PostgreSQL init scripts run only when the data directory is empty. Run `make local-reset`. Never use that command against a database containing valuable data.

### API container cannot connect to PostgreSQL

Inside Compose, the database host must be `postgres`, not `localhost`. `localhost` inside the API container means the API container itself.

### Host-run API cannot connect

For a host process, use `localhost` and ensure `make local-db` reports healthy. Check that root and API `.env` credentials match.

### Azure authentication fails

Run `az login`, choose the intended subscription, and ensure the identity has inference permission on the Azure OpenAI resource. Verify endpoint and deployment names. Azure is not required for non-LLM tests.

### Tests import the wrong Python packages

Activate `.venv` or use the explicit `.venv/bin/python` commands. Python 3.12 is the supported local baseline.

## 12. Next implementation work

1. Link `audit.llm_runs` from Azure calls inside the turn transaction and attach `llm_run_id` on decision events.
2. Schedule memory compaction from the turn path using `MemoryCompactor.due`.
3. Compute and persist `matching.project_fits` when stage reaches project matching.
4. Integration tests against PostgreSQL for migrations, rollback, history reproduction, and immutable tracing.
5. Production Bicep networking, secrets, database URL construction, registry access, Azure OpenAI RBAC, health probes, and outputs.

The architecture remains intentionally strict: models may propose or phrase, but deterministic application code owns evidence acceptance, profile state, stage transitions, question target selection, and project eligibility.
