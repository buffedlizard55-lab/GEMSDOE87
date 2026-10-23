"""H87-LWD: magnetic tilt local-wavenumber contact locator.

Physical inputs to the candidate are cached TMI horizontal-gradient magnitude
(band 3) and TMI vertical gradient (band 9) only. No catalogue, labels,
previous prediction raster, or fitted hyperparameter is accepted.

Tilt angle (Miller & Singh 1994): TDR = arctan(VDR / THDR) with THDR >= 0.
Local wavenumber (Thurston & Smith 1997 SPI): k = |grad(TDR)|. Maxima sit over
2-D contacts independently of magnetization direction. The ranking is
k * analytic-signal reliability. A continuous 1/k field is NOT treated as SPI
depth; depth is only defined at k peaks and is not this candidate.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import ndimage as ndi

from gems87.features import bounded_control, load_band, sha256

GAUSSIAN_PX = 1.0
GUARD_PX = 8
EPS = 1e-8


def tilt_local_wavenumber(hg: np.ndarray, vg: np.ndarray, footprint: np.ndarray,
                          log: Callable[[str], None] = lambda _: None) -> tuple[dict[str, np.ndarray], dict]:
    """Return bounded finite diagnostic channels and the LWD confidence surface."""
    hg = np.asarray(hg, np.float32)
    vg = np.asarray(vg, np.float32)
    fp = np.asarray(footprint, bool)
    if hg.shape != vg.shape or hg.shape != fp.shape or hg.ndim != 2 or not fp.any():
        raise ValueError('HG, VG and nonempty footprint must share a 2D grid')
    good = (fp & np.isfinite(hg) & np.isfinite(vg)
            & (np.abs(hg) < 1e30) & (np.abs(vg) < 1e30) & (hg >= 0))
    if good.sum() < 100:
        raise ValueError('Insufficient magnetic-derivative support')
    padded = ndi.distance_transform_edt(np.pad(good, 1, constant_values=False))
    usable = good & (padded[1:-1, 1:-1] > GUARD_PX)
    del padded
    if not usable.any():
        raise ValueError('No support after the preregistered missing-data guard')

    hg_f = np.where(good, hg, 0.0)
    vg_f = np.where(good, vg, 0.0)
    hg_s = ndi.gaussian_filter(hg_f, GAUSSIAN_PX, mode='nearest')
    vg_s = ndi.gaussian_filter(vg_f, GAUSSIAN_PX, mode='nearest')
    del hg_f, vg_f
    # Miller & Singh tilt: arctan(VDR / THDR), THDR is nonnegative HGM.
    tilt = np.arctan2(vg_s, hg_s + EPS)
    as_amp = np.hypot(hg_s, vg_s)
    dty, dtx = np.gradient(tilt)
    k = np.hypot(dty, dtx).astype(np.float32)
    del dty, dtx, hg_s, vg_s
    energy = max(float(np.median(as_amp[usable])), EPS)
    reliability = (as_amp / (as_amp + energy)).astype(np.float32)
    # High where tilt crosses zero (contact locator complementary to k).
    tilt_zero = (1.0 - np.abs(tilt) / (np.pi / 2.0)).astype(np.float32)
    np.clip(tilt_zero, 0, 1, out=tilt_zero)
    score = (k * reliability).astype(np.float32)

    names = ('lwd', 'local_wavenumber', 'analytic_signal', 'tilt_zero', 'tilt_reliability')
    out = {n: np.zeros(hg.shape, np.float32) for n in names}
    out['local_wavenumber'][usable] = k[usable]
    out['analytic_signal'][usable] = as_amp[usable]
    out['tilt_zero'][usable] = tilt_zero[usable]
    out['tilt_reliability'][usable] = reliability[usable]
    out['lwd'][usable] = score[usable]
    del k, as_amp, tilt_zero, reliability, score, tilt

    for key in ('local_wavenumber', 'analytic_signal', 'lwd'):
        peak = float(out[key][usable].max())
        if peak <= 0:
            raise ValueError(f'Degenerate {key} surface')
        out[key] /= peak
    for key, value in out.items():
        if not np.isfinite(value).all() or (value < 0).any() or (value > 1 + 1e-6).any():
            raise ValueError(f'Unexpected feature range for {key}')
        np.clip(value, 0, 1, out=value)
        value[~fp] = 0
    log('LWD tilt local-wavenumber surface complete')
    return out, dict(
        hypothesis='H87-LWD',
        physical_input_bands=[3, 9],
        inputs=['tmi_hg', 'tmi_vg'],
        catalogue_derived_features=[],
        catalogue_inputs_accepted=False,
        gaussian_px=GAUSSIAN_PX,
        guard_px=GUARD_PX,
        tilt_definition='atan2(VDR, THDR) with THDR = supplied nonnegative TMI HGM',
        local_wavenumber_definition='hypot(d(tilt)/drow, d(tilt)/dcol) in radians/pixel',
        ranking='k * AS/(AS+median_AS) then label-free max-normalization; not probability',
        raw_available_pixels=int(good.sum()),
        usable_pixels=int(usable.sum()),
        unsupported_footprint_pixels=int((fp & ~usable).sum()),
        analytic_signal_median=energy,
        references=[
            'Miller, H.G. & Singh, V., 1994, Potential field tilt — a new concept for location of potential field sources, Geophysics 59, 446–453, doi:10.1190/1.1443674',
            'Thurston, J.B. & Smith, R.S., 1997, Automatic conversion of magnetic data to depth, dip, and susceptibility contrast using the SPI method, Geophysics 62, 807–813, doi:10.1190/1.1444190',
            'Grauch, V.J.S., Hudson, M.R. & Minor, S.A., 2001, Aeromagnetic expression of faults that offset basin fill, Albuquerque basin, New Mexico, Geophysics 66, 707–720, doi:10.1190/1.1444961',
        ],
    )


def session_controls(root, footprint) -> dict[str, np.ndarray]:
    """Label-free physical controls. Gravity HGM uses absolute signed gradient."""
    fp = np.asarray(footprint, bool)
    mag = bounded_control(load_band(root, 3), fp)
    grav = bounded_control(np.abs(np.array(load_band(root, 18), dtype=np.float32)), fp)
    topo = bounded_control(load_band(root, 19), fp)
    return dict(magnetic_hgm_control=mag, gravity_hgm_control=grav,
                topographic_slope_control=topo)
