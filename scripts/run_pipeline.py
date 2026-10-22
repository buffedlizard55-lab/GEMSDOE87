#!/usr/bin/env python3
"""One-command, fail-closed local GEMS pipeline.

It validates placed data, reuses/builds the cached feature stack, runs the one
pre-registered holdout experiment, refreshes the public duplicate registry, and
creates a release only if every gate passes. It never submits to DrivenData.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"


def run(script: str, *args: str) -> None:
    command = [str(PYTHON if PYTHON.exists() else Path(sys.executable)), str(ROOT / "scripts" / script), *args]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="fetch pinned owner mirrors before validation")
    ap.add_argument("--refresh-registry", action="store_true", help="discover the live public registry instead of reproducing against the pinned catalog snapshot")
    ap.add_argument("--timestamp", default="20261022T220000Z")
    args = ap.parse_args()
    if args.fetch:
        run("fetch_competition_mirrors.py", "--core")
    run("prepare_data.py")
    run("build_feature_stack.py")
    run("evaluate_holdout.py")
    # The committed catalog is a reproducibility snapshot from before this
    # release existed. A live refresh intentionally re-checks all current public
    # candidates and can fail closed if it sees this exact prior artifact.
    if args.refresh_registry:
        run("sync_registry.py")
    else:
        run("sync_registry.py", "--reuse-catalog")
    run("build_submission.py", "--timestamp", args.timestamp)
    run("build_site.py")
    card = json.loads((ROOT / "evidence" / "run_card_h87_frb.json").read_text())
    print(json.dumps({"verdict": card["verdict"], "submission": card["submission"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
