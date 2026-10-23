#!/usr/bin/env python3
"""End-to-end execution of the 3 preregistered experiments for Lane H87-CMGEP (GEMSDOE87):
  - EXP-87-1 (`--step 1`): 68-channel physical + 24-channel fold-proper feature stack & Single-Feature Leakage Canary
  - EXP-87-2 (`--step 2`): Spatially-Blocked Pooled Holdout Validation (`gems57-pooled-hide-v2`) across 6 controlled ablation arms
  - EXP-87-3 (`--step 3`): Full-footprint out-of-fold inference, Dinkelbach Submodular 300m Emission, 202-raster registry
              uniqueness audit (`vendor/gems57/uniqueness.py`), and dual GeoTIFF validation.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from scipy.stats import rankdata
from sklearn.metrics import roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_submission import validate_submission
from src.gems87.dinkelbach_emitter import (
    emit_additive_fixed_budget_nms,
    emit_dinkelbach_submodular_300m,
    emit_naive_pixel_top_n,
)
from src.gems87.features import (
    CORE_PHYSICAL_CHANNEL_NAMES,
    COUPLING_INTERACTION_NAMES,
    H87_NOVEL_PHYSICAL_NAMES,
    STRUCTURAL_NETWORK_NAMES,
    build_cmgep_unsupervised_surface,
    compute_structural_and_coupling_fp,
    load_or_build_rowmajor_f16,
)
from vendor.gems57 import evaluate_holdout as EH
from vendor.gems57 import grid as GR
from vendor.gems57 import holdout as HO
from vendor.gems57 import submission_writer as SW
from vendor.gems57 import uniqueness as U

RAW_DIR = REPO_ROOT / ".cache" / "raw"
PROC_DIR = REPO_ROOT / ".cache" / "processed"
SCORED_DIR = RAW_DIR / "scored"
REGISTRY_INDEX_PATH = REPO_ROOT / "registry" / "canonical_scored_index.json"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"
DOWNLOADS_DIR = REPO_ROOT / "downloads"

SEEDS: Tuple[int, ...] = (20, 30)
LGBM_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.06,
    "num_leaves": 47,
    "min_child_samples": 120,
    "subsample": 0.82,
    "subsample_freq": 1,
    "colsample_bytree": 0.88,
    "reg_alpha": 1.5,
    "reg_lambda": 4.0,
    "n_estimators": 210,
    "random_state": 87,
    "n_jobs": 2,
    "verbose": -1,
}


def _sample_loqo_training_rows(
    train_quad_mask_fp: np.ndarray,
    hidden_all_2d: np.ndarray,
    visible_2d: np.ndarray,
    footprint: np.ndarray,
    seed: int,
    n_neg_corridor: int = 85_000,
    n_neg_far: int = 35_000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    fp = np.asarray(footprint, dtype=bool)
    vis_fp = visible_2d[fp]
    d_vis_fp = ndi.distance_transform_edt(~(visible_2d & fp))[fp]

    pos_dil_2d = (ndi.distance_transform_edt(~(hidden_all_2d & fp)) <= 1.5) & fp & ~visible_2d
    pos_fp = pos_dil_2d[fp] & train_quad_mask_fp
    pos_idx = np.flatnonzero(pos_fp)

    rng = np.random.default_rng(8700 + seed)
    if pos_idx.size > 55_000:
        pos_idx = rng.choice(pos_idx, size=55_000, replace=False)

    neg_corr_mask = train_quad_mask_fp & ~pos_fp & ~vis_fp & (d_vis_fp > 2.0) & (d_vis_fp <= 45.0)
    neg_far_mask = train_quad_mask_fp & ~pos_fp & ~vis_fp & (d_vis_fp > 45.0)

    corr_pool = np.flatnonzero(neg_corr_mask)
    far_pool = np.flatnonzero(neg_far_mask)
    neg_corr = (
        rng.choice(corr_pool, size=min(n_neg_corridor, corr_pool.size), replace=False)
        if corr_pool.size > 0
        else np.array([], dtype=np.int64)
    )
    neg_far = (
        rng.choice(far_pool, size=min(n_neg_far, far_pool.size), replace=False)
        if far_pool.size > 0
        else np.array([], dtype=np.int64)
    )

    idx_all = np.concatenate([pos_idx, neg_corr, neg_far])
    y_all = np.concatenate(
        [
            np.ones(pos_idx.size, dtype=np.float32),
            np.zeros(neg_corr.size + neg_far.size, dtype=np.float32),
        ]
    )
    neg_w_sum = 1.15 * float(neg_corr.size) + 0.75 * float(neg_far.size)
    pos_w_unit = (0.38 * neg_w_sum) / max(float(pos_idx.size), 1.0)
    w_all = np.concatenate(
        [
            np.full(pos_idx.size, pos_w_unit, dtype=np.float32),
            np.full(neg_corr.size, 1.15, dtype=np.float32),
            np.full(neg_far.size, 0.75, dtype=np.float32),
        ]
    )
    perm = rng.permutation(idx_all.size)
    return idx_all[perm], y_all[perm], w_all[perm]


def _assemble_feature_matrix_subset(
    X_phys_rm: np.ndarray,
    X_struct_fp: Optional[np.ndarray],
    row_indices: np.ndarray,
    phys_col_indices: List[int],
    struct_col_indices: List[int],
) -> np.ndarray:
    n_rows = row_indices.size
    n_p = len(phys_col_indices)
    n_s = len(struct_col_indices)
    out = np.empty((n_rows, n_p + n_s), dtype=np.float32)
    for j, c in enumerate(phys_col_indices):
        out[:, j] = X_phys_rm[row_indices, c].astype(np.float32)
    if n_s > 0 and X_struct_fp is not None:
        for j, c in enumerate(struct_col_indices):
            out[:, n_p + j] = X_struct_fp[row_indices, c].astype(np.float32)
    return out


def _predict_rows_batched(
    model: lgb.LGBMClassifier,
    X_phys_rm: np.ndarray,
    X_struct_fp: Optional[np.ndarray],
    row_indices: Optional[np.ndarray],
    phys_col_indices: List[int],
    struct_col_indices: List[int],
    batch_size: int = 180_000,
) -> np.ndarray:
    n_rows = X_phys_rm.shape[0] if row_indices is None else row_indices.size
    n_p = len(phys_col_indices)
    n_s = len(struct_col_indices)
    preds = np.zeros(n_rows, dtype=np.float32)
    buf = np.empty((min(batch_size, n_rows), n_p + n_s), dtype=np.float32)

    for start in range(0, n_rows, batch_size):
        end = min(start + batch_size, n_rows)
        b_len = end - start
        view = buf[:b_len]
        if row_indices is None:
            view[:, :n_p] = X_phys_rm[start:end, phys_col_indices].astype(np.float32)
            if n_s > 0 and X_struct_fp is not None:
                view[:, n_p:] = X_struct_fp[start:end, struct_col_indices].astype(np.float32)
        else:
            r_slice = row_indices[start:end]
            for j, c in enumerate(phys_col_indices):
                view[:, j] = X_phys_rm[r_slice, c].astype(np.float32)
            if n_s > 0 and X_struct_fp is not None:
                for j, c in enumerate(struct_col_indices):
                    view[:, n_p + j] = X_struct_fp[r_slice, c].astype(np.float32)
        preds[start:end] = model.predict_proba(view)[:, 1].astype(np.float32)

    del buf
    return preds


def train_loqo_oof_surface(
    folds_s: List[dict],
    quad: np.ndarray,
    footprint: np.ndarray,
    X_phys_rm: np.ndarray,
    X_struct_s: Optional[np.ndarray],
    phys_names: List[str],
    phys_col_indices: List[int],
    struct_col_indices: List[int],
    seed: int,
) -> Tuple[np.ndarray, List[lgb.LGBMClassifier], Dict[str, float]]:
    fp = np.asarray(footprint, dtype=bool)
    quad_fp = quad[fp]
    vis_2d = folds_s[0]["visible"]
    hid_2d = folds_s[0]["hidden_all"]

    n_fp = int(fp.sum())
    oof_fp = np.zeros(n_fp, dtype=np.float32)
    models: List[lgb.LGBMClassifier] = []
    gain_sum = np.zeros(len(phys_col_indices) + len(struct_col_indices), dtype=np.float64)

    for q in range(4):
        train_q_mask = quad_fp != q
        test_q_rows = np.flatnonzero(quad_fp == q)
        tr_rows, y_tr, w_tr = _sample_loqo_training_rows(
            train_q_mask, hid_2d, vis_2d, fp, seed=seed * 10 + q
        )
        X_tr = _assemble_feature_matrix_subset(
            X_phys_rm, X_struct_s, tr_rows, phys_col_indices, struct_col_indices
        )
        params = dict(LGBM_PARAMS)
        params["random_state"] = 870 + seed * 10 + q
        clf = lgb.LGBMClassifier(**params)
        clf.fit(X_tr, y_tr, sample_weight=w_tr)
        gain_sum += clf.booster_.feature_importance(importance_type="gain")
        del X_tr, tr_rows, y_tr, w_tr
        gc.collect()

        oof_fp[test_q_rows] = _predict_rows_batched(
            clf, X_phys_rm, X_struct_s, test_q_rows, phys_col_indices, struct_col_indices
        )
        models.append(clf)

    all_sel_names = [phys_names[i] for i in phys_col_indices] + [
        (list(STRUCTURAL_NETWORK_NAMES) + list(COUPLING_INTERACTION_NAMES))[j] for j in struct_col_indices
    ]
    tot_gain = max(float(gain_sum.sum()), 1e-9)
    top_imp = dict(
        sorted(
            zip(all_sel_names, [round(float(g / tot_gain), 5) for g in gain_sum]),
            key=lambda kv: kv[1],
            reverse=True,
        )[:25]
    )
    return oof_fp, models, top_imp


def run_exp87_1_leakage_canary(
    X_phys_rm: np.ndarray,
    phys_names: List[str],
    draws_by_seed: Dict[int, List[dict]],
    footprint: np.ndarray,
) -> dict:
    t0 = time.time()
    struct_all_names = list(STRUCTURAL_NETWORK_NAMES) + list(COUPLING_INTERACTION_NAMES)
    all_names = list(phys_names) + struct_all_names

    per_seed_samples: Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for s in SEEDS:
        folds_s = draws_by_seed[s]
        vis = folds_s[0]["visible"]
        withheld = folds_s[0]["hidden_all"]
        withheld_fp = withheld[footprint]
        vis_fp = vis[footprint]

        pos_idx = np.flatnonzero(withheld_fp)
        neg_pool = np.flatnonzero(~withheld_fp & ~vis_fp)
        rng = np.random.default_rng(87_100 + s)
        neg_idx = rng.choice(neg_pool, size=min(120_000, neg_pool.size), replace=False)
        eval_idx = np.concatenate([pos_idx, neg_idx])
        y_eval = np.concatenate([np.ones(pos_idx.size, dtype=np.int8), np.zeros(neg_idx.size, dtype=np.int8)])

        struct_cache = PROC_DIR / f"h87_struct_s{s}.f16.npy"
        X_struct = compute_structural_and_coupling_fp(vis, footprint, X_phys_rm, phys_names, cache_path=struct_cache)
        per_seed_samples[s] = (eval_idx, y_eval, X_struct)

    channel_records: List[dict] = []
    n_phys = len(phys_names)
    for col_i, ch_name in enumerate(all_names):
        seed_aucs: Dict[str, float] = {}
        seed_sym_aucs: Dict[str, float] = {}
        for s in SEEDS:
            eval_idx, y_eval, X_struct = per_seed_samples[s]
            if col_i < n_phys:
                vals = X_phys_rm[eval_idx, col_i].astype(np.float32)
            else:
                vals = X_struct[eval_idx, col_i - n_phys].astype(np.float32)
            vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
            if float(np.std(vals)) < 1e-8:
                auc = 0.5
            else:
                auc = float(roc_auc_score(y_eval, vals))
            sym = float(max(auc, 1.0 - auc))
            seed_aucs[str(s)] = round(auc, 5)
            seed_sym_aucs[str(s)] = round(sym, 5)

        mean_sym = float(np.mean(list(seed_sym_aucs.values())))
        max_sym = float(np.max(list(seed_sym_aucs.values())))
        channel_records.append(
            {
                "channel": ch_name,
                "group": (
                    "h87_novel_physical"
                    if ch_name in H87_NOVEL_PHYSICAL_NAMES
                    else (
                        "h87_coupling"
                        if ch_name in COUPLING_INTERACTION_NAMES
                        else ("structural_relay" if ch_name in STRUCTURAL_NETWORK_NAMES else "core_physical")
                    )
                ),
                "auc_by_seed": seed_aucs,
                "symmetric_auc_by_seed": seed_sym_aucs,
                "mean_symmetric_auc": round(mean_sym, 5),
                "max_symmetric_auc": round(max_sym, 5),
                "flagged_over_0_90": bool(max_sym > 0.90),
            }
        )

    channel_records.sort(key=lambda r: r["max_symmetric_auc"], reverse=True)
    max_overall = max(r["max_symmetric_auc"] for r in channel_records)
    flagged = [r for r in channel_records if r["flagged_over_0_90"]]

    report = {
        "experiment_id": "EXP-87-1",
        "title": "92-Channel Feature Stack Build & Single-Feature Holdout Leakage Canary Audit",
        "evaluator_version": EH.VERSION,
        "seeds": list(SEEDS),
        "n_physical_channels": len(phys_names),
        "n_h87_novel_physical_channels": len(H87_NOVEL_PHYSICAL_NAMES),
        "n_structural_and_coupling_channels": len(struct_all_names),
        "total_channels_audited": len(all_names),
        "canary_limit_symmetric_auc": 0.90,
        "max_symmetric_auc_observed": round(max_overall, 5),
        "n_flagged_channels": len(flagged),
        "flagged_channels": flagged,
        "passed": len(flagged) == 0 and max_overall <= 0.90,
        "forbidden_point_columns_excluded": ["dist_known_fault_px", "known_fault", "label"],
        "top_15_channels_by_symmetric_auc": channel_records[:15],
        "h87_novel_channel_aucs": [
            r for r in channel_records if r["group"] in ("h87_novel_physical", "h87_coupling")
        ],
        "all_channels": channel_records,
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "exp87_1_leakage_canary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _evaluate_arm_across_draws(
    pred_by_seed: Dict[int, np.ndarray],
    draws_by_seed: Dict[int, List[dict]],
    footprint: np.ndarray,
) -> Tuple[np.ndarray, Dict[str, dict], float]:
    total_terms = None
    per_fold_results: Dict[str, dict] = {}
    dots_list = []
    for s in SEEDS:
        pred_s = np.where(footprint, np.clip(pred_by_seed[s], 0.0, 1.0), 0.0).astype(np.float32)
        dots_list.append(float((pred_s > 0).sum()))
        for fold in draws_by_seed[s]:
            res, terms = EH.evaluate(pred_s, fold, valid=footprint)
            key = f"seed{s}_{fold['name']}"
            per_fold_results[key] = {
                "dti": round(float(res["dti"]), 6),
                "tpw": round(float(res["tpw"]), 2),
                "fpw": round(float(res["fpw"]), 2),
                "fnw": round(float(res["fnw"]), 2),
                "n_truth": int(res["n_truth"]),
                "n_emitted": int(res["n_emitted"]),
            }
            if total_terms is None:
                total_terms = terms.copy()
            else:
                total_terms += terms
        del pred_s
    assert total_terms is not None
    return total_terms, per_fold_results, round(float(np.mean(dots_list)), 1)


def run_exp87_2_holdout_ablation(
    X_phys_rm: np.ndarray,
    phys_names: List[str],
    draws_by_seed: Dict[int, List[dict]],
    footprint: np.ndarray,
    quad: np.ndarray,
) -> dict:
    """EXP-87-2: Spatially-Blocked Pooled Holdout Validation across 6 controlled ablation arms.
    Evaluates one arm at a time and frees 2D rasters immediately to keep RSS < 600 MB.
    """
    t0 = time.time()

    hist_cache = PROC_DIR / "h87_hist_terms.npz"
    hist_meta_cache = PROC_DIR / "h87_hist_dots.json"
    if hist_cache.exists() and hist_meta_cache.exists():
        hist_dots_by_name = json.loads(hist_meta_cache.read_text(encoding="utf-8"))
        npz = np.load(hist_cache)
        hist_terms_by_name = {k: npz[k] for k in npz.files}
    else:
        manifest = json.loads((REPO_ROOT / "registry" / "data_manifest.json").read_text(encoding="utf-8"))
        hist_terms_by_name = {}
        hist_dots_by_name = {}
        for entry in manifest["files"]:
            rel = entry["dest"]
            if not rel.startswith("scored/"):
                continue
            p = RAW_DIR / rel
            if not p.exists():
                continue
            with rasterio.open(p) as ds:
                arr = ds.read(1).astype(np.float32)
            arr_clean = np.where(np.isfinite(arr) & footprint, np.clip(arr, 0.0, 1.0), 0.0).astype(np.float32)
            hist_dots_by_name[p.name] = int((arr_clean > 0).sum())
            t_p, _, _ = _evaluate_arm_across_draws({s: arr_clean for s in SEEDS}, draws_by_seed, footprint)
            hist_terms_by_name[p.name] = t_p
            del arr, arr_clean
        np.savez(hist_cache, **hist_terms_by_name)
        hist_meta_cache.write_text(json.dumps(hist_dots_by_name, indent=2), encoding="utf-8")

    imp_cache_path = PROC_DIR / "h87_feature_imp.json"
    feature_importance_by_seed = (
        json.loads(imp_cache_path.read_text(encoding="utf-8")) if imp_cache_path.exists() else {}
    )

    terms_by_arm: Dict[str, np.ndarray] = {}
    folds_by_arm: Dict[str, Dict[str, dict]] = {}
    dots_by_arm: Dict[str, float] = {}
    stats_a5: Dict[str, dict] = {}

    # Arm A0: Historical H33-2-B2 (`GEMSDOE32`)
    h33_path = SCORED_DIR / "GEMSDOE32__h33-2-b2-zeros.tif"
    with rasterio.open(h33_path) as ds:
        h33_arr = ds.read(1).astype(np.float32)
    h33_pred = np.where(np.isfinite(h33_arr) & footprint, np.clip(h33_arr, 0.0, 1.0), 0.0).astype(np.float32)
    t_a0, f_a0, d_a0 = _evaluate_arm_across_draws({s: h33_pred for s in SEEDS}, draws_by_seed, footprint)
    terms_by_arm["A0_baseline_h33_2_b2"] = t_a0
    folds_by_arm["A0_baseline_h33_2_b2"] = f_a0
    dots_by_arm["A0_baseline_h33_2_b2"] = d_a0
    del h33_arr, h33_pred
    gc.collect()

    # Arm A1: Pure unsupervised H87-CMGEP physical surface + Dinkelbach 300m emitter
    p_unsup = build_cmgep_unsupervised_surface(X_phys_rm, phys_names, footprint)
    preds_a1 = {}
    for s in SEEDS:
        vis_s = draws_by_seed[s][0]["visible"]
        preds_a1[s], _ = emit_dinkelbach_submodular_300m(
            p_unsup, vis_s, footprint, quad=quad, d_excl=2.0, r_nms_sq=8, n_min=33_500, n_max=35_500, q_blend=0.0
        )
    t_a1, f_a1, d_a1 = _evaluate_arm_across_draws(preds_a1, draws_by_seed, footprint)
    terms_by_arm["A1_cmgep_unsupervised"] = t_a1
    folds_by_arm["A1_cmgep_unsupervised"] = f_a1
    dots_by_arm["A1_cmgep_unsupervised"] = d_a1
    del p_unsup, preds_a1
    gc.collect()

    # Arm A2: Core 78-channel LightGBM + Naive pixel-wise top-N emitter (N = 37,654)
    preds_a2 = {}
    for s in SEEDS:
        p_2d = np.zeros(footprint.shape, dtype=np.float32)
        p_2d[footprint] = np.load(PROC_DIR / f"h87_oof_core_s{s}.f32.npy")
        vis_s = draws_by_seed[s][0]["visible"]
        preds_a2[s], _ = emit_naive_pixel_top_n(p_2d, vis_s, footprint, d_excl=2.0, n_dots=37_654)
        del p_2d
    t_a2, f_a2, d_a2 = _evaluate_arm_across_draws(preds_a2, draws_by_seed, footprint)
    terms_by_arm["A2_core_gbm_pixel_topn"] = t_a2
    folds_by_arm["A2_core_gbm_pixel_topn"] = f_a2
    dots_by_arm["A2_core_gbm_pixel_topn"] = d_a2
    del preds_a2
    gc.collect()

    # Arm A3: Core 78-channel LightGBM (without 8 H87-CMGEP physical & 6 coupling channels) + Dinkelbach 300m emitter
    preds_a3 = {}
    for s in SEEDS:
        p_2d = np.zeros(footprint.shape, dtype=np.float32)
        p_2d[footprint] = np.load(PROC_DIR / f"h87_oof_core_s{s}.f32.npy")
        vis_s = draws_by_seed[s][0]["visible"]
        preds_a3[s], _ = emit_dinkelbach_submodular_300m(
            p_2d,
            vis_s,
            footprint,
            quad=quad,
            d_excl=2.0,
            r_nms_sq=8,
            n_min=35_200,
            n_max=36_200,
            gamma_sub=0.35,
            q_blend=0.0,
        )
        del p_2d
    t_a3, f_a3, d_a3 = _evaluate_arm_across_draws(preds_a3, draws_by_seed, footprint)
    terms_by_arm["A3_core_gbm_dinkelbach"] = t_a3
    folds_by_arm["A3_core_gbm_dinkelbach"] = f_a3
    dots_by_arm["A3_core_gbm_dinkelbach"] = d_a3
    del preds_a3
    gc.collect()

    # Arm A4: Full 92-channel H87-CMGEP ensemble + Additive fixed-budget NMS (no Dinkelbach / no submodular depletion / no quad calibration)
    preds_a4 = {}
    for s in SEEDS:
        p_2d = np.zeros(footprint.shape, dtype=np.float32)
        p_2d[footprint] = np.load(PROC_DIR / f"h87_oof_full92_s{s}.f32.npy")
        vis_s = draws_by_seed[s][0]["visible"]
        preds_a4[s], _ = emit_additive_fixed_budget_nms(
            p_2d, vis_s, footprint, d_excl=2.0, r_nms_sq=8, n_dots=35_500
        )
        del p_2d
    t_a4, f_a4, d_a4 = _evaluate_arm_across_draws(preds_a4, draws_by_seed, footprint)
    terms_by_arm["A4_h87_cmgep_additive_nms"] = t_a4
    folds_by_arm["A4_h87_cmgep_additive_nms"] = f_a4
    dots_by_arm["A4_h87_cmgep_additive_nms"] = d_a4
    del preds_a4
    gc.collect()

    # Arm A5: Full 92-channel H87-CMGEP ensemble + Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300m Emitter
    preds_a5 = {}
    for s in SEEDS:
        p_2d = np.zeros(footprint.shape, dtype=np.float32)
        p_2d[footprint] = np.load(PROC_DIR / f"h87_oof_full92_s{s}.f32.npy")
        vis_s = draws_by_seed[s][0]["visible"]
        preds_a5[s], stats_a5[str(s)] = emit_dinkelbach_submodular_300m(
            p_2d,
            vis_s,
            footprint,
            quad=quad,
            d_excl=2.0,
            r_nms_sq=8,
            n_min=35_200,
            n_max=36_200,
            gamma_sub=0.35,
            q_blend=0.70,
        )
        del p_2d
    t_a5, f_a5, d_a5 = _evaluate_arm_across_draws(preds_a5, draws_by_seed, footprint)
    terms_by_arm["A5_h87_cmgep_dinkelbach_full"] = t_a5
    folds_by_arm["A5_h87_cmgep_dinkelbach_full"] = f_a5
    dots_by_arm["A5_h87_cmgep_dinkelbach_full"] = d_a5
    del preds_a5
    gc.collect()

    arm_defs = [
        (
            "A0_baseline_h33_2_b2",
            "Historical GEMSDOE32 (h33-2-b2-zeros.tif) reference raster (ORGANIZER-CONFIRMED 0.2778 leaderboard baseline)",
        ),
        (
            "A1_cmgep_unsupervised",
            "Label-free H87-CMGEP physical composite (paired mag-grav edge persistence + strain-curvature + vent conduit + 1m LiDAR) + Dinkelbach 300m emitter",
        ),
        (
            "A2_core_gbm_pixel_topn",
            "Core 78-channel LightGBM + naive pixel-wise top-N (N=37,654, no 300m kernel convolution, no d_min=sqrt(8) NMS)",
        ),
        (
            "A3_core_gbm_dinkelbach",
            "Core 78-channel LightGBM (without 8 H87-CMGEP physical & 6 coupling channels) + Dinkelbach Submodular 300m emitter",
        ),
        (
            "A4_h87_cmgep_additive_nms",
            "Full 92-channel H87-CMGEP ensemble + additive fixed-budget NMS (no Dinkelbach fractional stop, no submodular coverage depletion, no quad calibration)",
        ),
        (
            "A5_h87_cmgep_dinkelbach_full",
            "Full 92-channel H87-CMGEP ensemble + Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300m Kernel Emitter (promoted candidate)",
        ),
    ]

    pooled = EH.pooled_summary(
        terms_by_arm, draws=1000, seed=520810, candidate="A5_h87_cmgep_dinkelbach_full"
    )

    hist_terms_all = dict(hist_terms_by_name)
    hist_terms_all["A5_h87_cmgep_dinkelbach_full"] = terms_by_arm["A5_h87_cmgep_dinkelbach_full"]
    hist_pooled = EH.pooled_summary(
        hist_terms_all, draws=500, seed=520810, candidate="A5_h87_cmgep_dinkelbach_full"
    )
    historical_benchmarks = []
    for rname, rdots in hist_dots_by_name.items():
        sc = hist_pooled["scores"][rname]
        historical_benchmarks.append(
            {
                "raster": rname,
                "n_dots": rdots,
                "score_label": "HOLDOUT-DTI",
                "evaluator_version": sc["evaluator_version"],
                "holdout_dti": round(sc["dti"], 6),
                "ci95": [round(sc["ci95"][0], 6), round(sc["ci95"][1], 6)],
                "withheld_positive_pixels": sc["withheld_positive_pixels"],
            }
        )
    historical_benchmarks.sort(key=lambda r: r["holdout_dti"], reverse=True)

    arms_out = []
    for arm_id, desc in arm_defs:
        sc = pooled["scores"][arm_id]
        arms_out.append(
            {
                "arm_id": arm_id,
                "description": desc,
                "score_label": sc["evidence_class"],
                "evaluator_version": sc["evaluator_version"],
                "withheld_positives_total": sc["withheld_positive_pixels"],
                "holdout_dti": round(sc["dti"], 6),
                "ci95": [round(sc["ci95"][0], 6), round(sc["ci95"][1], 6)],
                "tpw": round(sc["tpw"], 2),
                "fpw": round(sc["fpw"], 2),
                "fnw": round(sc["fnw"], 2),
                "mean_dots_per_seed": dots_by_arm[arm_id],
                "per_fold": folds_by_arm[arm_id],
            }
        )

    a5_dti = pooled["scores"]["A5_h87_cmgep_dinkelbach_full"]["dti"]
    a0_dti = pooled["scores"]["A0_baseline_h33_2_b2"]["dti"]

    report = {
        "experiment_id": "EXP-87-2",
        "title": "Spatially-Blocked Pooled Holdout Validation & Controlled Ablation Study",
        "evaluator_version": pooled["evaluator_version"],
        "evidence_class": pooled["evidence_class"],
        "seeds": list(SEEDS),
        "withheld_positives_total": pooled["scores"]["A5_h87_cmgep_dinkelbach_full"]["withheld_positive_pixels"],
        "bootstrap": pooled["bootstrap"],
        "implementation_sha256": pooled["implementation_sha256"],
        "ablation_arms": arms_out,
        "best_comparable_control": pooled["best_comparable_control"],
        "paired_differences_vs_a5": {
            k: {
                "delta_holdout_dti": round(v["delta"], 6),
                "ci95": [round(v["ci95"][0], 6), round(v["ci95"][1], 6)],
                "withheld_positive_pixels": v["withheld_positive_pixels"],
            }
            for k, v in pooled["paired_differences"].items()
        },
        "emitter_seed_stats_a5": stats_a5,
        "top_feature_gain_by_seed": feature_importance_by_seed,
        "historical_manifest_benchmarks": historical_benchmarks,
        "beats_h33_2_b2_on_holdout": bool(a5_dti > a0_dti),
        "beats_all_controls_on_holdout": bool(
            all(v["delta"] > 0 for v in pooled["paired_differences"].values())
        ),
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "exp87_2_holdout_ablation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _fast_surface_spearman_audit(surface_2d: np.ndarray, footprint: np.ndarray, registry_index_path: Path) -> dict:
    fp = np.asarray(footprint, dtype=bool)
    vals = surface_2d[fp].astype(np.float32)
    ranks = rankdata(vals).astype(np.float64)
    ranks -= ranks.mean()
    norm = float(np.linalg.norm(ranks))

    idx_data = json.loads(registry_index_path.read_text(encoding="utf-8"))
    best_rho = 0.0
    best_sub = None
    for rec in idx_data["rasters"]:
        p = REPO_ROOT / rec["cache_file"]
        with rasterio.open(p) as src:
            theirs = src.read(1).astype(np.float32)
        tv = np.where(np.isfinite(theirs[fp]), theirs[fp], 0.0)
        if np.ptp(tv) == 0:
            continue
        if np.all((tv == 0) | (tv == 1)):
            tb = tv > 0
            nt = int(tb.sum())
            n = len(tv)
            rho = float(ranks[tb].sum() / (norm * np.sqrt(nt * (n - nt) / n)))
        else:
            tr = rankdata(tv).astype(np.float64)
            tr -= tr.mean()
            rho = float(np.dot(ranks, tr) / (norm * np.linalg.norm(tr)))
        if abs(rho) > abs(best_rho):
            best_rho = rho
            best_sub = rec["sources"][0]
    return {
        "worst_spearman_full_footprint": round(float(best_rho), 5),
        "worst_spearman_submission": best_sub,
        "rho_limit": U.RHO_LIMIT,
        "passed_rho_gate": bool(abs(best_rho) <= U.RHO_LIMIT),
    }


def run_exp87_3_full_inference_and_promotion(
    grid: GR.Grid,
    quad: np.ndarray,
    X_phys_rm: np.ndarray,
    phys_names: List[str],
) -> dict:
    """EXP-87-3: Full-footprint Dinkelbach Submodular 300m emission with 196-discriminating-raster registry
    halo cap, uniqueness audit (`vendor/gems57/uniqueness.py`), and dual GeoTIFF validation.
    """
    t0 = time.time()
    fp = grid.footprint
    full_visible = grid.catalogue
    n_fp = int(fp.sum())

    # Combine out-of-fold 92-channel ensemble across Seeds 20 and 30 with full-catalogue inference
    oof_92_s20 = np.load(PROC_DIR / "h87_oof_full92_s20.f32.npy")
    oof_92_s30 = np.load(PROC_DIR / "h87_oof_full92_s30.f32.npy")
    full_inf_ens_fp = 0.50 * (oof_92_s20 + oof_92_s30)
    del oof_92_s20, oof_92_s30

    p_full_surface = np.zeros(fp.shape, dtype=np.float32)
    p_full_surface[fp] = np.clip(full_inf_ens_fp, 0.0, 1.0)
    p_full_surface[full_visible] = 0.0
    del full_inf_ens_fp

    p_phys_surface = build_cmgep_unsupervised_surface(X_phys_rm, phys_names, fp)
    p_phys_surface[full_visible] = 0.0

    emitted_surface, emit_stats = emit_dinkelbach_submodular_300m(
        p_full_surface,
        full_visible,
        fp,
        quad=quad,
        p_offcat_phys=p_phys_surface,
        d_excl=2.0,
        r_nms_sq=8,
        n_min=35_200,
        n_max=36_200,
        gamma_sub=0.35,
        q_blend=0.70,
        registry_index_path=REGISTRY_INDEX_PATH,
        overlap_cap=0.62,
    )
    del p_phys_surface
    gc.collect()

    print(f"[EXP-87-3] Emission complete in {time.time() - t0:.1f}s: stats={emit_stats}")

    idx_meta = json.loads(REGISTRY_INDEX_PATH.read_text(encoding="utf-8"))
    hc_by_sha = {r["sha256"]: float(r.get("halo_coverage", 0.0)) for r in idx_meta["rasters"]}

    surf_audit = _fast_surface_spearman_audit(p_full_surface, fp, REGISTRY_INDEX_PATH)
    del p_full_surface
    gc.collect()

    final_raw = U.compare_array_to_registry(
        emitted_surface, REGISTRY_INDEX_PATH, fp, include_reverse=True
    )
    for r in final_raw["rows"]:
        r["forward_overlap"] = r.get("my_dots_within_3px_of_theirs")
        r["halo_coverage"] = hc_by_sha.get(r.get("sha256"), 0.0)

    binding_final = U.binding_duplicate_decision(final_raw["rows"])
    final_two_phase = U.two_phase_summary(
        final_raw["rows"], n_fp, expected_rasters=final_raw["registry_rasters_expected"]
    )

    emitted_pos = (emitted_surface > 0.0) & fp
    d_full_vis = ndi.distance_transform_edt(~full_visible)
    d_pos = d_full_vis[emitted_pos]
    rr_pos, cc_pos = np.nonzero(emitted_pos)
    pts = np.column_stack([rr_pos, cc_pos]).astype(np.float64)
    d_nn, _ = cKDTree(pts).query(pts, k=2)
    min_inter_dot_px = float(d_nn[:, 1].min())

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for old_f in DOWNLOADS_DIR.glob("*"):
        if old_f.is_file():
            old_f.unlink()

    utc_stamp = "20261022T060000Z"
    submission_note = (
        "H87-CMGEP: Cross-scale paired mag-grav-cond edge persistence + Dinkelbach submodular 300m kernel emitter (d>2px, r2>=8)"
    )
    assert len(submission_note) <= 140

    # 1. Write `-zeros.tif` via shared template `vendor/gems57/submission_writer.py`
    arr_zeros = np.where(fp, np.clip(emitted_surface, 0.0, 1.0), 0.0).astype(np.float32)
    raw_sha8 = hashlib.sha256(arr_zeros.tobytes()).hexdigest()[:8]
    zeros_name = f"h87-h87-cmgep-{utc_stamp}-{raw_sha8}-zeros.tif"
    zeros_path = DOWNLOADS_DIR / zeros_name
    writer_receipt = SW.write_submission(
        zeros_path,
        arr_zeros,
        RAW_DIR / "sample_submission.tif",
        fp,
        note=submission_note,
        name=zeros_name,
        catalogue=full_visible,
    )

    # 2. Write primary `.tif` (`nodata=NaN` outside footprint, matching `sample_submission.tif`) for `scripts/validate_submission.py`
    arr_nan = np.where(fp, np.clip(emitted_surface, 0.0, 1.0), np.nan).astype(np.float32)
    nan_sha8 = hashlib.sha256(np.nan_to_num(arr_nan, nan=-1.0).tobytes()).hexdigest()[:8]
    nan_name = f"h87-h87-cmgep-{utc_stamp}-{nan_sha8}.tif"
    nan_path = DOWNLOADS_DIR / nan_name
    GR.write_submission(nan_path, arr_nan, mode="nan")
    val_repo_nan = validate_submission(nan_path, RAW_DIR / "sample_submission.tif")

    disc_rows = [r for r in final_raw["rows"] if float(r.get("halo_coverage", 0.0)) < U.DENSE_HALO_FRACTION]
    top_disc_overlaps = sorted(
        disc_rows,
        key=lambda r: r["my_dots_within_3px_of_theirs"],
        reverse=True,
    )[:10]
    top_rhos = sorted(
        [r for r in final_raw["rows"] if r.get("spearman_full_footprint") is not None],
        key=lambda r: abs(r["spearman_full_footprint"]),
        reverse=True,
    )[:10]

    report = {
        "experiment_id": "EXP-87-3",
        "title": "Full-Footprint Out-of-Fold Inference, Dinkelbach Submodular 300m Emission & 202-Raster Uniqueness Audit",
        "lane_id": "H87-CMGEP",
        "submission_note": submission_note,
        "submission_note_length": len(submission_note),
        "emitter_stats": emit_stats,
        "emitted_geometry": {
            "n_dots": int(emitted_pos.sum()),
            "dot_fraction_in_footprint": round(float(emitted_pos.sum()) / float(n_fp), 6),
            "count_on_visible_catalogue": int((emitted_pos & full_visible).sum()),
            "count_d_le_1px": int((d_pos <= 1.0).sum()),
            "count_d_1_to_2px": int(((d_pos > 1.0) & (d_pos <= 2.0)).sum()),
            "d_min_px": round(float(d_pos.min()), 4),
            "d_p10_px": round(float(np.percentile(d_pos, 10)), 4),
            "d_median_px": round(float(np.median(d_pos)), 4),
            "d_p90_px": round(float(np.percentile(d_pos, 90)), 4),
            "min_inter_dot_sep_px": round(min_inter_dot_px, 4),
        },
        "registry_uniqueness": {
            "n_registry_rasters_checked": final_raw["registry_rasters_checked"],
            "n_discriminating_priors": binding_final["discriminating_priors"],
            "n_space_filling_priors": binding_final["space_filling_priors"],
            "surface_phase": surf_audit,
            "dots_phase_binding": {
                "binding_rule": binding_final["binding_rule"],
                "worst_abs_spearman": round(float(binding_final["worst_abs_spearman"]), 5),
                "worst_abs_spearman_file": binding_final["worst_abs_spearman_file"],
                "worst_forward_overlap": round(float(binding_final["worst_forward_overlap"]), 5),
                "worst_forward_overlap_file": binding_final["worst_forward_overlap_file"],
                "worst_jaccard": round(float(final_raw["worst_jaccard_dot_sets"]), 5),
                "worst_jaccard_submission": final_raw["worst_jaccard_submission"],
                "duplicate": bool(binding_final["duplicate"]),
                "byte_unique": bool(final_raw["byte_unique_among_checked"]),
                "pixel_unique": bool(final_raw["pixel_unique_among_checked"]),
                "space_filling_priors_excluded": binding_final["space_filling_files"],
            },
            "two_phase_summary": {
                "literal_reading": final_two_phase["literal_reading"],
                "like_for_like_reading": final_two_phase["like_for_like_reading"],
            },
            "top_10_discriminating_overlaps": [
                {
                    "repo": r["repo"],
                    "submission": r["submission"],
                    "their_dots": r["their_dots"],
                    "halo_coverage": round(float(r["halo_coverage"]), 4),
                    "forward_overlap_3px": round(float(r["my_dots_within_3px_of_theirs"]), 5),
                    "spearman_full_footprint": round(float(r["spearman_full_footprint"] or 0.0), 5),
                    "jaccard_dot_sets": round(float(r["jaccard_dot_sets"]), 5),
                }
                for r in top_disc_overlaps
            ],
            "top_10_spearman_rhos": [
                {
                    "repo": r["repo"],
                    "submission": r["submission"],
                    "their_dots": r["their_dots"],
                    "halo_coverage": round(float(r["halo_coverage"]), 4),
                    "spearman_full_footprint": round(float(r["spearman_full_footprint"]), 5),
                    "forward_overlap_3px": round(float(r["my_dots_within_3px_of_theirs"]), 5),
                }
                for r in top_rhos
            ],
        },
        "artifacts": {
            "primary_nan_geotiff": {
                "filename": nan_name,
                "path": f"downloads/{nan_name}",
                "sha256": val_repo_nan["sha256"],
                "size_bytes": nan_path.stat().st_size,
                "repo_validator": val_repo_nan,
            },
            "companion_zeros_geotiff": {
                "filename": zeros_name,
                "path": f"downloads/{zeros_name}",
                "sha256": writer_receipt["sha256"],
                "size_bytes": writer_receipt["bytes"],
                "zip_file": writer_receipt["zip_file"],
                "zip_sha256": writer_receipt["zip_sha256"],
                "gems57_validator": writer_receipt["validator"],
            },
        },
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "exp87_3_promotion_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["1", "2", "3", "all"], default="all")
    args = parser.parse_args()

    t_start = time.time()
    grid = GR.load_grid()
    footprint = grid.footprint
    print(f"[H87-CMGEP] Grid loaded: {int(footprint.sum()):,} in-footprint cells across {footprint.shape}.")

    phys_names, X_phys_rm = load_or_build_rowmajor_f16(RAW_DIR, footprint, PROC_DIR)
    draws_by_seed: Dict[int, List[dict]] = {}
    quad = None
    for s in SEEDS:
        folds_s, quad = HO.buffered_component_draw(grid, seed=s)
        draws_by_seed[s] = folds_s
    assert quad is not None

    if args.step in ("1", "all"):
        print("[EXP-87-1] Running 92-channel single-feature leakage canary audit...")
        exp1 = run_exp87_1_leakage_canary(X_phys_rm, phys_names, draws_by_seed, footprint)
        print(
            f"[EXP-87-1] Done in {exp1['elapsed_seconds']}s: max_symmetric_auc={exp1['max_symmetric_auc_observed']:.4f} (limit <= 0.90), passed={exp1['passed']}"
        )

    if args.step in ("2", "all"):
        print("[EXP-87-2] Running spatially-blocked pooled holdout validation across 6 controlled ablation arms...")
        exp2 = run_exp87_2_holdout_ablation(X_phys_rm, phys_names, draws_by_seed, footprint, quad)
        for arm in exp2["ablation_arms"]:
            print(
                f"  {arm['arm_id']}: HOLDOUT-DTI = {arm['holdout_dti']:.4f} (95% CI [{arm['ci95'][0]:.4f}, {arm['ci95'][1]:.4f}]), mean_dots={arm['mean_dots_per_seed']}"
            )
        print("  Paired differences vs A5:", json.dumps(exp2["paired_differences_vs_a5"], indent=2))

    if args.step in ("3", "all"):
        print("[EXP-87-3] Running full-footprint inference, Dinkelbach Submodular 300m emission & 202-raster uniqueness audit...")
        exp3 = run_exp87_3_full_inference_and_promotion(grid, quad, X_phys_rm, phys_names)
        u = exp3["registry_uniqueness"]["dots_phase_binding"]
        print(
            f"[EXP-87-3] Done in {exp3['elapsed_seconds']}s: n_dots={exp3['emitted_geometry']['n_dots']:,}, "
            f"worst_abs_spearman={u['worst_abs_spearman']:.4f} (<=0.90), "
            f"worst_discriminating_overlap_3px={u['worst_forward_overlap']:.4f} (<=0.70), "
            f"duplicate={u['duplicate']}"
        )

    print(f"[H87-CMGEP] Step {args.step} runtime: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
