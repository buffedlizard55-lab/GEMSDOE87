"""AXIS = RELIEF: controlled mass reallocation across geomorphic relief terciles.

Agent Brief v2 (§5):
  "RELIEF: shift 10-15% of mass between basin / piedmont / range-front terciles
   (relief from the detrended-elevation bands), count fixed."

Design invariants (holding MASS, SPACING, PRUNE collar, and SNAP fixed):
  1. Geomorphic terciles (T0 = Basin, T1 = Piedmont, T2 = Range-Front) are computed
     strictly from the two organizer-provided detrended-elevation bands in
     `training_features.tif`:
       - Band 12 (`det_elev`): detrended elevation relative to regional base level
       - Band 19 (`det_elev_slope`): local slope of detrended elevation
     via the empirical-quantile composite `R = 0.85 * q(det_elev) + 0.15 * q(det_elev_slope)`
     partitioned at the 33.33% and 66.67% footprint percentiles.
  2. Total dot count stays strictly fixed at `37,654` (`MASS` invariant), exclusions stay
     strictly `d_cat > 2.0 px` and `0` on catalogue (`PRUNE` invariant), minimum inter-dot
     spacing stays `sqrt(8) = 2.8284 px` (`MIN_SEP2 = 8`, `SPACING` invariant), and the
     uninvolved third tercile is 100% untouched (`0` dots added or removed).
  3. Source-tercile removals are ranked by exact sequential leave-one-out DTI marginal loss
     `dT_loss` on `H19-5` using `gems57.metric._KERNEL` (`R = 3 px = 300 m` triangular kernel),
     breaking ties by weakest local `H19-5` 5x5 support and weakest subsurface potential-field
     crest score.
  4. Destination-tercile additions place dots at `MIN_SEP2 = 8` first by exact sequential DTI
     marginal gain `dT > 0` on uncovered `H19-5` ridges (Tier 1), and once `H19-5` saturates at
     `sqrt(8)` spacing (notably in flat playas where DEM openness starved `H19-5`), complete
     the quota on parent-corroborated `H19-5` 5x5 support + isotropic potential-field 1-D
     Hessian crests (`|grad_H(RTP)|` Band 02 + isotropic `iso_grav_anom_slope` Band 05; never
     directional Band 18 `dg/dx`) (Tier 2).
"""
from __future__ import annotations

import heapq
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter

from gems57.metric import OFF_DX, OFF_DY, OFF_K, RADIUS_PX, kernel
from gems87.concentration import MIN_SEP2, SUPPORT_K, box_sum, exclusion_offsets, seed_blocked

TERCILE_NAMES: dict[int, str] = {
    0: "basin",
    1: "piedmont",
    2: "range_front",
}


def fast_empirical_quantile(arr: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Deterministic empirical mid-rank quantile in (0, 1] on `valid` pixels."""
    out = np.zeros(arr.shape, dtype=np.float32)
    vals = np.asarray(arr, dtype=np.float32)[valid]
    if vals.size == 0:
        return out
    sorted_vals = np.sort(vals)
    left = np.searchsorted(sorted_vals, vals, side="left")
    right = np.searchsorted(sorted_vals, vals, side="right")
    out[valid] = ((left + right + 1) * (0.5 / float(vals.size))).astype(np.float32)
    return out


def compute_relief_terciles(
    det_elev: np.ndarray,
    det_elev_slope: np.ndarray,
    footprint: np.ndarray,
    *,
    w_elev: float = 0.85,
    w_slope: float = 0.15,
) -> dict[str, Any]:
    """Partition `footprint` into Basin (0), Piedmont (1), and Range-Front (2) terciles."""
    fp = np.asarray(footprint, dtype=bool)
    elev = np.asarray(det_elev, dtype=np.float32)
    slope = np.asarray(det_elev_slope, dtype=np.float32)
    if elev.shape != fp.shape or slope.shape != fp.shape:
        raise ValueError("det_elev, det_elev_slope, and footprint must share shape")

    valid = fp & np.isfinite(elev) & np.isfinite(slope) & (elev > -1e30) & (slope > -1e30)
    if not np.any(valid):
        raise ValueError("no valid detrended-elevation pixels inside footprint")

    q_elev = fast_empirical_quantile(elev, valid)
    q_slope = fast_empirical_quantile(slope, valid)
    relief_index = (float(w_elev) * q_elev + float(w_slope) * q_slope).astype(np.float32)

    cut1, cut2 = np.percentile(relief_index[valid], [100.0 / 3.0, 200.0 / 3.0])
    cut1_f = float(cut1)
    cut2_f = float(cut2)

    tercile = np.full(fp.shape, -1, dtype=np.int8)
    tercile[fp & ((~valid) | (relief_index <= cut1_f))] = 0
    tercile[fp & valid & (relief_index > cut1_f) & (relief_index <= cut2_f)] = 1
    tercile[fp & valid & (relief_index > cut2_f)] = 2

    counts = {TERCILE_NAMES[t]: int((tercile == t).sum()) for t in (0, 1, 2)}
    det_elev_cuts_approx = tuple(
        float(x) for x in np.percentile(elev[valid], [100.0 / 3.0, 200.0 / 3.0])
    )
    return {
        "relief_index": relief_index,
        "tercile": tercile,
        "cuts": (cut1_f, cut2_f),
        "weights": {"det_elev_band12": float(w_elev), "det_elev_slope_band19": float(w_slope)},
        "footprint_pixel_counts": counts,
        "det_elev_tercile_reference_m": det_elev_cuts_approx,
    }


def _masked_gaussian(arr: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    vals = np.where(valid, np.asarray(arr, dtype=np.float32), 0.0).astype(np.float32)
    wts = valid.astype(np.float32)
    num = gaussian_filter(vals, sigma=sigma, mode="nearest")
    den = np.maximum(gaussian_filter(wts, sigma=sigma, mode="nearest"), 1e-6)
    return (num / den).astype(np.float32)


def hessian_ridge_crest_quantile(
    edge_mag: np.ndarray,
    valid: np.ndarray,
    *,
    smooth_sigma: float = 1.2,
) -> np.ndarray:
    """1-D Hessian crest curvature `-lambda_min(H(edge_mag))_+` mapped to [0, 1] quantiles.

    Zero on linear regional ramps and convex troughs; positive only along true 1-D edge crests.
    """
    sm = _masked_gaussian(edge_mag, valid, sigma=smooth_sigma)
    gy, gx = np.gradient(sm)
    gyy, gyx = np.gradient(gy)
    gxy, gxx = np.gradient(gx)
    hxy = 0.5 * (gyx + gxy)
    trace = gxx + gyy
    disc = np.sqrt(np.maximum(0.25 * (gxx - gyy) ** 2 + hxy * hxy, 0.0))
    lam_min = 0.5 * trace - disc
    crest = np.where(valid, np.maximum(-lam_min, 0.0), 0.0).astype(np.float32)
    pos = valid & (crest > 0.0)
    out = np.zeros(edge_mag.shape, dtype=np.float32)
    if np.any(pos):
        out[pos] = fast_empirical_quantile(crest, pos)[pos]
    return out


def compute_subsurface_crest_score(
    rtp_tmi: np.ndarray,
    iso_grav_slope: np.ndarray,
    footprint: np.ndarray,
) -> np.ndarray:
    """Isotropic magnetic + gravity 1-D crest composite from Band 02 (RTP) and Band 05 (|grad_H g|).

    Intentionally avoids Band 18 (`iso_grav_anom_hg`), which is directional `dg/dx`.
    """
    fp = np.asarray(footprint, dtype=bool)
    rtp = np.asarray(rtp_tmi, dtype=np.float32)
    gslope = np.asarray(iso_grav_slope, dtype=np.float32)
    valid_rtp = fp & np.isfinite(rtp) & (rtp > -1e30)
    valid_grav = fp & np.isfinite(gslope) & (gslope > -1e30)

    rtp_filled = _masked_gaussian(rtp, valid_rtp, sigma=1.0)
    ry, rx = np.gradient(rtp_filled)
    rtp_hgm = np.hypot(rx, ry).astype(np.float32)

    q_rtp_crest = hessian_ridge_crest_quantile(rtp_hgm, valid_rtp, smooth_sigma=1.2)
    q_grav_crest = hessian_ridge_crest_quantile(gslope, valid_grav, smooth_sigma=1.2)
    return (0.5 * q_rtp_crest + 0.5 * q_grav_crest).astype(np.float32)


def _kernel_entries() -> list[tuple[int, int, float]]:
    return [
        (int(dy), int(dx), float(kw))
        for dy, dx, kw in zip(OFF_DY.tolist(), OFF_DX.tolist(), OFF_K.tolist())
    ]


def _mark_exclusion(blocked: np.ndarray, row: int, col: int, offsets: np.ndarray) -> None:
    h, w = blocked.shape
    for dy, dx in offsets:
        rr = row + int(dy)
        cc = col + int(dx)
        if 0 <= rr < h and 0 <= cc < w:
            blocked[rr, cc] = True


def _prune_source_exact_dti(
    dots: np.ndarray,
    ref_pos: np.ndarray,
    src_mask: np.ndarray,
    support: np.ndarray,
    subsurface_score: np.ndarray,
    n_drop: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sequentially remove `n_drop` dots inside `src_mask` with smallest exact LOO DTI loss on `ref_pos`."""
    if n_drop == 0:
        return dots.copy(), {
            "n_dropped": 0,
            "sum_dT_loss": 0.0,
            "mean_dT_loss": 0.0,
            "max_dT_loss": 0.0,
        }

    h, w = dots.shape
    kent = _kernel_entries()
    rad = int(RADIUS_PX)
    kmat = np.zeros((2 * rad + 1, 2 * rad + 1), dtype=np.float32)
    for dy, dx, kw in kent:
        kmat[dy + rad, dx + rad] = kw

    top1 = np.zeros((h, w), dtype=np.float32)
    top1_id = np.full((h, w), -1, dtype=np.int32)
    top2 = np.zeros((h, w), dtype=np.float32)

    all_r, all_c = np.nonzero(dots)
    dot_id_grid = np.full((h, w), -1, dtype=np.int32)
    for idx in range(all_r.size):
        r = int(all_r[idx])
        c = int(all_c[idx])
        dot_id_grid[r, c] = idx
        for dy, dx, kw in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc]:
                if kw > top1[rr, cc]:
                    top2[rr, cc] = top1[rr, cc]
                    top1[rr, cc] = kw
                    top1_id[rr, cc] = idx
                elif kw > top2[rr, cc]:
                    top2[rr, cc] = kw

    def dot_loss(idx: int, r: int, c: int) -> float:
        loss = 0.0
        for dy, dx, _ in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc] and top1_id[rr, cc] == idx:
                loss += float(top1[rr, cc] - top2[rr, cc])
        return loss

    heap: list[tuple[float, int, float, int, int]] = []
    for idx in range(all_r.size):
        r = int(all_r[idx])
        c = int(all_c[idx])
        if not src_mask[r, c]:
            continue
        loss = dot_loss(idx, r, c)
        heap.append((loss, int(support[r, c]), float(subsurface_score[r, c]), r * w + c, idx))
    if len(heap) < n_drop:
        raise ValueError(f"source tercile has only {len(heap)} parent dots, cannot drop {n_drop}")
    heapq.heapify(heap)

    active = np.ones(all_r.size, dtype=bool)
    out = dots.copy()
    dropped = 0
    losses: list[float] = []

    while dropped < n_drop:
        loss_est, sup_v, sub_v, flat_rc, idx = heapq.heappop(heap)
        if not active[idx]:
            continue
        r = int(all_r[idx])
        c = int(all_c[idx])
        cur_loss = dot_loss(idx, r, c)
        if cur_loss > loss_est + 1e-6:
            heapq.heappush(heap, (cur_loss, sup_v, sub_v, flat_rc, idx))
            continue

        active[idx] = False
        out[r, c] = False
        dot_id_grid[r, c] = -1
        dropped += 1
        losses.append(cur_loss)

        for dy, dx, _ in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc] and top1_id[rr, cc] == idx:
                b1 = 0.0
                b1_id = -1
                b2 = 0.0
                y0 = max(0, rr - rad)
                y1 = min(h, rr + rad + 1)
                x0 = max(0, cc - rad)
                x1 = min(w, cc + rad + 1)
                for nr in range(y0, y1):
                    for nc in range(x0, x1):
                        nidx = int(dot_id_grid[nr, nc])
                        if nidx >= 0:
                            nw = float(kmat[nr - rr + rad, nc - cc + rad])
                            if nw > b1:
                                b2 = b1
                                b1 = nw
                                b1_id = nidx
                            elif nw > b2:
                                b2 = nw
                top1[rr, cc] = b1
                top1_id[rr, cc] = b1_id
                top2[rr, cc] = b2

    return out, {
        "n_dropped": dropped,
        "sum_dT_loss": float(sum(losses)),
        "mean_dT_loss": float(np.mean(losses)) if losses else 0.0,
        "max_dT_loss": float(max(losses)) if losses else 0.0,
    }


def _refill_dest_exact_dti_and_crests(
    base_dots: np.ndarray,
    ref_pos: np.ndarray,
    dst_allowed: np.ndarray,
    support: np.ndarray,
    subsurface_score: np.ndarray,
    n_add: int,
    *,
    min_sep2: int = MIN_SEP2,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Place `n_add` dots inside `dst_allowed` at `min_sep2` spacing.

    Tier 1 places dots with positive exact sequential DTI marginal gain `dT > 0` on `ref_pos`
    (preferring direct `ref_pos` pixels, then 300 m kernel-halo support, tie-broken by
    `subsurface_score`). Tier 2 (if `ref_pos` saturates at `min_sep2`) completes the quota on
    isotropic potential-field 1-D Hessian crests + `ref_pos` 5x5 support.
    """
    if n_add == 0:
        return base_dots.copy(), {
            "n_added": 0,
            "n_added_tier1_exact_dti": 0,
            "n_added_on_h19_5": 0,
            "n_added_tier2_subsurface_crest": 0,
            "sum_dT_gain": 0.0,
            "mean_tier2_crest_score": 0.0,
        }

    h, w = base_dots.shape
    kent = _kernel_entries()
    offsets = exclusion_offsets(min_sep2)
    blocked = seed_blocked(base_dots, offsets)
    out = base_dots.copy()

    # Exact current DTI kernel coverage C[r, c] on ref_pos from base_dots.
    cov = np.zeros((h, w), dtype=np.float32)
    br, bc = np.nonzero(base_dots)
    for r, c in zip(br.tolist(), bc.tolist()):
        for dy, dx, kw in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc] and kw > cov[rr, cc]:
                cov[rr, cc] = kw

    def exact_dT(r: int, c: int) -> float:
        gain = 0.0
        for dy, dx, kw in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc]:
                cur = float(cov[rr, cc])
                if kw > cur:
                    gain += kw - cur
        return gain

    # Tier 1 candidates: destination allowed pixels within R=3 px of any ref_pos pixel.
    near_ref = box_sum(ref_pos, 2 * int(RADIUS_PX) + 1) > 0
    t1_cand = dst_allowed & near_ref & ~blocked
    t1_r, t1_c = np.nonzero(t1_cand)

    heap: list[tuple[float, int, float, int]] = []
    for r, c in zip(t1_r.tolist(), t1_c.tolist()):
        g = exact_dT(r, c)
        if g > 1e-6:
            on_ref = 1 if ref_pos[r, c] else 0
            heap.append((-g, -on_ref, -float(subsurface_score[r, c]), r * w + c))
    heapq.heapify(heap)

    added_total = 0
    added_t1 = 0
    added_on_ref = 0
    gains: list[float] = []

    while added_total < n_add and heap:
        neg_g, neg_on_ref, neg_sub, flat_rc = heapq.heappop(heap)
        r, c = divmod(flat_rc, w)
        if blocked[r, c]:
            continue
        cur_g = exact_dT(r, c)
        if cur_g <= 1e-6:
            continue
        if cur_g < (-neg_g) - 1e-6:
            heapq.heappush(heap, (-cur_g, neg_on_ref, neg_sub, flat_rc))
            continue

        out[r, c] = True
        _mark_exclusion(blocked, r, c, offsets)
        for dy, dx, kw in kent:
            rr = r + dy
            cc = c + dx
            if 0 <= rr < h and 0 <= cc < w and ref_pos[rr, cc] and kw > cov[rr, cc]:
                cov[rr, cc] = kw
        added_total += 1
        added_t1 += 1
        if ref_pos[r, c]:
            added_on_ref += 1
        gains.append(cur_g)

    # Tier 2 completion (when H19-5 in dst_tercile is saturated at sqrt(8)):
    # rank remaining unblocked dst_allowed pixels by (on_ref, support_5x5 > 0, subsurface_score).
    added_t2 = 0
    t2_scores: list[float] = []
    if added_total < n_add:
        rem_need = n_add - added_total
        t2_cand = dst_allowed & ~blocked
        c_rows, c_cols = np.nonzero(t2_cand)
        if c_rows.size < rem_need:
            raise RuntimeError(
                f"destination tercile has only {c_rows.size} unblocked pixels left, need {rem_need}"
            )
        c_on_ref = ref_pos[c_rows, c_cols].astype(np.int8)
        c_sup = np.minimum(support[c_rows, c_cols], 3).astype(np.int8)
        c_sub = subsurface_score[c_rows, c_cols]
        order = np.lexsort((c_cols, c_rows, -c_sub, -c_sup, -c_on_ref))
        for i in order.tolist():
            r = int(c_rows[i])
            c = int(c_cols[i])
            if blocked[r, c]:
                continue
            out[r, c] = True
            _mark_exclusion(blocked, r, c, offsets)
            added_total += 1
            added_t2 += 1
            if ref_pos[r, c]:
                added_on_ref += 1
            t2_scores.append(float(c_sub[i]))
            if added_total == n_add:
                break

    if added_total != n_add:
        raise RuntimeError(f"spacing-limited: placed {added_total} of {n_add} requested dots")

    return out, {
        "n_added": added_total,
        "n_added_tier1_exact_dti": added_t1,
        "n_added_on_h19_5": added_on_ref,
        "n_added_tier2_subsurface_crest": added_t2,
        "sum_dT_gain": float(sum(gains)),
        "mean_dT_gain_tier1": float(np.mean(gains)) if gains else 0.0,
        "mean_tier2_crest_score": float(np.mean(t2_scores)) if t2_scores else 0.0,
    }


def tercile_dot_census(dots: np.ndarray, tercile: np.ndarray) -> dict[str, Any]:
    total = int(dots.sum())
    counts: dict[str, int] = {}
    fracs: dict[str, float] = {}
    for t in (0, 1, 2):
        name = TERCILE_NAMES[t]
        cnt = int((dots & (tercile == t)).sum())
        counts[name] = cnt
        fracs[name] = (cnt / float(total)) if total > 0 else 0.0
    return {"counts": counts, "fractions": fracs, "total": total}


def shift_relief_mass(
    parent_dots: np.ndarray,
    h19_5: np.ndarray,
    tercile: np.ndarray,
    allowed: np.ndarray,
    subsurface_score: np.ndarray,
    *,
    src_tercile: int,
    dst_tercile: int,
    n_shift: int,
    min_sep2: int = MIN_SEP2,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Shift `n_shift` dots from `src_tercile` to `dst_tercile`, holding count & spacing fixed."""
    if src_tercile not in (0, 1, 2) or dst_tercile not in (0, 1, 2):
        raise ValueError("src_tercile and dst_tercile must be in {0, 1, 2}")
    if src_tercile == dst_tercile:
        raise ValueError("src_tercile and dst_tercile must differ")
    if n_shift < 0:
        raise ValueError("n_shift must be >= 0")

    parent = np.asarray(parent_dots, dtype=bool)
    ref_pos = np.asarray(h19_5, dtype=bool) & np.asarray(allowed, dtype=bool)
    allow = np.asarray(allowed, dtype=bool)
    terc = np.asarray(tercile, dtype=np.int8)
    sub = np.asarray(subsurface_score, dtype=np.float32)

    if not (parent.shape == ref_pos.shape == allow.shape == terc.shape == sub.shape):
        raise ValueError("all input grids must share exact shape")
    if np.any(parent & ~allow):
        raise ValueError("parent_dots contains pixels outside allowed mask")

    n_parent = int(parent.sum())
    parent_census = tercile_dot_census(parent, terc)

    if n_shift == 0:
        out = parent.copy()
        return out, {
            "src_tercile": TERCILE_NAMES[src_tercile],
            "dst_tercile": TERCILE_NAMES[dst_tercile],
            "n_parent": n_parent,
            "n_dots": n_parent,
            "n_shifted": 0,
            "pct_changed": 0.0,
            "symmetric_diff_dots": 0,
            "parent_terciles": parent_census,
            "variant_terciles": parent_census,
            "untouched_tercile_unchanged": True,
        }

    support = box_sum(ref_pos, SUPPORT_K)
    src_mask = terc == src_tercile
    dst_allowed = allow & (terc == dst_tercile)

    pruned, prune_info = _prune_source_exact_dti(
        parent, ref_pos, src_mask, support, sub, n_shift
    )
    out, add_info = _refill_dest_exact_dti_and_crests(
        pruned, ref_pos, dst_allowed, support, sub, n_shift, min_sep2=min_sep2
    )

    if int(out.sum()) != n_parent:
        raise RuntimeError(f"count drifted: {int(out.sum())} != {n_parent}")
    if np.any(out & ~allow):
        raise RuntimeError("RELIEF placed mass outside allowed mask")

    other_tercile = ({0, 1, 2} - {src_tercile, dst_tercile}).pop()
    other_mask = terc == other_tercile
    untouched_identical = bool(np.array_equal(parent & other_mask, out & other_mask))
    if not untouched_identical:
        raise RuntimeError("uninvolved third tercile was modified")

    variant_census = tercile_dot_census(out, terc)
    sym_diff = int(np.logical_xor(parent, out).sum())
    if sym_diff != 2 * n_shift:
        raise RuntimeError(f"unexpected symmetric diff {sym_diff} != {2 * n_shift}")

    return out, {
        "src_tercile": TERCILE_NAMES[src_tercile],
        "dst_tercile": TERCILE_NAMES[dst_tercile],
        "untouched_tercile": TERCILE_NAMES[other_tercile],
        "untouched_tercile_unchanged": untouched_identical,
        "min_sep2": int(min_sep2),
        "min_sep_px": round(float(np.sqrt(min_sep2)), 4),
        "n_parent": n_parent,
        "n_dots": int(out.sum()),
        "n_shifted": int(n_shift),
        "pct_changed": round(100.0 * float(n_shift) / float(n_parent), 4),
        "pct_symmetric_diff": round(100.0 * float(sym_diff) / float(n_parent), 4),
        "symmetric_diff_dots": sym_diff,
        "shared_with_parent": int((parent & out).sum()),
        "parent_terciles": parent_census,
        "variant_terciles": variant_census,
        "prune_source": prune_info,
        "refill_dest": add_info,
    }
