#!/usr/bin/env python3
"""Reopen and validate a candidate GeoTIFF against the exact local template."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.paths import RAW  # noqa: E402
from gems87.submission import validate_submission_geotiff  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("geotiff", type=Path)
    ap.add_argument("--template", type=Path, default=RAW / "sample_submission.tif")
    ap.add_argument("--labels", type=Path, default=RAW / "labels.tif")
    args = ap.parse_args()
    report = validate_submission_geotiff(args.geotiff, template_path=args.template, labels_path=args.labels)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
