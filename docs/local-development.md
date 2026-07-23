# Scratly implementation guide and local testing

How to run Scratly locally and verify the assessment path. For *how the product works*, start at [README.md](README.md) (architecture, student model, scoring, policy).

This guide stays candid about what is local-ready versus Azure-production scaffolding.

## 1. Current implementation

### Monorepo layout

- `apps/api/` is a Python 3.12 FastAPI service with configuration loading, async SQLAlchemy connectivity, public/admin route surfaces, deterministic assessment services, Azure OpenAI access, and production container packaging.
- `apps/web/` is a Node.js 22 / Next.js 15 app: student chat at `/` and teacher inspection console at `/teacher`, with a production standalone container image.
- `migrations/` contains ordered PostgreSQL 16 migrations. PostgreSQL is the only state database.
- `infra/bicep/` describes the future Azure topology.
- `docs/` explains architecture, student model, scoring, conversation policy/quality, and this local workflow ([index](README.md)).
- `scripts/sim_assessment_conversation.py` runs live Maya-style Azure sims with assertion reports.

### API contracts and deterministic assessment

Strict Pydantic models describe proposed and validated evidence, question output, memory snapshots, profile reviews, generated projects, turns, and decision traces. Evidence proposals must include owned source-message IDs and an exact source quote.

The service boundaries are:

1. `evidence_extractor.py` may propose evidence (prompt v2) but cannot mutate profile state.
2. `grounding_validator.py` checks session ownership, exact quotes, proposal caps, and motivation taxonomy.
3. `profile_reducer.py` reads accepted evidence only and records reducer v2 (V1 scores; silence stays unknown).
4. `contradiction_engine.py` (v2) opens only true conflicts; resolution never averages strengths.
5. `turn_intent_classifier.py` / `student_answerer.py` handle process/profile/project Q&A (refuse homework).
6. `thin_answer.py` / `elicitation_policy.py` switch thin assessment replies to option-style questions.
7. `question_policy.py` deterministically chooses the next intent and derives stage (incl. `location_ready`).
8. `question_quality.py` overrides generic/duplicate/elicitation-missing assistant questions before persist.
9. `context_builder.py` supplies task-specific, bounded contexts (writer ≈ last 8 messages + memory).
10. `memory_compactor.py` regenerates from bounded raw messages; scheduled from the turn path when due.
11. `opportunity_matcher.py` geo-gates and ranks curated opportunities (40/40/20); capability gaps → scaffolding.
12. `web_research_client.py` / `project_composer.py` / `project_citation_gate.py` add optional URL research and citation-grounded offers.
13. `turn_processor.py` is the sole normal transaction path (intent → answer/extract → reduce → elicit → stage → write → match → compact → decision trace).

Azure OpenAI uses Microsoft Entra tokens (service principal or `az login` via Azure CLI credential) and structured outputs. With `AZURE_OPENAI_API_VERSION=2024-12-01-preview` the client uses chat.completions structured parse; at `2025-03-01-preview` or later it uses the Responses API (also required for optional `web_search`). Deployment names are configuration. It does not use the Assistants API or ordinary free-form JSON mode.

### PostgreSQL model

`001_initial.sql` creates:

- `core`: students and sessions.
- `conversation`: idempotent turns, ordered raw messages, and bounded memory snapshots.
- `assessment`: dimensions, motivation values, question intents, evidence/source links, coverage, profile snapshots, profile changes, contradictions, and question history.
- `matching`: seeded project archetypes and reproducible project-fit results.
- `audit`: metadata-only LLM runs.

The database uniqueness constraint on `(session_id, idempotency_key)` is the concurrency-safe idempotency guard. Seed data includes eight dimensions, motivation values, six prioritized question intents with fallback templates, and initial project archetypes.

`002_decision_tracing.sql` adds an append-only decision-event ledger. A trace contains correlation and sequence IDs, component/version, stable reason code, safe inputs/outputs, entity references, optional LLM-run linkage, and timing. A database trigger blocks updates and deletes. Raw student text remains in `conversation.messages` and is not duplicated into audit events.

`003_contradiction_resolution.sql` adds `contradiction_resolved` and `question_quality_gate` event types plus `clarification_attempts` on contradictions.

`004_student_ux_and_projects.sql` adds student Q&A / elicitation / location / research / project decision events, `matching.opportunities` (+ seeds), research runs/findings, generated projects + citations, session counters (`consecutive_student_questions`, elicitation attempts, `profile_reviewed`), and assistant `message_kind`. After editing migrations on an existing volume, run `make local-reset` (wipes local data).

### Student chat and teacher UI

Student chat at `:3000` uses public APIs only: create/resume session, list messages, submit turns (with `message_kind` / elicitation), and list generated projects. History rebuilds from `GET /v1/sessions/{id}/messages` (session id stored in the browser).

The teacher page at `:3000/teacher` loads live admin data: profile, evidence ledger, conversation, timeline, contradictions, question history, next-question rationale, project ranking, and decision trace. It can create sessions and submit turns against the local API (`NEXT_PUBLIC_API_BASE_URL`).

The Bicep file sketches two Container Apps, PostgreSQL Flexible Server, Blob Storage for files, Application Insights, Log Analytics, managed identities, and Blob RBAC. It is not required for local testing and should not be deployed as production infrastructure until its database connection, networking, registry access, Azure OpenAI RBAC, and secret references are completed. Blob and App Insights stay out of the local compose path.

## 2. Honest readiness status

Session/turn persistence, student chat, admin inspection, teacher console, contradiction v2, stage pacing, LLM audit linkage, and memory compaction are wired for a local end-to-end assessment journey:

1. `POST /v1/sessions` creates a student + session in PostgreSQL.
2. `POST /v1/sessions/{id}/turns` runs `process_student_turn()` (intent → optional student answer → evidence → grounding → reduce → resolve → thin/elicitation → stage → question → quality gate → optional project match → memory → decision trace).
3. Student chat at `:3000` creates sessions, submits turns, and resumes transcript via `GET /v1/sessions/{id}/messages`.
4. Teacher UI at `:3000/teacher` lists sessions, submits turns, and loads live admin views + decision trace.
5. `scripts/sim_assessment_conversation.py` can run multi-turn Azure sims with assertions.

Azure OpenAI is optional: with `AZURE_OPENAI_ENDPOINT` set and `az login` (host) or SP env vars (container), the extractor/writer/compactor use structured Azure calls and record `audit.llm_runs` linked from extract/write events. Without it, the extractor returns no evidence and the writer uses seeded fallback question templates — the persistence path still works.

Azure Blob Storage and Application Insights are **not** part of the local path (Bicep sketches only).

### Remaining gaps

- Production Bicep (networking, OpenAI RBAC, secrets) remains incomplete.
- Broader integration tests against Postgres (rollback / history reproduction) can still be expanded.
- Live Azure `web_search` requires Responses API version + tool entitlement; without it, matching uses the curated opportunity catalog only (`research_failed` / `web_search_unconfigured`).

Student questions, thin-answer elicitation, location gates, and citation-grounded project
composition are implemented on the sole turn path. Verify with:

```bash
.venv/Scripts/python -m pytest apps/api/tests/test_student_ux.py apps/api/tests/test_determinism.py -q
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 5 --student-questions --out sim-student-q.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --thin-answer-probe --out sim-thin.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --project-matching-probe --out sim-projects.json
```

After pulling migration `004_student_ux_and_projects.sql`, run `make local-reset` (or recreate the Postgres volume) so new enums/tables exist.

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

Open `http://127.0.0.1:3000` for student chat, or `http://127.0.0.1:3000/teacher` for inspection.

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

- Student chat: `http://127.0.0.1:3000`
- Teacher console: `http://127.0.0.1:3000/teacher`
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

1. Open `http://127.0.0.1:3000` — student chat creates a session and shows a welcome invite
2. Send a first message; confirm an assistant question appears and the stage chip updates
3. Refresh the page — transcript should restore from `GET /v1/sessions/{id}/messages`
4. Open `http://127.0.0.1:3000/teacher` — select the session and confirm Conversation, Question history, and Decision trace panels populate

Idempotent retries: repeat the same `idempotency_key` and you get the same completed turn.

### Playwright (student chat)

With API on `:8000` and web on `:3000`:

```bash
npm --prefix apps/web install
npx --prefix apps/web playwright install chromium
npm --prefix apps/web run test:e2e
```

Covers session create, two turns, Postgres-backed transcript resume, New chat, and teacher console visibility.

### Live conversation sim

With Postgres up and a host API using Azure credentials:

```bash
# from repo root, with API on :8000
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 5 --out sim-p0-5turn.json
.venv/Scripts/python scripts/sim_assessment_conversation.py --turns 12 --conflict-probe --out sim-final-proof.json
```

The script creates a session, posts Maya-like turns, dumps admin views + decision-trace, enriches `llm_runs` / memory counts via Compose Postgres when available, and prints an assertions report.

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

1. Compute and persist `matching.project_fits` when stage reaches project matching.
2. Expand integration tests against PostgreSQL for migrations, rollback, history reproduction, and immutable tracing.
3. Production Bicep networking, secrets, database URL construction, registry access, Azure OpenAI RBAC, health probes, and outputs.

The architecture remains intentionally strict: models may propose or phrase, but deterministic application code owns evidence acceptance, profile state, stage transitions, question target selection, and project eligibility.
