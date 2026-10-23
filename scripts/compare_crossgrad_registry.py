#!/usr/bin/env python3
"""Targeted lane-drift check for the H87-CROSSGRAD artifacts.

The protocol's uniqueness rule is: stop if rank correlation with any registry
raster exceeds 0.90, or if more than 70% of my dots fall within 3 px of one
registry raster's dots. Running that against all 1,193 restored rasters is a
multi-hour job, so this script checks the ones whose recorded filenames show
they target the *same physical transform family* as this lane, plus the
saturated witness and the strongest known sparse priors.

Scope honesty: a pass here is NOT global clearance. `complete_accessible_scan`
is false (one malformed registry TIFF), and un-named priors are not compared.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'vendor'), str(ROOT / 'src')]

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation
from scipy.stats import rankdata

from gems57.grid import load_grid, TRANSFORM
from gems57.metric import RADIUS_PX

# Substring filters over the recorded source paths. Deliberately broad: anything
# whose filename mentions this lane's transform family is treated as a prior.
FAMILY_FILTERS = ('crossgrad', 'cross-grad', 'xgrad', 'gravmag', 'crosslayer',
                  'crossdrain', 'crosscut', 'cross-family')
# Priors the earlier sessions already compared against; kept for continuity.
EXTRA_SOURCES = (
    'GEMSDOE32:',      # H33 educational reference (37,654-dot sparse field)
    '57GEMSDOE:docs/downloads/h57-continuous-anatomy-20261009T201252Z-f44b207a70f0.tif',
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def near(support: np.ndarray, radius: float = RADIUS_PX) -> np.ndarray:
    r = int(np.ceil(radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return binary_dilation(support, structure=yy * yy + xx * xx <= radius * radius)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--index', default='evidence/registry_refreshed.json')
    ap.add_argument('--out', default='evidence/h87crossgrad/registry_check.json')
    args = ap.parse_args()

    grid = load_grid(ROOT / 'data/raw')
    fp = np.asarray(grid.footprint, bool)

    card = json.loads((ROOT / 'evidence/h87crossgrad/run_card.json').read_text())
    candidates = {
        'dots': ROOT / 'docs/downloads' / card['submission_file'],
        'continuous': ROOT / 'docs/downloads' / card['archived_secondary_artifact']['submission_file'],
    }
    mine = {}
    for label, path in candidates.items():
        with rasterio.open(path) as src:
            a = src.read(1)
            if src.shape != fp.shape or src.crs is None or src.crs.to_epsg() != 32611:
                raise SystemExit(f'{path.name}: grid/CRS mismatch')
            if tuple(src.transform)[:6] != tuple(TRANSFORM)[:6]:
                raise SystemExit(f'{path.name}: transform mismatch')
        a = np.where(np.isfinite(a), a, 0.0).astype(np.float32)
        a[~fp] = 0.0
        mine[label] = a
        print(f'{label}: {(a > 0).sum():,} positive pixels', flush=True)

    # Candidate ranks computed once over the footprint.
    base = mine['continuous'][fp]
    base_ranks = rankdata(base).astype(np.float64)
    base_ranks -= base_ranks.mean()
    base_norm = float(np.linalg.norm(base_ranks))
    dot_support = mine['dots'] > 0
    dot_near = near(dot_support)

    index = json.loads((ROOT / args.index).read_text())
    selected = []
    for record in index['rasters']:
        blob = ' '.join(record['sources'])
        if any(f in blob.lower() for f in FAMILY_FILTERS) or any(s in blob for s in EXTRA_SOURCES):
            selected.append(record)
    print(f'selected {len(selected)} family/continuity priors of {len(index["rasters"])}', flush=True)

    rows, errors = [], []
    for record in selected:
        path = ROOT / record['cache_file']
        label = record['sources'][0]
        try:
            if not path.is_file():
                raise FileNotFoundError('registry cache file missing')
            if sha256(path) != record['sha256']:
                raise ValueError('registry content hash mismatch')
            with rasterio.open(path) as src:
                if src.count != 1 or src.shape != fp.shape:
                    raise ValueError(f'grid mismatch {src.shape} count={src.count}')
                if src.crs is None or src.crs.to_epsg() != 32611:
                    raise ValueError('CRS mismatch')
                if tuple(src.transform)[:6] != tuple(TRANSFORM)[:6]:
                    raise ValueError('transform mismatch')
                theirs = src.read(1).astype(np.float32)
        except (OSError, ValueError, rasterio.errors.RasterioError) as exc:
            errors.append(dict(submission=label, error=f'{type(exc).__name__}: {exc}'))
            print(f'  ERROR {label}: {exc}', flush=True)
            continue

        theirs = np.where(np.isfinite(theirs), theirs, 0.0)
        theirs[~fp] = 0.0
        tv = theirs[fp]
        support = (theirs > 0) & fp
        rho = None
        if base_norm > 0 and np.ptp(tv) > 0:
            tr = rankdata(tv).astype(np.float64)
            tr -= tr.mean()
            norm = float(np.linalg.norm(tr))
            if norm > 0:
                rho = float(np.dot(base_ranks, tr) / (base_norm * norm))
        their_near = near(support) if support.any() else None
        forward = float(their_near[dot_support].mean()) if (support.any() and dot_support.any()) else 0.0
        reverse = float(dot_near[support].mean()) if (support.any() and dot_support.any()) else 0.0
        union = int(dot_support.sum() + support.sum() - (dot_support & support).sum())
        jaccard = float((dot_support & support).sum() / union) if union else 0.0
        row = dict(
            submission=label,
            repo=record['repo_first'],
            file=record['cache_file'],
            their_positive_pixels=int(support.sum()),
            support_fraction=float(support.sum() / fp.sum()),
            spearman_full_footprint=rho,
            my_dots_within_3px_of_theirs=forward,
            their_dots_within_3px_of_mine=reverse,
            jaccard_dot_sets=jaccard,
            identical_bytes=bool(sha256(path) == sha256(candidates['dots'])),
            duplicate_by_rho=bool(rho is not None and rho > 0.90),
            duplicate_by_overlap=bool(forward > 0.70),
        )
        rows.append(row)
        print(f'  rho={rho if rho is None else round(rho, 6)}  forward={forward:.4f}  '
              f'reverse={reverse:.4f}  jaccard={jaccard:.4f}  {label[:78]}', flush=True)

    rho_rows = [r for r in rows if r['spearman_full_footprint'] is not None]
    worst_rho = max(rho_rows, key=lambda r: r['spearman_full_footprint'], default=None)
    worst_forward = max(rows, key=lambda r: r['my_dots_within_3px_of_theirs'], default=None)
    duplicates = [r for r in rows if r['duplicate_by_rho'] or r['duplicate_by_overlap']
                  or r['identical_bytes']]

    result = dict(
        evidence_class='REGISTRY-MEASUREMENT',
        generated_utc=__import__('datetime').datetime.now(
            __import__('datetime').timezone.utc).isoformat(),
        candidate_dots=card['submission_file'],
        candidate_dots_sha256=card['raster_sha256'],
        candidate_continuous=card['archived_secondary_artifact']['submission_file'],
        candidate_continuous_sha256=card['archived_secondary_artifact']['raster_sha256'],
        scope=('Targeted check of every restored registry raster whose recorded source path '
               'names this transform family, plus the continuity priors already used in '
               'earlier sessions. NOT a full-inventory clearance.'),
        priors_selected=len(selected),
        priors_compared=len(rows),
        priors_errored=len(errors),
        errors=errors,
        thresholds=dict(spearman=0.90, forward_overlap_3px=0.70),
        worst_spearman=worst_rho['spearman_full_footprint'] if worst_rho else None,
        worst_spearman_submission=worst_rho['submission'] if worst_rho else None,
        worst_forward_overlap=worst_forward['my_dots_within_3px_of_theirs'] if worst_forward else None,
        worst_forward_overlap_submission=worst_forward['submission'] if worst_forward else None,
        duplicate_count=len(duplicates),
        duplicate_by_literal_rule=bool(duplicates),
        full_registry_clearance_claimed=False,
        rows=rows,
    )
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f'\nworst rho={result["worst_spearman"]}  worst forward overlap={result["worst_forward_overlap"]}')
    print(f'duplicates under the literal rule: {len(duplicates)}')
    print(f'wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
