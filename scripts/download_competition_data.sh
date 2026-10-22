#!/usr/bin/env bash
# Compatibility entry point.  Uses SHA-pinned GitHub mirrors and fails closed.
# This does NOT authenticate against DrivenData or claim organizer provenance.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
exec "$PYTHON_BIN" "$ROOT/scripts/fetch_competition_mirrors.py" --core "$@"
