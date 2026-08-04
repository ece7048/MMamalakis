#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="/Users/mamala01/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

exec "$PYTHON" "$ROOT_DIR/tools/create_l205_highlights.py"
