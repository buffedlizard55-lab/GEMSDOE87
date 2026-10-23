"""H87 bilateral magnetic texture dislocation (BMTD), without fault-map inputs.

The sole physical input to the candidate is cached RTP magnetics (band 2).
The model tests whether tangentially shifting one side of a possible line
restores texture similarity better than leaving it unshifted. This is a
hypothesis about a structural signature, not proof of faulting or permeability.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
from scipy import ndimage as ndi

ORIENTATIONS = ((1.0, 0.0), (0.0, 1.0),
                (2 ** -0.5, 2 ** -0.5), (2 ** -0.5, -(2 ** -0.5)))
SHIFTS_PX = (-4.0, -2.0, 2.0, 4.0)
NORMAL_OFFSET_PX = 3.0
WINDOW_PX = 9
GUARD_PX = 40


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_band(root: Path, number: int) -> np.ndarray:
    receipt = json.loads((root / 'evidence/feature_cache.json').read_text())
    entry = next(e for e in receipt['bands'] if e['band'] == number)
    path = root / entry['cache_file']
    if sha256(path) != entry['sha256']:
        raise ValueError(f'Cached physical band {number} failed its hash pin')
    return np.load(path, mmap_mode='r')


def shifted(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    return ndi.shift(a, (dy, dx), order=1, mode='nearest', prefilter=False)


def moments(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = ndi.uniform_filter(a, WINDOW_PX, mode='nearest')
    v = np.maximum(ndi.uniform_filter(a * a, WINDOW_PX, mode='nearest') - m * m, 0)
    return m, v


def ncc(a: np.ndarray, b: np.ndarray, ma: np.ndarray, va: np.ndarray,
        mb: np.ndarray, vb: np.ndarray) -> np.ndarray:
    covariance = ndi.uniform_filter(a * b, WINDOW_PX, mode='nearest') - ma * mb
    denominator = np.sqrt(va * vb)
    out = np.divide(covariance, denominator, out=np.zeros_like(a), where=denominator > 1e-8)
    return np.clip(out, -1, 1)


def bmtd(rtp: np.ndarray, footprint: np.ndarray,
         log: Callable[[str], None] = lambda _: None) -> tuple[dict[str, np.ndarray], dict]:
    """Return bounded, finite diagnostic features and a confidence surface.

    No catalogue, labels, previous raster, hidden truth, or fitted hyperparameter
    is accepted. A guard excludes filter/interpolation neighborhoods touching
    missing input or the footprint boundary. Unsupported truth remains in the
    evaluation denominator, so missing coverage cannot silently boost recall.
    """
    a = np.asarray(rtp, np.float32)
    fp = np.asarray(footprint, bool)
    if a.ndim != 2 or a.shape != fp.shape or not fp.any():
        raise ValueError('RTP and nonempty footprint must share a 2D grid')
    good = fp & np.isfinite(a) & (np.abs(a) < 1e30)
    if good.sum() < 100:
        raise ValueError('Insufficient magnetic support')
    # Include OUTSIDE THE ARRAY as missing. Without this explicit pad, SciPy's
    # EDT sees only interior zeros and can let edge-replicated texture survive
    # near a footprint touching the GeoTIFF bounds (IR87-016). The archived
    # negative experiment used the pre-fix implementation; it is not rerun.
    padded_distance = ndi.distance_transform_edt(np.pad(good, 1, constant_values=False))
    usable = good & (padded_distance[1:-1, 1:-1] > GUARD_PX)
    del padded_distance
    if not usable.any():
        raise ValueError('No support after the preregistered missing-data guard')
    med = float(np.median(a[good]))
    scale = max(float(np.median(np.abs(a[good] - med))) * 1.4826, 1e-6)
    filled = (np.where(good, a, med) - med) / scale
    texture = ndi.gaussian_filter(filled, 1.0, mode='nearest') - ndi.gaussian_filter(filled, 6.0, mode='nearest')
    del filled
    _, v0 = moments(texture)
    energy_scale = max(float(np.median(v0[usable])), 1e-8)
    del v0
    shape = a.shape
    names = ('dislocation_gain', 'restored_similarity', 'bilateral_balance',
             'texture_reliability', 'bmtd')
    out = {n: np.zeros(shape, np.float32) for n in names}
    for index, (ty, tx) in enumerate(ORIENTATIONS):
        ny, nx = -tx, ty
        side_a = shifted(texture, NORMAL_OFFSET_PX * ny, NORMAL_OFFSET_PX * nx)
        side_b = shifted(texture, -NORMAL_OFFSET_PX * ny, -NORMAL_OFFSET_PX * nx)
        ma, va = moments(side_a)
        mb, vb = moments(side_b)
        base = ncc(side_a, side_b, ma, va, mb, vb)
        best = np.full(shape, -1, np.float32)
        for shift in SHIFTS_PX:
            b = shifted(side_b, shift * ty, shift * tx)
            bm, bv = moments(b)
            c = ncc(side_a, b, ma, va, bm, bv)
            np.maximum(best, c, out=best)
            del b, bm, bv, c
        gain = np.maximum(best - base, 0) * 0.5
        restored = np.maximum(best, 0)
        balance = 2 * np.sqrt(va * vb) / (va + vb + 1e-8)
        min_var = np.minimum(va, vb)
        reliability = min_var / (min_var + energy_scale)
        score = gain * restored * restored * balance * reliability
        for name, values in (('dislocation_gain', gain), ('restored_similarity', restored),
                             ('bilateral_balance', balance), ('texture_reliability', reliability),
                             ('bmtd', score)):
            np.maximum(out[name], np.where(usable, values, 0), out=out[name])
        log(f'BMTD orientation {index + 1}/{len(ORIENTATIONS)} complete')
        del side_a, side_b, ma, va, mb, vb, base, best, gain, restored, balance, min_var, reliability, score
    # This is a bounded confidence index, NOT a calibrated probability.
    # A monotone rescaling raises visualization contrast without consulting labels.
    maximum = float(out['bmtd'][usable].max())
    if maximum <= 0:
        raise ValueError('Degenerate BMTD surface')
    out['bmtd'] /= maximum
    for key, value in out.items():
        if not np.isfinite(value).all() or (value < 0).any() or (value > 1 + 1e-6).any():
            raise ValueError(f'Unexpected feature range for {key}')
        np.clip(value, 0, 1, out=value)  # numerical rounding of analytic [0,1] features only
        value[~fp] = 0
    return out, dict(
        hypothesis='H87-BMTD', physical_input_band=2, input='rtp',
        catalogue_derived_features=[], catalogue_inputs_accepted=False,
        orientations_yx=[list(x) for x in ORIENTATIONS], tangential_shifts_px=list(SHIFTS_PX),
        normal_offset_px=NORMAL_OFFSET_PX, ncc_window_px=WINDOW_PX,
        gaussian_scales_px=[1, 6], guard_px=GUARD_PX,
        raw_available_pixels=int(good.sum()), usable_pixels=int(usable.sum()),
        unsupported_footprint_pixels=int((fp & ~usable).sum()),
        normalization='fixed analytic bounded confidence, divided by label-free in-footprint maximum; not probability calibration',
        median_rtp=med, robust_rtp_scale=scale, texture_variance_reference=energy_scale,
        original_bmtd_max=maximum)


def bounded_control(a: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Monotone physical control scaling; no labels or sample predictions."""
    a = np.asarray(a, np.float32)
    good = np.asarray(footprint, bool) & np.isfinite(a) & (np.abs(a) < 1e30)
    if not good.any():
        raise ValueError('Control has no physical measurements')
    v = np.maximum(a[good], 0)
    scale = max(float(np.quantile(v, 0.99)), 1e-8)
    out = np.zeros_like(a)
    out[good] = np.clip(v / scale, 0, 1)
    return out
