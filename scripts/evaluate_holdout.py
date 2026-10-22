#!/usr/bin/env python3
"""Run the H87-FRB spatially blocked holdout; this never spends a submission slot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.holdout import run_h87_frb_experiment  # noqa: E402
from gems87.paths import EVIDENCE, RAW, WORK  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", type=Path, default=WORK / "h87_frb_feature_stack.npy")
    ap.add_argument("--template", type=Path, default=RAW / "sample_submission.tif")
    ap.add_argument("--labels", type=Path, default=RAW / "labels.tif")
    ap.add_argument("--out", type=Path, default=EVIDENCE / "experiment_h87_frb.json")
    args = ap.parse_args()
    report = run_h87_frb_experiment(stack_path=args.stack, template_path=args.template, labels_path=args.labels, output_path=args.out)
    print(json.dumps({"out": str(args.out), "verdict": report["promotion_gate"]["verdict"], "summary": report["summary"], "paired_contrast": report["paired_contrast"]}, indent=2))
    # A negative research result is successful command execution.  The build
    # script itself enforces the no-submission gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
