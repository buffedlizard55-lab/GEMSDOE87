#!/usr/bin/env python3
"""Build/reuse the label-free cached H87-FRB structural feature stack."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.features import build_feature_stack  # noqa: E402
from gems87.paths import RAW, WORK  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", type=Path, default=RAW / "training_features.tif")
    ap.add_argument("--template", type=Path, default=RAW / "sample_submission.tif")
    ap.add_argument("--out", type=Path, default=WORK / "h87_frb_feature_stack.npy")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    receipt = build_feature_stack(features_path=args.features, template_path=args.template, output_path=args.out, force=args.force)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
