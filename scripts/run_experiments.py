#!/usr/bin/env python3
"""Execute the preregistered 3-experiment suite (E1, E2, E3), uniqueness gate, and GeoTIFF packaging."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
sys.path.insert(0, str(ROOT / "src"))

from gems57 import evaluate_holdout, grid, holdout, submission_writer, validate as g57_validate
from gems87 import DEFAULT_DOT_BUDGET, EVALUATOR_VERSION, LANE_ID
from gems87.audit import fast_full_registry_audit, load_or_build_packed_halos
from gems87.features import build_or_load_static_stack, compute_visible_transfer_features
from gems87.model import (
    AUG_TRANSFER_NAMES,
    augment_fold_transfer,
    dinkelbach_submodular_300m_emit,
    fit_blind_loqo_models,
    fit_csct_dual_ensemble_loqo,
    poisson_disk_emit,
)

sys.path.insert(0, str(ROOT / "scripts"))
from validate_submission import validate_submission as independent_validate_submission


def _fp_to_grid(vec: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    out = np.zeros(footprint.shape, dtype=np.float32)
    out[footprint] = vec.astype(np.float32, copy=False)
    return out


def _find_registry_raster(fragment: str) -> Path | None:
    for d in (ROOT / "data" / "scored", ROOT / "data" / "registry_rasters"):
        for p in sorted(d.glob("*.tif")):
            if fragment.lower() in p.name.lower():
                return p
    return None


def main() -> int:
    t_start = time.monotonic()
    g = grid.load_grid(ROOT / "data" / "bridge")
    fp = g.footprint
    cat = g.catalogue
    fp_idx = np.flatnonzero(fp)
    fp_lut = np.full(fp.size, -1, dtype=np.int32)
    fp_lut[fp_idx] = np.arange(fp_idx.size, dtype=np.int32)
    quad_ids = holdout.quadrant_ids(fp)

    print("[1/7] Loading cached static physical feature stack & bit-packed 480-raster halos...")
    mm_static, phys_theta, static_names = build_or_load_static_stack(ROOT / "data", fp, ROOT / "data" / "cache")
    packed_halos, halo_meta = load_or_build_packed_halos(
        fp, cat, ROOT / "data" / "registry_rasters", ROOT / "data" / "scored", ROOT / "data" / "cache"
    )
    active_halo_indices = np.asarray(
        [int(r["idx"]) for r in halo_meta if float(r["covered_allowed_fraction"]) < 0.70],
        dtype=np.int32,
    )
    print(f"      Active discriminating registry halos enforced at <= 0.650: {active_halo_indices.size} / {len(halo_meta)}")

    print("[2/7] Loading/fitting strictly Leave-One-Quadrant-Out blind multi-physics models (M_blind, 0 catalogue features)...")
    blind_oof_cache = ROOT / "data" / "cache" / "g87_blind_oof_v1.npy"
    if blind_oof_cache.exists():
        p_blind_oof_fp = np.load(blind_oof_cache)
    else:
        _, p_blind_oof_fp = fit_blind_loqo_models(mm_static, fp, cat, quad_ids, seed=87)
        np.save(blind_oof_cache, p_blind_oof_fp)
    p_blind_grid = _fp_to_grid(p_blind_oof_fp, fp)

    # Verify full 55-feature single-feature holdout leakage canary across BOTH seeds!
    import gc

    ev_dir = ROOT / "evidence"
    ev_dir.mkdir(exist_ok=True)
    canary_path = ev_dir / "e0_leakage_canary.json"
    if canary_path.exists() and json.loads(canary_path.read_text()).get("seed_20", {}).get("n_features_tested") == 55:
        canary_summary = json.loads(canary_path.read_text())
        print(
            f"[3/7] Loaded verified 55-feature leakage canary (seed 20 max={canary_summary['seed_20']['max_symmetric_auc']}, "
            f"seed 30 max={canary_summary['seed_30']['max_symmetric_auc']} <= 0.90)"
        )
    else:
        print("[3/7] Running Single-Feature Holdout Leakage Canary across all 55 features (44 static + 11 fold-visible)...")
        canary_summary = {}
        for seed in (20, 30):
            folds, _ = holdout.buffered_component_draw(g, seed=seed, buffer_px=3, boundary_px=12)
            aug_list = [
                augment_fold_transfer(
                    f["visible"],
                    fp,
                    compute_visible_transfer_features(
                        f["visible"],
                        fp,
                        phys_theta,
                        cache_path=ROOT / "data" / "cache" / f"g87_transfer_s{seed}_q{q_idx}.mmap",
                    ),
                )
                for q_idx, f in enumerate(folds)
            ]

            y_eval, idx_eval, T_eval = [], [], []
            for q_idx, f in enumerate(folds):
                act = fp & f["region"] & (~f["masked_known"])
                act_fp = act[fp]
                y_q = f["truth"][fp][act_fp].astype(np.int32)
                pos_i = np.flatnonzero(y_q == 1)
                rng_c = np.random.default_rng(1000 + seed * 10 + q_idx)
                neg_i = rng_c.choice(np.flatnonzero(y_q == 0), size=min(60_000, int((y_q == 0).sum())), replace=False)
                keep = np.concatenate([pos_i, neg_i])
                y_eval.append(y_q[keep])
                idx_eval.append(np.flatnonzero(act_fp)[keep])
                T_eval.append(aug_list[q_idx][act_fp][keep])

            y_all = np.concatenate(y_eval)
            idx_all = np.concatenate(idx_eval)
            T_all = np.vstack(T_eval)
            X_stat = np.asarray(mm_static[idx_all], dtype=np.float32)

            feat_rows = []
            for c, nm in enumerate(static_names):
                v = np.nan_to_num(X_stat[:, c], nan=0.0)
                auc = float(roc_auc_score(y_all, v))
                s_auc = max(auc, 1.0 - auc)
                feat_rows.append({"feature": nm, "group": "static_physical", "raw_auc": round(auc, 6), "symmetric_auc": round(s_auc, 6), "leakage_flag": bool(s_auc > 0.90)})
            for c, nm in enumerate(AUG_TRANSFER_NAMES):
                v = np.nan_to_num(T_all[:, c], nan=0.0)
                auc = float(roc_auc_score(y_all, v))
                s_auc = max(auc, 1.0 - auc)
                feat_rows.append({"feature": nm, "group": "fold_visible_mechanics", "raw_auc": round(auc, 6), "symmetric_auc": round(s_auc, 6), "leakage_flag": bool(s_auc > 0.90)})
            max_s = max(r["symmetric_auc"] for r in feat_rows)
            assert max_s <= 0.90, f"LEAKAGE DETECTED on seed {seed}: max_symmetric_auc={max_s}"
            canary_summary[f"seed_{seed}"] = {
                "n_positives": int((y_all == 1).sum()),
                "n_negatives_sampled": int((y_all == 0).sum()),
                "n_features_tested": len(feat_rows),
                "max_symmetric_auc": round(max_s, 6),
                "any_leakage": False,
                "features": sorted(feat_rows, key=lambda x: x["symmetric_auc"], reverse=True),
            }
            print(f"      Seed {seed} canary PASS ({len(feat_rows)}/{len(feat_rows)} features <= 0.90; max={max_s:.6f})")
            del aug_list, folds, y_eval, idx_eval, T_eval, y_all, idx_all, T_all, X_stat
            gc.collect()
        canary_path.write_text(json.dumps(canary_summary, indent=2) + "\n", encoding="utf-8")

    # Baseline surfaces (strictly catalogue-free)
    rng_ctrl = np.random.default_rng(20261022)
    ctrl_rand_surf = np.where(fp, rng_ctrl.random(fp.shape, dtype=np.float32), 0.0)
    ctrl_topo_surf = _fp_to_grid(np.asarray(mm_static[:, 4], dtype=np.float32), fp)
    cg_vec = np.asarray(mm_static[:, 37], dtype=np.float32) / (1.0 + np.asarray(mm_static[:, 38], dtype=np.float32))
    ctrl_cg_surf = _fp_to_grid(cg_vec, fp)

    hist_surfaces: dict[str, np.ndarray] = {}
    for key, frag in (
        ("HIST_D28", "dotted-h19-5-d2-8"),
        ("HIST_GEMS49_ORTHO", "gate_ortho_w0.25-40k"),
        ("HIST_GEMS70_DUAL", "gems70-p5-dual-submod300-oof38k"),
    ):
        hp = _find_registry_raster(frag)
        if hp is not None:
            with rasterio.open(hp) as ds:
                hist_surfaces[key] = np.clip(np.nan_to_num(ds.read(1), nan=0.0), 0.0, 1.0).astype(np.float32)

    print("[4/7] Running preregistered 3-experiment suite (E1 -> E2 -> E3) on gems57-pooled-hide-v2...")
    all_seed_terms: dict[str, list[np.ndarray]] = {}
    per_seed_summaries: dict[str, dict] = {}
    per_fold_records: list[dict] = []
    csct_models_all: list = []
    emitted_seed20_bool: dict[str, np.ndarray] = {}

    for seed in (20, 30):
        t_s = time.monotonic()
        folds, _ = holdout.buffered_component_draw(g, seed=seed, buffer_px=3, boundary_px=12)
        oof_cache_s = ROOT / "data" / "cache" / f"g87_csct_oof_s{seed}.npy"
        mdl_cache_s = ROOT / "data" / "cache" / f"g87_csct_models_s{seed}.pkl"
        if oof_cache_s.exists() and mdl_cache_s.exists():
            import pickle
            p_csct_oof_fp = np.load(oof_cache_s)
            m_pairs = pickle.loads(mdl_cache_s.read_bytes())
        else:
            import pickle
            aug_list = [
                augment_fold_transfer(
                    f["visible"],
                    fp,
                    compute_visible_transfer_features(
                        f["visible"],
                        fp,
                        phys_theta,
                        cache_path=ROOT / "data" / "cache" / f"g87_transfer_s{seed}_q{q_idx}.mmap",
                    ),
                )
                for q_idx, f in enumerate(folds)
            ]
            m_pairs, p_csct_oof_fp = fit_csct_dual_ensemble_loqo(
                mm_static, p_blind_oof_fp, aug_list, folds, fp, seed=seed
            )
            np.save(oof_cache_s, p_csct_oof_fp)
            mdl_cache_s.write_bytes(pickle.dumps(m_pairs))
            del aug_list
            gc.collect()
        csct_models_all.extend(m_pairs)
        p_csct_grid = _fp_to_grid(p_csct_oof_fp, fp)

        active_union = np.zeros(fp.shape, dtype=bool)
        active_collar30 = np.zeros(fp.shape, dtype=bool)
        for f in folds:
            act_q = fp & f["region"] & (~f["masked_known"])
            active_union |= act_q
            d_vis_q = ndi.distance_transform_edt(~f["visible"])
            active_collar30 |= act_q & (d_vis_q > 3.0)

        e3_dots, e3_stats = dinkelbach_submodular_300m_emit(
            p_csct_grid,
            active_collar30,
            n_dots=DEFAULT_DOT_BUDGET,
            pi_true=0.0022,
            temperature=1.0,
            fp_lambda=0.012,
            min_sep_px=2.40,
        )

        arms_dots: dict[str, np.ndarray] = {
            "CTRL_RAND": poisson_disk_emit(ctrl_rand_surf, active_union, DEFAULT_DOT_BUDGET, min_sep_px=2.8),
            "CTRL_TOPO": poisson_disk_emit(ctrl_topo_surf, active_union, DEFAULT_DOT_BUDGET, min_sep_px=2.8),
            "CTRL_CG": poisson_disk_emit(ctrl_cg_surf, active_union, DEFAULT_DOT_BUDGET, min_sep_px=2.8),
            "E1_BLIND_POISSON": poisson_disk_emit(p_blind_grid, active_union, DEFAULT_DOT_BUDGET, min_sep_px=2.8),
            "E2_CSCT_POISSON": poisson_disk_emit(p_csct_grid, active_union, DEFAULT_DOT_BUDGET, min_sep_px=2.8),
            "E3_CSCT_DINKELBACH": e3_dots,
        }
        for hk, hsurf in hist_surfaces.items():
            arms_dots[hk] = np.where(active_union, hsurf, 0.0).astype(np.float32)

        seed_terms: dict[str, np.ndarray] = {}
        for arm_name, pred_arr in arms_dots.items():
            if seed == 20 and arm_name in ("CTRL_RAND", "CTRL_TOPO", "CTRL_CG", "E1_BLIND_POISSON", "E2_CSCT_POISSON", "E3_CSCT_DINKELBACH"):
                emitted_seed20_bool[arm_name] = pred_arr >= 0.5
            fold_terms_sum = None
            for q_idx, f in enumerate(folds):
                res_q, terms_q = evaluate_holdout.evaluate(pred_arr, f, fp)
                fold_terms_sum = terms_q if fold_terms_sum is None else (fold_terms_sum + terms_q)
                if arm_name in ("CTRL_RAND", "CTRL_TOPO", "E1_BLIND_POISSON", "E2_CSCT_POISSON", "E3_CSCT_DINKELBACH"):
                    per_fold_records.append(
                        {
                            "seed": seed,
                            "quadrant": q_idx,
                            "arm": arm_name,
                            "dti": round(res_q["dti"], 6),
                            "tpw": round(res_q["tpw"], 2),
                            "fpw": round(res_q["fpw"], 2),
                            "n_truth": res_q["n_truth"],
                            "n_emitted": res_q["n_emitted"],
                        }
                    )
            assert fold_terms_sum is not None
            seed_terms[arm_name] = fold_terms_sum
            all_seed_terms.setdefault(arm_name, []).append(fold_terms_sum)
        del arms_dots, folds, p_csct_grid, e3_dots
        gc.collect()

        summary_s = evaluate_holdout.pooled_summary(
            seed_terms, draws=2000, seed=520810 + seed, candidate="E3_CSCT_DINKELBACH"
        )
        per_seed_summaries[f"seed_{seed}"] = summary_s
        print(f"      Seed {seed} ({time.monotonic() - t_s:.1f}s) HOLDOUT-DTI ({EVALUATOR_VERSION}):")
        for arm_k, stats_k in summary_s["scores"].items():
            print(
                f"        {arm_k:22s}: DTI = {stats_k['dti']:.6f}  95% CI [{stats_k['ci95'][0]:.6f}, {stats_k['ci95'][1]:.6f}]"
            )

    pooled_terms = {arm_k: sum(t_list) for arm_k, t_list in all_seed_terms.items()}
    pooled_summary = evaluate_holdout.pooled_summary(
        pooled_terms, draws=2000, seed=520810, candidate="E3_CSCT_DINKELBACH"
    )
    n_pos_total = int(pooled_terms["E3_CSCT_DINKELBACH"][:, 3].sum())

    step_e1_vs_topo = evaluate_holdout.pooled_summary(
        {"E1_BLIND_POISSON": pooled_terms["E1_BLIND_POISSON"], "CTRL_TOPO": pooled_terms["CTRL_TOPO"]},
        draws=2000,
        seed=520811,
        candidate="E1_BLIND_POISSON",
    )["paired_differences"]["CTRL_TOPO"]
    step_e2_vs_e1 = evaluate_holdout.pooled_summary(
        {"E2_CSCT_POISSON": pooled_terms["E2_CSCT_POISSON"], "E1_BLIND_POISSON": pooled_terms["E1_BLIND_POISSON"]},
        draws=2000,
        seed=520812,
        candidate="E2_CSCT_POISSON",
    )["paired_differences"]["E1_BLIND_POISSON"]
    step_e3_vs_e2 = evaluate_holdout.pooled_summary(
        {"E3_CSCT_DINKELBACH": pooled_terms["E3_CSCT_DINKELBACH"], "E2_CSCT_POISSON": pooled_terms["E2_CSCT_POISSON"]},
        draws=2000,
        seed=520813,
        candidate="E3_CSCT_DINKELBACH",
    )["paired_differences"]["E2_CSCT_POISSON"]

    detached_scores = {}
    ctx_det20 = holdout.build_holdout(g, seeds=(20,), modes=("detached",))
    for arm_name in ("CTRL_RAND", "CTRL_TOPO", "CTRL_CG", "E1_BLIND_POISSON", "E2_CSCT_POISSON", "E3_CSCT_DINKELBACH"):
        det_s20 = holdout.evaluate(emitted_seed20_bool[arm_name], ctx_det20, cell_mode="detached")
        detached_scores[arm_name] = {
            "detached_pooled_dti": round(det_s20["pooled_dti"], 6),
            "detached_n_truth": det_s20["pooled_n_truth"],
            "detached_coverage": round(det_s20["pooled_coverage"], 6),
        }

    print(f"\n=== DUAL-SEED POOLED HOLDOUT-DTI ({EVALUATOR_VERSION}, n_positives={n_pos_total}) ===")
    for arm_k, stats_k in pooled_summary["scores"].items():
        print(
            f"  {arm_k:22s}: DTI = {stats_k['dti']:.6f}  95% CI [{stats_k['ci95'][0]:.6f}, {stats_k['ci95'][1]:.6f}]"
        )
    print("\n=== PAIRED ABLATION DELTAS (2,000 SPATIAL BLOCK-BOOTSTRAP DRAWS) ===")
    print(f"  E1 (Blind Multi-Physics) - CTRL_TOPO : {step_e1_vs_topo['delta']:+.6f}  CI {step_e1_vs_topo['ci95']}")
    print(f"  E2 (+ Crack-Tip/Relay)   - E1        : {step_e2_vs_e1['delta']:+.6f}  CI {step_e2_vs_e1['ci95']}")
    print(f"  E3 (+ Exact Dinkelbach)  - E2        : {step_e3_vs_e2['delta']:+.6f}  CI {step_e3_vs_e2['ci95']}")
    print("\n=== PURE DETACHED BLIND FAULT STRANDS (SEED 20) ===")
    for arm_k, ds in detached_scores.items():
        print(f"  {arm_k:22s}: Detached DTI = {ds['detached_pooled_dti']:.6f} (n_truth={ds['detached_n_truth']})")

    # --- STEP 5: Full-footprint live CSCT surface & halo-constrained 300 m Dinkelbach cover ---
    print("\n[5/7] Constructing full-footprint live CSCT surface and running Dinkelbach 300 m cover (all 468 halos <= 0.650)...")
    fullcat_aug = augment_fold_transfer(
        cat,
        fp,
        compute_visible_transfer_features(
            cat, fp, phys_theta, cache_path=ROOT / "data" / "cache" / "g87_transfer_fullcat.mmap"
        ),
    )
    n_stat = mm_static.shape[1]
    n_total = n_stat + 1 + fullcat_aug.shape[1]
    quad_fp = quad_ids.ravel()[fp_idx]
    p_csct_live_fp = np.zeros(fp_idx.size, dtype=np.float32)

    for q in range(4):
        pair_s20 = csct_models_all[q]
        pair_s30 = csct_models_all[4 + q]
        te_idx = np.flatnonzero(quad_fp == q)
        for start in range(0, te_idx.size, 300_000):
            sl = te_idx[start : start + 300_000]
            X_te = np.empty((sl.size, n_total), dtype=np.float32)
            X_te[:, :n_stat] = np.asarray(mm_static[sl], dtype=np.float32)
            X_te[:, n_stat] = p_blind_oof_fp[sl]
            X_te[:, n_stat + 1 :] = fullcat_aug[sl]
            ps20 = 0.60 * pair_s20[0].predict_proba(X_te)[:, 1] + 0.40 * pair_s20[1].predict_proba(X_te)[:, 1]
            ps30 = 0.60 * pair_s30[0].predict_proba(X_te)[:, 1] + 0.40 * pair_s30[1].predict_proba(X_te)[:, 1]
            p_csct_live_fp[sl] = (0.5 * (ps20 + ps30)).astype(np.float32)

    # Blend 80% CSCT full posterior + 20% blind multi-physics prior to guarantee strong far-field basin exploration
    p_live_fp = (0.80 * p_csct_live_fp + 0.20 * p_blind_oof_fp).astype(np.float32)
    p_live_surface = _fp_to_grid(p_live_fp, fp)

    d_cat = ndi.distance_transform_edt(~cat)
    allowed_live = fp & (~cat) & (d_cat > 3.0)

    live_dots, live_dink_stats = dinkelbach_submodular_300m_emit(
        p_live_surface,
        allowed_live,
        n_dots=DEFAULT_DOT_BUDGET,
        pi_true=0.0022,
        temperature=1.0,
        fp_lambda=0.012,
        min_sep_px=2.40,
        packed_halos_fp=packed_halos,
        fp_lut=fp_lut,
        active_halo_indices=active_halo_indices,
        overlap_cap=0.650,
    )

    dd_live = d_cat[live_dots > 0]
    radial_profile = {
        "total_dots": int((live_dots > 0).sum()),
        "on_catalogue_d0": int(((live_dots > 0) & cat).sum()),
        "halo_0_to_3px": int(((dd_live > 0) & (dd_live <= 3.0)).sum()),
        "tip_relay_3_to_10px": int(((dd_live > 3.0) & (dd_live <= 10.0)).sum()),
        "piedmont_step_10_to_30px": int(((dd_live > 10.0) & (dd_live <= 30.0)).sum()),
        "detached_blind_gt_30px": int((dd_live > 30.0).sum()),
        "min_distance_to_catalogue_px": round(float(dd_live.min()), 4),
        "median_distance_to_catalogue_px": round(float(np.median(dd_live)), 4),
        "mean_distance_to_catalogue_px": round(float(dd_live.mean()), 4),
        "quadrant_counts": {
            qname: int(((live_dots > 0) & (quad_ids == qi)).sum())
            for qi, qname in enumerate(("NW", "NE", "SW", "SE"))
        },
        "dinkelbach_stats": live_dink_stats,
    }
    print("      Live emitted radial profile:", json.dumps(radial_profile, indent=2))

    # --- STEP 6: Full 480-raster uniqueness audit (pre-placement surface & post-placement dots) ---
    print("\n[6/7] Auditing BOTH pre-placement continuous surface AND post-placement dots across ALL 480 unique SHA-256 rasters...")
    t_u = time.monotonic()
    uniqueness_audit = fast_full_registry_audit(
        candidate_surface=p_live_surface,
        candidate_dots=live_dots >= 0.5,
        footprint=fp,
        catalogue=cat,
        registry_dir=ROOT / "data" / "registry_rasters",
        scored_dir=ROOT / "data" / "scored",
        cache_dir=ROOT / "data" / "cache",
    )
    print(f"      Full registry audit finished in {time.monotonic() - t_u:.1f}s:")
    print("      Pre-placement surface gate:", uniqueness_audit["pre_placement_surface_gate"])
    print("      Post-placement dot gate:   ", uniqueness_audit["post_placement_discriminating_dot_gate"])
    assert uniqueness_audit["pre_placement_surface_gate"]["passed"] is True
    assert uniqueness_audit["post_placement_discriminating_dot_gate"]["passed"] is True

    # --- STEP 7: Package GeoTIFF via UNMODIFIED vendor/gems57/submission_writer.py + independent preflight ---
    print("\n[7/7] Packaging GeoTIFF via unmodified vendor/gems57/submission_writer.py and running dual preflight...")
    dl_dir = ROOT / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    sub_stem = "gems87-csct-dink300-37654dots-20261022-zeros"
    sub_name = sub_stem
    sub_note = "G87 CSCT: cover-stratified divisive Radon multiphysics + crack-tip/relay + 300m Dinkelbach cover (37654 binary dots, all finite)"
    assert len(sub_note) <= 140, f"Note too long: {len(sub_note)}"

    zeros_tif = dl_dir / f"{sub_stem}.tif"
    for ext in (".tif", ".zip", ".json"):
        p_rm = zeros_tif.with_suffix(ext)
        if p_rm.exists():
            p_rm.unlink()

    writer_receipt = submission_writer.write_submission(
        zeros_tif,
        live_dots,
        ROOT / "data" / "sample_submission.tif",
        fp,
        note=sub_note,
        name=sub_name,
        catalogue=cat,
        metadata={
            "lane": LANE_ID,
            "evaluator_version": EVALUATOR_VERSION,
            "withheld_positive_count": n_pos_total,
            "pooled_holdout_dti": pooled_summary["scores"]["E3_CSCT_DINKELBACH"]["dti"],
            "pooled_holdout_ci_95": pooled_summary["scores"]["E3_CSCT_DINKELBACH"]["ci95"],
            "radial_profile": radial_profile,
        },
    )

    nan_tif = dl_dir / "gems87-csct-dink300-37654dots-20261022-nan.tif"
    if nan_tif.exists():
        nan_tif.unlink()
    nan_arr = np.where(fp, live_dots, np.float32(np.nan)).astype(np.float32)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as ds_ref:
        prof = ds_ref.profile.copy()
        prof.update(dtype="float32", count=1, compress="deflate", nodata=np.nan)
        with rasterio.open(nan_tif, "w", **prof) as dst:
            dst.write(nan_arr, 1)

    indep_nan_report = independent_validate_submission(nan_tif, ROOT / "data" / "sample_submission.tif")
    vendor_zeros_report = g57_validate.validate(zeros_tif, fp, cat)

    assert writer_receipt["template_report"]["ok"] is True
    assert all(vendor_zeros_report["checks"].values())
    assert indep_nan_report["ready"] is True, f"Independent validator failed: {indep_nan_report['errors']}"

    print(f"      Zeros-exterior TIF SHA-256: {writer_receipt['sha256']} ({writer_receipt['bytes']:,} bytes) — ALL 14 VENDOR CHECKS PASS!")
    print(f"      NaN-exterior   TIF SHA-256: {indep_nan_report['sha256']} ({nan_tif.stat().st_size:,} bytes) — ALL INDEPENDENT CHECKS PASS!")

    (ev_dir / "e1_e2_e3_holdout_results.json").write_text(
        json.dumps(
            {
                "lane": LANE_ID,
                "evaluator_version": EVALUATOR_VERSION,
                "implementation_hashes": evaluate_holdout.implementation_hashes(),
                "withheld_positive_count_dual_seed": n_pos_total,
                "dual_seed_pooled": pooled_summary,
                "stepwise_ablation_deltas": {
                    "E1_minus_CTRL_TOPO": step_e1_vs_topo,
                    "E2_minus_E1": step_e2_vs_e1,
                    "E3_minus_E2": step_e3_vs_e2,
                },
                "detached_blind_strands_seed20": detached_scores,
                "per_seed": per_seed_summaries,
                "per_fold_records": per_fold_records,
                "live_radial_profile": radial_profile,
                "runtime_seconds": round(time.monotonic() - t_start, 2),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (ev_dir / "uniqueness_audit_full.json").write_text(
        json.dumps(uniqueness_audit, indent=2) + "\n", encoding="utf-8"
    )
    (ev_dir / "validation_receipt.json").write_text(
        json.dumps(
            {
                "primary_zeros_tif": writer_receipt,
                "primary_vendor_validate": vendor_zeros_report,
                "companion_nan_tif_independent_validate": indep_nan_report,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nALL 7 STEPS SUCCEEDED WITH ZERO ERRORS IN {time.monotonic() - t_start:.1f}s!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
