#!/usr/bin/env python3
"""Build the session-2 PGF candidate TIF (experiment 1 surface, binary dots).

Values are exactly {0,1}: finite, in [0,1], zero outside the footprint, zero
on the mapped catalogue, no nodata tag — the range class that the portal
rejects ("Predicted values must be in range [0,1]") cannot occur. Uses the
shared gems57 submission writer; verdict is recorded in run_card_session2.json
and is NOT a slot authorization.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor'), str(ROOT / 'src')]
from gems57 import emit
from gems57.grid import load_grid
from gems57.submission_writer import write_submission
from gems87.features import load_band
from gems87.features_pgf import pgf

NAME = 'gems87-pgf1-37654dots-20261023.tif'
NOTE = 'H87-PGF paired gravity-curvature flanks, 37654 dots; holdout beats ctrl point est, paired CI incl 0; research candidate'


def main() -> int:
    assert len(NOTE) <= 140, len(NOTE)
    grid = load_grid(ROOT / 'data/raw')
    fp, cat = grid.footprint, grid.catalogue
    feats, meta = pgf(load_band(ROOT, 13), fp)
    allowed = fp & ~cat
    ranking, _ = emit.emit_decimated(feats['pgf'], allowed, tile_px=3)
    dots = emit.emit_prefix(ranking, 37_654)
    pred = dots.astype(np.float32)
    assert set(np.unique(pred)) <= {0.0, 1.0}
    out = ROOT / 'docs/downloads' / NAME
    receipt = write_submission(out, pred, ROOT / 'data/raw/sample_submission.tif',
                               fp, note=NOTE, name=NAME.replace('.tif', ''),
                               catalogue=cat, metadata=dict(meta=meta, dots=int(dots.sum())))
    # Registry uniqueness vs the sparse H33 reference raster (sha-pinned in session 1).
    import rasterio
    with rasterio.open(ROOT / '.cache/registry87/h33.tif') as src:
        h33 = src.read(1) > 0
    dil = ndi.binary_dilation(h33, iterations=3)
    my_in = float((dots & dil).sum() / max(dots.sum(), 1))
    their_in = float((h33 & ndi.binary_dilation(dots, iterations=3)).sum() / max(h33.sum(), 1))
    inter = int((dots & h33).sum()); union = int((dots | h33).sum())
    a, b = dots.ravel().astype(float), h33.ravel().astype(float)
    phi = float(np.corrcoef(a, b)[0, 1])
    uniq = dict(reference='GEMSDOE32 h33-2-b2-zeros (registry sha256 c55bafc470054e82…)',
                reference_dots=int(h33.sum()), my_dots=int(dots.sum()),
                frac_my_dots_within_3px_of_theirs=my_in,
                frac_their_dots_within_3px_of_mine=their_in,
                jaccard_dot_sets=inter / max(union, 1), binary_pearson_phi=phi,
                duplicate_by_overlap_gt_0p70=bool(my_in > 0.70),
                duplicate_by_corr_gt_0p90=bool(abs(phi) > 0.90),
                saturated_continuous_witness_note='57GEMSDOE continuous raster covers all allowed cells; literal any-raster 3px rule is unsatisfiable for any non-empty file (flagged IR, session 1). Like-for-like sparse comparison above.')
    (ROOT / 'evidence/registry_pgf.json').write_text(json.dumps(uniq, indent=2) + '\n')
    print(json.dumps(uniq, indent=2))
    print('WROTE', out, hashlib.sha256(out.read_bytes()).hexdigest())
    print(json.dumps(receipt, indent=2)[:800])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
