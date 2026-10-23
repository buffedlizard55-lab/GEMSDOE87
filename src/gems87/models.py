"""Leave-One-Quadrant-Out (`LOQO`) multi-family ensembles, `has_lidar` quantile
deconfounding, Two-Regime Bayesian synthesis, and Dual-Head Dinkelbach allocation
for Lane G87 (`H87-KDMI`).

STRICT INVARIANTS:
1. ZERO `SGMC` input columns exist anywhere in `X` (`M_Quat`, `M_Pied`, `M_Geo`, `Head M`).
2. Strictly Leave-One-Quadrant-Out (`quad != q_val` with `16 px = 1.6 km` boundary erosion
   away from `quad == q_val`) — zero training pixels or segments overlap any held-out
   fold cell in `seed=20`, `seed=30`, or full-footprint quadrant `q_val`.
3. `M_Geo` features on every holdout fold cell are computed strictly from `ctx.visible(key)`.
"""
from __future__ import annotations

import gc
import time
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.kernel_approximation import Nystroem
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

from gems57 import emit, holdout, metric
from gems57.network import segments
from .fracture_geo import compute_visible_fracture_features_fp
from .kdmi_features import extract_rows_from_fmajor

# Top 24 pure-physics KDMI indices paired with the 12 visible fracture-mechanics channels in M_Geo
KDMI_SUBSET_FOR_GEO = [
    11, 14, 16, 17, 18, 20, 23, 25,
    26, 28, 29, 31, 32, 34, 36, 39,
    41, 42, 43, 44, 45, 47, 48, 75,
]

# Non-LiDAR indices for the smooth RBF kernel branch (avoids imputing NaN LiDAR in non-LiDAR tiles)
NON_LIDAR_IDX = [j for j in range(92) if not (50 <= j <= 61)]


def recalibrate_prior(prob_sub: np.ndarray, pi_sub: float, pi_true: float) -> np.ndarray:
    """Exact Bayes prior-odds adjustment from subsampled prevalence `pi_sub` to `pi_true`."""
    p = np.clip(prob_sub.astype(np.float64), 1e-6, 1.0 - 1e-6)
    odds = (p / (1.0 - p)) * ((pi_true / (1.0 - pi_true)) / (pi_sub / (1.0 - pi_sub)))
    return (odds / (1.0 + odds)).astype(np.float32)


def align_non_lidar_quantiles(score_q: np.ndarray, has_lidar_q: np.ndarray) -> np.ndarray:
    """Deconfound USGS 3DEP 1m LiDAR survey boundary within a single validation quadrant.

    Maps the empirical quantile distribution of `score_q[~has_lidar_q]` onto the exact
    quantile function of `score_q[has_lidar_q]` using only unlabeled predictions inside `q_val`.
    """
    lid = has_lidar_q > 0.5
    n_no = int((~lid).sum())
    n_yes = int(lid.sum())
    if n_no < 500 or n_yes < 500:
        return score_q
    out = score_q.copy()
    q_grid = np.linspace(0.0, 1.0, 2001)
    src_q = np.quantile(score_q[~lid], q_grid)
    dst_q = np.quantile(score_q[lid], q_grid)
    # Remove flat duplicate knots for monotonic interp
    uniq_src, uniq_idx = np.unique(src_q, return_index=True)
    if len(uniq_src) >= 16:
        out[~lid] = np.interp(score_q[~lid], uniq_src, dst_q[uniq_idx]).astype(np.float32)
    return out


def spaced_greedy_topk(
    score: np.ndarray,
    allowed: np.ndarray,
    budget: int = 37_654,
    min_spacing_px: float = 2.85,
    candidate_cap: int = 320_000,
) -> np.ndarray:
    """Pure priority-ordered Poisson-disk / minimum-spacing emission (`Exp 1` & `Exp 2`)."""
    h, w = score.shape
    s = np.where(allowed, score, -1.0)
    ys, xs = np.nonzero(s > 0.0)
    if ys.size == 0:
        return np.zeros((h, w), dtype=bool)
    if ys.size > candidate_cap:
        top = np.argpartition(-s[ys, xs], candidate_cap)[:candidate_cap]
        ys, xs = ys[top], xs[top]
    order = np.argsort(-s[ys, xs], kind="stable")
    ys = ys[order].astype(np.int32)
    xs = xs[order].astype(np.int32)

    r_ex = int(np.floor(min_spacing_px))
    ex_dy, ex_dx = [], []
    for dy in range(-r_ex, r_ex + 1):
        for dx in range(-r_ex, r_ex + 1):
            if dy * dy + dx * dx < min_spacing_px * min_spacing_px - 1e-9:
                ex_dy.append(dy)
                ex_dx.append(dx)
    ex_dy_a = np.asarray(ex_dy, dtype=np.int32)
    ex_dx_a = np.asarray(ex_dx, dtype=np.int32)

    blocked = np.zeros((h, w), dtype=bool)
    emitted = np.zeros((h, w), dtype=bool)
    n_emit = 0
    for i in range(ys.size):
        if n_emit >= budget:
            break
        y = int(ys[i])
        x = int(xs[i])
        if blocked[y, x]:
            continue
        emitted[y, x] = True
        n_emit += 1
        by = y + ex_dy_a
        bx = x + ex_dx_a
        ok = (by >= 0) & (by < h) & (bx >= 0) & (bx < w)
        blocked[by[ok], bx[ok]] = True
    return emitted


@dataclass
class QuadrantModels:
    q_val: int
    quat_hgb: HistGradientBoostingClassifier
    quat_lgb: lgb.LGBMClassifier
    quat_rbf: object
    quat_pi_sub: float
    quat_pi_true: float
    pied_hgb: HistGradientBoostingClassifier
    pied_lgb: lgb.LGBMClassifier
    pied_pi_sub: float
    pied_pi_true: float
    geo_hgb: HistGradientBoostingClassifier
    geo_lgb: lgb.LGBMClassifier
    geo_pi_sub: float
    geo_pi_true: float
    head_m_reg: HistGradientBoostingRegressor


def _stratified_sample_indices(
    y_fp: np.ndarray, eligible_fp: np.ndarray, neg_mult: int, seed: int, max_pos: int = 65_000
) -> tuple[np.ndarray, float, float]:
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(eligible_fp & (y_fp == 1))
    neg = np.flatnonzero(eligible_fp & (y_fp == 0))
    pi_true = float(len(pos)) / max(float(len(pos) + len(neg)), 1.0)
    if len(pos) > max_pos:
        pos = rng.choice(pos, size=max_pos, replace=False)
    n_neg = min(len(neg), len(pos) * neg_mult)
    neg_sub = rng.choice(neg, size=n_neg, replace=False)
    idx = np.concatenate([pos, neg_sub])
    rng.shuffle(idx)
    pi_sub = float(len(pos)) / max(float(len(idx)), 1.0)
    return np.sort(idx), pi_sub, pi_true


def predict_quat_on_indices(qm: QuadrantModels, X: np.ndarray) -> np.ndarray:
    p1 = qm.quat_hgb.predict_proba(X)[:, 1]
    p2 = qm.quat_lgb.predict_proba(X)[:, 1]
    p3 = qm.quat_rbf.predict_proba(X[:, NON_LIDAR_IDX])[:, 1]
    p_ens = 0.44 * p1 + 0.42 * p2 + 0.14 * p3
    return recalibrate_prior(p_ens, qm.quat_pi_sub, qm.quat_pi_true)


def predict_pied_on_indices(qm: QuadrantModels, X: np.ndarray) -> np.ndarray:
    p1 = qm.pied_hgb.predict_proba(X)[:, 1]
    p2 = qm.pied_lgb.predict_proba(X)[:, 1]
    p_ens = 0.50 * p1 + 0.50 * p2
    return recalibrate_prior(p_ens, qm.pied_pi_sub, qm.pied_pi_true)


def predict_geo_on_indices(qm: QuadrantModels, X_geo36: np.ndarray) -> np.ndarray:
    p1 = qm.geo_hgb.predict_proba(X_geo36)[:, 1]
    p2 = qm.geo_lgb.predict_proba(X_geo36)[:, 1]
    p_ens = 0.52 * p1 + 0.48 * p2
    return recalibrate_prior(p_ens, qm.geo_pi_sub, qm.geo_pi_true)


def fuse_two_regime_posterior(
    p_quat_fp: np.ndarray,
    p_pied_fp: np.ndarray,
    p_geo_fp: np.ndarray,
    pied_hab_fp: np.ndarray,
    pluvial_mimic_fp: np.ndarray,
    fg_fp: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Combine `M_Quat`, `M_Pied`, and `M_Geo` via exact Bayesian Noisy-OR synthesis.

    1. `p_phys`: Pure-physics `KDMI` posterior fusing `M_Quat` + piedmont-weighted `M_Pied`
       with Pleistocene pluvial shoreline mimic suppression (`0` catalogue & `0` SGMC inputs).
    2. `p_two`: Exact Noisy-OR union `1 - (1 - p_phys) * (1 - p_geo_tip)` gated strictly to
       genuine outward tip/relay stress lobes (`ray11 + bridge11 > 0.04`) so parallel flanks
       never bloat and remaining budget flows cleanly into concealed piedmont/basin faults.
    """
    pluv_gate = 1.0 - 0.34 * np.clip(pluvial_mimic_fp, 0.0, 1.0)
    pied_boost = 0.55 + 0.90 * np.clip(pied_hab_fp, 0.0, 1.0)

    p_phys = np.clip(
        (0.50 * p_quat_fp + 0.50 * p_pied_fp * pied_boost) * pluv_gate,
        0.0,
        0.95,
    ).astype(np.float32)
    # Match pure-physics marginal total mass to empirical off-catalogue expectation (~14,500 px)
    p_phys *= float(14_500.0 / max(float(p_phys.sum()), 1.0))
    p_phys = np.clip(p_phys, 0.0, 0.92)

    # Gate M_Geo excess strictly by outward tip ray / bilateral bridge intensity (`fg_fp[:, 3], fg_fp[:, 5]`)
    tip_bridge_signal = fg_fp[:, 3] + 1.8 * fg_fp[:, 5]
    tip_gate = np.clip(tip_bridge_signal / (tip_bridge_signal + 0.12), 0.0, 1.0)
    p_geo_tip = np.clip((p_geo_fp - float(np.median(p_geo_fp))) * tip_gate, 0.0, 0.92).astype(np.float32)

    p_two = (1.0 - (1.0 - p_phys) * (1.0 - p_geo_tip)).astype(np.float32)
    p_two *= float(14_500.0 / max(float(p_two.sum()), 1.0))
    p_two = np.clip(p_two, 0.0, 0.95).astype(np.float32)
    return p_phys, p_two


def fit_quadrant_models(
    q_val: int,
    mm_92: np.memmap,
    fp_idx: np.ndarray,
    grid_shape: tuple[int, int],
    quad_full: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    sgmc_binary_for_aux_target_only: np.ndarray,
    hidden_union_in_qval: np.ndarray,
) -> QuadrantModels:
    """Fit `M_Quat`, `M_Pied`, `M_Geo`, and `Head M` strictly outside quadrant `q_val`."""
    t0 = time.time()
    q_target = quad_full == q_val
    dist_from_qval = ndi.distance_transform_edt(~q_target)
    train_mask = footprint & (quad_full != q_val) & (dist_from_qval > 16.0)

    # HARD ZERO-LEAKAGE ASSERTIONS
    assert not np.any(train_mask & q_target), "Train/val quadrant overlap!"
    assert not np.any(train_mask & hidden_union_in_qval), "Withheld pixels leaked into train_mask!"

    train_fp = train_mask.ravel()[fp_idx]
    cat_fp = catalogue.ravel()[fp_idx].astype(np.uint8)
    hbase_fp = mm_92[14, :].astype(np.float32)
    pied_hab_fp = mm_92[77, :].astype(np.float32)
    geod_fp = mm_92[3, :].astype(np.float32)
    rad9_fp = mm_92[45, :].astype(np.float32)

    # 1. Fit M_Quat (HGB + LightGBM + Nystroem-RBF) on X_92 strictly inside train_mask
    sub_q, pi_sub_q, pi_true_q = _stratified_sample_indices(
        cat_fp, train_fp, neg_mult=4, seed=8710 + q_val, max_pos=50_000
    )
    X_q = extract_rows_from_fmajor(mm_92, sub_q)
    y_q = cat_fp[sub_q]

    quat_hgb = HistGradientBoostingClassifier(
        max_iter=170,
        max_leaf_nodes=63,
        min_samples_leaf=80,
        learning_rate=0.06,
        l2_regularization=4.0,
        random_state=8701 + q_val,
    )
    quat_hgb.fit(X_q, y_q)

    quat_lgb = lgb.LGBMClassifier(
        n_estimators=185,
        num_leaves=47,
        min_child_samples=90,
        colsample_bytree=0.55,
        subsample=0.80,
        subsample_freq=1,
        learning_rate=0.06,
        reg_alpha=2.0,
        reg_lambda=6.0,
        n_jobs=2,
        random_state=8711 + q_val,
        verbose=-1,
    )
    quat_lgb.fit(X_q, y_q)

    quat_rbf = make_pipeline(
        SimpleImputer(strategy="median"),
        RobustScaler(),
        Nystroem(kernel="rbf", gamma=0.015, n_components=260, random_state=8721 + q_val),
        LogisticRegression(C=1.0, max_iter=300),
    )
    quat_rbf.fit(X_q[:, NON_LIDAR_IDX], y_q)

    # Also fit `Head M` regressor directly on 300 m halo coverage magnitude inside train_mask!
    halo_truth = metric.kernel(ndi.distance_transform_edt(~(catalogue & train_mask))).astype(np.float32)
    y_halo_q = halo_truth.ravel()[fp_idx][sub_q]
    del halo_truth
    head_m_reg = HistGradientBoostingRegressor(
        max_iter=160,
        max_leaf_nodes=47,
        min_samples_leaf=90,
        learning_rate=0.06,
        l2_regularization=5.0,
        random_state=8731 + q_val,
    )
    head_m_reg.fit(X_q, y_halo_q)
    del X_q, y_q, y_halo_q
    gc.collect()

    # 2. Fit M_Pied on X_92 ONLY (ZERO SGMC input features!) targeting concealed piedmont/basin faults in train_mask
    sgmc_fp = (sgmc_binary_for_aux_target_only > 0).ravel()[fp_idx].astype(np.uint8)
    pied_domain_fp = train_fp & ((hbase_fp >= 160.0) | (pied_hab_fp >= 0.30))
    y_pied_all = np.where((cat_fp == 1) | (sgmc_fp == 1), 1, 0).astype(np.uint8)
    sub_p, pi_sub_p, pi_true_p = _stratified_sample_indices(
        y_pied_all, pied_domain_fp, neg_mult=4, seed=8740 + q_val, max_pos=45_000
    )
    X_p = extract_rows_from_fmajor(mm_92, sub_p)
    y_p = y_pied_all[sub_p]
    del sgmc_fp, y_pied_all

    pied_hgb = HistGradientBoostingClassifier(
        max_iter=200,
        max_leaf_nodes=55,
        min_samples_leaf=85,
        learning_rate=0.055,
        l2_regularization=4.5,
        random_state=8751 + q_val,
    )
    pied_hgb.fit(X_p, y_p)

    pied_lgb = lgb.LGBMClassifier(
        n_estimators=220,
        num_leaves=43,
        min_child_samples=90,
        colsample_bytree=0.55,
        subsample=0.80,
        subsample_freq=1,
        learning_rate=0.055,
        reg_alpha=2.0,
        reg_lambda=6.0,
        n_jobs=2,
        random_state=8761 + q_val,
        verbose=-1,
    )
    pied_lgb.fit(X_p, y_p)
    del X_p, y_p
    gc.collect()

    # 3. Fit M_Geo via strict nested segment hide-and-recover SOLELY inside `train_mask`!
    cat_train = catalogue & train_mask
    seg_tr, n_seg_tr = segments(cat_train, max_len_px=12)[:2]
    all_seg_ids = np.arange(1, n_seg_tr + 1)
    rng_g = np.random.default_rng(8770 + q_val)

    X_geo_parts, y_geo_parts = [], []
    pi_true_list = []
    for draw_k in range(2):
        perm = rng_g.permutation(all_seg_ids)
        hid_ids = perm[: max(1, int(0.20 * len(all_seg_ids)))]
        hid_inner = np.isin(seg_tr, hid_ids) & train_mask
        vis_inner = cat_train & ~hid_inner
        fg_fp = compute_visible_fracture_features_fp(vis_inner, fp_idx, geod_fp, rad9_fp)

        elig_inner_fp = (train_mask & ~vis_inner).ravel()[fp_idx]
        y_inner_fp = hid_inner.ravel()[fp_idx].astype(np.uint8)
        sub_g, pi_sub_g, pi_true_g = _stratified_sample_indices(
            y_inner_fp, elig_inner_fp, neg_mult=7, seed=8780 + 10 * q_val + draw_k, max_pos=18_000
        )
        X_sub24 = np.column_stack([mm_92[j, sub_g].astype(np.float32) for j in KDMI_SUBSET_FOR_GEO])
        X_geo_parts.append(np.hstack([fg_fp[sub_g], X_sub24]))
        y_geo_parts.append(y_inner_fp[sub_g])
        pi_true_list.append(pi_true_g)
        del fg_fp, X_sub24

    X_g = np.vstack(X_geo_parts)
    y_g = np.concatenate(y_geo_parts)
    pi_sub_g_all = float(y_g.mean())
    pi_true_g_all = float(np.mean(pi_true_list))
    del X_geo_parts, y_geo_parts

    geo_hgb = HistGradientBoostingClassifier(
        max_iter=190,
        max_leaf_nodes=47,
        min_samples_leaf=80,
        learning_rate=0.055,
        l2_regularization=4.0,
        random_state=8791 + q_val,
    )
    geo_hgb.fit(X_g, y_g)

    geo_lgb = lgb.LGBMClassifier(
        n_estimators=210,
        num_leaves=39,
        min_child_samples=85,
        colsample_bytree=0.65,
        subsample=0.80,
        subsample_freq=1,
        learning_rate=0.055,
        reg_alpha=1.5,
        reg_lambda=5.0,
        n_jobs=2,
        random_state=8801 + q_val,
        verbose=-1,
    )
    geo_lgb.fit(X_g, y_g)
    del X_g, y_g
    gc.collect()

    print(f"  [LOQO q_val={q_val}] Fitted M_Quat (3-family) + M_Pied + M_Geo + Head M in {time.time() - t0:.1f}s")
    return QuadrantModels(
        q_val=q_val,
        quat_hgb=quat_hgb,
        quat_lgb=quat_lgb,
        quat_rbf=quat_rbf,
        quat_pi_sub=pi_sub_q,
        quat_pi_true=pi_true_q,
        pied_hgb=pied_hgb,
        pied_lgb=pied_lgb,
        pied_pi_sub=pi_sub_p,
        pied_pi_true=pi_true_p,
        geo_hgb=geo_hgb,
        geo_lgb=geo_lgb,
        geo_pi_sub=pi_sub_g_all,
        geo_pi_true=pi_true_g_all,
        head_m_reg=head_m_reg,
    )
