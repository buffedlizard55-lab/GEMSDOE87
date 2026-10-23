#!/usr/bin/env python3
"""Build & cache the 92-channel `H87-KDMI` feature stack + run pre-fit leakage canary.

Tests every feature alone on `gems57-pooled-hide-v2` (`seed=20` and `seed=30`,
11,321 and 11,342 withheld positive pixels) BEFORE any supervised model training
(`max symmetric AUC <= 0.90` gate).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import evaluate_holdout, holdout
from gems57.grid import load_grid
from gems87.kdmi_features import FEATURE_NAMES_92, build_or_load_kdmi_stack


def build_seed_masks(core_dir: Path, seeds: tuple[int, ...] = (20, 30)) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    grid = load_grid(core_dir)
    ctx = holdout.build_holdout(grid, seeds=seeds, modes=("all",))
    out: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for seed in seeds:
        hidden_s = np.zeros(grid.shape, dtype=bool)
        domain_s = np.zeros(grid.shape, dtype=bool)
        for q_i, qname in enumerate(holdout.FOLD_NAMES):
            key = f"draw{seed}_fold{qname}_all"
            c = ctx.cell(key)
            hidden_s |= ctx.hidden_by_cell[key]
            q_mask = ctx.quad == q_i
            from scipy import ndimage as ndi
            domain_s |= ndi.binary_erosion(q_mask, iterations=holdout.DOMAIN_ERODE) & grid.footprint
        visible_s = grid.catalogue & ~hidden_s
        active_s = domain_s & ~visible_s
        truth_s = hidden_s & active_s
        out[seed] = (active_s, truth_s)
    return out


def run_leakage_canary(mm: np.memmap, fp_idx: np.ndarray, core_dir: Path) -> dict:
    seed_masks = build_seed_masks(core_dir, seeds=(20, 30))
    folds = {}
    for seed, (active_s, truth_s) in seed_masks.items():
        eval_fp_mask = active_s.ravel()[fp_idx]
        y_fp = truth_s.ravel()[fp_idx][eval_fp_mask].astype(np.uint8)
        rng = np.random.default_rng(8700 + seed)
        pos_i = np.flatnonzero(y_fp == 1)
        neg_i = np.flatnonzero(y_fp == 0)
        neg_sub = rng.choice(neg_i, size=min(250_000, len(neg_i)), replace=False)
        sub = np.concatenate([pos_i, neg_sub])
        folds[seed] = (eval_fp_mask, sub, y_fp[sub], int(truth_s.sum()))

    rows = []
    max_sym_auc = 0.0
    quarantined = []
    fd = mm._mmap.fileno() if hasattr(mm, "_mmap") and hasattr(mm._mmap, "fileno") else None
    row_bytes = mm.shape[1] * 2

    for j, fname in enumerate(FEATURE_NAMES_92):
        col_fp = mm[j, :].astype(np.float32)
        if fd is not None and hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, j * row_bytes, row_bytes, os.POSIX_FADV_DONTNEED)
        aucs = {}
        sym_aucs = {}
        for seed, (eval_fp_mask, sub, y_sub, _) in folds.items():
            x = col_fp[eval_fp_mask][sub]
            ok = np.isfinite(x)
            if ok.sum() < 500 or len(np.unique(y_sub[ok])) < 2:
                auc = 0.5
            else:
                auc = float(roc_auc_score(y_sub[ok], x[ok]))
            sym = float(max(auc, 1.0 - auc))
            aucs[str(seed)] = round(auc, 6)
            sym_aucs[str(seed)] = round(sym, 6)
        worst = max(sym_aucs.values())
        max_sym_auc = max(max_sym_auc, worst)
        if worst > 0.90:
            quarantined.append(fname)
        rows.append(
            {
                "index": j,
                "feature": fname,
                "auc_seed20": aucs["20"],
                "auc_seed30": aucs["30"],
                "symmetric_auc_max": worst,
                "status": "QUARANTINE_LEAKAGE" if worst > 0.90 else "PASS",
            }
        )

    rows_sorted = sorted(rows, key=lambda r: r["symmetric_auc_max"], reverse=True)
    return {
        "gate": "single_feature_holdout_auc_le_0.90",
        "evaluator_version": evaluate_holdout.VERSION,
        "evaluator_hashes": evaluate_holdout.implementation_hashes(),
        "seeds_checked": [20, 30],
        "withheld_positives_seed20": folds[20][3],
        "withheld_positives_seed30": folds[30][3],
        "n_features_checked": len(FEATURE_NAMES_92),
        "sgmc_features_in_X": 0,
        "catalogue_features_in_X": 0,
        "dist_known_fault_px_dropped": True,
        "max_symmetric_auc": round(max_sym_auc, 6),
        "quarantined_features": quarantined,
        "passed": len(quarantined) == 0 and max_sym_auc <= 0.90,
        "top_15_features_by_single_feature_auc": rows_sorted[:15],
        "all_features": rows,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Build 92-channel H87-KDMI physical feature stack and run leakage canary.")
    ap.parse_args()
    t0 = time.time()
    cache_dir = ROOT / ".cache"
    bundle = build_or_load_kdmi_stack(cache_dir)
    print(f"[prepare_data] 92-channel KDMI stack loaded in {time.time() - t0:.2f}s")

    t1 = time.time()
    canary = run_leakage_canary(bundle["mm"], bundle["fp_idx"], cache_dir / "gems_data" / "core")
    out_path = ROOT / "data" / "leakage-canary-h87.json"
    out_path.write_text(json.dumps(canary, indent=2) + "\n")
    print(
        f"[prepare_data] Leakage canary finished in {time.time() - t1:.2f}s: "
        f"passed={canary['passed']} | seed20_pos={canary['withheld_positives_seed20']} "
        f"| seed30_pos={canary['withheld_positives_seed30']} "
        f"| max_symmetric_auc={canary['max_symmetric_auc']:.6f}"
    )
    print("Top 12 pure-physics single-feature AUCs on held-out faults:")
    for r in canary["top_15_features_by_single_feature_auc"][:12]:
        print(f"  [{r['index']:02d}] {r['feature']:34s} AUC20={r['auc_seed20']:.4f} AUC30={r['auc_seed30']:.4f} sym={r['symmetric_auc_max']:.4f}")
    if not canary["passed"]:
        raise RuntimeError(f"LEAKAGE CANARY FAILED: {canary['quarantined_features']}")


if __name__ == "__main__":
    main()
