"""Fold-safe visible-catalogue fracture mechanics & bilateral tip-ray coincidence (`M_Geo`).

STRICT RULE: Every function here accepts ONLY a `visible` boolean mask (never withheld labels).
Computes outward mode-II/III fault-tip propagation lobes, rotationally well-conditioned
2-cut bilateral opposing-tip relay bridge coincidence, flank stress-shadow suppression ratio,
and geodetic GPS strain-accommodation deficit.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, convolve, distance_transform_edt, gaussian_filter

GEO_FEATURE_NAMES_12 = [
    "vis_dist_log",
    "vis_tip_dist_log",
    "tip_ray_short_5",
    "tip_ray_med_11",
    "tip_ray_long_22",
    "bridge_coinc_med_11",
    "bridge_coinc_long_22",
    "flank_suppression_ratio",
    "vis_density_r8",
    "vis_density_r24",
    "vis_strain_deficit",
    "kdmi_x_tip_corroboration",
]

K3 = np.ones((3, 3), dtype=np.int16)


def find_visible_tips_and_rays(visible: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Locate visible trace endpoints & their outward unit propagation vectors `(ey, ex)`.

    At each visible pixel with <= 2 neighbors in `3x3` (excluding isolated 0-neighbor specks),
    the outward unit tangent points strictly AWAY from the local `[ -6..+6 ]` visible trace
    centroid `(cy, cx)` through `(ty, tx)` into unmapped crust.
    """
    vis_u8 = visible.astype(np.int16)
    nb_count = convolve(vis_u8, K3, mode="constant", cval=0) - vis_u8
    tip_mask = visible & (nb_count >= 1) & (nb_count <= 2)
    ty_all, tx_all = np.nonzero(tip_mask)
    if ty_all.size == 0:
        e = np.empty(0, dtype=np.float32)
        return ty_all, tx_all, e, e

    # Local centroid via box/Gaussian weighted coordinate moments (O(H*W), 0.12s vectorized!)
    h, w = visible.shape
    vis_f = visible.astype(np.float32)
    w_mass = gaussian_filter(vis_f, sigma=3.2, mode="constant", cval=0.0)
    ry_w = gaussian_filter(vis_f * np.arange(h, dtype=np.float32)[:, None], sigma=3.2, mode="constant", cval=0.0)
    cx_w = gaussian_filter(vis_f * np.arange(w, dtype=np.float32)[None, :], sigma=3.2, mode="constant", cval=0.0)

    m_at = np.maximum(w_mass[ty_all, tx_all], 1e-6)
    cy = ry_w[ty_all, tx_all] / m_at
    cx = cx_w[ty_all, tx_all] / m_at

    dy = ty_all.astype(np.float32) - cy
    dx = tx_all.astype(np.float32) - cx
    nrm = np.hypot(dy, dx)
    good = nrm > 0.35  # Genuine terminal tip with asymmetric backward trace mass!
    ty = ty_all[good].astype(np.int32)
    tx = tx_all[good].astype(np.int32)
    ey = (dy[good] / nrm[good]).astype(np.float32)
    ex = (dx[good] / nrm[good]).astype(np.float32)
    return ty, tx, ey, ex


def _splat_rays(
    shape: tuple[int, int],
    ty: np.ndarray,
    tx: np.ndarray,
    ey: np.ndarray,
    ex: np.ndarray,
    max_step: int,
    decay_px: float,
    sigma_perp: float,
) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    if ty.size == 0:
        return grid
    h, w = shape
    steps = np.arange(1, max_step + 1, dtype=np.float32)[None, :]  # (1, S)
    rr = np.rint(ty[:, None] + ey[:, None] * steps).astype(np.int32)
    cc = np.rint(tx[:, None] + ex[:, None] * steps).astype(np.int32)
    ww = np.broadcast_to(np.exp(-steps / decay_px).astype(np.float32), rr.shape)
    ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
    np.add.at(grid, (rr[ok], cc[ok]), ww[ok])
    return gaussian_filter(grid, sigma=sigma_perp, mode="nearest").astype(np.float32, copy=False)


def compute_visible_fracture_features_fp(
    visible: np.ndarray,
    fp_idx: np.ndarray,
    geod_strain_fp: np.ndarray,
    kdmi_radon9_fp: np.ndarray,
) -> np.ndarray:
    """Compute `(len(fp_idx), 12)` float32 fracture-mechanics matrix strictly from `visible`."""
    shape = visible.shape
    n_fp = len(fp_idx)
    out = np.empty((n_fp, 12), dtype=np.float32)

    d_vis = distance_transform_edt(~visible).astype(np.float32)
    ty, tx, ey, ex = find_visible_tips_and_rays(visible)

    tip_bin = np.zeros(shape, dtype=bool)
    if ty.size > 0:
        tip_bin[ty, tx] = True
        d_tip = distance_transform_edt(~tip_bin).astype(np.float32)
    else:
        d_tip = np.full(shape, 500.0, dtype=np.float32)

    out[:, 0] = np.log1p(d_vis.ravel()[fp_idx])
    out[:, 1] = np.log1p(d_tip.ravel()[fp_idx])

    ray5 = _splat_rays(shape, ty, tx, ey, ex, max_step=12, decay_px=5.0, sigma_perp=1.5)
    ray11 = _splat_rays(shape, ty, tx, ey, ex, max_step=24, decay_px=11.0, sigma_perp=1.9)
    ray22 = _splat_rays(shape, ty, tx, ey, ex, max_step=36, decay_px=22.0, sigma_perp=2.6)
    out[:, 2] = ray5.ravel()[fp_idx]
    out[:, 3] = ray11.ravel()[fp_idx]
    out[:, 4] = ray22.ravel()[fp_idx]

    # Rotationally balanced 2-cut bilateral opposing-tip relay bridge coincidence
    # Cut 1: North-facing vs South-facing; Cut 2: East-facing vs West-facing
    ns_pos = ey >= 0.0
    ew_pos = ex >= 0.0
    for col_j, max_s, dec, sig in ((5, 26, 11.0, 2.0), (6, 40, 22.0, 2.8)):
        r_n = _splat_rays(shape, ty[ns_pos], tx[ns_pos], ey[ns_pos], ex[ns_pos], max_s, dec, sig)
        r_s = _splat_rays(shape, ty[~ns_pos], tx[~ns_pos], ey[~ns_pos], ex[~ns_pos], max_s, dec, sig)
        r_e = _splat_rays(shape, ty[ew_pos], tx[ew_pos], ey[ew_pos], ex[ew_pos], max_s, dec, sig)
        r_w = _splat_rays(shape, ty[~ew_pos], tx[~ew_pos], ey[~ew_pos], ex[~ew_pos], max_s, dec, sig)
        bridge = np.maximum(np.sqrt(r_n * r_s), np.sqrt(r_e * r_w))
        out[:, col_j] = bridge.ravel()[fp_idx]
        del r_n, r_s, r_e, r_w, bridge

    out[:, 7] = (d_tip / (d_vis + 1.5)).ravel()[fp_idx]
    del d_vis, d_tip, ray5, ray22

    vis_f = visible.astype(np.float32)
    dens8 = gaussian_filter(vis_f, sigma=8.0, mode="constant", cval=0.0)
    dens24 = gaussian_filter(vis_f, sigma=24.0, mode="constant", cval=0.0)
    out[:, 8] = dens8.ravel()[fp_idx]
    d24_fp = dens24.ravel()[fp_idx]
    out[:, 9] = d24_fp
    del vis_f, dens8, dens24

    p95 = float(np.percentile(d24_fp, 95)) + 1e-6
    strain_norm = 1.0 / (1.0 + np.exp(-np.clip((geod_strain_fp - np.median(geod_strain_fp)) / 10.0, -8.0, 8.0)))
    out[:, 10] = strain_norm * (1.0 - np.clip(d24_fp / p95, 0.0, 1.0))

    r11_fp = out[:, 3]
    br11_fp = out[:, 5]
    out[:, 11] = kdmi_radon9_fp * (r11_fp + 1.5 * br11_fp)
    return out
