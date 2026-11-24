#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_BIN_DIR="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
PNPM_BIN="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"
API_PORT="${VITAK_API_PORT:-8000}"
WEB_PORT="${VITAK_WEB_PORT:-5173}"
API_TARGET="${VITE_API_TARGET:-http://127.0.0.1:${API_PORT}}"

cd "$ROOT/backend"
../.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port "$API_PORT" \
  --reload &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
VITE_STATIC_DEMO=false \
VITE_API_TARGET="$API_TARGET" \
PATH="$NODE_BIN_DIR:$PATH" \
"$PNPM_BIN" dev --host 127.0.0.1 --port "$WEB_PORT"
