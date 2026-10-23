"""Session 2 model & expected-credit emitter for `H87B-STFD`.

Implements:
1. Within-fold Counterfactual Exposure Debiasing:
   - Strictly inside `fold["train"]` and `fold["visible"]` (zero hidden truth pixels read),
     hides 50% of 8-connected training fault components (with 3-px safety halo) plus a
     regional sub-basin block, teaching every learner calibrated probabilities across both
     near-tip en-echelon relays (`3 < d_vis < 30 px`) and blind frontier basins (`d_vis > 30 px`).
   - Mild positive sample weights (`1 + 0.35 * cover_regime`) counteract observational
     scarp-mapping bias without distorting posterior log-odds rankings.
2. Multi-Scale Histogram-Boosted + Smooth Linear-Logit Ensemble (`< 25 MB` model RAM):
   - Model 1: Deep interaction `HistGradientBoostingClassifier` (`max_leaf_nodes=63, l2=3.0`)
   - Model 2: Medium interaction `HistGradientBoostingClassifier` (`max_leaf_nodes=35, l2=8.0, feature_fraction=0.75`)
   - Model 3: Strongly regularized shallow `HistGradientBoostingClassifier` (`max_leaf_nodes=19, l2=18.0, feature_fraction=0.65`)
   - Model 4: Smooth L2-regularized `RobustScaler + LogisticRegression` physical prior
3. Exact 300 m Triangular Expected-Credit Priority Disc Thinning (`r_min = 2.83 px`):
   - Convolves calibrated posterior fault probabilities with the exact competition 300 m
     triangular kernel `K(d) = max(0, 1 - d / 3)` before deterministic priority disc
     suppression so every emitted dot maximizes non-redundant expected recall.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation, convolve, label
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from gems57.grid import Grid
from gems87.stfd_features import compute_visible_structural_features


def _triangular_kernel_300m() -> np.ndarray:
    rad = 3
    yy, xx = np.ogrid[-rad : rad + 1, -rad : rad + 1]
    d = np.hypot(xx.astype(np.float32), yy.astype(np.float32))
    k = np.maximum(0.0, 1.0 - d / 3.0).astype(np.float32)
    return k / float(k.sum())


def _disc_mask(min_dist_px: float) -> tuple[int, np.ndarray]:
    rad = int(np.floor(min_dist_px))
    yy, xx = np.ogrid[-rad : rad + 1, -rad : rad + 1]
    mask = (xx * xx + yy * yy) <= (min_dist_px * min_dist_px + 1e-6)
    return rad, mask


TRI_KERNEL_300M = _triangular_kernel_300m()


def build_counterfactual_training_table(
    grid: Grid,
    phys_arr: np.ndarray,
    aux: dict[str, np.ndarray],
    train_mask: np.ndarray,
    visible_mask: np.ndarray,
    rng: np.random.Generator,
    include_structural: bool = True,
    pos_per_world: int = 12_000,
    neg_ratio: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct leak-free training rows `(X, y, sample_weight)` strictly from `(train_mask, visible_mask)`."""
    fp = grid.footprint
    train_fp = (train_mask & fp)[fp]
    vis_clean = visible_mask & train_mask & fp

    if not include_structural:
        pos_idx = np.flatnonzero(vis_clean[fp])
        neg_idx = np.flatnonzero(train_fp & (~vis_clean[fp]))
        n_pos = min(len(pos_idx), pos_per_world * 2)
        n_neg = min(len(neg_idx), n_pos * neg_ratio)
        sel_p = rng.choice(pos_idx, size=n_pos, replace=False)
        sel_n = rng.choice(neg_idx, size=n_neg, replace=False)
        idx = np.concatenate([sel_p, sel_n])
        X = np.asarray(phys_arr[idx], dtype=np.float32)
        y = np.concatenate([np.ones(n_pos, np.int32), np.zeros(n_neg, np.int32)])
        cov = aux["cover_regime_fp"][idx]
        w = np.where(y == 1, 1.0 + 0.35 * cov, 1.0).astype(np.float32)
        perm = rng.permutation(len(y))
        return X[perm], y[perm], w[perm]

    comp_map, n_comp = label(vis_clean, structure=np.ones((3, 3), dtype=int))
    comp_perm = rng.permutation(max(n_comp, 1)) + 1
    buf_struct = np.ones((7, 7), dtype=bool)

    X_blocks: list[np.ndarray] = []
    y_blocks: list[np.ndarray] = []
    w_blocks: list[np.ndarray] = []

    # World 0: whole-component hide-and-recover (50% hidden components, 3-px safety halo)
    half = max(1, len(comp_perm) // 2)
    hidden_ids = comp_perm[:half]
    cf_hidden = np.isin(comp_map, hidden_ids) & vis_clean
    cf_vis = vis_clean & (~binary_dilation(cf_hidden, structure=buf_struct))
    struct_fp, d_fp = compute_visible_structural_features(grid, cf_vis, aux)

    pos_pool = np.flatnonzero(cf_hidden[fp] & (d_fp > 3.0))
    neg_pool = np.flatnonzero(train_fp & (~vis_clean[fp]) & (d_fp > 3.0))
    n_p = min(len(pos_pool), pos_per_world)
    n_n = min(len(neg_pool), n_p * neg_ratio)
    if n_p >= 50 and n_n >= 50:
        sp = rng.choice(pos_pool, size=n_p, replace=False)
        sn = rng.choice(neg_pool, size=n_n, replace=False)
        idx = np.concatenate([sp, sn])
        X_blocks.append(np.hstack([np.asarray(phys_arr[idx], dtype=np.float32), struct_fp[idx]]))
        y_w = np.concatenate([np.ones(n_p, np.int32), np.zeros(n_n, np.int32)])
        y_blocks.append(y_w)
        w_blocks.append(np.where(y_w == 1, 1.0 + 0.35 * aux["cover_regime_fp"][idx], 1.0).astype(np.float32))
    del struct_fp, d_fp, cf_hidden, cf_vis

    # World 1: regional sub-basin block masking so far-field / quadrant-held-out pixels remain calibrated
    rows_fp, cols_fp = np.nonzero(fp)
    r_med = float(np.median(rows_fp[train_fp]))
    c_med = float(np.median(cols_fp[train_fp]))
    sub_block_fp = train_fp & (rows_fp >= r_med) & (cols_fp >= c_med)
    sub_block_2d = np.zeros(grid.shape, dtype=bool)
    sub_block_2d[fp] = sub_block_fp
    cf_vis_far = vis_clean & (~binary_dilation(sub_block_2d, iterations=8))
    struct_far, d_far = compute_visible_structural_features(grid, cf_vis_far, aux)

    pos_far = np.flatnonzero(vis_clean[fp] & sub_block_fp & (d_far > 8.0))
    neg_far = np.flatnonzero(train_fp & (~vis_clean[fp]) & sub_block_fp & (d_far > 8.0))
    n_pf = min(len(pos_far), pos_per_world // 2)
    n_nf = min(len(neg_far), n_pf * neg_ratio)
    if n_pf >= 50 and n_nf >= 50:
        spf = rng.choice(pos_far, size=n_pf, replace=False)
        snf = rng.choice(neg_far, size=n_nf, replace=False)
        idx_f = np.concatenate([spf, snf])
        X_blocks.append(np.hstack([np.asarray(phys_arr[idx_f], dtype=np.float32), struct_far[idx_f]]))
        y_f = np.concatenate([np.ones(n_pf, np.int32), np.zeros(n_nf, np.int32)])
        y_blocks.append(y_f)
        w_blocks.append(np.where(y_f == 1, 1.0 + 0.35 * aux["cover_regime_fp"][idx_f], 1.0).astype(np.float32))
    del struct_far, d_far

    X_all = np.vstack(X_blocks)
    y_all = np.concatenate(y_blocks)
    w_all = np.concatenate(w_blocks)
    perm = rng.permutation(len(y_all))
    return X_all[perm], y_all[perm], w_all[perm]


class HeterogeneousSTFDEnsemble:
    """Fast, memory-lean multi-capacity histogram-boosted + smooth linear-logit ensemble."""

    def __init__(self, mode: str = "full_4family", seed: int = 8702) -> None:
        self.mode = mode
        self.seed = seed
        self.models: list[tuple[str, float, object]] = []

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray) -> "HeterogeneousSTFDEnsemble":
        if self.mode == "single_hgb":
            m1 = HistGradientBoostingClassifier(
                max_iter=160,
                learning_rate=0.065,
                max_leaf_nodes=45,
                min_samples_leaf=50,
                l2_regularization=5.0,
                early_stopping=True,
                validation_fraction=0.12,
                n_iter_no_change=12,
                random_state=self.seed,
            )
            m1.fit(X, y, sample_weight=sample_weight)
            self.models = [("hgb_single", 1.0, m1)]
            return self

        hgb_deep = HistGradientBoostingClassifier(
            max_iter=210,
            learning_rate=0.055,
            max_leaf_nodes=63,
            min_samples_leaf=40,
            l2_regularization=3.0,
            max_features=0.85,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=14,
            random_state=self.seed,
        ).fit(X, y, sample_weight=sample_weight)

        hgb_mid = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_leaf_nodes=35,
            min_samples_leaf=65,
            l2_regularization=8.0,
            max_features=0.72,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=14,
            random_state=self.seed + 11,
        ).fit(X, y, sample_weight=sample_weight)

        hgb_smooth = HistGradientBoostingClassifier(
            max_iter=190,
            learning_rate=0.048,
            max_leaf_nodes=19,
            min_samples_leaf=110,
            l2_regularization=18.0,
            max_features=0.62,
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=14,
            random_state=self.seed + 23,
        ).fit(X, y, sample_weight=sample_weight)

        lin_prior = Pipeline(
            [
                ("scale", RobustScaler()),
                ("lr", LogisticRegression(C=0.5, max_iter=200)),
            ]
        ).fit(X, y, lr__sample_weight=sample_weight)

        self.models = [
            ("hgb_deep", 0.42, hgb_deep),
            ("hgb_mid", 0.30, hgb_mid),
            ("hgb_smooth", 0.23, hgb_smooth),
            ("linear_prior", 0.05, lin_prior),
        ]
        return self

    def predict_fp_surface(
        self,
        phys_arr: np.ndarray,
        struct_fp: np.ndarray | None,
        subset_idx: np.ndarray | None = None,
        chunk_size: int = 500_000,
    ) -> np.ndarray:
        """Stream probability predictions cleanly over `subset_idx` (or all `N_fp` pixels)."""
        n_fp = phys_arr.shape[0]
        target_idx = np.arange(n_fp, dtype=np.int64) if subset_idx is None else np.asarray(subset_idx, dtype=np.int64)
        out = np.zeros(n_fp, dtype=np.float32)

        for start in range(0, len(target_idx), chunk_size):
            idx_c = target_idx[start : start + chunk_size]
            if struct_fp is None:
                Xc = np.asarray(phys_arr[idx_c], dtype=np.float32)
            else:
                Xc = np.hstack([np.asarray(phys_arr[idx_c], dtype=np.float32), struct_fp[idx_c]])
            acc_logit = np.zeros(len(idx_c), dtype=np.float32)
            for _name, weight, mdl in self.models:
                p = np.clip(mdl.predict_proba(Xc)[:, 1], 1e-6, 1.0 - 1e-6)
                acc_logit += weight * np.log(p / (1.0 - p)).astype(np.float32)
            out[idx_c] = (1.0 / (1.0 + np.exp(-np.clip(acc_logit, -20.0, 20.0)))).astype(np.float32)
        return out


def apply_cover_propensity_calibration(
    prob_fp: np.ndarray,
    cover_regime_fp: np.ndarray,
    strength: float = 0.0,
) -> np.ndarray:
    """Optional smooth PU odds tilt without variance inflation."""
    if strength <= 0.0:
        return prob_fp
    p = np.clip(prob_fp, 1e-6, 1.0 - 1e-6)
    logit = np.log(p / (1.0 - p)) + strength * np.clip(cover_regime_fp, 0.0, 1.0)
    return (1.0 / (1.0 + np.exp(-np.clip(logit, -20.0, 20.0)))).astype(np.float32)


def emit_expected_credit_dots(
    surface_2d: np.ndarray,
    eligible_mask: np.ndarray,
    n_dots: int,
    min_dist_px: float = 2.83,
    use_expected_credit_kernel: bool = True,
) -> np.ndarray:
    """Emit deterministic binary `{0.0, 1.0}` float32 dots maximizing 300 m expected recall."""
    h, w = surface_2d.shape
    out = np.zeros((h, w), dtype=np.float32)
    if n_dots <= 0 or not eligible_mask.any():
        return out

    base = np.where(np.isfinite(surface_2d), np.clip(surface_2d, 0.0, 1.0), 0.0).astype(np.float32)
    if use_expected_credit_kernel:
        priority = 0.68 * convolve(base, TRI_KERNEL_300M, mode="nearest") + 0.32 * base
    else:
        priority = base

    er, ec = np.nonzero(eligible_mask)
    scores = priority[er, ec]
    pool_k = min(len(scores), max(n_dots * 12, n_dots))
    if pool_k < len(scores):
        top_sub = np.argpartition(-scores, pool_k - 1)[:pool_k]
        er = er[top_sub]
        ec = ec[top_sub]
        scores = scores[top_sub]

    order = np.lexsort((ec, er, -scores))
    er = er[order]
    ec = ec[order]

    rad, disc = _disc_mask(min_dist_px)
    blocked = np.zeros((h + 2 * rad, w + 2 * rad), dtype=bool)
    picked = 0
    for i in range(len(er)):
        r = int(er[i])
        c = int(ec[i])
        br = r + rad
        bc = c + rad
        if blocked[br, bc]:
            continue
        out[r, c] = 1.0
        blocked[br - rad : br + rad + 1, bc - rad : bc + rad + 1] |= disc
        picked += 1
        if picked >= n_dots:
            break

    if picked < n_dots:
        for i in range(len(er)):
            r = int(er[i])
            c = int(ec[i])
            if out[r, c] == 0.0:
                out[r, c] = 1.0
                picked += 1
                if picked >= n_dots:
                    break
    return out
