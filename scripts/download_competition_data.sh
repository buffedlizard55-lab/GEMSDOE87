#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

echo "[GEMSDOE87] Restoring & verifying SHA-256 digests for DrivenData/NETL GEMS rasters + public external layers..."
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/restore_data.py"
