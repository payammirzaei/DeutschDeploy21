SHELL := /bin/bash

.PHONY: bootstrap dev up down logs api-dev worker-dev web-dev migrate api-openapi api-client check

bootstrap:
	@test -f .env || cp .env.example .env
	cd apps/api && uv sync --dev
	npm install

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

api-dev:
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-dev:
	cd apps/api && uv run python -m app.worker.main

web-dev:
	npm run web:dev

migrate:
	cd apps/api && uv run alembic upgrade head

api-openapi:
	cd apps/api && uv run python -m app.scripts.export_openapi

api-client: api-openapi
	npm run api:generate

check:
	cd apps/api && uv run ruff check .
	cd apps/api && uv run pytest
	make api-client
	npm run web:lint
	npm run web:typecheck
	npm run web:build
