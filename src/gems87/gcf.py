"""H87-GCF: paired opposite-sign gravity-curvature flanks.

Candidate input: isostatic gravity anomaly (band 13) only.
A fault-like basement step produces a bipolar curvature couplet. The pixel
between opposite-sign Laplacian flanks is scored; a smooth ramp with high
|gradient| but no couplet is suppressed. No catalogue input.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import ndimage as ndi

ORIENTATIONS = ((1.0, 0.0), (0.0, 1.0),
                (2 ** -0.5, 2 ** -0.5), (2 ** -0.5, -(2 ** -0.5)))
SMOOTH_PX = 2.0
OFFSET_PX = 3.0
GUARD_PX = 16


def shifted(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    return ndi.shift(a, (dy, dx), order=1, mode='nearest', prefilter=False)


def gravity_curvature_flanks(grav: np.ndarray, footprint: np.ndarray,
                             log: Callable[[str], None] = lambda _: None) -> tuple[dict[str, np.ndarray], dict]:
    g = np.asarray(grav, np.float32)
    fp = np.asarray(footprint, bool)
    if g.ndim != 2 or g.shape != fp.shape or not fp.any():
        raise ValueError('Gravity and nonempty footprint must share a 2D grid')
    good = fp & np.isfinite(g) & (np.abs(g) < 1e30)
    if good.sum() < 100:
        raise ValueError('Insufficient gravity support')
    padded = ndi.distance_transform_edt(np.pad(good, 1, constant_values=False))
    usable = good & (padded[1:-1, 1:-1] > GUARD_PX)
    del padded
    if not usable.any():
        raise ValueError('No support after the preregistered missing-data guard')
    med = float(np.median(g[good]))
    scale = max(float(np.median(np.abs(g[good] - med))) * 1.4826, 1e-6)
    filled = (np.where(good, g, med) - med) / scale
    smooth = ndi.gaussian_filter(filled, SMOOTH_PX, mode='nearest')
    del filled
    lap = ndi.laplace(smooth, mode='nearest')
    shape = g.shape
    pair = np.zeros(shape, np.float32)
    energy = np.zeros(shape, np.float32)
    for index, (ny, nx) in enumerate(ORIENTATIONS):
        left = shifted(lap, OFFSET_PX * ny, OFFSET_PX * nx)
        right = shifted(lap, -OFFSET_PX * ny, -OFFSET_PX * nx)
        opposite = np.maximum(-left * right, 0.0)
        amp = np.abs(left) + np.abs(right)
        np.maximum(pair, opposite, out=pair)
        np.maximum(energy, amp, out=energy)
        log(f'GCF orientation {index + 1}/{len(ORIENTATIONS)} complete')
        del left, right, opposite, amp
    ref = max(float(np.median(energy[usable])), 1e-8)
    reliability = energy / (energy + ref)
    score = np.sqrt(pair) * reliability
    out = {
        'gcf': np.zeros(shape, np.float32),
        'curvature_pair': np.zeros(shape, np.float32),
        'curvature_energy': np.zeros(shape, np.float32),
        'flank_reliability': np.zeros(shape, np.float32),
    }
    out['curvature_pair'][usable] = pair[usable]
    out['curvature_energy'][usable] = energy[usable]
    out['flank_reliability'][usable] = reliability[usable]
    out['gcf'][usable] = score[usable]
    for key in ('gcf', 'curvature_pair', 'curvature_energy'):
        peak = float(out[key][usable].max())
        if peak <= 0:
            raise ValueError(f'Degenerate {key} surface')
        out[key] /= peak
    for key, value in out.items():
        if not np.isfinite(value).all() or (value < 0).any() or (value > 1 + 1e-6).any():
            raise ValueError(f'Unexpected feature range for {key}')
        np.clip(value, 0, 1, out=value)
        value[~fp] = 0
    return out, dict(
        hypothesis='H87-GCF', physical_input_band=13, input='iso_grav_anom',
        catalogue_derived_features=[], catalogue_inputs_accepted=False,
        orientations_yx=[list(x) for x in ORIENTATIONS],
        smooth_px=SMOOTH_PX, offset_px=OFFSET_PX, guard_px=GUARD_PX,
        raw_available_pixels=int(good.sum()), usable_pixels=int(usable.sum()),
        unsupported_footprint_pixels=int((fp & ~usable).sum()),
        gravity_median=med, gravity_robust_scale=scale, curvature_energy_median=ref,
        ranking='sqrt(max(-L_left*L_right,0)) * energy reliability; label-free max-normalization',
    )
