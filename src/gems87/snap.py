"""Controlled AXIS=SNAP operator on Parent R0 (Agent Brief v2).

Moves each R0 dot by <= 2.0 px (<= 200 m) cross-strike onto prominent 1-D edge/scarp
crests computed strictly from organizer-provided `training_features.tif` channels
(no external lidar rasters), holding dot count (37,654), R0 exclusions (`d_cat > 2 px`,
in-footprint, zero on catalogue), and minimum inter-dot spacing (`sqrt(8)` px) fixed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import binary_erosion, uniform_filter

DEFAULT_MAX_RADIUS_PX = 2.0
DEFAULT_MIN_SEP_SQ = 8  # Matches R0's exact d2.8 minimum spacing sqrt(8) = 2.8284 px
DEFAULT_CROSS_STRIKE_COS = 0.80
DEFAULT_COHERENCE_FLOOR = 0.10


def empirical_quantile_map(arr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Exact midrank empirical quantile in (0, 1] on `valid`, `-inf` outside `valid`."""
    arr32 = np.asarray(arr, dtype=np.float32)
    mask = np.asarray(valid, dtype=bool) & np.isfinite(arr32)
    out = np.full(arr32.shape, -np.inf, dtype=np.float32)
    n = int(mask.sum())
    if n == 0:
        return out
    v = arr32[mask]
    sv = np.sort(v)
    lo = np.searchsorted(sv, v, side="left")
    hi = np.searchsorted(sv, v, side="right")
    out[mask] = ((lo + hi + 1) * (0.5 / float(n))).astype(np.float32)
    return out


def isotropic_horizontal_gradient(field: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Central-difference isotropic horizontal gradient magnitude `hypot(df/dx, df/dy)` with 3x3 nodata guard."""
    f = np.asarray(field, dtype=np.float32)
    v = np.asarray(valid, dtype=bool) & np.isfinite(f)
    v_int = binary_erosion(v, structure=np.ones((3, 3), dtype=bool), border_value=False)
    fill_val = float(np.median(f[v])) if v.any() else 0.0
    clean = np.where(v, f, fill_val).astype(np.float32)
    p = np.pad(clean, 1, mode="edge")
    gx = 0.5 * (p[1:-1, 2:] - p[1:-1, :-2])
    gy = 0.5 * (p[2:, 1:-1] - p[:-2, 1:-1])
    grad = np.where(v_int, np.hypot(gx, gy), 0.0).astype(np.float32)
    return grad, v_int


def hessian_crest_quantile(grad_mag: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """1-D Blakely-Simpson Hessian ridge crest `-lambda_min(nabla^2 log(1 + G))` mapped to quantiles."""
    g = np.asarray(grad_mag, dtype=np.float32)
    v = np.asarray(valid, dtype=bool) & np.isfinite(g)
    v_int = binary_erosion(v, structure=np.ones((3, 3), dtype=bool), border_value=False)
    fl = np.where(v, np.log1p(np.maximum(g, 0.0)), 0.0).astype(np.float32)
    p = np.pad(fl, 1, mode="edge")
    f_xx = p[1:-1, 2:] - 2.0 * p[1:-1, 1:-1] + p[1:-1, :-2]
    f_yy = p[2:, 1:-1] - 2.0 * p[1:-1, 1:-1] + p[:-2, 1:-1]
    f_xy = 0.25 * (p[2:, 2:] - p[2:, :-2] - p[:-2, 2:] + p[:-2, :-2])
    lam_min = 0.5 * ((f_xx + f_yy) - np.hypot(f_xx - f_yy, 2.0 * f_xy))
    crest = np.where(v_int, np.maximum(0.0, -lam_min), 0.0).astype(np.float32)
    return empirical_quantile_map(crest, v_int), v_int


def compute_cross_strike_frame(ridge_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute local cross-strike unit normal `(nx, ny)` and coherence `[0, 1]` from parent binary ridge."""
    s = uniform_filter(np.asarray(ridge_mask, dtype=np.float32), size=5, mode="nearest")
    p = np.pad(s, 1, mode="edge")
    hx = 0.5 * (p[1:-1, 2:] - p[1:-1, :-2])
    hy = 0.5 * (p[2:, 1:-1] - p[:-2, 1:-1])
    j_xx = uniform_filter(hx * hx, size=7, mode="nearest")
    j_yy = uniform_filter(hy * hy, size=7, mode="nearest")
    j_xy = uniform_filter(hx * hy, size=7, mode="nearest")
    diff = j_xx - j_yy
    rad = np.hypot(diff, 2.0 * j_xy)
    tr = j_xx + j_yy
    coherence = np.where(tr > 1e-10, rad / np.maximum(tr, 1e-10), 0.0).astype(np.float32)
    theta_n = 0.5 * np.arctan2(2.0 * j_xy, diff)
    nx = np.cos(theta_n).astype(np.float32)
    ny = np.sin(theta_n).astype(np.float32)
    return nx, ny, coherence


def snap_window_offsets(max_radius_px: float = DEFAULT_MAX_RADIUS_PX) -> list[tuple[int, int, float]]:
    """Non-zero integer pixel offsets within `<= max_radius_px`, ordered by `(dist, dy, dx)`."""
    if max_radius_px <= 0.0 or max_radius_px > 2.0 + 1e-9:
        raise ValueError(f"Brief v2 SNAP requires 0 < max_radius_px <= 2.0, got {max_radius_px}")
    r_int = int(np.floor(max_radius_px + 1e-9))
    r2_lim = max_radius_px * max_radius_px + 1e-9
    offs = [
        (dy, dx, float(np.hypot(dy, dx)))
        for dy in range(-r_int, r_int + 1)
        for dx in range(-r_int, r_int + 1)
        if 0 < dy * dy + dx * dx <= r2_lim
    ]
    offs.sort(key=lambda t: (t[2], t[0], t[1]))
    return offs


def separation_exclusion_offsets(min_sep_sq: int = DEFAULT_MIN_SEP_SQ) -> list[tuple[int, int]]:
    """Offsets `(dy, dx)` with `dy^2 + dx^2 < min_sep_sq` forbidden around other dots."""
    if min_sep_sq <= 0:
        return [(0, 0)]
    rad = int(np.ceil(np.sqrt(min_sep_sq)))
    return [
        (dy, dx)
        for dy in range(-rad, rad + 1)
        for dx in range(-rad, rad + 1)
        if dy * dy + dx * dx < min_sep_sq
    ]


def snap_dots(
    parent_dots: np.ndarray,
    crest_score: np.ndarray,
    allowed: np.ndarray,
    valid_score: np.ndarray,
    nx_norm: np.ndarray,
    ny_norm: np.ndarray,
    coherence: np.ndarray,
    *,
    max_radius_px: float = DEFAULT_MAX_RADIUS_PX,
    min_sep_sq: int = DEFAULT_MIN_SEP_SQ,
    min_peak_q: float = 0.75,
    min_gain_q: float = 0.10,
    cross_strike_cos: float = DEFAULT_CROSS_STRIKE_COS,
    coherence_floor: float = DEFAULT_COHERENCE_FLOOR,
    n_sweeps: int = 2,
) -> dict[str, Any]:
    """Deterministic bijective `<= max_radius_px` cross-strike crest SNAP preserving count, exclusions & spacing."""
    base = np.asarray(parent_dots, dtype=bool)
    allow = np.asarray(allowed, dtype=bool)
    v_score = np.asarray(valid_score, dtype=bool) & np.isfinite(crest_score)
    score = np.asarray(crest_score, dtype=np.float32)

    if base.shape != allow.shape or base.shape != score.shape:
        raise ValueError("Shape mismatch in snap_dots inputs")
    if int((base & ~allow).sum()) != 0:
        raise ValueError("Parent dots violate `allowed` exclusion mask")

    H, W = base.shape
    ry, rx = np.nonzero(base)
    n_dots = int(ry.size)
    if n_dots == 0:
        raise ValueError("parent_dots is empty")

    offs = snap_window_offsets(max_radius_px)
    sep_offs = separation_exclusion_offsets(min_sep_sq)

    orig_valid = v_score[ry, rx]
    orig_s = np.where(orig_valid, score[ry, rx].astype(np.float64), -np.inf)
    win_best = np.full(n_dots, -np.inf, dtype=np.float64)

    for dy, dx, dist in offs:
        ny = ry + dy
        nx = rx + dx
        in_b = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        idx = np.flatnonzero(in_b)
        cond = allow[ny[idx], nx[idx]] & v_score[ny[idx], nx[idx]] & orig_valid[idx]
        if cross_strike_cos > 0.0:
            coh = coherence[ry[idx], rx[idx]]
            proj = np.abs(dx * nx_norm[ry[idx], rx[idx]] + dy * ny_norm[ry[idx], rx[idx]]) / dist
            cond &= (coh < coherence_floor) | (proj >= cross_strike_cos)
        idx = idx[cond]
        if idx.size:
            win_best[idx] = np.maximum(win_best[idx], score[ny[idx], nx[idx]].astype(np.float64))

    gain = np.full(n_dots, -1.0, dtype=np.float64)
    ok_g = np.isfinite(win_best) & np.isfinite(orig_s)
    gain[ok_g] = win_best[ok_g] - orig_s[ok_g]

    # Deterministic priority order: largest potential crest gain first, row-major flat index tie-break
    order = np.lexsort((ry * W + rx, -np.round(gain, 6)))

    cur_y = ry.copy()
    cur_x = rx.copy()
    out = base.copy()

    for _ in range(max(1, int(n_sweeps))):
        changed_in_sweep = 0
        for idx_i in order:
            if gain[idx_i] < min_gain_q:
                continue
            r0_y = int(ry[idx_i])
            r0_x = int(rx[idx_i])
            cy = int(cur_y[idx_i])
            cx = int(cur_x[idx_i])
            s0 = float(score[r0_y, r0_x])

            out[cy, cx] = False
            best_s = s0
            best_rc = (r0_y, r0_x)

            coh_i = float(coherence[r0_y, r0_x])
            nx_i = float(nx_norm[r0_y, r0_x])
            ny_i = float(ny_norm[r0_y, r0_x])

            for dy, dx, dist in offs:
                if cross_strike_cos > 0.0 and coh_i >= coherence_floor:
                    if abs(dx * nx_i + dy * ny_i) / dist < cross_strike_cos:
                        continue
                nr = r0_y + dy
                nc = r0_x + dx
                if not (0 <= nr < H and 0 <= nc < W):
                    continue
                if not (allow[nr, nc] and v_score[nr, nc]):
                    continue
                s_cand = float(score[nr, nc])
                if s_cand < min_peak_q or (s_cand - s0) < min_gain_q:
                    continue
                # Strict `>` preserves smaller-distance / row-major offset tie-break from `offs`
                if s_cand <= best_s:
                    continue
                conflict = False
                for sdy, sdx in sep_offs:
                    snr = nr + sdy
                    snc = nc + sdx
                    if 0 <= snr < H and 0 <= snc < W and out[snr, snc]:
                        conflict = True
                        break
                if not conflict:
                    best_s = s_cand
                    best_rc = (nr, nc)

            ny_new, nx_new = best_rc
            out[ny_new, nx_new] = True
            if (ny_new, nx_new) != (cy, cx):
                cur_y[idx_i] = ny_new
                cur_x[idx_i] = nx_new
                changed_in_sweep += 1
        if changed_in_sweep == 0:
            break

    if int(out.sum()) != n_dots:
        raise RuntimeError(f"Bijective SNAP count invariant violated: {int(out.sum())} != {n_dots}")

    disps = np.hypot((cur_y - ry).astype(np.float64), (cur_x - rx).astype(np.float64))
    if float(disps.max()) > max_radius_px + 1e-9:
        raise RuntimeError(f"Max displacement {float(disps.max())} exceeds {max_radius_px} px")

    moved_mask = disps > 0.0
    n_moved = int(moved_mask.sum())
    n_removed_set = int((base & ~out).sum())
    moved_disps = disps[moved_mask]
    n_step_1 = int(np.isclose(disps, 1.0).sum())
    n_step_sqrt2 = int(np.isclose(disps, np.sqrt(2.0)).sum())
    n_step_2 = int(np.isclose(disps, 2.0).sum())

    return {
        "dots": out,
        "orig_yx": np.column_stack([ry, rx]),
        "final_yx": np.column_stack([cur_y, cur_x]),
        "displacements_px": disps,
        "n_dots": n_dots,
        "n_moved_bijective": n_moved,
        "pct_moved_bijective": round(100.0 * n_moved / float(n_dots), 4),
        "n_set_changed": n_removed_set,
        "pct_changed": round(100.0 * n_removed_set / float(n_dots), 4),
        "mean_displacement_all_px": round(float(disps.mean()), 4),
        "mean_displacement_all_m": round(100.0 * float(disps.mean()), 2),
        "mean_displacement_moved_px": round(float(moved_disps.mean()), 4) if n_moved else 0.0,
        "mean_displacement_moved_m": round(100.0 * float(moved_disps.mean()), 2) if n_moved else 0.0,
        "median_displacement_moved_px": round(float(np.median(moved_disps)), 4) if n_moved else 0.0,
        "p95_displacement_all_px": round(float(np.percentile(disps, 95)), 4),
        "max_displacement_px": round(float(disps.max()), 4),
        "step_counts": {
            "0_px": int(n_dots - n_moved),
            "1_px": n_step_1,
            "sqrt2_px": n_step_sqrt2,
            "2_px": n_step_2,
        },
    }
