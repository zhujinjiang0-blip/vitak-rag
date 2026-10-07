#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3}"
NODE_BIN_DIR="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin"
PNPM_BIN="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"

cd "$ROOT"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e 'backend[dev]'
if ! PATH="$NODE_BIN_DIR:$PATH" "$PNPM_BIN" --dir frontend install; then
  PATH="$NODE_BIN_DIR:$PATH" "$PNPM_BIN" --dir frontend approve-builds --all
fi
.venv/bin/vitak seed-demo
