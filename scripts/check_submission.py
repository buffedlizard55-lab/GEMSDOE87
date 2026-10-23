#!/usr/bin/env python3
"""Independent, automated re-read of the downloadable TIFF and single-TIFF ZIP.

Exit 0 for valid local FORMAT with --format-only, or exit 0 without --format-only
ONLY when BOTH format checks AND on-disk holdout, leakage-canary, and registry
uniqueness receipts pass independently. Never trusts bare JSON booleans alone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor'), str(ROOT / 'src')]
import numpy as np
import rasterio
from gems57 import gates
from gems57.grid import load_grid
from gems57.validate import validate
from scripts.validate_submission import _distinct_output_path, _write_json_report


def _verify_promoted_receipts(card: dict, root: Path, digest: str, decoded: str) -> tuple[bool, list[str]]:
    """Independently verify on-disk scientific & novelty receipts for promoted G87-CSCT."""
    reasons: list[str] = []
    try:
        canary = json.loads((root / 'evidence/e0_leakage_canary.json').read_text())
        holdout = json.loads((root / 'evidence/e1_e2_e3_holdout_results.json').read_text())
        uniq = json.loads((root / 'evidence/uniqueness_audit_full.json').read_text())
        val = json.loads((root / 'evidence/validation_receipt.json').read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f'Missing or unreadable scientific receipt: {exc}']

    for sk in ('seed_20', 'seed_30'):
        if canary.get(sk, {}).get('any_leakage') is not False or canary.get(sk, {}).get('max_symmetric_auc', 1.0) > 0.90:
            reasons.append(f'Leakage canary failed on {sk}')
    scores = holdout.get('dual_seed_pooled', {}).get('scores', {})
    e3 = scores.get('E3_CSCT_DINKELBACH', {}).get('dti', 0.0)
    ctrl = max(scores.get('CTRL_TOPO', {}).get('dti', 1.0), scores.get('HIST_D28', {}).get('dti', 1.0))
    if not (e3 > ctrl and e3 > 0.206817):
        reasons.append('Holdout improvement gate failed on E3_CSCT_DINKELBACH')
    if not uniq.get('pre_placement_surface_gate', {}).get('passed') or not uniq.get('post_placement_discriminating_dot_gate', {}).get('passed'):
        reasons.append('Registry novelty gate failed')
    val_sha = (val.get('primary_zeros_tif') or {}).get('sha256') or val.get('zeros_sha256')
    if val_sha != digest or uniq.get('decoded_raster_sha256') != decoded:
        reasons.append('Scientific/validation receipts are not bound to the current GeoTIFF hash')
    if len(card.get('submission_note', '')) > 140:
        reasons.append('Submission note exceeds 140 characters')
    return (len(reasons) == 0), reasons


def check_bundle(card: dict, root: Path = ROOT, data_dir: Path | None = None) -> dict:
    path = root / 'docs/downloads' / card['submission_file']
    zip_path = root / 'docs/downloads' / card['submission_zip']
    download_root = (root / 'docs/downloads').resolve()
    if path.resolve().parent != download_root or zip_path.resolve().parent != download_root:
        raise ValueError('Artifact path escapes the download directory')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != card['raster_sha256']:
        raise ValueError('The shipped TIFF differs from the run card hash')
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
    template = gates.format_report(path, reference_dir / 'sample_submission.tif', footprint=grid.footprint)
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
    reasons = list(card.get('reasons', []))
    permitted = False
    if card.get('verdict') == 'promote' and card.get('safe_to_submit') is True:
        sci_ok, sci_reasons = _verify_promoted_receipts(card, root, digest, decoded)
        if format_ok and sci_ok:
            permitted = True
        else:
            reasons.extend(sci_reasons or ['Format validation failed on promoted candidate'])
    elif card.get('safe_to_submit') is True or card.get('verdict') != 'negative':
        reasons.append('Checker refuses edited approval flags without verified promotion receipts.')

    return dict(
        local_format_valid=format_ok,
        safe_to_submit=permitted,
        reference_mirror_hashes_match=True,
        no_nan_inside_footprint=report['checks']['in_footprint_all_finite'],
        range_0_1=report['checks']['range_0_1_guaranteed'],
        crs_shape_transform_match=bool(template['ok']),
        zip_contains_exactly_one_matching_tiff=bool(zip_names_ok and zip_bytes_ok and zip_crc_ok),
        raster_sha256=digest,
        decoded_raster_sha256=decoded,
        validator=report,
        template_report=template,
        submission_name=card['submission_name'],
        note=card['submission_note'],
        note_length=len(card['submission_note']),
        approved_for_weekly_slot=permitted,
        decision='READY — VALIDATED & SAFE TO DOWNLOAD / SUBMIT' if permitted else 'DO NOT SUBMIT',
        authorization_scope='Independent byte + holdout/canary/uniqueness verification; organizer score still unconfirmed until uploaded',
        reasons=reasons,
        submission_slots_used=card['submission_slots_used'],
    )


def checked_report_output(output: Path, card: dict, root: Path = ROOT) -> Path:
    """A receipt must never overwrite inputs, cards or another existing file."""
    output = output if output.is_absolute() else root / output
    default = root / 'docs/evidence/independent_validation.json'
    if output.suffix.lower() != '.json':
        raise ValueError('The report output must have a .json extension, not a raster/ZIP path')
    if output.is_symlink() or (output.exists() and output.stat().st_nlink != 1):
        raise ValueError('The report output must not be a symbolic/hard-link alias')
    if output.exists() and output.resolve() != default.resolve():
        raise ValueError('Refusing to overwrite an existing file other than the designated validation report')
    protected = [('frozen TIFF', root / 'docs/downloads' / card['submission_file']),
                 ('frozen ZIP', root / 'docs/downloads' / card['submission_zip']),
                 ('run card', root / 'run_card.json'),
                 ('sample', root / 'data/raw/sample_submission.tif'),
                 ('catalogue', root / 'data/raw/existing_faults.tif')]
    return _distinct_output_path(output, protected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format-only', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('docs/evidence/independent_validation.json'),
                        help='New .json receipt path, or the designated default; existing other files are never overwritten')
    args = parser.parse_args()
    card = json.loads((ROOT / 'docs/evidence/run_card.json').read_text())
    try:
        output = checked_report_output(args.output, card)
        result = check_bundle(card)
        _write_json_report(output, json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        print(json.dumps(dict(safe_to_submit=False, inspection_completed=False, errors=[str(exc)]), indent=2))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['local_format_valid'] and (args.format_only or result['safe_to_submit']) else 2


if __name__ == '__main__':
    raise SystemExit(main())
