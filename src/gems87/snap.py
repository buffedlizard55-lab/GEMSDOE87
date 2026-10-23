"""AXIS = SNAP: move each parent dot <= r px onto the strongest edge crest in its window.

Pure numpy and deterministic (no RNG). The tests are in ``tests/test_snap_axis.py``.

Operator (per edge band E):
1. ``crest_mask(E)`` uses a 4-direction maxima test on E. A pixel counts as a crest when it is a
   strict local maximum along at least ``min_dirs`` of the four lines through it (E-W, N-S, NE-SW,
   NW-SE) and E is finite. This is the classic horizontal-gradient-maxima picker used to put
   contacts and faults on potential-field gradient grids.
2. ``snap_dots`` builds a candidate list for each dot: crest pixels within Euclidean radius
   ``radius`` (dy^2 + dx^2 <= radius^2) that are inside ``allowed`` (footprint, off-catalogue,
   parent collar). Candidates are ranked by E (descending), then distance (ascending), then flat
   index. A dot that already sits on the best crest stays put. A dot with no crest in its window
   stays put.
3. Dots are processed in descending order of gain (E_best - E_here), with flat index breaking
   ties. A move is accepted only if the target keeps squared distance >= ``min_dist_sq`` to every
   other current dot. If the best target fails, the next-ranked crest is tried; if every target
   fails, the dot stays. The count is therefore preserved exactly, and so is the parent's
   minimum spacing.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def disk_offsets(radius: float) -> list[tuple[int, int]]:
    r = int(np.floor(radius))
    lim = radius * radius + 1e-9
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dy * dy + dx * dx <= lim]


def clean_band(band: np.ndarray, footprint: np.ndarray, nodata_floor: float = -1e30) -> np.ndarray:
    """float64 copy with nodata / non-finite / out-of-footprint set to NaN."""
    e = np.asarray(band, dtype=np.float64).copy()
    bad = ~np.isfinite(e) | (e < nodata_floor) | ~np.asarray(footprint, bool)
    e[bad] = np.nan
    return e


def crest_mask(e: np.ndarray, min_dirs: int = 2) -> np.ndarray:
    """4-direction strict-maxima crest picker. NaN neighbours never beat the centre."""
    e = np.asarray(e, dtype=np.float64)
    H, W = e.shape
    pad = np.full((H + 2, W + 2), -np.inf)
    finite = np.isfinite(e)
    pad[1:-1, 1:-1] = np.where(finite, e, -np.inf)
    c = pad[1:-1, 1:-1]
    count = np.zeros((H, W), dtype=np.int8)
    for (ay, ax), (by, bx) in (((0, -1), (0, 1)), ((-1, 0), (1, 0)), ((-1, 1), (1, -1)), ((-1, -1), (1, 1))):
        a = pad[1 + ay : 1 + ay + H, 1 + ax : 1 + ax + W]
        b = pad[1 + by : 1 + by + H, 1 + bx : 1 + bx + W]
        count += ((c > a) & (c > b)).astype(np.int8)
    return finite & (count >= min_dirs)


def snap_dots(
    dots: np.ndarray,
    e: np.ndarray,
    crest: np.ndarray,
    allowed: np.ndarray,
    radius: float = 2.0,
    min_dist_sq: int = 5,
) -> tuple[np.ndarray, dict[str, Any]]:
    dots = np.asarray(dots, bool)
    H, W = dots.shape
    e = np.asarray(e, dtype=np.float64)
    target_ok = np.asarray(crest, bool) & np.asarray(allowed, bool) & np.isfinite(e)
    offs = disk_offsets(radius)
    rs = int(np.ceil(np.sqrt(min_dist_sq)))
    space = [(dy, dx) for dy in range(-rs, rs + 1) for dx in range(-rs, rs + 1)
             if dy * dy + dx * dx < min_dist_sq and (dy, dx) != (0, 0)]

    ys, xs = np.nonzero(dots)
    n = ys.size
    plans: list[tuple[float, int, int, list[tuple[float, float, int, int, int]]]] = []
    for k in range(n):
        y, x = int(ys[k]), int(xs[k])
        here = e[y, x]
        here_v = here if np.isfinite(here) else -np.inf
        cands = []
        for dy, dx in offs:
            ty, tx = y + dy, x + dx
            if 0 <= ty < H and 0 <= tx < W and target_ok[ty, tx]:
                cands.append((-e[ty, tx], float(dy * dy + dx * dx), ty * W + tx, ty, tx))
        if not cands:
            continue
        cands.sort()
        best_y, best_x = cands[0][3], cands[0][4]
        if (best_y, best_x) == (y, x):
            continue  # already on the strongest crest in its window
        cands = [c for c in cands if (c[3], c[4]) != (y, x)]
        gain = -cands[0][0] - here_v
        plans.append((-gain, y * W + x, k, cands))
    plans.sort(key=lambda p: (p[0], p[1]))

    occ = dots.copy()
    disp = np.zeros(n, dtype=np.float64)
    dst = (ys * W + xs).astype(np.int64)
    moved = 0
    blocked = 0
    for _, _, k, cands in plans:
        y, x = int(ys[k]), int(xs[k])
        occ[y, x] = False
        done = False
        for _, d2, _, ty, tx in cands:
            if occ[ty, tx]:
                continue
            ok = True
            for dy, dx in space:
                qy, qx = ty + dy, tx + dx
                if 0 <= qy < H and 0 <= qx < W and occ[qy, qx]:
                    ok = False
                    break
            if ok:
                occ[ty, tx] = True
                disp[k] = np.sqrt(d2)
                dst[k] = ty * W + tx
                moved += 1
                done = True
                break
        if not done:
            occ[y, x] = True
            blocked += 1
    if int(occ.sum()) != n:
        raise AssertionError("snap changed the dot count")
    if np.unique(dst).size != n or not occ.ravel()[dst].all():
        raise AssertionError("snap mapping is not a bijection onto the output support")
    return occ, {
        "_src_flat": (ys * W + xs).astype(np.int64),
        "_dst_flat": dst,
        "n_dots": int(n),
        "n_with_better_crest": int(len(plans)),
        "n_moved": int(moved),
        "n_blocked_by_spacing": int(blocked),
        "pct_moved": round(100.0 * moved / max(n, 1), 4),
        "mean_displacement_px_all_dots": round(float(disp.mean()) if n else 0.0, 4),
        "mean_displacement_px_moved_dots": round(float(disp[disp > 0].mean()) if moved else 0.0, 4),
        "mean_displacement_m_all_dots": round(100.0 * (float(disp.mean()) if n else 0.0), 1),
        "displacement_histogram_px": {f"{v:.4f}": int((np.isclose(disp, v)).sum())
                                      for v in sorted({0.0} | {float(np.sqrt(a * a + b * b)) for a, b in offs})},
    }


def snap_credit_proxy(
    dots: np.ndarray,
    snapped: np.ndarray,
    truth: np.ndarray,
    radius_px: float = 3.0,
) -> dict[str, float]:
    """Mean triangular-kernel self-credit max_g k(d) of dots, before and after."""
    from scipy.ndimage import distance_transform_edt

    d = distance_transform_edt(~np.asarray(truth, bool))
    k = np.maximum(1.0 - d / radius_px, 0.0)
    a = float(k[np.asarray(dots, bool)].mean())
    b = float(k[np.asarray(snapped, bool)].mean())
    return {"mean_credit_before": a, "mean_credit_after": b, "delta": b - a}
