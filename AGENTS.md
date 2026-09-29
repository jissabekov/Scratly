# Scratly — agent instructions

Explainable student discovery & project matching: FastAPI + PostgreSQL backend (`apps/api`), Next.js web (`apps/web`), deterministic policy owns all state; Azure OpenAI only proposes. Read `docs/README.md` first; `docs/system-guide.md` is the end-to-end reference; `docs/architecture.md` has the hard rules.

## Commands (Windows)

- Unit tests (must be green before claiming any change done): `.venv/Scripts/python -m pytest apps/api/tests -q`
- Compile check: `.venv/Scripts/python -m compileall -q apps/api/app`
- Web build: `npm --prefix apps/web run build`
- DB only: `docker compose up -d --wait postgres` · full stack: `docker compose --profile full up -d --build --wait`
- Learning content seed (Plan 03/04; run before learning/quiz e2e — validates `content/modules/**` incl. `quiz.json` and upserts the `learning` schema; idempotent): `.venv/Scripts/python scripts/seed_learning_content.py` (add `--dry-run` to validate only). Migrations are applied lexically on first Postgres volume only; apply a new one to an existing volume with `docker compose exec -T postgres psql -U scratly -d scratly < migrations/<file>.sql`.
- Quiz e2e needs the API launched with `LEARNING_QUIZ_COOLDOWN_SECONDS=0` (default 600s blocks the immediate alternate-form retry the remediation loop promises): `cd apps/api && set -a && source .env && set +a && export LEARNING_QUIZ_COOLDOWN_SECONDS=0 && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Live eval suite (needs API on :8000 + Postgres + Azure): set `PYTHONIOENCODING=utf-8`, then `.venv/Scripts/python scripts/eval_conversation_suite.py --out-dir eval/traces/<new-dir>`; analyze with `.venv/Scripts/python eval/analyze_post_fix.py <dir>`

## Hard rules (from docs/architecture.md — do not violate)

1. LLMs propose; only the versioned deterministic reducer mutates the profile.
2. Raw messages are the only source of truth; snapshots/memory are disposable aids.
3. Every profile transition keeps a versioned snapshot + change record + evidence linked to exact quotes in owned messages.
4. Student answers never write profile state.
5. Research findings never override evidence.
6. Project text without citation links to stored opportunities/findings is rejected.

## Change discipline

- Sole assessment write path: `process_student_turn` in `apps/api/app/services/turn_processor.py`, one DB transaction, idempotent by `UNIQUE(session_id, idempotency_key)`. Never write assessment state elsewhere.
- Migrations are ordered, append-only SQL in `migrations/`; never edit an applied migration.
- Prompts are versioned directories (`apps/api/prompts/<name>/vN/system.txt`); add a new version rather than editing one in place when behavior changes.
- Never lower eval thresholds or weaken assertions to make the suite pass ("fake green") — fix the policy; see docs/eval-findings-and-fix-plan.md §8.
- Azure OpenAI auth: API key via `AZURE_OPENAI_API_KEY` (preferred), Entra fallback — see `apps/api/app/services/azure_openai.py`. Keys live only in `.env` / `apps/api/.env` (gitignored); never commit or print them.
- Windows: use `.venv/Scripts/python` (the Makefile's `.venv/bin/` targets are Linux-style).

## Skills (use these instead of re-deriving procedures)

- `/verify` — full verification gate (compile check + unit tests + optional web build); run before claiming any change is done.
- `/eval-suite` — run and interpret the 21-scenario live conversation eval (assertions A1–A18, baseline comparison).
- `/state-report` — generate a current-state report (commit timeline, eval results, pending work).
- `/research` — parallel web + GitHub-ecosystem research via subagents, synthesized into actionable recommendations.
- `/frontend-ui` — build/modify web UI (lesson player, quizzes, chat) per `apps/web/AGENTS.md` conventions.
- `/web-e2e` — run and extend Playwright e2e tests.

## Execution plans

`docs/plan/00-MASTER-ORCHESTRATION.md` is the master sequencing file (phases, dependencies, status, verification gates); `01`–`06` are the per-phase plans. Always check the master file before starting work and update phase status when a phase completes.
