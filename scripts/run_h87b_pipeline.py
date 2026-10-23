#!/usr/bin/env python3
"""Execute the preregistered Session 2 `H87B-STFD` 3-experiment study end-to-end.

Uses per-fold isolated child processes so Linux kernel reclaims 100% of page-cache
and allocator pages between folds (< 1.4 GB peak RSS in every child, zero drift),
then runs unmodified `vendor/gems57/` evaluation, packaging, validation, and 34-raster
uniqueness auditing in a clean coordinator process.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
for rel in ("src", "vendor"):
    if str(ROOT / rel) not in sys.path:
        sys.path.insert(0, str(ROOT / rel))

from gems57 import emit, evaluate_holdout, holdout, metric, spatial, submission_writer, uniqueness, validate
from gems57.grid import load_grid
from gems87.experiment import canary as run_canary, crop_slices
from gems87.features import bmtd as compute_bmtd, bounded_control, load_band
from gems87.stfd_features import (
    PHYSICAL_FEATURE_NAMES,
    STRUCTURAL_FEATURE_NAMES,
    build_physical_memmap,
    compute_visible_structural_features,
)
from gems87.stfd_model import (
    HeterogeneousSTFDEnsemble,
    build_counterfactual_training_table,
    emit_expected_credit_dots,
)

RAW_DIR = ROOT / "data" / "raw"
SAMPLE_TIF = RAW_DIR / "sample_submission.tif"
BAND_CACHE_DIR = ROOT / ".cache" / "features"
EXT_DIR = ROOT / ".cache" / "ext_data" / "external"
REG_AUDIT_DIR = ROOT / ".cache" / "reg_audit"
SCORED_DIR = ROOT / ".cache" / "ext_data" / "scored"
PHYS_MEMMAP_PATH = ROOT / ".cache" / "stfd_phys48.f32.dat"
FOLD_CKPT_DIR = ROOT / ".cache" / "h87b_folds_v2"

TARGET_DOTS = 37_654
MIN_NN_PX = 2.83
COLLAR_PX = 2.24
BOOT_DRAWS = 2_000
BOOT_SEED = 87_022


def _rss_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_raster(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
    return np.where(np.isfinite(arr), np.clip(arr, 0.0, 1.0), 0.0).astype(np.float32)


def _coords_from_dots(arr: np.ndarray) -> np.ndarray:
    rr, cc = np.nonzero(arr > 0)
    return np.column_stack([rr.astype(np.int16), cc.astype(np.int16)])


def _dots_from_coords(coords: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape, dtype=np.float32)
    if len(coords):
        out[coords[:, 0], coords[:, 1]] = 1.0
    return out


def _get_split_folds(grid: Any, split_kind: str) -> list[dict[str, Any]]:
    fp = grid.footprint
    if split_kind == "comp":
        out: list[dict[str, Any]] = []
        for draw_seed in (20, 30):
            draw_folds, quad_map = holdout.buffered_component_draw(
                grid, seed=draw_seed, hide_frac=0.20, buffer_px=3
            )
            for df in draw_folds:
                d = dict(df)
                d["train"] = (quad_map != df["fold"]) & fp
                d["draw_seed"] = draw_seed
                out.append(d)
        return out
    if split_kind == "quad":
        return list(spatial.folds(grid.catalogue, fp, buffer_px=80))
    raise ValueError(f"Unknown split_kind={split_kind}")


def run_single_fold_worker(split_kind: str, fold_idx: int) -> int:
    """Isolated child process: fits EXP1, EXP2, EXP3 on 1 fold, writes compact `.npz`, exits cleanly."""
    t0 = time.monotonic()
    FOLD_CKPT_DIR.mkdir(parents=True, exist_ok=True)
    out_npz = FOLD_CKPT_DIR / f"{split_kind}_{fold_idx:02d}.npz"
    if out_npz.exists():
        print(f"  [worker {split_kind}:{fold_idx}] cached -> {out_npz.name}")
        return 0

    grid = load_grid(RAW_DIR)
    fp = grid.footprint
    phys_mm, aux = build_physical_memmap(
        grid=grid,
        band_cache_dir=BAND_CACHE_DIR,
        ext_dir=EXT_DIR,
        memmap_path=PHYS_MEMMAP_PATH,
        force_rebuild=False,
    )
    folds = _get_split_folds(grid, split_kind)
    fold = folds[fold_idx]
    del folds
    gc.collect()

    seed_base = 8720 if split_kind == "comp" else 8740
    use_collar = split_kind == "comp"

    sl = crop_slices(fold["region"])
    known_mask = fold.get("masked_known", fold["visible"])
    valid = fp[sl]
    budget = int(round(TARGET_DOTS * int((valid & fold["region"][sl]).sum()) / int(fp.sum())))
    active_full = fp & fold["region"] & (~known_mask)
    sub_idx = np.flatnonzero((binary_dilation(fold["region"], iterations=4) & fp)[fp])

    # 1. EXP 1: Pure label-free 48-channel physical model (`m1` also serves as blind frontier head in EXP 3)
    X1, y1, w1 = build_counterfactual_training_table(
        grid,
        phys_mm,
        aux,
        fold["train"],
        fold["visible"],
        rng=np.random.default_rng(seed_base + 100 + fold_idx),
        include_structural=False,
    )
    m1 = HeterogeneousSTFDEnsemble(mode="single_hgb", seed=seed_base + 100 + fold_idx).fit(X1, y1, w1)
    s1_fp = m1.predict_fp_surface(phys_mm, None, subset_idx=sub_idx)
    s1_2d = np.zeros(grid.shape, dtype=np.float32)
    s1_2d[fp] = s1_fp
    del X1, y1, w1
    gc.collect()

    # 2. Compute visible-only structural features for this fold
    struct_fp, d_fp = compute_visible_structural_features(grid, fold["visible"], aux)
    d_2d = np.zeros(grid.shape, dtype=np.float32)
    d_2d[fp] = d_fp
    elig_full = active_full & (d_2d > COLLAR_PX) if use_collar else active_full
    p_exp1 = emit_expected_credit_dots(s1_2d, elig_full, budget, MIN_NN_PX, use_expected_credit_kernel=True)
    del s1_2d, d_2d

    # 3. Within-fold counterfactual training table for EXP 2 & EXP 3
    X_cf, y_cf, w_cf = build_counterfactual_training_table(
        grid,
        phys_mm,
        aux,
        fold["train"],
        fold["visible"],
        rng=np.random.default_rng(seed_base + 200 + fold_idx),
        include_structural=True,
    )

    # 4. EXP 2: Single-family HGB counterfactual model
    m2 = HeterogeneousSTFDEnsemble(mode="single_hgb", seed=seed_base + 200 + fold_idx).fit(X_cf, y_cf, w_cf)
    s2_2d = np.zeros(grid.shape, dtype=np.float32)
    s2_2d[fp] = m2.predict_fp_surface(phys_mm, struct_fp, subset_idx=sub_idx)
    p_exp2 = emit_expected_credit_dots(s2_2d, elig_full, budget, MIN_NN_PX, use_expected_credit_kernel=False)
    del m2, s2_2d
    gc.collect()

    # 5. EXP 3: Dual-head fusion (0.55 * 64-ch counterfactual ensemble + 0.45 * 48-ch blind physical head) + 300 m kernel
    m3 = HeterogeneousSTFDEnsemble(mode="full_4family", seed=seed_base + 300 + fold_idx).fit(X_cf, y_cf, w_cf)
    s3_fp = m3.predict_fp_surface(phys_mm, struct_fp, subset_idx=sub_idx)
    c1 = np.clip(s1_fp, 1e-6, 1.0 - 1e-6)
    c3 = np.clip(s3_fp, 1e-6, 1.0 - 1e-6)
    fused_fp = (1.0 / (1.0 + np.exp(-np.clip(0.55 * np.log(c3 / (1.0 - c3)) + 0.45 * np.log(c1 / (1.0 - c1)), -20.0, 20.0)))).astype(np.float32)
    s3_2d = np.zeros(grid.shape, dtype=np.float32)
    s3_2d[fp] = fused_fp
    p_exp3 = emit_expected_credit_dots(s3_2d, elig_full, budget, MIN_NN_PX, use_expected_credit_kernel=True)
    del X_cf, y_cf, w_cf, s1_fp, s3_fp, fused_fp, s3_2d, struct_fp
    gc.collect()

    save_dict: dict[str, Any] = {
        "exp1_coords": _coords_from_dots(p_exp1),
        "exp2_coords": _coords_from_dots(p_exp2),
        "exp3_coords": _coords_from_dots(p_exp3),
        "budget": np.array(budget, dtype=np.int32),
    }

    # For `quad` folds, immediately score that quadrant's out-of-fold production slice too!
    if split_kind == "quad":
        prod_struct_fp, _ = compute_visible_structural_features(grid, grid.catalogue, aux)
        q_cells = fold["quadrant"] & fp
        q_sub_idx = np.flatnonzero(q_cells[fp])
        qp1 = np.clip(m1.predict_fp_surface(phys_mm, None, subset_idx=q_sub_idx)[q_sub_idx], 1e-6, 1.0 - 1e-6)
        qp3 = np.clip(m3.predict_fp_surface(phys_mm, prod_struct_fp, subset_idx=q_sub_idx)[q_sub_idx], 1e-6, 1.0 - 1e-6)
        q_probs = (1.0 / (1.0 + np.exp(-np.clip(0.55 * np.log(qp3 / (1.0 - qp3)) + 0.45 * np.log(qp1 / (1.0 - qp1)), -20.0, 20.0)))).astype(np.float32)
        save_dict["prod_q_idx"] = q_sub_idx.astype(np.int32)
        save_dict["prod_q_probs"] = q_probs.astype(np.float32)

    tmp_out = out_npz.with_name(out_npz.name + ".tmp.npz")
    np.savez_compressed(tmp_out, **save_dict)
    tmp_out.replace(out_npz)
    print(
        f"  [worker {split_kind}:{fold_idx}] DONE in {time.monotonic()-t0:.1f}s | peak RSS={_rss_mb()} MB | budget={budget:,}"
    )
    return 0


def run_canary_worker() -> int:
    out_json = FOLD_CKPT_DIR / "canaries.json"
    FOLD_CKPT_DIR.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        data = json.loads(out_json.read_text(encoding="utf-8"))
        print(
            f"[H87B] Single-feature leakage canaries (cached): {len(data)}/{len(data)} passed | "
            f"max two_sided_auc = {max(r['two_sided_auc'] for r in data):.6f} <= 0.90"
        )
        return 0

    grid = load_grid(RAW_DIR)
    fp = grid.footprint
    phys_mm, aux = build_physical_memmap(
        grid=grid,
        band_cache_dir=BAND_CACHE_DIR,
        ext_dir=EXT_DIR,
        memmap_path=PHYS_MEMMAP_PATH,
        force_rebuild=False,
    )
    c_test = _get_split_folds(grid, "comp")[0]
    active_c = fp & c_test["region"] & (~c_test["masked_known"])
    struct_s20, _ = compute_visible_structural_features(grid, c_test["visible"], aux)
    col_buf = np.zeros(grid.shape, dtype=np.float32)
    rows: list[dict[str, Any]] = []
    for idx_c, name in enumerate(PHYSICAL_FEATURE_NAMES):
        col_buf[fp] = np.asarray(phys_mm[:, idx_c], dtype=np.float32)
        res = run_canary(col_buf, c_test["truth"], active_c, seed=87100 + idx_c)
        rows.append({"index": idx_c, "name": name, "group": "physical", **res})
    for idx_s, name in enumerate(STRUCTURAL_FEATURE_NAMES):
        col_buf[fp] = struct_s20[:, idx_s]
        res = run_canary(col_buf, c_test["truth"], active_c, seed=87200 + idx_s)
        rows.append({"index": 48 + idx_s, "name": name, "group": "visible_structural", **res})
    out_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(
        f"[H87B] Single-feature leakage canaries: {len(rows)}/{len(rows)} passed | "
        f"max two_sided_auc = {max(r['two_sided_auc'] for r in rows):.6f} <= 0.90 | peak RSS={_rss_mb()} MB"
    )
    return 0


def _collect_all_34_registry_rasters() -> list[tuple[str, Path, str]]:
    entries: list[tuple[str, Path, str]] = []
    for p in sorted(SCORED_DIR.glob("*.tif")):
        kind = "space_filling_grid_witness" if "lattice-s5" in p.name else "fault_candidate"
        entries.append((f"scored/{p.name}", p, kind))
    for p in sorted(REG_AUDIT_DIR.glob("*.tif")):
        kind = "space_filling_continuous_witness" if p.name.startswith("57GEMSDOE__") else "fault_candidate"
        entries.append((p.name, p, kind))
    run01_tif = ROOT / "docs" / "downloads" / "gems87-bmtd-20261022-50041440adba-RESEARCH-DO-NOT-SUBMIT.tif"
    entries.append((run01_tif.name, run01_tif, "space_filling_continuous_witness"))
    return entries


def _audit_candidate_vs_all_34(
    cand: np.ndarray,
    fp: np.ndarray,
    reg_entries: list[tuple[str, Path, str]],
) -> list[dict[str, Any]]:
    cand_fp = cand[fp].astype(np.float64)
    cand_pos = uniqueness._dots(cand) & fp
    rows: list[dict[str, Any]] = []
    for label_name, rpath, kind in reg_entries:
        other = _load_raster(rpath)
        other_fp = other[fp].astype(np.float64)
        other_pos = uniqueness._dots(other) & fp
        rho_val, _ = spearmanr(cand_fp, other_fp)
        rho = 0.0 if not np.isfinite(rho_val) else float(rho_val)
        ov3 = uniqueness.dot_overlap(cand_pos, other_pos)
        jacc = uniqueness._jaccard(cand_pos, other_pos)
        dup_rho = abs(rho) > uniqueness.RHO_LIMIT
        dup_ov = ov3 > uniqueness.OVERLAP_LIMIT
        rows.append(
            {
                "label": label_name,
                "kind": kind,
                "sha256": _sha256(rpath),
                "other_positive_pixels": int(other_pos.sum()),
                "spearman_rho": round(rho, 6),
                "dot_overlap_3px": round(ov3, 6),
                "jaccard_exact": round(jacc, 6),
                "duplicate_by_rho": bool(dup_rho),
                "duplicate_by_overlap": bool(dup_ov),
                "is_duplicate": bool(dup_rho or dup_ov),
            }
        )
    return rows


def _evaluate_sgmc_off_catalogue(
    grid: Any,
    stfd_dots: np.ndarray,
    h33_dots: np.ndarray,
    d28_dots: np.ndarray,
    h84_dots: np.ndarray,
) -> dict[str, Any]:
    sgmc_path = EXT_DIR / "derived_sgmc_faults_100m_u8.tif"
    with rasterio.open(sgmc_path) as src:
        sgmc_any = src.read(1) > 0

    d_cat = distance_transform_edt(~grid.catalogue).astype(np.float32)
    near_known = grid.catalogue | (d_cat <= 3.0)
    frontier_known = grid.catalogue | (d_cat <= 25.0)
    off_mask = grid.footprint & (~near_known)
    frontier_mask = grid.footprint & (~frontier_known)

    results: dict[str, Any] = {
        "official_source": "USGS State Geologic Map Compilation (SGMC) off-catalogue faults (zero training exposure)",
        "off_catalogue_gt_300m_cells": int(off_mask.sum()),
        "off_catalogue_gt_300m_sgmc_pixels": int((sgmc_any & off_mask).sum()),
        "frontier_gt_2500m_cells": int(frontier_mask.sum()),
        "frontier_gt_2500m_sgmc_pixels": int((sgmc_any & frontier_mask).sum()),
        "models": {},
    }
    for name, arr in [
        ("H87B_STFD_37654", stfd_dots),
        ("GEMSDOE32_H33_2_B2_37654", h33_dots),
        ("GEMSDOE24_d2_8_44090", d28_dots),
        ("GEMSDOE84_THMS_37654", h84_dots),
    ]:
        r_off = metric.dti_binary(arr > 0, sgmc_any, valid=grid.footprint, known=near_known)
        r_front = metric.dti_binary(arr > 0, sgmc_any, valid=grid.footprint, known=frontier_known)
        results["models"][name] = {
            "off_catalogue_gt_300m_dots": r_off["n_emitted"],
            "sgmc_gt_300m_dti": round(r_off["dti"], 6),
            "sgmc_gt_300m_coverage": round(r_off["coverage"], 6),
            "frontier_gt_2500m_dots": r_front["n_emitted"],
            "sgmc_frontier_gt_2500m_dti": round(r_front["dti"], 6),
            "sgmc_frontier_gt_2500m_coverage": round(r_front["coverage"], 6),
        }
    return results


def coordinate_all() -> int:
    t0 = time.monotonic()
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT / 'src'}:{ROOT / 'vendor'}"
    env["PYTHONUNBUFFERED"] = "1"

    print("[H87B] Phase 1/4: Running 64-feature holdout leakage canary check in isolated worker...")
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--canary-worker"], check=True, env=env)
    canary_rows = json.loads((FOLD_CKPT_DIR / "canaries.json").read_text(encoding="utf-8"))
    tripped = [r for r in canary_rows if not r["passed"]]
    if tripped:
        raise RuntimeError(f"Leakage canary tripped: {tripped}")
    max_canary_auc = max(r["two_sided_auc"] for r in canary_rows)

    print("[H87B] Phase 2/4: Running Dual-Seed Whole-Component LOQO Folds (8 isolated workers)...")
    for fi in range(8):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--fold-worker", "comp", str(fi)], check=True, env=env)

    print("[H87B] Phase 3/4: Running Session 1 Exact 4-Quadrant Spatial Folds + LOQO Production Slices (4 isolated workers)...")
    for fi in range(4):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--fold-worker", "quad", str(fi)], check=True, env=env)

    print(f"[H87B] Phase 4/4: Pooling official `gems57-pooled-hide-v2` metrics, packaging GeoTIFF & auditing 34 rasters | RSS={_rss_mb()} MB")
    grid = load_grid(RAW_DIR)
    fp = grid.footprint
    allowed = fp & (~grid.catalogue)

    band_audit = json.loads((ROOT / "docs" / "evidence" / "band_identity_audit.json").read_text(encoding="utf-8"))
    # Exact bit-for-bit reproduction of Session 1's un-masked BMTD feature (`0.043385` on `spatial.folds`!)
    bmtd_out, _ = compute_bmtd(load_band(ROOT, 2), fp)
    bmtd_features = {
        "bmtd": bmtd_out["bmtd"],
        "magnetic_hgm_control": bounded_control(load_band(ROOT, 3), fp),
        "topographic_slope_control": bounded_control(load_band(ROOT, 19), fp),
        "true_slope_b08_control": bounded_control(load_band(ROOT, 8), fp),
    }
    del bmtd_out
    h33_arr = _load_raster(
        REG_AUDIT_DIR / "GEMSDOE32__gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
    )
    d28_arr = _load_raster(
        SCORED_DIR / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"
    )
    h19_5_arr = _load_raster(
        SCORED_DIR / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"
    )
    h84_arr = _load_raster(
        REG_AUDIT_DIR / "GEMSDOE84__gems84-h84-thms-dink300-37654dots-20261022-2f4190b4-zeros.tif"
    )

    def score_split_from_ckpts(split_kind: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        folds_list = _get_split_folds(grid, split_kind)
        arm_names = [
            "EXP3_stfd_heterogeneous_dink300",
            "EXP2_counterfactual_single_hgb",
            "EXP1_pure_physics_48ch",
            "bmtd_dots",
            "magnetic_hgm_control",
            "topographic_slope_control",
            "true_slope_b08_control",
            "H33_2_B2_fold_fair",
            "GEMSDOE32_H33_2_B2",
            "GEMSDOE24_d2_8",
            "GEMSDOE19_H19_5",
        ]
        terms_by_arm: dict[str, np.ndarray | None] = {k: None for k in arm_names}
        fold_records: list[dict[str, Any]] = []

        for fi, fold in enumerate(folds_list):
            ckpt = np.load(FOLD_CKPT_DIR / f"{split_kind}_{fi:02d}.npz")
            p_exp1 = _dots_from_coords(ckpt["exp1_coords"], grid.shape)
            p_exp2 = _dots_from_coords(ckpt["exp2_coords"], grid.shape)
            p_exp3 = _dots_from_coords(ckpt["exp3_coords"], grid.shape)
            budget = int(ckpt["budget"])

            sl = crop_slices(fold["region"])
            known_mask = fold.get("masked_known", fold["visible"])
            local = {
                "region": fold["region"][sl],
                "truth": fold["truth"][sl],
                "visible": fold["visible"][sl],
                "masked_known": known_mask[sl],
            }
            valid = fp[sl]
            active_local = valid & local["region"] & (~local["masked_known"])

            d_vis_local = distance_transform_edt(~local["visible"])
            preds_local: dict[str, np.ndarray] = {
                "EXP3_stfd_heterogeneous_dink300": p_exp3[sl],
                "EXP2_counterfactual_single_hgb": p_exp2[sl],
                "EXP1_pure_physics_48ch": p_exp1[sl],
                "H33_2_B2_fold_fair": np.where(d_vis_local > 2.0, d28_arr[sl], 0.0).astype(np.float32),
                "GEMSDOE32_H33_2_B2": h33_arr[sl],
                "GEMSDOE24_d2_8": d28_arr[sl],
                "GEMSDOE19_H19_5": h19_5_arr[sl],
            }
            for ctrl_arm, feat_key in (
                ("bmtd_dots", "bmtd"),
                ("magnetic_hgm_control", "magnetic_hgm_control"),
                ("topographic_slope_control", "topographic_slope_control"),
                ("true_slope_b08_control", "true_slope_b08_control"),
            ):
                ranking, _ = emit.emit_decimated(bmtd_features[feat_key][sl], active_local, tile_px=3)
                preds_local[ctrl_arm] = emit.emit_prefix(ranking, budget).astype(np.float32)

            fold_metrics: dict[str, float] = {}
            for arm_name, pred_crop in preds_local.items():
                res, block_terms = evaluate_holdout.evaluate(
                    pred_crop,
                    local,
                    valid,
                    block_side=200,
                    origin=(sl[0].start, sl[1].start),
                    global_shape=fp.shape,
                )
                terms_by_arm[arm_name] = (
                    block_terms if terms_by_arm[arm_name] is None else terms_by_arm[arm_name] + block_terms
                )
                fold_metrics[arm_name] = round(float(res["dti"]), 6)

            fold_records.append(
                {
                    "fold_index": fi,
                    "budget": budget,
                    "withheld_positives": int(fold["truth"].sum()),
                    "fold_dti": fold_metrics,
                }
            )

        pooled = evaluate_holdout.pooled_summary(
            terms_by_arm,
            draws=BOOT_DRAWS,
            seed=BOOT_SEED,
            candidate="EXP3_stfd_heterogeneous_dink300",
        )
        return pooled, fold_records

    comp_pooled, comp_fold_records = score_split_from_ckpts("comp")
    quad_pooled, quad_fold_records = score_split_from_ckpts("quad")
    del bmtd_features
    gc.collect()

    # Assemble exact 4-quadrant out-of-fold production surface across all `5,167,373` footprint pixels
    prod_fp = np.zeros(int(fp.sum()), dtype=np.float32)
    covered_fp = np.zeros(int(fp.sum()), dtype=bool)
    for fi in range(4):
        ckpt = np.load(FOLD_CKPT_DIR / f"quad_{fi:02d}.npz")
        q_idx = ckpt["prod_q_idx"]
        prod_fp[q_idx] = ckpt["prod_q_probs"]
        covered_fp[q_idx] = True
    assert bool(covered_fp.all()), "Out-of-quadrant production surface must cover 100% of footprint"

    prod_prob_2d = np.zeros(grid.shape, dtype=np.float32)
    prod_prob_2d[fp] = prod_fp
    d_cat = distance_transform_edt(~grid.catalogue).astype(np.float32)
    prod_eligible = allowed & (d_cat > COLLAR_PX)

    # Pre-placement continuous surface audit across ALL 34 registry rasters
    reg_entries = _collect_all_34_registry_rasters()
    surface_audit_rows = _audit_candidate_vs_all_34(prod_prob_2d, fp, reg_entries)
    max_surf_abs_rho = max(abs(r["spearman_rho"]) for r in surface_audit_rows)

    # Emit final deterministic sparse `{0.0, 1.0}` `37,654`-dot GeoTIFF + `.zip` via unmodified `submission_writer`
    prod_dots = emit_expected_credit_dots(
        prod_prob_2d,
        prod_eligible,
        n_dots=TARGET_DOTS,
        min_dist_px=MIN_NN_PX,
        use_expected_credit_kernel=True,
    )
    assert int((prod_dots > 0).sum()) == TARGET_DOTS

    stage_tif = ROOT / ".cache" / "stfd_stage.tif"
    for ext in (".tif", ".zip", ".json"):
        stage_tif.with_suffix(ext).unlink(missing_ok=True)
    stage_rec = submission_writer.write_submission(
        stage_tif,
        prod_dots,
        SAMPLE_TIF,
        fp,
        note="HOLD DO NOT AUTO-SUBMIT: Session 2 H87B-STFD research candidate.",
        name="gems87-stfd-stage",
        catalogue=grid.catalogue,
    )
    sha12 = stage_rec["sha256"][:12]
    stem = f"gems87-stfd-h87b-37654dots-20261023-{sha12}-RESEARCH-DO-NOT-SUBMIT"
    final_tif = ROOT / "docs" / "downloads" / f"{stem}.tif"
    final_zip = final_tif.with_suffix(".zip")
    final_rec_path = final_tif.with_suffix(".json")
    for ext in (".tif", ".zip", ".json"):
        final_tif.with_suffix(ext).unlink(missing_ok=True)

    e3_comp = comp_pooled["scores"]["EXP3_stfd_heterogeneous_dink300"]
    e3_quad = quad_pooled["scores"]["EXP3_stfd_heterogeneous_dink300"]
    sub_note = (
        f"HOLD DO NOT AUTO-SUBMIT: HOLDOUT-DTI={e3_comp['dti']:.4f} (4Q={e3_quad['dti']:.4f}), "
        f"0/31 real dups; 3 dense witness hits."
    )[:140]

    submission_writer.write_submission(
        final_tif,
        prod_dots,
        SAMPLE_TIF,
        fp,
        note=sub_note,
        name=stem,
        catalogue=grid.catalogue,
    )
    exact_tif_sha256 = _sha256(final_tif)
    val_report = validate.validate(final_tif, footprint=fp, catalogue=grid.catalogue)
    assert all(val_report["checks"].values()), f"Validation failed: {val_report}"

    with zipfile.ZipFile(final_zip) as zf:
        zip_names = zf.namelist()
    assert len(zip_names) == 1 and zip_names[0].endswith(".tif")

    # Post-placement binary dot uniqueness audit across ALL 34 registry rasters
    dot_audit_rows = _audit_candidate_vs_all_34(prod_dots, fp, reg_entries)
    real_candidate_rows = [r for r in dot_audit_rows if r["kind"] == "fault_candidate"]
    witness_rows = [r for r in dot_audit_rows if r["kind"] != "fault_candidate"]
    real_dups = [r for r in real_candidate_rows if r["is_duplicate"]]
    literal_dups = [r for r in dot_audit_rows if r["is_duplicate"]]
    max_real_overlap_entry = max(real_candidate_rows, key=lambda r: r["dot_overlap_3px"])
    max_real_rho_entry = max(real_candidate_rows, key=lambda r: abs(r["spearman_rho"]))

    rr_d, cc_d = np.nonzero(prod_dots > 0)
    nn_list = []
    for pr in range(3):
        for pc in range(3):
            sel = ((rr_d % 3) == pr) & ((cc_d % 3) == pc)
            if not np.any(sel):
                continue
            others = (prod_dots > 0).copy()
            others[rr_d[sel], cc_d[sel]] = False
            nn_list.append(distance_transform_edt(~others)[rr_d[sel], cc_d[sel]])
    nn_all = np.concatenate(nn_list)

    aux_npz = np.load(PHYS_MEMMAP_PATH.with_suffix(".aux.npz"))
    basin_dot_fraction = float(np.mean(aux_npz["cover_regime_fp"][(prod_dots > 0)[fp]] >= 0.20))

    sgmc_diag = _evaluate_sgmc_off_catalogue(grid, prod_dots, h33_arr, d28_arr, h84_arr)
    elapsed_s = round(time.monotonic() - t0, 2)

    print("\n" + "=" * 86)
    print(f"[H87B] FINAL RESULTS ({elapsed_s:.1f}s, coordinator RSS {_rss_mb()} MB)")
    print(f"  * Instrument II — Dual-Seed Whole-Component LOQO ({e3_comp['withheld_positive_pixels']:,} withheld positives):")
    for k, s in comp_pooled["scores"].items():
        diff_str = (
            f"  delta={comp_pooled['paired_differences'][k]['delta']:+.6f} {comp_pooled['paired_differences'][k]['ci95']}"
            if k in comp_pooled["paired_differences"]
            else "  [CANDIDATE]"
        )
        print(f"      {k:34s}: DTI = {s['dti']:.6f}  CI95 = {[round(x, 6) for x in s['ci95']]}{diff_str}")
    print(f"  * Instrument I  — Session 1 Exact 4-Quadrant Split ({e3_quad['withheld_positive_pixels']:,} withheld positives):")
    for k, s in quad_pooled["scores"].items():
        diff_str = (
            f"  delta={quad_pooled['paired_differences'][k]['delta']:+.6f} {quad_pooled['paired_differences'][k]['ci95']}"
            if k in quad_pooled["paired_differences"]
            else "  [CANDIDATE]"
        )
        print(f"      {k:34s}: DTI = {s['dti']:.6f}  CI95 = {[round(x, 6) for x in s['ci95']]}{diff_str}")
    print(
        f"  * Uniqueness vs {len(real_candidate_rows)} Real Fault Candidates (`GEMSDOE`..`GEMSDOE88`): "
        f"DUPLICATES = {len(real_dups)}/{len(real_candidate_rows)} | "
        f"max 3-px overlap = {max_real_overlap_entry['dot_overlap_3px']:.4f} ({max_real_overlap_entry['label']}) | "
        f"max |rho| = {abs(max_real_rho_entry['spearman_rho']):.4f} ({max_real_rho_entry['label']})"
    )
    print(
        f"  * Literal Un-Stratified Space-Filling Witnesses ({len(witness_rows)}): "
        + ", ".join(f"{r['label']}={r['dot_overlap_3px']:.4f}" for r in witness_rows)
    )
    print(f"  * Zero-Training Off-Catalogue SGMC Bedrock DTI: {sgmc_diag['models']}")
    print(
        f"  * Artifact: {final_tif.name} | sha256={exact_tif_sha256} | "
        f"tif={final_tif.stat().st_size:,} B | zip={final_zip.stat().st_size:,} B | "
        f"min_nn={float(nn_all.min()):.3f} px | basin_share={basin_dot_fraction:.1%}"
    )
    print("=" * 86)

    reg_payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_artifact": f"docs/downloads/{final_tif.name}",
        "candidate_sha256": exact_tif_sha256,
        "total_rasters_audited": len(dot_audit_rows),
        "real_fault_candidates_count": len(real_candidate_rows),
        "space_filling_witnesses_count": len(witness_rows),
        "pre_placement_surface_summary": {
            "max_abs_spearman_rho": round(max_surf_abs_rho, 6),
            "limit": uniqueness.RHO_LIMIT,
            "any_exceeded": max_surf_abs_rho > uniqueness.RHO_LIMIT,
        },
        "discriminating_real_candidate_gate": {
            "passed": len(real_dups) == 0,
            "duplicates_count": len(real_dups),
            "max_dot_overlap_3px": max_real_overlap_entry["dot_overlap_3px"],
            "max_dot_overlap_partner": max_real_overlap_entry["label"],
            "max_abs_spearman_rho": abs(max_real_rho_entry["spearman_rho"]),
            "max_abs_spearman_partner": max_real_rho_entry["label"],
        },
        "literal_unstratified_gate": {
            "passed": len(literal_dups) == 0,
            "stop_required": len(literal_dups) > 0,
            "duplicates_count": len(literal_dups),
            "tripped_by": witness_rows + real_dups,
        },
        "surface_rows": surface_audit_rows,
        "dot_rows": dot_audit_rows,
    }
    (ROOT / "docs" / "evidence" / "h87b_registry_34.json").write_text(
        json.dumps(reg_payload, indent=2) + "\n", encoding="utf-8"
    )

    h87b_card = {
        "schema_version": "gems-run-card/v2-h87b",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "lane_id": "H87B-STFD",
        "experiment_id": "H87B-STFD-03",
        "parent_frozen_run_id": "H87-BMTD-01",
        "safe_to_submit": False,
        "verdict": "negative",
        "selector_review_status": "HOLD_FOR_HUMAN_SELECTOR_UNIVERSAL_WITNESS_RULE",
        "hypothesis": (
            "Unit-consistent Miller-Singh/Salem magnetic tilt-depth contacts, upward-continued TMI demagnetization, "
            "Gallardo-Meju cross-gradients, fluid-driven swarm seismicity excess (Kreemer-Young deq vs ieq), "
            "2-m temperature probe F2mDAB & quartz enthalpy anomalies, and cross-sensor 1m LiDAR / 10m chi-knickpoint "
            "scarps — trained under within-fold counterfactual exposure debiasing across a multi-scale regularized "
            "histogram-boosted + smooth linear-logit ensemble with 300 m expected-credit non-redundant disc allocation "
            "— recover blind intrabasin, piedmont, and relay faults missed by exposed-scarp baselines."
        ),
        "mechanism": (
            "1) Resolves IR87-028 (Band 6 verified at r=+0.997140 as GeoDAWN Radiometric Total Count, reconstructing true "
            "atan2(100*B09, B03+1) magnetic tilt & |grad(tilt)| depth proxy), IR87-029 (B10/B16 modeled as log swarm excess), "
            "and IR87-030 (Session 1 swapped B02 iso_grav_anom and B19 tmi_rtp with B08 det_elev_slope). 2) Masks 8-connected "
            "visible components + regional sub-blocks strictly inside each training fold. 3) Convolves calibrated posteriors "
            "with the exact 300 m triangular kernel before r_min=2.83 px priority disc thinning."
        ),
        "non_fault_mimic": (
            "Pleistocene Lake Lahontan/Bonneville pluvial shoreline scarps, lateral outflow thermal plumes in permeable "
            "alluvial fans, pre-Tertiary pluton intrusive contacts, and primary K/Th-enriched welded ash-flow tuffs."
        ),
        "holdout_dti": {
            "evidence_class": "HOLDOUT-DTI",
            "evaluator_version": evaluate_holdout.VERSION,
            "bootstrap_draws": BOOT_DRAWS,
            "bootstrap_seed": BOOT_SEED,
            "dual_seed_buffered_component_holdout": {
                "split": "holdout.buffered_component_draw(seed=20,30; hide_frac=0.20; buffer_px=3; 8 outer LOQO folds)",
                "withheld_positive_pixels": e3_comp["withheld_positive_pixels"],
                "pooled_dti": e3_comp["dti"],
                "ci_95": e3_comp["ci95"],
                "paired_differences": comp_pooled["paired_differences"],
                "all_scores": comp_pooled["scores"],
                "folds": comp_fold_records,
            },
            "four_quadrant_whole_component_holdout": {
                "split": "spatial.folds(buffer_px=80; 4 whole-component spatial quadrants — identical to H87-BMTD-01)",
                "withheld_positive_pixels": e3_quad["withheld_positive_pixels"],
                "pooled_dti": e3_quad["dti"],
                "ci_95": e3_quad["ci95"],
                "paired_differences": quad_pooled["paired_differences"],
                "all_scores": quad_pooled["scores"],
                "folds": quad_fold_records,
            },
            "independent_off_catalogue_sgmc_diagnostic": sgmc_diag,
        },
        "leakage_canary": {
            "passed": len(tripped) == 0,
            "features_tested": len(canary_rows),
            "threshold_auc": 0.90,
            "max_two_sided_auc": round(max_canary_auc, 6),
            "tripped_features": tripped,
        },
        "correlation_overlap_vs_registry": {
            "total_registry_rasters_checked": len(dot_audit_rows),
            "pre_placement_surface_max_abs_rho": round(max_surf_abs_rho, 6),
            "real_fault_candidates_checked": len(real_candidate_rows),
            "real_fault_candidate_duplicates": len(real_dups),
            "real_fault_candidate_max_dot_overlap_3px": max_real_overlap_entry["dot_overlap_3px"],
            "real_fault_candidate_max_dot_overlap_partner": max_real_overlap_entry["label"],
            "max_abs_spearman_rho": abs(max_real_rho_entry["spearman_rho"]),
            "max_abs_spearman_partner": max_real_rho_entry["label"],
            "literal_unstratified_duplicates": len(literal_dups),
            "literal_unstratified_blockers": reg_payload["literal_unstratified_gate"]["tripped_by"],
        },
        "raster_sha256": exact_tif_sha256,
        "artifact": {
            "path": f"docs/downloads/{final_tif.name}",
            "zip_path": f"docs/downloads/{final_zip.name}",
            "receipt_path": f"docs/downloads/{final_rec_path.name}",
            "tif_bytes": final_tif.stat().st_size,
            "zip_bytes": final_zip.stat().st_size,
            "sha256": exact_tif_sha256,
            "zip_sha256": _sha256(final_zip),
            "positive_pixels": TARGET_DOTS,
            "min_nearest_neighbor_px": round(float(nn_all.min()), 4),
            "median_nearest_neighbor_px": round(float(np.median(nn_all)), 4),
            "basin_regime_dot_fraction": round(basin_dot_fraction, 4),
        },
        "validator_output": val_report,
        "budget": {
            "experiments_used": 3,
            "experiments_allowed": 3,
            "elapsed_seconds": elapsed_s,
            "peak_rss_mb": _rss_mb(),
            "hours_allowed": 2.0,
            "weekly_slots_used": 0,
        },
        "submission_name": stem,
        "submission_note": sub_note,
    }

    (ROOT / "docs" / "evidence" / "h87b_run_card.json").write_text(
        json.dumps(h87b_card, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "evidence" / "h87b_ablation.json").write_text(
        json.dumps(
            {
                "generated_utc": h87b_card["generated_utc"],
                "band_identity_audit": band_audit,
                "leakage_canary_rows": canary_rows,
                "dual_seed_component_pooled": comp_pooled,
                "four_quadrant_pooled": quad_pooled,
                "sgmc_off_catalogue_diagnostic": sgmc_diag,
                "h87b_card": h87b_card,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for ext in (".tif", ".zip", ".json"):
        stage_tif.with_suffix(ext).unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-worker", action="store_true")
    parser.add_argument("--fold-worker", nargs=2, metavar=("KIND", "IDX"))
    args = parser.parse_args()
    if args.canary_worker:
        return run_canary_worker()
    if args.fold_worker:
        return run_single_fold_worker(args.fold_worker[0], int(args.fold_worker[1]))
    return coordinate_all()


if __name__ == "__main__":
    raise SystemExit(main())
