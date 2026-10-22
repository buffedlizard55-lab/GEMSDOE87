#!/usr/bin/env bash
# Autonomous SHA-pinned owner mirrors, not an authenticated DrivenData download.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo 'Create .venv and install requirements-lock.txt first (see README).' >&2
  exit 2
fi
exec "$PYTHON" "$ROOT/scripts/restore_data.py" --target-dir "$ROOT/data/raw" "$@"
