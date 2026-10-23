#!/usr/bin/env python3
"""Configure the inherited registry scanner for all currently accessible GEMSDOE repos.

Inventory is historical pins UNION immutable current default-branch commits.
Candidate bytes stay ignored. No score claims are imported as confirmed results.
This is inventory orchestration, not a second uniqueness policy.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    repos = subprocess.run(
        ['gh', 'api', '--paginate', 'users/buffedlizard55-lab/repos?per_page=100',
         '--jq', '.[] | select(.name | test("GEMSDOE"; "i")) | .name'],
        capture_output=True, check=True, text=True).stdout.splitlines()
    names = sorted({name for name in repos if re.search('GEMSDOE', name, re.I)})
    spec = importlib.util.spec_from_file_location('shared_registry_inventory', ROOT / 'scripts/refresh_registry.py')
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    scanner.REPOS = names
    # Only demonstrable source inputs; ambiguous prediction surfaces remain in scope.
    scanner.INPUT_PATTERNS += ('/geodawn_dem_', '/topo_10m_', '/dem10_chi_',
                               '/topo_100m', '/dem_100m', '/official_bands')
    old = json.loads((ROOT / 'registry/historical_index.json').read_text())
    records = []
    for r in old['rasters']:
        records.append(dict(repo_first=r['repo'], blob=r['blob'],
                            sources=r.get('aliases') or [f"{r['repo']}:{r['path']}"],
                            historical_source='GEMSDOE82 registry snapshot; Git blob verified on restore'))
    (ROOT / 'evidence/registry_full_index.json').write_text(json.dumps({'rasters': records}, indent=2) + '\n')
    result = scanner.refresh(ROOT, workers=4)
    print(json.dumps({k: result[k] for k in ('n_unique_grid_rasters', 'complete_accessible_scan', 'errors')}, indent=2))
    return 0 if result['complete_accessible_scan'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
