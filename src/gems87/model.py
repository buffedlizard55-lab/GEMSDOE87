"""Two-population CSCT probability heads (LightGBM + HGB) and exact Dinkelbach 300 m submodular cover."""

from __future__ import annotations

from array import array
import gc
import heapq
import math
from typing import Any

import lightgbm as lgb
import numpy as np
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier

from . import ALPHA, BETA, DEFAULT_DOT_BUDGET

KERNEL_300M: tuple[tuple[int, int, float], ...] = tuple(
    (dy, dx, float(1.0 - math.hypot(dy, dx) / 3.0))
    for dy in range(-2, 3)
    for dx in range(-2, 3)
    if math.hypot(dy, dx) < 3.0
)

AUG_TRANSFER_NAMES: tuple[str, ...] = (
    "t00_tip_beam_near",
    "t01_tip_beam_far",
    "t02_tip_horsetail_splay",
    "t03_relay_breach_overlap",
    "t04_strand_aniso_cont",
    "t05_tip_phys_strike_lock",
    "t06_host_len_halo",
    "t07_meso_tectonic_prox",
    "t08_log_d_vis",
    "t09_log_d_tip",
    "t10_relay_collar_band",
)


def augment_fold_transfer(
    vis_faults: np.ndarray,
    footprint: np.ndarray,
    base_transfer: np.ndarray,
) -> np.ndarray:
    """Append exact fold-visible distance/tip decay channels (derived ONLY from `vis_faults`)."""
    vis = np.asarray(vis_faults, dtype=bool)
    fp = np.asarray(footprint, dtype=bool)
    n_fp = int(fp.sum())
    out = np.empty((n_fp, 11), dtype=np.float32)
    out[:, :8] = np.asarray(base_transfer, dtype=np.float32)

    d_vis = ndi.distance_transform_edt(~vis)[fp].astype(np.float32)
    deg = ndi.convolve(vis.astype(np.int16), np.ones((3, 3), dtype=np.int16), mode="constant", cval=0)
    tips = vis & (deg <= 2)
    d_tip = (
        ndi.distance_transform_edt(~tips)[fp].astype(np.float32)
        if tips.any()
        else np.full(n_fp, 200.0, dtype=np.float32)
    )

    out[:, 8] = np.log1p(d_vis)
    out[:, 9] = np.log1p(d_tip)
    out[:, 10] = np.exp(-0.5 * ((d_vis - 4.0) / 3.5) ** 2).astype(np.float32)
    return out


def bayes_prior_calibrate(
    p_raw: np.ndarray,
    allowed_mask: np.ndarray,
    pi_true: float = 0.0022,
    temperature: float = 1.0,
    eps: float = 1e-6,
    quadrant_calibrate: bool = True,
) -> np.ndarray:
    """Calibrate classifier probabilities on `allowed_mask` via exact log-odds bisection per quadrant."""
    allow = np.asarray(allowed_mask, dtype=bool)
    out = np.zeros(p_raw.shape, dtype=np.float32)
    if not allow.any():
        return out

    def _cal_sub(mask_sub: np.ndarray) -> None:
        if not mask_sub.any():
            return
        v = np.clip(np.asarray(p_raw[mask_sub], dtype=np.float64), eps, 1.0 - eps)
        logit = np.log(v / (1.0 - v)) / float(temperature)
        sample = logit[::8] if logit.size > 200_000 else logit
        lo, hi = -25.0, 25.0
        for _ in range(32):
            mid = 0.5 * (lo + hi)
            if float((1.0 / (1.0 + np.exp(-(sample + mid)))).mean()) < pi_true:
                lo = mid
            else:
                hi = mid
        shift = 0.5 * (lo + hi)
        out[mask_sub] = (1.0 / (1.0 + np.exp(-(logit + shift)))).astype(np.float32)

    if not quadrant_calibrate:
        _cal_sub(allow)
        return out

    yy, xx = np.nonzero(allow)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    gy, gx = np.ogrid[: p_raw.shape[0], : p_raw.shape[1]]
    for qm in (
        allow & (gy < ym) & (gx < xm),
        allow & (gy < ym) & (gx >= xm),
        allow & (gy >= ym) & (gx < xm),
        allow & (gy >= ym) & (gx >= xm),
    ):
        _cal_sub(qm)
    return out


def poisson_disk_emit(
    surface: np.ndarray,
    allowed_mask: np.ndarray,
    n_dots: int = DEFAULT_DOT_BUDGET,
    min_sep_px: float = 2.8,
) -> np.ndarray:
    """Deterministic greedy Poisson-disk emitter in strictly descending rank order."""
    h, w = surface.shape
    cand_flat = np.flatnonzero(allowed_mask)
    scores = surface.ravel()[cand_flat]
    valid = np.isfinite(scores)
    cand_flat = cand_flat[valid]
    scores = scores[valid]

    top_k = min(cand_flat.size, n_dots * 28)
    if cand_flat.size > top_k:
        part = np.argpartition(scores, -top_k)[-top_k:]
        cand_flat = cand_flat[part]
        scores = scores[part]
    order = np.argsort(-scores, kind="mergesort")
    cand_flat = cand_flat[order]

    ys = cand_flat // w
    xs = cand_flat % w

    r_int = int(math.ceil(min_sep_px))
    dy, dx = np.mgrid[-r_int : r_int + 1, -r_int : r_int + 1]
    disk_mask = (dy * dy + dx * dx) < (min_sep_px * min_sep_px)
    offs_y, offs_x = np.nonzero(disk_mask)
    offs_y = offs_y - r_int
    offs_x = offs_x - r_int

    pad = r_int + 1
    blocked = np.zeros((h + 2 * pad, w + 2 * pad), dtype=bool)
    out = np.zeros((h, w), dtype=np.float32)

    count = 0
    for i in range(cand_flat.size):
        yp = int(ys[i]) + pad
        xp = int(xs[i]) + pad
        if blocked[yp, xp]:
            continue
        out[yp - pad, xp - pad] = 1.0
        blocked[yp + offs_y, xp + offs_x] = True
        count += 1
        if count >= n_dots:
            break
    return out


def dinkelbach_submodular_300m_emit(
    p_raw: np.ndarray,
    allowed_mask: np.ndarray,
    n_dots: int = DEFAULT_DOT_BUDGET,
    pi_true: float = 0.0022,
    temperature: float = 1.0,
    fp_lambda: float = 0.012,
    min_sep_px: float = 2.40,
    candidate_pool: int = 1_500_000,
    packed_halos_fp: np.ndarray | None = None,
    fp_lut: np.ndarray | None = None,
    active_halo_indices: np.ndarray | None = None,
    overlap_cap: float = 0.650,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Exact CELF lazy-greedy Dinkelbach 300 m submodular maximum coverage with optional registry halo cap.

    Maximizes exact linear expectation of the 300 m Tversky kernel without pixel-independence assumptions:
      Delta E[TP_w](x | M_S) = sum_{|y - x| < 3} p_cal(y) * max(0, K(|y - x|) - M_S(y))
      u(x | M_S) = Delta E[TP_w](x | M_S) - fp_lambda * (1 - max_{|y - x| < 3} K(|y - x|) * p_cal(y))
    while guaranteeing forward 3-px overlap <= overlap_cap across every tracked registry raster.
    """
    h, w = p_raw.shape
    allow = np.asarray(allowed_mask, dtype=bool)
    if n_dots <= 0 or not allow.any():
        return np.zeros((h, w), dtype=np.float32), {"n_dots": 0}

    p_cal = bayes_prior_calibrate(
        p_raw, allow, pi_true=pi_true, temperature=temperature, quadrant_calibrate=True
    )
    k_hat = float(p_cal[allow].sum())

    pad = 3
    hp, wp = h + 2 * pad, w + 2 * pad
    p_pad = np.zeros((hp, wp), dtype=np.float32)
    p_pad[pad : pad + h, pad : pad + w] = np.where(allow, p_cal, np.float32(0.0))

    init_tp = np.zeros((h, w), dtype=np.float32)
    q_self = np.zeros((h, w), dtype=np.float32)
    for dy, dx, kw in KERNEL_300M:
        sub = p_pad[pad + dy : pad + dy + h, pad + dx : pad + dx + w]
        init_tp += np.float32(kw) * sub
        np.maximum(q_self, np.float32(kw) * sub, out=q_self)

    f_cost = (np.float32(1.0) - np.minimum(q_self, np.float32(1.0))).astype(np.float32)
    del q_self
    u0 = init_tp - np.float32(fp_lambda) * f_cost

    cand_flat = np.flatnonzero(allow & (init_tp > 0.0))
    del init_tp
    if cand_flat.size > candidate_pool:
        sub_u = u0.ravel()[cand_flat]
        keep = np.argpartition(sub_u, -candidate_pool)[-candidate_pool:]
        cand_flat = cand_flat[keep]

    sub_u = u0.ravel()[cand_flat]
    order = np.argsort(-sub_u, kind="mergesort")
    cand_flat = cand_flat[order]
    sub_u = sub_u[order]
    f_cand = array("f", f_cost.ravel()[cand_flat].astype(np.float32).tobytes())
    del u0, f_cost

    halo_bits: np.ndarray | None = None
    halo_counts: np.ndarray | None = None
    total_bits = 0
    cap_int = int(math.floor(overlap_cap * n_dots))
    if packed_halos_fp is not None and fp_lut is not None and active_halo_indices is not None:
        cand_fp_idx = fp_lut[cand_flat]
        halo_bits = np.asarray(packed_halos_fp[cand_fp_idx], dtype=np.uint8)
        total_bits = halo_bits.shape[1] * 8
        halo_counts = np.zeros(int(active_halo_indices.size), dtype=np.int32)

    ys_p = array("i", (cand_flat // w + pad).astype(np.int32).tobytes())
    xs_p = array("i", (cand_flat % w + pad).astype(np.int32).tobytes())
    p_flat = array("f", np.ascontiguousarray(p_pad.ravel(), dtype=np.float32).tobytes())
    del p_pad
    cov_flat = array("f", b"\x00\x00\x00\x00") * (hp * wp)
    gc.collect()
    blocked = np.zeros((hp, wp), dtype=bool)
    sep_offs = (
        tuple(
            (dy, dx)
            for dy in range(-3, 4)
            for dx in range(-3, 4)
            if math.hypot(dy, dx) < min_sep_px
        )
        if min_sep_px > 0.0
        else ()
    )
    off_k = tuple((dy * wp + dx, kw) for dy, dx, kw in KERNEL_300M)

    heap: list[tuple[float, int]] = [(-float(sub_u[i]), i) for i in range(cand_flat.size)]
    heapq.heapify(heap)
    pop = heapq.heappop
    push = heapq.heappush

    dots = np.zeros((h, w), dtype=np.float32)
    picked = 0
    cum_tp = 0.0
    cum_fp = 0.0
    best_dti = -1.0
    best_step = 0
    cap_skips = 0

    while picked < n_dots and heap:
        _, ci = pop(heap)
        yp, xp = ys_p[ci], xs_p[ci]
        if blocked[yp, xp]:
            continue
        base = yp * wp + xp
        dtp = 0.0
        for off, kw in off_k:
            j = base + off
            pj = p_flat[j]
            if pj > 0.0:
                rem = kw - cov_flat[j]
                if rem > 0.0:
                    dtp += pj * rem
        dfp = f_cand[ci]
        val = dtp - fp_lambda * dfp
        if not heap or val >= -heap[0][0] - 1e-12:
            if halo_bits is not None and halo_counts is not None and active_halo_indices is not None:
                row_bool = np.unpackbits(halo_bits[ci], count=total_bits)[active_halo_indices].astype(bool)
                if row_bool.any() and int(halo_counts[row_bool].max()) >= cap_int:
                    cap_skips += 1
                    continue
                halo_counts[row_bool] += 1
            y, x = yp - pad, xp - pad
            if dots[y, x] == 0.0:
                dots[y, x] = 1.0
                picked += 1
                for off, kw in off_k:
                    j = base + off
                    if kw > cov_flat[j]:
                        cov_flat[j] = kw
                for dy, dx in sep_offs:
                    blocked[yp + dy, xp + dx] = True
                cum_tp += dtp
                cum_fp += dfp
                denom = ALPHA * cum_tp + ALPHA * cum_fp + BETA * k_hat
                est_dti = cum_tp / max(denom, 1e-12)
                if est_dti > best_dti:
                    best_dti = est_dti
                    best_step = picked
        elif dtp > 0.0:
            push(heap, (-val, ci))

    max_ov = (
        float(halo_counts.max() / max(picked, 1))
        if (halo_counts is not None and halo_counts.size > 0)
        else 0.0
    )
    stats = {
        "n_dots": int(picked),
        "expected_tp_w": round(cum_tp, 4),
        "expected_fp_w": round(cum_fp, 4),
        "expected_k_hat": round(k_hat, 4),
        "expected_dti_at_budget": round(
            cum_tp / max(ALPHA * cum_tp + ALPHA * cum_fp + BETA * k_hat, 1e-12), 6
        ),
        "dinkelbach_peak_expected_dti": round(best_dti, 6),
        "dinkelbach_opt_budget": int(best_step),
        "overlap_cap_skips": int(cap_skips),
        "max_tracked_halo_overlap": round(max_ov, 6),
    }
    return dots, stats


def fit_blind_loqo_models(
    static_mm: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    quad_ids: np.ndarray,
    seed: int = 87,
) -> tuple[list[lgb.LGBMClassifier], np.ndarray]:
    """Fit strictly Leave-One-Quadrant-Out blind multi-physics models (ZERO catalogue input)."""
    fp_idx = np.flatnonzero(footprint)
    y_fp = catalogue.ravel()[fp_idx].astype(np.int32)
    q_fp = quad_ids.ravel()[fp_idx]

    d_cat = ndi.distance_transform_edt(~catalogue)
    clean_neg = ((d_cat > 6.0).ravel()[fp_idx]) & (y_fp == 0)

    rng = np.random.default_rng(seed)
    models: list[lgb.LGBMClassifier] = []
    oof_raw = np.zeros(fp_idx.size, dtype=np.float32)

    for q in range(4):
        tr_q = q_fp != q
        pos_idx = np.flatnonzero(tr_q & (y_fp == 1))
        neg_pool = np.flatnonzero(tr_q & clean_neg)
        n_neg = min(neg_pool.size, pos_idx.size * 5)
        neg_sub = np.sort(rng.choice(neg_pool, size=n_neg, replace=False))

        sel = np.concatenate([pos_idx, neg_sub])
        X_tr = np.asarray(static_mm[sel], dtype=np.float32)
        y_tr = np.concatenate([
            np.ones(pos_idx.size, dtype=np.int32),
            np.zeros(neg_sub.size, dtype=np.int32),
        ])

        clf = lgb.LGBMClassifier(
            n_estimators=360,
            num_leaves=63,
            learning_rate=0.05,
            min_child_samples=80,
            subsample=0.80,
            subsample_freq=1,
            colsample_bytree=0.75,
            reg_alpha=1.5,
            reg_lambda=4.0,
            random_state=seed + q,
            n_jobs=-1,
            verbose=-1,
        )
        clf.fit(X_tr, y_tr)
        models.append(clf)

        te_idx = np.flatnonzero(q_fp == q)
        for start in range(0, te_idx.size, 400_000):
            sl = te_idx[start : start + 400_000]
            oof_raw[sl] = clf.predict_proba(np.asarray(static_mm[sl], dtype=np.float32))[:, 1].astype(np.float32)

    prior = float(y_fp.mean())
    sample_prior = 1.0 / 6.0
    odds = oof_raw / np.maximum(1.0 - oof_raw, 1e-6)
    oof_cal = (odds * (prior / sample_prior)) / (1.0 + odds * (prior / sample_prior))
    return models, oof_cal.astype(np.float32)


def fit_csct_dual_ensemble_loqo(
    static_mm: np.ndarray,
    p_blind_oof_fp: np.ndarray,
    transfer_by_q: list[np.ndarray],
    folds: list[dict],
    footprint: np.ndarray,
    seed: int = 87,
) -> tuple[list[tuple[lgb.LGBMClassifier, HistGradientBoostingClassifier]], np.ndarray]:
    """Fit full 56-feature cross-tree (LightGBM + HGB) CSCT ensemble strictly Leave-One-Quadrant-Out.

    Features per pixel:
      - Columns 0..43  : 44 cover-stratified physical tomograms (LiDAR, DEM, Grav, Mag, GeoDAWN, MT, GDR)
      - Column  44     : out-of-quadrant pure blind probability `p_blind_oof_fp`
      - Columns 45..55 : 11 fold-visible fracture-mechanics channels (`augment_fold_transfer(f["visible"])`)

    Trained strictly on `tr_q != q` AND `d_vis > 2.5 px` (off-collar counterfactual regime matching
    real undiscovered targets outside the digitization halo of mapped faults).
    """
    fp_idx = np.flatnonzero(footprint)
    rng = np.random.default_rng(seed + 300)
    n_stat = static_mm.shape[1]
    n_tran = 11
    n_total = n_stat + 1 + n_tran

    y_by_q = []
    act_offcollar_by_q = []
    act_eval_by_q = []
    for f in folds:
        y_by_q.append(f["truth"].ravel()[fp_idx].astype(np.int32))
        d_vis_fp = ndi.distance_transform_edt(~f["visible"]).ravel()[fp_idx]
        act_eval = (footprint & f["region"] & (~f["masked_known"])).ravel()[fp_idx]
        act_eval_by_q.append(act_eval)
        act_offcollar_by_q.append(act_eval & (d_vis_fp > 2.5))

    def _assemble_rows(T_q: np.ndarray, rows_idx: np.ndarray) -> np.ndarray:
        X = np.empty((rows_idx.size, n_total), dtype=np.float32)
        X[:, :n_stat] = np.asarray(static_mm[rows_idx], dtype=np.float32)
        X[:, n_stat] = p_blind_oof_fp[rows_idx]
        X[:, n_stat + 1 :] = T_q[rows_idx]
        return X

    model_pairs: list[tuple[lgb.LGBMClassifier, HistGradientBoostingClassifier]] = []
    oof_prob = np.zeros(fp_idx.size, dtype=np.float32)

    for q in range(4):
        X_parts = []
        y_parts = []
        for tr_q in range(4):
            if tr_q == q:
                continue
            act = act_offcollar_by_q[tr_q]
            yq = y_by_q[tr_q]
            pos_i = np.flatnonzero(act & (yq == 1))
            neg_i = np.flatnonzero(act & (yq == 0))
            n_neg = min(neg_i.size, max(pos_i.size * 14, 42_000))
            neg_sub = np.sort(rng.choice(neg_i, size=n_neg, replace=False))
            sel = np.concatenate([pos_i, neg_sub])
            X_parts.append(_assemble_rows(transfer_by_q[tr_q], sel))
            y_parts.append(
                np.concatenate([
                    np.ones(pos_i.size, dtype=np.int32),
                    np.zeros(neg_sub.size, dtype=np.int32),
                ])
            )

        X_tr = np.vstack(X_parts)
        y_tr = np.concatenate(y_parts)

        m_lgb = lgb.LGBMClassifier(
            n_estimators=360,
            num_leaves=63,
            learning_rate=0.045,
            min_child_samples=80,
            subsample=0.80,
            subsample_freq=1,
            colsample_bytree=0.72,
            reg_alpha=1.5,
            reg_lambda=5.0,
            random_state=seed + 20 + q,
            n_jobs=-1,
            verbose=-1,
        )
        m_lgb.fit(X_tr, y_tr)

        m_hgb = HistGradientBoostingClassifier(
            max_iter=260,
            max_leaf_nodes=63,
            learning_rate=0.05,
            min_samples_leaf=80,
            l2_regularization=3.0,
            random_state=seed + 40 + q,
        )
        m_hgb.fit(X_tr, y_tr)
        model_pairs.append((m_lgb, m_hgb))

        te_idx = np.flatnonzero(act_eval_by_q[q])
        T_te = transfer_by_q[q]
        for start in range(0, te_idx.size, 300_000):
            sl = te_idx[start : start + 300_000]
            X_te = _assemble_rows(T_te, sl)
            p1 = m_lgb.predict_proba(X_te)[:, 1].astype(np.float32)
            p2 = m_hgb.predict_proba(X_te)[:, 1].astype(np.float32)
            oof_prob[sl] = 0.60 * p1 + 0.40 * p2

    return model_pairs, oof_prob
