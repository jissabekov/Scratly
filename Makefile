.PHONY: local-db local-up local-down local-reset local-logs api-test api-run web-run lint check

local-db:
	docker compose up -d --wait postgres

local-up:
	docker compose --profile full up -d --build --wait

local-down:
	docker compose --profile full down

local-reset:
	docker compose --profile full down -v
	docker compose up -d --wait postgres

local-logs:
	docker compose --profile full logs -f

api-test:
	.venv/Scripts/python -m pytest -q

api-run:
	cd apps/api && ../../.venv/Scripts/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web-run:
	npm --prefix apps/web run dev

lint:
	.venv/Scripts/python -m ruff check apps/api
	.venv/Scripts/python -m ruff format --check apps/api

check:
	.venv/Scripts/python -m compileall -q apps/api/app
	.venv/Scripts/python -m pytest -q
	$(MAKE) lint
	npm --prefix apps/web run build
