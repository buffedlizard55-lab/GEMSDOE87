#!/usr/bin/env python3
"""Generate H87-CROSSGRAD research GeoTIFF (continuous surface and binary dots)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'vendor')]

import numpy as np
import rasterio
from gems57.grid import load_grid, TRANSFORM
from gems57 import emit, gates
from gems57.submission_writer import write_submission
from gems87.features_crossgrad import crossgrad, bounded_control, load_band


def main():
    # Load grid and footprint
    grid = load_grid(ROOT / 'data/raw')
    fp = grid.footprint
    catalogue = grid.catalogue

    # Load cached features
    cache = ROOT / 'data/derived/h87_crossgrad'
    features = {}
    for npy in cache.glob('*.npy'):
        name = npy.stem
        features[name] = np.load(npy, mmap_mode='r')

    # Continuous surface - zero on catalogue
    surface = features['crossgrad'].astype(np.float32)
    surface[~fp] = 0
    surface[catalogue] = 0
    surface = np.clip(surface, 0, 1)

    # Binary dots (same budget as H33/H87-BMTD: 37,654)
    full_budget = 37_654
    active = fp & ~catalogue
    ranking, _ = emit.emit_decimated(surface, active, tile_px=3)
    dots = emit.emit_prefix(ranking, full_budget).astype(np.float32)
    dots[~fp] = 0
    dots[catalogue] = 0
    dots = np.clip(dots, 0, 1)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    # Generate continuous surface TIF
    cont_name = f'gems87-crossgrad-continuous-{timestamp}-RESEARCH-DO-NOT-SUBMIT.tif'
    cont_path = ROOT / 'docs/downloads' / cont_name
    cont_zip = cont_path.with_suffix('.zip')

    # Remove existing
    for p in (cont_path, cont_zip):
        if p.exists():
            p.unlink()

    print("Writing continuous surface GeoTIFF...")
    receipt_cont = write_submission(
        path=cont_path,
        prediction=surface,
        sample=ROOT / 'data/raw/sample_submission.tif',
        footprint=fp,
        note='H87 gravity-magnetic cross-gradient continuous; research only; DO NOT SUBMIT',
        name='GEMSDOE87-CROSSGRAD-CONT-01',
        catalogue=catalogue,
        metadata=dict(
            hypothesis='H87-CROSSGRAD',
            experiment_id='H87-CROSSGRAD-01',
            generated_utc=datetime.now(timezone.utc).isoformat(),
            representation='continuous_confidence',
            holdout_dti=0.028277683379447173,
            holdout_ci95=[0.024335868924318563, 0.03250845956873381],
            withheld_positives=60988,
            evaluator_version='gems57-pooled-hide-v2',
        )
    )

    # Generate binary dots TIF
    dots_name = f'gems87-crossgrad-dots-{timestamp}-RESEARCH-DO-NOT-SUBMIT.tif'
    dots_path = ROOT / 'docs/downloads' / dots_name
    dots_zip = dots_path.with_suffix('.zip')

    for p in (dots_path, dots_zip):
        if p.exists():
            p.unlink()

    print("Writing binary dots GeoTIFF...")
    receipt_dots = write_submission(
        path=dots_path,
        prediction=dots,
        sample=ROOT / 'data/raw/sample_submission.tif',
        footprint=fp,
        note='H87 gravity-magnetic cross-gradient binary dots (37,654); research only; DO NOT SUBMIT',
        name='GEMSDOE87-CROSSGRAD-DOTS-01',
        catalogue=catalogue,
        metadata=dict(
            hypothesis='H87-CROSSGRAD',
            experiment_id='H87-CROSSGRAD-01',
            generated_utc=datetime.now(timezone.utc).isoformat(),
            representation='binary_dots',
            budget=full_budget,
            holdout_dti=0.047177285117414834,
            holdout_ci95=[0.03914854847061432, 0.05570285827576389],
            withheld_positives=60988,
            evaluator_version='gems57-pooled-hide-v2',
            paired_vs_magnetic_hg_delta=0.0035043523739134164,
            paired_vs_magnetic_hg_ci95=[-0.007014868684160611, 0.013883642486734413],
            paired_vs_gravity_hg_delta=0.0025764736142117467,
            paired_vs_gravity_hg_ci95=[-0.011157287386068686, 0.015770986599922227],
            paired_vs_topo_slope_delta=0.02474192812111521,
            paired_vs_topo_slope_ci95=[0.01479812215168702, 0.035109612211320786],
        )
    )

    # Verify both TIFs
    for name, path, receipt in [('continuous', cont_path, receipt_cont), ('dots', dots_path, receipt_dots)]:
        with rasterio.open(path) as src:
            written = src.read(1)
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            decoded = hashlib.sha256(np.ascontiguousarray(written).tobytes()).hexdigest()
            print(f"\n{name} TIF:")
            print(f"  File: {path.name}")
            print(f"  SHA256: {sha256}")
            print(f"  Decoded SHA256: {decoded}")
            print(f"  Shape: {written.shape}")
            print(f"  Range: [{written.min():.6f}, {written.max():.6f}]")
            print(f"  Positive pixels: {(written > 0).sum()}")
            print(f"  Catalogue overlap: {((written > 0) & catalogue).sum()}")
            print(f"  Format valid: {receipt['template_report']['ok']}")
            print(f"  Validation: {receipt['validator']['all_checks_passed']}")

    # Format validation
    print("\nRunning format validation...")
    sys.path.insert(0, str(ROOT / 'scripts'))
    from check_submission import check_bundle

    for name, tif_name, zip_name, receipt in [
        ('continuous', cont_name, cont_name.replace('.tif', '.zip'), receipt_cont),
        ('dots', dots_name, dots_name.replace('.tif', '.zip'), receipt_dots)
    ]:
        card = {
            'submission_file': tif_name,
            'submission_zip': zip_name,
            'raster_sha256': hashlib.sha256((ROOT / 'docs/downloads' / tif_name).read_bytes()).hexdigest(),
            'decoded_raster_sha256': hashlib.sha256(np.ascontiguousarray(rasterio.open(ROOT / 'docs/downloads' / tif_name).read(1)).tobytes()).hexdigest(),
            'submission_name': receipt['submission_name'],
            'submission_note': receipt['note'],
            'submission_slots_used': 0,
            'reasons': [],
            'verdict': 'research',
            'safe_to_submit': False,
        }
        val_result = check_bundle(card)
        print(f"{name}: format_ok={val_result['local_format_valid']}, safe_to_submit={val_result['safe_to_submit']}")

    print(f"\nGenerated research TIFs:")
    print(f"  Continuous: {cont_path}")
    print(f"  Binary dots: {dots_path}")
    print("\nNOTE: These are RESEARCH artifacts. DO NOT SUBMIT to competition.")
    print("The crossgrad detector does not demonstrate statistically significant improvement")
    print("over the best physical controls (paired CI vs magnetic_hg includes zero).")
    print("The continuous surface will fail the literal uniqueness gate due to a")
    print("saturated registry witness covering all allowed pixels.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())