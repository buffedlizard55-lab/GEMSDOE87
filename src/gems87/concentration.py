"""Km-scale CONCENTRATION axis: relocate parent dots, count and collar fixed.

Parent ranking at block scale is the parent's own field mass (H19-5 count per
block). Dots move from lowest-prior blocks onto unused allowed pixels in
highest-prior blocks. Min inter-dot spacing is inherited from the parent
(sqrt(8) px) so this axis does not also change SPACING.
"""
from __future__ import annotations

from typing import Any

import numpy as np

MIN_SEP2 = 8  # parent min inter-dot is sqrt(8); forbid d^2 < 8
BLOCK_PX = 10  # 1 km at the 100 m grid
SUPPORT_K = 5


def exclusion_offsets(min_sep2: int = MIN_SEP2) -> np.ndarray:
    """Pixel offsets with Euclidean d^2 < min_sep2 (center included)."""
    rmax = int(np.floor(np.sqrt(max(min_sep2 - 1, 0)))) + 1
    offs = [
        (dy, dx)
        for dy in range(-rmax, rmax + 1)
        for dx in range(-rmax, rmax + 1)
        if dy * dy + dx * dx < min_sep2
    ]
    return np.asarray(offs, dtype=np.int16)


def box_sum(mask: np.ndarray, k: int = SUPPORT_K) -> np.ndarray:
    """Inclusive kxk window sum via a padded integral image."""
    a = mask.astype(np.int32, copy=False)
    h, w = a.shape
    integral = np.zeros((h + 1, w + 1), dtype=np.int32)
    integral[1:, 1:] = np.cumsum(np.cumsum(a, axis=0), axis=1)
    radius = k // 2
    y0 = np.clip(np.arange(h) - radius, 0, h)
    y1 = np.clip(np.arange(h) + radius + 1, 0, h)
    x0 = np.clip(np.arange(w) - radius, 0, w)
    x1 = np.clip(np.arange(w) + radius + 1, 0, w)
    return (
        integral[y1[:, None], x1[None, :]]
        - integral[y0[:, None], x1[None, :]]
        - integral[y1[:, None], x0[None, :]]
        + integral[y0[:, None], x0[None, :]]
    )


def block_index(shape: tuple[int, int], block_px: int = BLOCK_PX) -> tuple[np.ndarray, int, int]:
    """Row-major block id per pixel, plus (n_block_rows, n_block_cols)."""
    h, w = shape
    nby = (h + block_px - 1) // block_px
    nbx = (w + block_px - 1) // block_px
    rows = np.arange(h, dtype=np.int32) // block_px
    cols = np.arange(w, dtype=np.int32) // block_px
    idx = rows[:, None] * nbx + cols[None, :]
    return idx, nby, nbx


def bincount_blocks(idx: np.ndarray, mask: np.ndarray, n_blocks: int) -> np.ndarray:
    if not mask.any():
        return np.zeros(n_blocks, dtype=np.int32)
    return np.bincount(idx[mask], minlength=n_blocks).astype(np.int32)


def density_cv(counts: np.ndarray, areas: np.ndarray) -> dict[str, float | int | None]:
    """Block-density CV among footprint blocks; also occupied-count CV."""
    foot = areas > 0
    n_foot = int(foot.sum())
    counts_f = counts[foot].astype(np.float64)
    areas_f = areas[foot].astype(np.float64)
    dens = np.divide(counts_f, areas_f, out=np.zeros_like(counts_f), where=areas_f > 0)
    occ = counts_f > 0

    def _cv(x: np.ndarray) -> float | None:
        if x.size == 0:
            return None
        mean = float(x.mean())
        if mean <= 0:
            return None
        return float(x.std(ddof=0) / mean)

    return {
        "n_foot_blocks": n_foot,
        "n_occupied_blocks": int(occ.sum()),
        "mean_count_all": float(counts_f.mean()) if n_foot else 0.0,
        "mean_count_occupied": float(counts_f[occ].mean()) if occ.any() else 0.0,
        "cv_count_all": _cv(counts_f),
        "cv_count_occupied": _cv(counts_f[occ]),
        "cv_density_all": _cv(dens),
        "max_count": int(counts_f.max()) if n_foot else 0,
    }


def _mark_exclusion(
    blocked: np.ndarray,
    row: int,
    col: int,
    offsets: np.ndarray,
) -> None:
    h, w = blocked.shape
    for dy, dx in offsets:
        rr = row + int(dy)
        cc = col + int(dx)
        if 0 <= rr < h and 0 <= cc < w:
            blocked[rr, cc] = True


def seed_blocked(dots: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    blocked = np.zeros(dots.shape, dtype=bool)
    rows, cols = np.where(dots)
    for r, c in zip(rows.tolist(), cols.tolist()):
        _mark_exclusion(blocked, r, c, offsets)
    return blocked


def relocate(
    parent_dots: np.ndarray,
    prior_field: np.ndarray,
    allowed: np.ndarray,
    n_move: int,
    *,
    block_px: int = BLOCK_PX,
    min_sep2: int = MIN_SEP2,
) -> dict[str, Any]:
    """Move ``n_move`` parent dots from lowest-prior blocks to highest-prior ones.

    ``prior_field`` is a boolean/numeric field whose block *sum* is the prior
    (H19-5 positives). ``allowed`` already encodes footprint, collar, and
    catalogue exclusion. Count of True pixels in the returned mask equals the
    parent count. Raises if the allowed set cannot absorb ``n_move`` under
    spacing.
    """
    if n_move < 0:
        raise ValueError("n_move must be >= 0")
    parent = np.asarray(parent_dots, dtype=bool)
    prior_pos = np.asarray(prior_field) > 0.5
    allowed = np.asarray(allowed, dtype=bool)
    if parent.shape != allowed.shape or prior_pos.shape != parent.shape:
        raise ValueError("parent, prior_field, and allowed must share shape")
    n_parent = int(parent.sum())
    if n_move == 0:
        out = parent.copy()
        return {
            "dots": out,
            "n_parent": n_parent,
            "n_move": 0,
            "n_removed": 0,
            "n_added": 0,
            "pct_changed": 0.0,
            "n_added_on_prior_field": 0,
        }
    if n_move >= n_parent:
        raise ValueError("n_move must be < n_parent")
    if np.any(parent & ~allowed):
        raise ValueError("parent dots exist outside the allowed mask")

    idx, nby, nbx = block_index(parent.shape, block_px)
    n_blocks = nby * nbx
    prior_counts = bincount_blocks(idx, prior_pos, n_blocks)
    support = box_sum(prior_pos, SUPPORT_K)
    offsets = exclusion_offsets(min_sep2)

    p_rows, p_cols = np.where(parent)
    p_block = idx[p_rows, p_cols]
    p_prior = prior_counts[p_block]
    p_support = support[p_rows, p_cols]
    remove_order = np.lexsort((p_cols, p_rows, p_support, p_prior))
    take = remove_order[:n_move]
    keep = np.ones(p_rows.size, dtype=bool)
    keep[take] = False

    remaining = np.zeros_like(parent)
    remaining[p_rows[keep], p_cols[keep]] = True
    removed_rows = p_rows[take]
    removed_cols = p_cols[take]

    cand = allowed & ~remaining
    c_rows, c_cols = np.where(cand)
    if c_rows.size < n_move:
        raise RuntimeError(f"only {c_rows.size} allowed vacancies, need {n_move}")
    c_block = idx[c_rows, c_cols]
    c_prior = prior_counts[c_block]
    c_h19 = prior_pos[c_rows, c_cols].astype(np.int8)
    c_support = support[c_rows, c_cols]
    # Highest prior first, then prior-field pixels, then local support, then (r,c).
    add_order = np.lexsort((c_cols, c_rows, -c_support, -c_h19, -c_prior))

    blocked = seed_blocked(remaining, offsets)
    added_rows: list[int] = []
    added_cols: list[int] = []
    added_on_field = 0
    for i in add_order.tolist():
        r = int(c_rows[i])
        c = int(c_cols[i])
        if blocked[r, c]:
            continue
        remaining[r, c] = True
        _mark_exclusion(blocked, r, c, offsets)
        added_rows.append(r)
        added_cols.append(c)
        if c_h19[i]:
            added_on_field += 1
        if len(added_rows) == n_move:
            break
    if len(added_rows) != n_move:
        raise RuntimeError(
            f"spacing-limited: placed {len(added_rows)} of {n_move} requested relocations"
        )

    out = remaining
    if int(out.sum()) != n_parent:
        raise RuntimeError(f"count drifted: {int(out.sum())} != {n_parent}")
    return {
        "dots": out,
        "n_parent": n_parent,
        "n_move": n_move,
        "n_removed": n_move,
        "n_added": n_move,
        "pct_changed": 100.0 * n_move / n_parent,
        "n_added_on_prior_field": added_on_field,
        "removed_rows": np.asarray(removed_rows, dtype=np.int32),
        "removed_cols": np.asarray(removed_cols, dtype=np.int32),
        "added_rows": np.asarray(added_rows, dtype=np.int32),
        "added_cols": np.asarray(added_cols, dtype=np.int32),
        "prior_counts": prior_counts,
        "block_index": idx,
        "nby": nby,
        "nbx": nbx,
        "block_px": block_px,
    }
