.PHONY: bootstrap seed api web test lint build evaluate

bootstrap:
	./scripts/bootstrap.sh

seed:
	.venv/bin/vitak seed-demo

api:
	cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

web:
	cd frontend && PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$$PATH" /Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm dev --host 127.0.0.1 --port 5173

test:
	cd backend && ../.venv/bin/pytest

lint:
	cd backend && ../.venv/bin/ruff check app tests

build:
	cd frontend && PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$$PATH" /Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm build

evaluate:
	.venv/bin/vitak evaluate
