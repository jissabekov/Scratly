.PHONY: local-db local-up local-down local-reset local-logs api-test api-run web-run check

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
	.venv/bin/python -m pytest -q

api-run:
	cd apps/api && ../../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web-run:
	npm --prefix apps/web run dev

check:
	.venv/bin/python -m compileall -q apps/api/app
	.venv/bin/python -m pytest -q
	npm --prefix apps/web run build
