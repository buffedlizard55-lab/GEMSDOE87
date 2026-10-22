#!/usr/bin/env python3
"""Verify source hashes and source/template geometry; write an auditable receipt."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.data import inspect_core_data  # noqa: E402
from gems87.paths import EVIDENCE, RAW  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=RAW)
    ap.add_argument("--no-hash", action="store_true", help="only inspect rasters; normally hashes are required")
    ap.add_argument("--out", type=Path, default=EVIDENCE / "data_receipt.json")
    args = ap.parse_args()
    receipt = inspect_core_data(args.data_dir, verify_hashes=not args.no_hash)
    receipt["generated_utc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
