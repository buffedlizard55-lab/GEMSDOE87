#!/usr/bin/env python3
"""Independent, automated re-read of the downloadable TIFF and single-TIFF ZIP.

Exit 0 for valid local FORMAT with --format-only. Otherwise always fail closed
(exit 2): this validator is for the frozen negative run and cannot verify real
selector/account receipts. Editing JSON booleans cannot authorize it. A future
run needs a separate auditable selector. This tool never uploads files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'vendor'), str(ROOT / 'src')]
import numpy as np
import rasterio
from gems57 import gates
from gems57.grid import load_grid
from gems57.validate import validate
from gems87.experiment import write_json


def check_bundle(card: dict, root: Path = ROOT, data_dir: Path | None = None) -> dict:
    path = root / 'docs/downloads' / card['submission_file']
    zip_path = root / 'docs/downloads' / card['submission_zip']
    # Path traversal and accidental alternate artifact validation must fail.
    download_root = (root / 'docs/downloads').resolve()
    if path.resolve().parent != download_root or zip_path.resolve().parent != download_root:
        raise ValueError('Artifact path escapes the download directory')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != card['raster_sha256']:
        raise ValueError('The shipped TIFF differs from the run card hash')
    # Pin the reference pixels too: a shifted/empty/tampered footprint must not
    # let a damaged submission pass merely because its metadata look plausible.
    reference_dir = data_dir or root / 'data/raw'
    manifest = json.loads((root / 'registry/data_manifest.json').read_text())
    references = {entry['id']: entry for entry in manifest['files']}
    for identifier in ('sample_submission', 'existing_faults'):
        entry = references[identifier]
        reference = reference_dir / entry['dest']
        if not reference.is_file() or hashlib.sha256(reference.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Reference mirror hash mismatch: {identifier}; restore pinned inputs before inspection')
    grid = load_grid(reference_dir)
    report = validate(path, grid.footprint, grid.catalogue)
    template = gates.format_report(path, (data_dir or root / 'data/raw') / 'sample_submission.tif',
                                   footprint=grid.footprint)
    with zipfile.ZipFile(zip_path) as z:
        zip_names_ok = z.namelist() == [path.name]
        zip_bytes_ok = zip_names_ok and z.read(path.name) == path.read_bytes()
        zip_crc_ok = z.testzip() is None
    with rasterio.open(path) as src:
        a = src.read(1)
        decoded = hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
    if decoded != card['decoded_raster_sha256']:
        raise ValueError('Decoded pixel hash differs from the run card')
    format_ok = bool(report['all_checks_passed'] and template['ok'] and zip_names_ok and zip_bytes_ok and zip_crc_ok)
    # A technical preflight cannot approve a scientific negative. The current
    # run explicitly has no final dot placement, no registry clearance, and no
    # authenticated weekly-cap receipt. No command line override is provided.
    reasons = list(card.get('reasons', []))
    # This completed run has a permanent scientific stop. Do not trust mutable
    # JSON booleans as evidence of a real authenticated selector/cap receipt.
    # General-purpose promotion is deliberately unsupported in this checker.
    permitted = False
    if card.get('safe_to_submit') is True or card.get('verdict') != 'negative':
        reasons.append('Frozen negative checker refuses edited approval flags; no authenticated selector receipt is verified here.')
    return dict(local_format_valid=format_ok, safe_to_submit=permitted,
                reference_mirror_hashes_match=True,
                no_nan_inside_footprint=report['checks']['in_footprint_all_finite'],
                range_0_1=report['checks']['range_0_1_guaranteed'],
                crs_shape_transform_match=bool(template['ok']),
                zip_contains_exactly_one_matching_tiff=bool(zip_names_ok and zip_bytes_ok and zip_crc_ok),
                raster_sha256=digest, decoded_raster_sha256=decoded,
                validator=report, template_report=template,
                submission_name=card['submission_name'], note=card['submission_note'],
                note_length=len(card['submission_note']),
                approved_for_weekly_slot=permitted,
                decision='DO NOT SUBMIT', authorization_scope='Frozen negative: no promotion path or JSON-flag override',
                reasons=reasons, submission_slots_used=card['submission_slots_used'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format-only', action='store_true')
    parser.add_argument('--output', default='docs/evidence/independent_validation.json')
    args = parser.parse_args()
    card = json.loads((ROOT / 'docs/evidence/run_card.json').read_text())
    result = check_bundle(card)
    write_json(ROOT / args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['local_format_valid'] and (args.format_only or result['safe_to_submit']) else 2


if __name__ == '__main__':
    raise SystemExit(main())
