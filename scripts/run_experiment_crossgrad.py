#!/usr/bin/env python3
"""Run the H87-CROSSGRAD experiment; independent lane from H87-BMTD."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'vendor')]

import numpy as np
from gems57.grid import load_grid
from gems87.features_crossgrad import crossgrad, bounded_control, load_band, sha256
from gems87.experiment_crossgrad import evaluate_features, write_json


EXPERIMENT_ID = 'H87-CROSSGRAD-01'
ARM = 'crossgrad_dots'
SURFACE_ARM = 'crossgrad_continuous_diagnostic'
CONTROL_NAMES = ('gravity_hg_control', 'magnetic_hg_control', 'topographic_slope_control')


def verify_template():
    pin = json.loads((ROOT / 'registry/template_pin.json').read_text())
    for name, metadata in pin['files'].items():
        if sha256(ROOT / 'vendor/gems57' / name) != metadata['sha256']:
            raise ValueError(f'Shared template changed: {name}; do not fork it locally')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features-only', action='store_true')
    args = parser.parse_args()
    verify_template()

    cache = ROOT / 'data/derived/h87_crossgrad'
    cache.mkdir(parents=True, exist_ok=True)

    with (cache / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

        budget_path = ROOT / 'evidence/budget_crossgrad.json'
        prereg_path = ROOT / 'registry/preregistration.json'
        prereg_hash = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
        now = datetime.now(timezone.utc)

        if budget_path.exists():
            budget = json.loads(budget_path.read_text())
            if budget['preregistration_sha256'] != prereg_hash:
                raise ValueError('Preregistration changed during the experiment')
        else:
            budget = dict(
                experiment_id=EXPERIMENT_ID,
                experiments_used=1,
                experiments_allowed=3,
                started_utc=now.isoformat(),
                maximum_hours=2,
                preregistration_sha256=prereg_hash,
                status='running'
            )
            write_json(budget_path, budget)

        start = datetime.fromisoformat(budget['started_utc'])
        if (now - start).total_seconds() >= 7200:
            raise RuntimeError('Two-hour scientific budget exhausted')

        grid = load_grid(ROOT / 'data/raw')
        meta_path = ROOT / 'evidence/feature_build_crossgrad.json'

        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta['algorithm_sha256'] != sha256(ROOT / 'src/gems87/features_crossgrad.py'):
                raise ValueError('Cached features belong to a different implementation')
            features = {}
            for name, item in meta['outputs'].items():
                path = ROOT / item['file']
                if sha256(path) != item['sha256']:
                    raise ValueError(f'Feature pin changed: {name}')
                features[name] = np.load(path, mmap_mode='r')
        else:
            t0 = time.time()
            grav = load_band(ROOT, 13)  # iso_grav_anom
            mag = load_band(ROOT, 2)    # rtp
            features, meta = crossgrad(grav, mag, grid.footprint,
                                        log=lambda s: print(s, flush=True))

            # Controls
            features['gravity_hg_control'] = bounded_control(load_band(ROOT, 18), grid.footprint)  # iso_grav_anom_hg
            features['magnetic_hg_control'] = bounded_control(load_band(ROOT, 3), grid.footprint)   # tmi_hg
            features['topographic_slope_control'] = bounded_control(load_band(ROOT, 19), grid.footprint)  # det_elev_slope

            outputs = {}
            for name, values in features.items():
                path = cache / (name + '.npy')
                np.save(path, values.astype(np.float32, copy=False))
                outputs[name] = dict(file=str(path.relative_to(ROOT)), sha256=sha256(path))

            meta.update(
                outputs=outputs,
                seconds=time.time() - t0,
                source='H87-CROSSGRAD: gravity-magnetic cross-gradient; no catalogue inputs',
                algorithm_sha256=sha256(ROOT / 'src/gems87/features_crossgrad.py')
            )
            write_json(meta_path, meta)

        print('Feature construction verified', flush=True)

        if not args.features_only:
            result_path = ROOT / 'evidence/holdout_crossgrad.json'
            if result_path.exists():
                print('Existing holdout receipt retained; not refitted.', flush=True)
            else:
                result = evaluate_features(features, grid.footprint, grid.catalogue,
                                           log=lambda s: print(s, flush=True))
                result['experiment_id'] = budget['experiment_id']
                result['generated_utc'] = datetime.now(timezone.utc).isoformat()
                write_json(result_path, result)
                write_json(ROOT / 'docs/evidence/holdout_crossgrad.json', result)

            budget.update(
                status='holdout-complete-awaiting-registry-stop-gate',
                elapsed_seconds=(datetime.now(timezone.utc) - start).total_seconds(),
                submission_slots_used=0,
                selector_invoked=False
            )
            write_json(budget_path, budget)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())