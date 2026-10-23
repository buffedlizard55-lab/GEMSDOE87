"""H87-PGF: paired opposite-sign gravity-curvature flanks (session 2).

Sole physical candidate input: cached isostatic gravity anomaly (band 13).
For each of 4 axial orientations, the cross-normal second derivative D2
(step 3 px) is sampled 6 px either side of the candidate pixel; a fault-like
basement flexure should show opposite-sign D2 lobes flanking the trace, so the
score is the geometric mean of the opposing lobes (sign-invariant sum of both
polarities). No catalogue, labels, or prior prediction raster is an input.
"""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from .features import shifted, load_band, bounded_control  # reuse, no fork

ORIENTATIONS = ((1.0, 0.0), (0.0, 1.0),
                (2 ** -0.5, 2 ** -0.5), (2 ** -0.5, -(2 ** -0.5)))
D2_STEP_PX = 3.0
FLANK_PX = 6.0
GUARD_PX = 40
SMOOTH_PX = 2.0


def _robust_fill(a, good):
    med = float(np.median(a[good]))
    scale = max(float(np.median(np.abs(a[good] - med))) * 1.4826, 1e-9)
    return (np.where(good, a, med) - med) / scale, med, scale


def pgf(grav, footprint):
    a = np.asarray(grav, np.float32)
    fp = np.asarray(footprint, bool)
    if a.ndim != 2 or a.shape != fp.shape or not fp.any():
        raise ValueError('gravity and nonempty footprint must share a 2D grid')
    good = fp & np.isfinite(a) & (np.abs(a) < 1e30)
    if good.sum() < 100:
        raise ValueError('insufficient gravity support')
    padded = ndi.distance_transform_edt(np.pad(good, 1, constant_values=False))
    usable = good & (padded[1:-1, 1:-1] > GUARD_PX)
    del padded
    filled, med, scale = _robust_fill(a, good)
    g = ndi.gaussian_filter(filled, SMOOTH_PX, mode='nearest')
    del filled
    shape = a.shape
    pair = np.zeros(shape, np.float32)
    d2_abs = np.zeros(shape, np.float32)
    for ty, tx in ORIENTATIONS:
        ny, nx = -tx, ty  # normal = tangent rotated 90 deg
        d2 = (shifted(g, D2_STEP_PX * ny, D2_STEP_PX * nx)
              - 2.0 * g
              + shifted(g, -D2_STEP_PX * ny, -D2_STEP_PX * nx))
        dp = shifted(d2, FLANK_PX * ny, FLANK_PX * nx)
        dm = shifted(d2, -FLANK_PX * ny, -FLANK_PX * nx)
        p = (np.sqrt(np.maximum(dp, 0) * np.maximum(-dm, 0))
             + np.sqrt(np.maximum(-dp, 0) * np.maximum(dm, 0)))
        np.maximum(pair, np.where(usable, p, 0), out=pair)
        np.maximum(d2_abs, np.where(usable, np.abs(d2), 0), out=d2_abs)
        del d2, dp, dm, p
    ref = max(float(np.quantile(pair[usable], 0.99)), 1e-9)
    ref_d2 = max(float(np.quantile(d2_abs[usable], 0.99)), 1e-9)
    out = {
        'pgf_pair_raw': pair,
        'pgf': np.clip(pair / ref, 0, 1).astype(np.float32),
        'pgf_d2_abs': np.clip(d2_abs / ref_d2, 0, 1).astype(np.float32),
    }
    for v in out.values():
        if not np.isfinite(v).all() or (v < 0).any() or (v > 1).any():
            raise ValueError('PGF feature out of [0,1]')
        v[~fp] = 0
    meta = dict(hypothesis='H87-PGF', physical_input_band=13, input='iso_grav_anom',
                catalogue_derived_features=[], orientations_yx=[list(x) for x in ORIENTATIONS],
                d2_step_px=D2_STEP_PX, flank_px=FLANK_PX, guard_px=GUARD_PX,
                smooth_px=SMOOTH_PX, median_grav=med, robust_scale=scale,
                pair_q99=ref, usable_pixels=int(usable.sum()))
    return out, meta
