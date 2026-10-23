#!/usr/bin/env python3
"""Build registry index in the format expected by uniqueness.compare_array_to_registry."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Load refreshed registry (has cache_file field)
    refreshed = json.loads((ROOT / 'evidence/registry_refreshed.json').read_text())

    records = []
    for r in refreshed.get('rasters', []):
        cache_file = ROOT / r['cache_file']
        if not cache_file.exists():
            continue
        records.append(dict(
            repo_first=r['repo_first'],
            sources=r['sources'],
            cache_file=r['cache_file'],
            sha256=r['sha256'],
        ))

    index = dict(
        rasters=records,
        complete_accessible_scan=refreshed.get('complete_accessible_scan', False),
        errors=refreshed.get('errors', [])
    )

    out_path = ROOT / 'docs/data/registry_index.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(index, indent=2) + '\n')
    print(f'Built registry index with {len(records)} rasters -> {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())