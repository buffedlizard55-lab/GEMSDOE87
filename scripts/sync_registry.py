#!/usr/bin/env python3
"""Refresh the public sibling submission registry without using it for modeling."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.paths import EVIDENCE, REGISTRY  # noqa: E402
from gems87.registry import discover_registry_catalog, materialize_registry, save_catalog  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=REGISTRY / "registry_catalog.json")
    ap.add_argument("--out", type=Path, default=EVIDENCE / "registry_materialization.json")
    ap.add_argument("--reuse-catalog", action="store_true", help="do not call GitHub discovery again")
    args = ap.parse_args()
    if args.reuse_catalog:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    else:
        catalog = discover_registry_catalog()
        save_catalog(catalog, args.catalog)
    materialized = materialize_registry(catalog)
    materialized["generated_utc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(materialized, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: materialized[k] for k in ("registry_artifacts_discovered", "registry_artifacts_materialized", "complete_discovery", "complete_materialization", "failures")}, indent=2))
    return 0 if materialized["complete_discovery"] and materialized["complete_materialization"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
