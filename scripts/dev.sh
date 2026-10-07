#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_BIN_DIR="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
PNPM_BIN="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"

cd "$ROOT/backend"
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
PATH="$NODE_BIN_DIR:$PATH" "$PNPM_BIN" dev --host 127.0.0.1 --port 5173

