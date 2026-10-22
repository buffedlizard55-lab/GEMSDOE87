#!/usr/bin/env python3
"""Verify pinned input bytes, then reuse the inherited feature cache builder.

Run restore_data.py first (or pass --fetch). No prediction is read from the
sample; it supplies footprint/grid only. Physical bands are cached unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        subprocess.run([sys.executable, str(ROOT / 'scripts/restore_data.py'),
                        '--target-dir', str(ROOT / 'data/raw')], check=True)
    manifest = json.loads((ROOT / 'registry/data_manifest.json').read_text())
    official = ROOT / 'data/official'
    official.mkdir(parents=True, exist_ok=True)
    for entry in manifest['files']:
        source = ROOT / 'data/raw' / entry['dest']
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f"Missing or mismatched source: {entry['id']}")
        dest = official / entry['dest']
        if dest.is_symlink():
            if dest.resolve() != source.resolve():
                raise ValueError(f'Unexpected existing link: {dest}')
        elif dest.exists():
            raise FileExistsError(f'Refusing to replace {dest}')
        else:
            dest.symlink_to(Path('../raw') / entry['dest'])
    pin = json.loads((ROOT / 'registry/template_pin.json').read_text())['cache_builder']
    builder = ROOT / 'vendor/prepare_data.py'
    if hashlib.sha256(builder.read_bytes()).hexdigest() != pin['sha256']:
        raise ValueError('Shared feature cache builder changed')
    spec = importlib.util.spec_from_file_location('shared_cache_builder', builder)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.cache_bands(ROOT)
    print(f"Verified and cached {receipt['count']} physical bands; no labels used as features.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
