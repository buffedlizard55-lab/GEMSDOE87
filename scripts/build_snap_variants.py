#!/usr/bin/env python3
"""Reproducible builder and validator for GEMSDOE87 Agent Brief v2 (AXIS = SNAP on Parent R0).

Workflow (strictly offline / GitHub-pinned inputs only; zero contact with drivendata.org or dropbox.com):
1. Verify all SHA-256 pins in `registry/data_manifest.json` against `.cache/raw/` (restoring from pinned
   GitHub commit tarballs on `codeload.github.com` if missing).
2. Rebuild Parent R0 (`h33-h33-2-b2`, GEMSDOE32, 37,654 unit-mass dots) from pinned manifest inputs and
   assert byte-for-byte SHA-256 identity against both R0 twins (`c55bafc4...` zeros / `baeae321...` NaN).
3. Read `ledger/submissions.csv` first and refuse to duplicate any existing `(parent, axis, value)` or
   `sha256`.
4. Build 3 controlled variants of R0 on `AXIS = SNAP`: each R0 dot may move <= 2 px (Euclidean) to the
   strongest edge response in its 13-pixel window (`dy^2 + dx^2 <= 4`), holding count fixed at 37,654 and
   keeping R0's exclusions (destination must satisfy `d_cat > 2 px` inside the footprint). Edge fields:
     - `tmi2`:  band 3 `tmi_hg` (TMI horizontal-gradient magnitude), 3x3 footprint-normalised mean;
     - `grav2`: band 18 `iso_grav_anom_hg` (isostatic-gravity horizontal gradient), same smoothing;
     - `comb2`: equal-weight mean of footprint rank-normalised `tmi2` and `grav2` fields.
   Fully deterministic: row-major dot processing; candidate order `(-E, dist, dy, dx)` (own pixel wins
   ties, i.e. a dot stays unless a valid unclaimed candidate is strictly stronger); collisions resolved
   to the next-best free candidate; overflow (all window candidates claimed) falls back to the nearest
   free valid pixel with `d_cat > 2 px` and is counted and reported (expected 0). No randomness.
5. Write `releases/<id>.tif` (NaN outside footprint, per spec) and `releases/<id>-zeros.tif` (0.0 outside
   fallback), re-read every file from disk, run MUST-PASS format/catalogue/hash/count gates, and compute
   REPORT-ONLY diagnostics (fold-proper hide-and-recover PROXY with n and 95% CI, single-feature leakage
   canary, USGS SGMC off-catalogue control). Diagnostics are never gates (Brief v2 Section 6).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, uniform_filter
from scipy.stats import rankdata

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_prune_variants import (
    CANONICAL_INDEX_PATH,
    FIXED_SEED,
    INVENTORY_PATH,
    LEDGER_COLUMNS,
    LEDGER_PATH,
    PARENT_ID,
    RAW_DIR,
    RELEASES_DIR,
    R0_EXPECTED_NAN_SHA256,
    R0_EXPECTED_ZEROS_SHA256,
    R0_TARGET_DOTS,
    compute_parent_diff_stats,
    rebuild_and_verify_r0,
    sha256_file,
    symmetric_auc_mann_whitney,
    verify_and_restore_manifest,
    write_geotiff_pair_exact_profile,
)
from scripts.build_prune_variants import git_head_sha
from scripts.validate_submission import validate_submission
from vendor.gems57 import evaluate_holdout as EH
from vendor.gems57 import grid as GR
from vendor.gems57 import holdout as HO
from vendor.gems57 import validate as V57

SESSION_DATE = "20261023"
SNAP_AXIS = "SNAP"
SNAP_MAX_DIST_PX = 2.0
SNAP_MIN_DCAT_PX = 2.0  # R0's own exclusion, unchanged ("same exclusions")
BAND_TMI_HG = 3  # 1-based rasterio band: "tmi_hg - Total magnetic intensity horizontal gradient"
BAND_ISO_GRAV_HG = 18  # 1-based rasterio band: "iso_grav_anom_hg - Isostatic gravity anomaly horizontal gradient"
OVERFLOW_MAX_RING_PX = 8

# Candidate offsets with Euclidean displacement <= 2 px, ordered (dist, dy, dx) — (0,0) first so ties stay.
SNAP_OFFSETS: list[tuple[int, int]] = sorted(
    [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3) if dy * dy + dx * dx <= 4],
    key=lambda t: (t[0] * t[0] + t[1] * t[1], t[0], t[1]),
)
RING_OFFSETS: dict[int, list[tuple[int, int]]] = {
    r: sorted(
        [
            (dy, dx)
            for dy in range(-r, r + 1)
            for dx in range(-r, r + 1)
            if r - 1 < np.hypot(dy, dx) <= r
        ],
        key=lambda t: (np.hypot(t[0], t[1]), t[0], t[1]),
    )
    for r in range(3, OVERFLOW_MAX_RING_PX + 1)
}


def load_edge_band(band_idx: int, footprint: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Load one training_features band; invalid pixels (non-finite or nodata) become the footprint minimum."""
    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        raw = ds.read(band_idx).astype(np.float64)
    bad = ~np.isfinite(raw) | (raw < -1e30) | ~footprint
    n_bad = int((bad & footprint).sum())
    filled = raw.copy()
    valid_min = float(raw[footprint & ~bad].min())
    filled[bad] = valid_min
    return filled, {
        "band_index_1based": band_idx,
        "description": None,
        "invalid_pixels_in_footprint": n_bad,
        "invalid_fill_value": valid_min,
    }


def smooth_footprint(field: np.ndarray, footprint: np.ndarray, size: int = 3) -> np.ndarray:
    """Footprint-normalised uniform (box) mean; pixels outside the footprint never contribute."""
    fp = footprint.astype(np.float64)
    num = uniform_filter(field * fp, size=size, mode="constant", cval=0.0)
    den = uniform_filter(fp, size=size, mode="constant", cval=0.0)
    out = np.zeros_like(field)
    nz = den > 1e-9
    out[nz] = num[nz] / den[nz]
    return out


def rank_normalise(field: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Rank-normalise to [0, 1] over footprint pixels only (average ranks for ties)."""
    out = np.zeros_like(field)
    vals = field[footprint]
    ranks = rankdata(vals, method="average")
    out[footprint] = (ranks - 1.0) / max(float(vals.size - 1), 1.0)
    return out


def snap_dots_to_edge(
    dots: np.ndarray,
    edge: np.ndarray,
    footprint: np.ndarray,
    d_cat: np.ndarray,
    h19_5: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Deterministic SNAP: move each dot <= 2 px to the strongest edge response; count is preserved."""
    H, W = dots.shape
    valid_dest = footprint & (d_cat > SNAP_MIN_DCAT_PX)
    out = np.zeros_like(dots)
    claimed = out  # alias: a claimed pixel is exactly an occupied destination

    ys, xs = np.nonzero(dots)  # row-major order
    n = ys.size
    moved = 0
    overflow = 0
    displacements = np.zeros(n, dtype=np.float64)
    edge_at_src = np.zeros(n, dtype=np.float64)
    edge_at_dst = np.zeros(n, dtype=np.float64)
    landed_off_ridge = 0

    for k in range(n):
        y, x = int(ys[k]), int(xs[k])
        best_key: tuple[float, float, int, int] | None = None  # (-E, dist, dy, dx)
        for dy, dx in SNAP_OFFSETS:
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= H or nx < 0 or nx >= W:
                continue
            if claimed[ny, nx] or not valid_dest[ny, nx]:
                continue
            key = (-float(edge[ny, nx]), float(dy * dy + dx * dx), dy, dx)
            if best_key is None or key < best_key:
                best_key = key
        if best_key is None:
            # Overflow fallback: nearest free valid pixel (count preservation is a MUST gate).
            placed = False
            for r in range(3, OVERFLOW_MAX_RING_PX + 1):
                for dy, dx in RING_OFFSETS[r]:
                    ny, nx = y + dy, x + dx
                    if ny < 0 or ny >= H or nx < 0 or nx >= W:
                        continue
                    if not claimed[ny, nx] and valid_dest[ny, nx]:
                        out[ny, nx] = True
                        overflow += 1
                        displacements[k] = float(np.hypot(dy, dx))
                        edge_at_src[k] = float(edge[y, x])
                        edge_at_dst[k] = float(edge[ny, nx])
                        if h19_5 is not None and not h19_5[ny, nx]:
                            landed_off_ridge += 1
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                raise RuntimeError(f"SNAP overflow: no free valid pixel within {OVERFLOW_MAX_RING_PX} px of ({y},{x})")
            continue
        _, dist2, dy, dx = best_key
        ny, nx = y + dy, x + dx
        out[ny, nx] = True
        disp = float(np.sqrt(dist2))
        displacements[k] = disp
        edge_at_src[k] = float(edge[y, x])
        edge_at_dst[k] = float(edge[ny, nx])
        if disp > 0.0:
            moved += 1
            if h19_5 is not None and not h19_5[ny, nx]:
                landed_off_ridge += 1

    if int(out.sum()) != n:
        raise RuntimeError(f"SNAP changed dot count: {int(out.sum())} != {n}")
    if overflow:
        raise RuntimeError(f"SNAP produced {overflow} overflow moves; investigate before accepting")

    moved_mask = displacements > 0.0
    stats: dict[str, Any] = {
        "n_dots_in": n,
        "n_dots_out": int(out.sum()),
        "n_moved": moved,
        "pct_moved": round(100.0 * moved / n, 4),
        "mean_displacement_px_all": round(float(displacements.mean()), 4),
        "mean_displacement_px_moved": round(float(displacements[moved_mask].mean()), 4) if moved else 0.0,
        "median_displacement_px_moved": round(float(np.median(displacements[moved_mask])), 4) if moved else 0.0,
        "max_displacement_px": round(float(displacements.max()), 4),
        "mean_displacement_m_all": round(float(displacements.mean()) * 100.0, 1),
        "displacement_hist_px": {
            "0": int((displacements == 0.0).sum()),
            "1": int((displacements == 1.0).sum()),
            "sqrt2": int((np.abs(displacements - np.sqrt(2.0)) < 1e-9).sum()),
            "2": int((displacements == 2.0).sum()),
        },
        "edge_gain_mean": round(float((edge_at_dst - edge_at_src).mean()), 6),
        "edge_gain_mean_moved": round(float((edge_at_dst[moved_mask] - edge_at_src[moved_mask]).mean()), 6)
        if moved
        else 0.0,
        "n_landed_off_h19_5": landed_off_ridge if h19_5 is not None else None,
        "pct_landed_off_h19_5": round(100.0 * landed_off_ridge / moved, 4) if (moved and h19_5 is not None) else None,
        "overflow_moves": overflow,
    }
    return out, stats


def build_edge_fields(footprint: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Build the three SNAP edge fields from pinned training_features bands (no external/lidar data)."""
    tmi_raw, tmi_meta = load_edge_band(BAND_TMI_HG, footprint)
    grav_raw, grav_meta = load_edge_band(BAND_ISO_GRAV_HG, footprint)
    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        tmi_meta["description"] = ds.descriptions[BAND_TMI_HG - 1]
        grav_meta["description"] = ds.descriptions[BAND_ISO_GRAV_HG - 1]
    e_tmi = smooth_footprint(tmi_raw, footprint)
    e_grav = smooth_footprint(grav_raw, footprint)
    e_comb = 0.5 * (rank_normalise(e_tmi, footprint) + rank_normalise(e_grav, footprint))
    fields = {"tmi2": e_tmi, "grav2": e_grav, "comb2": e_comb}
    meta = {
        "smoothing": "3x3 footprint-normalised box mean (suppresses 100 m gridding noise from 400 m line spacing)",
        "tmi2": tmi_meta,
        "grav2": grav_meta,
        "comb2": "0.5 * (rank(e_tmi) + rank(e_grav)) over footprint pixels; equal-weight hedge across sensors",
        "max_displacement_px": SNAP_MAX_DIST_PX,
        "window": "13 pixels with dy^2 + dx^2 <= 4 (Euclidean <= 2 px)",
        "tie_rule": "own pixel wins ties; a dot moves only to a strictly stronger valid unclaimed candidate",
        "exclusions": "destination requires footprint & d_cat > 2.0 px (identical to R0's exclusion)",
    }
    return fields, meta


def run_snap_report_only_diagnostics(
    static_masks: dict[str, np.ndarray],
    edge_fields: dict[str, np.ndarray],
    d28: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
) -> dict[str, Any]:
    """Section 6 REPORT-ONLY diagnostics for the SNAP session (never used as gates; labeled PROXY)."""
    t0 = time.time()
    grid = GR.load_grid(RAW_DIR)
    seeds = (20, 30)
    draws_by_seed = {s: HO.buffered_component_draw(grid, seed=s)[0] for s in seeds}

    # 1. Fold-proper hide-and-recover PROXY: re-apply R0's d>2 px collar on each seed's VISIBLE catalogue,
    #    then the identical SNAP operator (fold-fair: no full-catalogue information).
    fp_terms: dict[str, np.ndarray] = {}
    for s in seeds:
        vis_s = draws_by_seed[s][0]["visible"]
        d_vis = distance_transform_edt(~(vis_s & footprint))
        base_fp = d28 & (d_vis > SNAP_MIN_DCAT_PX) & footprint
        arms = {"R0_fp": base_fp}
        for value, field in edge_fields.items():
            arms[f"SNAP{value}_fp"], _ = snap_dots_to_edge(base_fp, field, footprint, d_vis)
        for arm_name, m_s in arms.items():
            pred_s = m_s.astype(np.float32)
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred_s, fold, valid=footprint)
                fp_terms[arm_name] = terms.copy() if arm_name not in fp_terms else (fp_terms[arm_name] + terms)

    fp_summary = EH.pooled_summary(fp_terms, draws=1000, seed=520810, candidate="SNAPtmi2_fp")

    # 2. Static-raster hide-and-recover PROXY (literal full-catalogue rasters).
    st_terms: dict[str, np.ndarray] = {}
    for arm_name, m_static in static_masks.items():
        tot = None
        pred = m_static.astype(np.float32)
        for s in seeds:
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred, fold, valid=footprint)
                tot = terms.copy() if tot is None else (tot + terms)
        assert tot is not None
        st_terms[arm_name] = tot
    st_summary = EH.pooled_summary(st_terms, draws=1000, seed=520810, candidate="SNAPtmi2")

    # 3. Single-feature leakage canary on withheld positives (AUC > 0.90 => stop and investigate).
    rng = np.random.default_rng(20261023)
    eval_masks = {}
    for s in seeds:
        vis_s = draws_by_seed[s][0]["visible"]
        hid_s = np.zeros_like(footprint)
        for fold in draws_by_seed[s]:
            hid_s |= (fold["truth"] & fold["region"] & footprint & ~vis_s)
        pos_idx = np.flatnonzero(hid_s[footprint])
        neg_pool = np.flatnonzero((~hid_s & ~vis_s & footprint)[footprint])
        neg_idx = rng.choice(neg_pool, size=min(80_000, neg_pool.size), replace=False)
        idx_all = np.concatenate([pos_idx, neg_idx])
        y_all = np.concatenate([np.ones(pos_idx.size, dtype=bool), np.zeros(neg_idx.size, dtype=bool)])
        eval_masks[s] = (idx_all, y_all)

    canary_channels: list[dict[str, Any]] = []

    def _audit_2d(name: str, arr2d: np.ndarray) -> None:
        v_fp = np.asarray(arr2d)[footprint]
        sym_by_s = {}
        auc_by_s = {}
        for s, (idx_all, y_all) in eval_masks.items():
            vals = v_fp[idx_all].astype(np.float64)
            vals = np.where(vals < -1e20, 0.0, vals)
            auc, sym = symmetric_auc_mann_whitney(y_all, vals)
            auc_by_s[str(s)] = round(auc, 5)
            sym_by_s[str(s)] = round(sym, 5)
        mx = max(sym_by_s.values())
        canary_channels.append(
            {
                "channel": name,
                "auc_by_seed": auc_by_s,
                "max_symmetric_auc": round(mx, 5),
                "flagged_over_0_90": bool(mx > 0.90),
            }
        )

    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        for b_idx in range(1, ds.count + 1):
            desc = (ds.descriptions[b_idx - 1] or f"band_{b_idx}").split(" - ")[0].strip()
            _audit_2d(f"training_b{b_idx:02d}_{desc}", ds.read(b_idx))
    for value, field in edge_fields.items():
        _audit_2d(f"snap_edge_{value}_smoothed", field)

    canary_channels.sort(key=lambda r: r["max_symmetric_auc"], reverse=True)
    max_sym_auc = max(r["max_symmetric_auc"] for r in canary_channels)
    flagged = [r for r in canary_channels if r["flagged_over_0_90"]]
    if flagged:
        raise RuntimeError(f"STOP: Leakage canary fired (> 0.90 symmetric AUC): {flagged}")

    # 4. Off-catalogue USGS SGMC control PROXY (d_cat > 3.0 px from mapped Quaternary faults).
    with rasterio.open(RAW_DIR / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    from vendor.gems57 import metric as M57

    sgmc_scores = {}
    for arm_name, m_static in static_masks.items():
        res = M57.dti_binary(m_static, sgmc_offcat := (sgmc & ~catalogue & (d_cat > 3.0)), valid=footprint, known=catalogue)
        sgmc_scores[arm_name] = {
            "evidence_label": "PROXY",
            "dti": round(float(res["dti"]), 6),
            "coverage": round(float(res["coverage"]), 6),
            "n_sgmc_offcat_pixels": int(res["n_truth"]),
            "n_emitted": int(res["n_emitted"]),
        }

    return {
        "evidence_label": "PROXY",
        "note": "REPORT ONLY — never used as promotion/rejection gates (Brief v2 Section 6).",
        "evaluator_version": EH.VERSION,
        "withheld_positive_pixels": int(fp_summary["scores"]["SNAPtmi2_fp"]["withheld_positive_pixels"]),
        "fold_proper_hide_and_recover_proxy": {
            k: {
                "evidence_label": "PROXY",
                "dti": round(float(v["dti"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
                "withheld_positive_pixels": int(v["withheld_positive_pixels"]),
            }
            for k, v in fp_summary["scores"].items()
        },
        "fold_proper_paired_vs_R0_fp": {
            k: {
                "evidence_label": "PROXY",
                "delta_arm_minus_r0": round(float(v["delta"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
            }
            for k, v in fp_summary["paired_differences"].items()
        },
        "static_raster_hide_and_recover_proxy": {
            k: {
                "evidence_label": "PROXY",
                "dti": round(float(v["dti"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
                "withheld_positive_pixels": int(v["withheld_positive_pixels"]),
                "caveat": "Static full-catalogue collar d_cat > 2 px zeroes predictions within 2 px of withheld G_fold subset C.",
            }
            for k, v in st_summary["scores"].items()
        },
        "leakage_canary": {
            "evidence_label": "PROXY",
            "channels_audited": len(canary_channels),
            "limit_symmetric_auc": 0.90,
            "max_symmetric_auc_observed": round(float(max_sym_auc), 5),
            "flagged_channels": flagged,
            "passed_investigation_check": len(flagged) == 0,
            "top_10_channels": canary_channels[:10],
        },
        "sgmc_offcatalogue_control_proxy": sgmc_scores,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-diagnostics", action="store_true", help="skip report-only holdout/canary diagnostics")
    args = ap.parse_args()

    t_start = time.time()
    print("[1/6] Verifying SHA-256 pins in registry/data_manifest.json ...", flush=True)
    manifest_receipt = verify_and_restore_manifest()
    print(f"      Verified {manifest_receipt['verified_count']} files against registry/data_manifest.json.", flush=True)

    template_tif = RAW_DIR / "sample_submission.tif"
    with rasterio.open(template_tif) as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(RAW_DIR / "existing_faults.tif") as ds:
        catalogue = (ds.read(1) > 0) & footprint
    with rasterio.open(RAW_DIR / "scored" / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif") as ds:
        h19_5 = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    with rasterio.open(RAW_DIR / "scored" / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") as ds:
        d28_manifest = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    d_cat = distance_transform_edt(~catalogue)

    print("[2/6] Rebuilding Parent R0 (h33-h33-2-b2) and verifying exact SHA-256 ...", flush=True)
    d28, r0_mask, r0_receipt = rebuild_and_verify_r0(
        h19_5, d28_manifest, footprint, catalogue, d_cat, template_tif
    )
    print(
        f"      R0 exact match verified: n_dots={r0_receipt['n_dots']}, "
        f"zeros_sha256={r0_receipt['zeros_sha256'][:16]}..., nan_sha256={r0_receipt['nan_sha256'][:16]}...",
        flush=True,
    )

    print("[3/6] Loading ledger/submissions.csv and checking deduplication ...", flush=True)
    existing_rows: list[dict[str, str]] = []
    if LEDGER_PATH.is_file():
        with LEDGER_PATH.open("r", encoding="utf-8", newline="") as f:
            existing_rows = list(csv.DictReader(f))
    seen_shas: set[str] = {r["sha256"] for r in existing_rows if r.get("sha256")}
    seen_shas |= {r["sha256_zeros"] for r in existing_rows if r.get("sha256_zeros")}
    seen_pairs: set[tuple[str, str, str]] = {
        (r.get("parent", ""), r.get("axis", ""), r.get("value", "")) for r in existing_rows
    }
    registry_shas: set[str] = set()
    if CANONICAL_INDEX_PATH.is_file():
        registry_shas = {r["sha256"] for r in json.loads(CANONICAL_INDEX_PATH.read_text(encoding="utf-8")).get("rasters", [])}
    inventory_shas: set[str] = set()
    if INVENTORY_PATH.is_file():
        inventory_shas = {r["sha256"] for r in json.loads(INVENTORY_PATH.read_text(encoding="utf-8")).get("rasters", [])}

    print("[4/6] Building 3 controlled AXIS=SNAP variants of R0 at fixed count 37,654 ...", flush=True)
    edge_fields, edge_meta = build_edge_fields(footprint)

    variant_specs = [
        {
            "value": "tmi2",
            "predicted_change": "+0.002 to +0.010 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "GeoDAWN Area 2 was flown at 400 m E-W line spacing and 150-200 m terrain clearance "
                    "(https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7), so the H19-5 ridge "
                    "positions that seeded R0 are uncertain by roughly the 300 m scoring-kernel radius. Where the "
                    "smoothed TMI horizontal-gradient magnitude (band 3, tmi_hg) peaks within 2 px of an R0 dot, "
                    "that crest is a better estimate of the magnetic-basement step (the fault) than the ridge "
                    "seed, and re-centering dots on crests converts partial kernel credit into full credit."
                ),
                "mechanism": (
                    "Move each of the 37,654 R0 dots <= 2 px (Euclidean, 13-pixel window) to the argmax of the "
                    "3x3-smoothed tmi_hg field; destination must stay inside the footprint at d_cat > 2 px (R0's "
                    "own exclusion); count fixed; deterministic row-major processing, own-pixel-wins ties. "
                    "DTI = T/(0.2T + 0.2(S-M) + 0.8|G|): mass S is unchanged, so only kernel credit T and the "
                    "S-M term can move; a 100-200 m re-centering onto the true trace raises K_300 overlap on "
                    "line-like truth (bar ~0.056 at DTI 0.28 for isolated truth, lower for lines)."
                ),
                "non_fault_mimic": (
                    "Flight-line corrugation residual between 400 m-spaced lines, cultural magnetics (pipelines, "
                    "powerlines), Tertiary dike swarms and caldera ring-fracture crests, and sharp lithologic "
                    "contacts all produce tmi_hg crests with no Quaternary fault; snapping can walk dots onto them."
                ),
                "predicted_live_change": "+0.002 to +0.010 DTI [MODEL] vs R0 (treat |delta| < 0.01 on public chunks as no evidence).",
                "falsifier": (
                    "Live public score drops by >= 0.01 vs R0's receipt: the H19-5 ridge positions are already at "
                    "or better than the tmi_hg crest, or snapping systematically walks dots onto non-fault crests."
                ),
            },
        },
        {
            "value": "grav2",
            "predicted_change": "-0.002 to +0.006 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "The isostatic-gravity horizontal gradient (band 18, iso_grav_anom_hg) marks the density "
                    "contrast across basin-margin normal faults independently of magnetics: where basin fill "
                    "thinks against range front, the Bouguer step tracks the fault even where TMI is blurred by "
                    "remagnetised volcanics. Re-centering R0 dots on gravity-gradient crests tests a second, "
                    "physically independent positioning signal."
                ),
                "mechanism": (
                    "Identical SNAP operator and exclusions as tmi2, but the edge field is the 3x3-smoothed "
                    "iso_grav_anom_hg band. Count fixed at 37,654; <= 2 px displacement; d_cat > 2 px preserved."
                ),
                "non_fault_mimic": (
                    "Isostatic-gravity compilations are smooth (station spacing km-scale): crests can mark "
                    "paleo-basin edges, buried pluton margins, or compaction-driven density gradients in "
                    "sediments rather than active fault scarps; the 100 m grid oversamples that smoothness."
                ),
                "predicted_live_change": "-0.002 to +0.006 DTI [MODEL] vs R0 (weaker positional information at 100-200 m scale).",
                "falsifier": (
                    "grav2 beats tmi2 by >= +0.01 live (gravity edges beat magnetic edges at 100-200 m), or "
                    "grav2 falls >= 0.01 below R0 (gravity-crest snapping actively harms placement)."
                ),
            },
        },
        {
            "value": "comb2",
            "predicted_change": "+0.002 to +0.008 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "Basin-margin normal faults in the Great Basin usually produce BOTH a magnetic basement step "
                    "and a Bouguer step; single-sensor crests include sensor-specific noise (flight-line "
                    "corrugation for TMI; compilation smoothing for gravity). The equal-weight rank-composite "
                    "crest requires partial agreement of both sensors, so snap targets should be more often "
                    "real fault traces than either single field's argmax."
                ),
                "mechanism": (
                    "Identical SNAP operator; edge field = 0.5 * (rank(smoothed tmi_hg) + rank(smoothed "
                    "iso_grav_anom_hg)) over footprint pixels, which equalises the sensors' units and dynamic "
                    "ranges before averaging. Count fixed; <= 2 px; d_cat > 2 px preserved."
                ),
                "non_fault_mimic": (
                    "Coincident magnetic + gravity gradients also occur at caldera resurgent-dome margins and at "
                    "major lithologic boundaries (e.g., granite-diorite contacts with density contrast), so "
                    "agreement filters noise but not all non-fault structure."
                ),
                "predicted_live_change": "+0.002 to +0.008 DTI [MODEL] vs R0 (hedge between tmi2 and grav2 outcomes).",
                "falsifier": (
                    "comb2 lands >= 0.01 below BOTH tmi2 and R0 live, i.e., averaging the sensors destroys "
                    "usable positional information that each sensor holds separately."
                ),
            },
        },
    ]

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    built_variants: list[dict[str, Any]] = []
    static_masks: dict[str, np.ndarray] = {"R0": r0_mask}
    new_ledger_rows: list[dict[str, str]] = []
    head_sha = git_head_sha()

    for spec in variant_specs:
        pair_key = (PARENT_ID, SNAP_AXIS, spec["value"])
        if pair_key in seen_pairs:
            raise RuntimeError(f"Duplicate (parent, axis, value) in ledger: {pair_key}")

        v_mask, snap_stats = snap_dots_to_edge(r0_mask, edge_fields[spec["value"]], footprint, d_cat, h19_5=h19_5)
        diff_stats = compute_parent_diff_stats(v_mask, r0_mask, d_cat, footprint)
        # SNAP is exempt from the 1-50% change rule, but the exact percentage is recorded.
        assert diff_stats["removed_from_parent"] == snap_stats["n_moved"], "diff/snap move-count disagreement"
        assert diff_stats["n_dots"] == R0_TARGET_DOTS

        form_note = (
            f"h33-h33-2-b2; SNAP<=2px on {spec['value']} edge crest (n=37654, d_cat>2 kept, "
            f"{snap_stats['pct_moved']:.1f}% moved, mean {snap_stats['mean_displacement_px_all']:.2f}px); "
            f"pred {spec['predicted_change']}"
        )
        if len(form_note) > 140:
            raise ValueError(f"Form note exceeds 140 chars ({len(form_note)}): {form_note}")

        tmp_nan = RELEASES_DIR / f"_tmp_SNAP{spec['value']}.tif"
        tmp_zeros = RELEASES_DIR / f"_tmp_SNAP{spec['value']}-zeros.tif"
        sha_nan_tmp, sha_zeros_tmp = write_geotiff_pair_exact_profile(
            v_mask, footprint, catalogue, template_tif, tmp_nan, tmp_zeros
        )
        sha8 = sha_nan_tmp[:8]
        var_id = f"{PARENT_ID}-{SNAP_AXIS}{spec['value']}-{SESSION_DATE}-{sha8}"
        final_nan = RELEASES_DIR / f"{var_id}.tif"
        final_zeros = RELEASES_DIR / f"{var_id}-zeros.tif"
        tmp_nan.rename(final_nan)
        tmp_zeros.rename(final_zeros)

        # MUST-PASS Gate 1: re-read both written files from disk; SHA-256 + pixel identity.
        sha_nan = sha256_file(final_nan)
        sha_zeros = sha256_file(final_zeros)
        assert sha_nan == sha_nan_tmp and sha_nan[:8] == sha8
        assert sha_zeros == sha_zeros_tmp
        with rasterio.open(final_nan) as ds_n, rasterio.open(final_zeros) as ds_z:
            arr_n = ds_n.read(1)
            arr_z = ds_z.read(1)
        assert np.array_equal((arr_n[footprint] > 0.5), v_mask[footprint])
        assert np.array_equal((arr_z[footprint] > 0.5), v_mask[footprint])
        assert int((arr_n[catalogue] > 0).sum()) == 0, "Non-zero catalogue mass in NaN GeoTIFF!"
        assert int((arr_z[catalogue] > 0).sum()) == 0, "Non-zero catalogue mass in zeros GeoTIFF!"
        assert int((arr_n[footprint] > 0.5).sum()) == R0_TARGET_DOTS

        # MUST-PASS Gate 2: official spec validator on NaN-outside; gems57 validator on zeros-outside.
        val_nan = validate_submission(final_nan, template_tif)
        if not val_nan["ready"] or val_nan["errors"]:
            raise RuntimeError(f"validate_submission failed on {final_nan}: {val_nan['errors']}")
        val_zeros = V57.validate(final_zeros, footprint=footprint, catalogue=catalogue)
        if not val_zeros["all_checks_passed"]:
            raise RuntimeError(f"gems57.validate failed on {final_zeros}: {val_zeros['checks']}")

        # MUST-PASS Gate 3: SHA-256 dedup vs ledger + canonical registry + inventory.
        for s_chk in (sha_nan, sha_zeros):
            if s_chk in seen_shas:
                raise RuntimeError(f"SHA-256 {s_chk} already exists in ledger/submissions.csv!")
            if s_chk in registry_shas or s_chk in inventory_shas:
                raise RuntimeError(f"SHA-256 {s_chk} collides with historical registry raster!")
        seen_shas.update({sha_nan, sha_zeros})
        seen_pairs.add(pair_key)
        static_masks[f"SNAP{spec['value']}"] = v_mask

        rec = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": SNAP_AXIS,
            "value": spec["value"],
            "n_dots": diff_stats["n_dots"],
            "pct_changed": round(diff_stats["pct_changed"], 2),
            "sha256": sha_nan,
            "sha8": sha8,
            "zeros_sha256": sha_zeros,
            "zeros_sha8": sha_zeros[:8],
            "content_digest8": hashlib.sha256(np.packbits(v_mask)).hexdigest()[:8],
            "primary_file": f"releases/{final_nan.name}",
            "primary_bytes": final_nan.stat().st_size,
            "zeros_fallback_file": f"releases/{final_zeros.name}",
            "zeros_bytes": final_zeros.stat().st_size,
            "status": "BUILT",
            "predicted_change": spec["predicted_change"],
            "form_note": form_note,
            "form_note_length": len(form_note),
            "snap_details": snap_stats,
            "parent_diff": diff_stats,
            "mechanism_card": spec["mechanism_card"],
            "format_validation": {
                "primary_nan_validator": val_nan,
                "fallback_zeros_validator": {
                    "all_checks_passed": val_zeros["all_checks_passed"],
                    "checks": val_zeros["checks"],
                    "sha256": val_zeros["sha256"],
                    "bytes": val_zeros["bytes"],
                    "emitted_positive_pixels": val_zeros["emitted_positive_pixels"],
                    "on_catalogue_positive_pixels": val_zeros["on_catalogue_positive_pixels"],
                },
            },
        }
        built_variants.append(rec)
        new_ledger_rows.append(
            {
                "id": var_id,
                "parent": PARENT_ID,
                "axis": SNAP_AXIS,
                "value": spec["value"],
                "n_dots": str(diff_stats["n_dots"]),
                "pct_changed": f"{diff_stats['pct_changed']:.2f}",
                "sha256": sha_nan,
                "sha256_zeros": sha_zeros,
                "status": "BUILT",
                "predicted_change": spec["predicted_change"],
                "receipt_score": "",
                "date": "",
                "description": form_note,
            }
        )
        print(
            f"      Built {var_id}: n={diff_stats['n_dots']}, moved={snap_stats['pct_moved']:.2f}%, "
            f"mean_disp={snap_stats['mean_displacement_px_all']:.3f}px ({snap_stats['mean_displacement_m_all']} m), "
            f"off_ridge={snap_stats['pct_landed_off_h19_5']}% of moves, min_dcat={diff_stats['d_catalogue_px']['min']}px",
            flush=True,
        )

    print("[5/6] Writing ledger/submissions.csv and ledger/mechanism_cards.json ...", flush=True)
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for r in existing_rows + new_ledger_rows:
            writer.writerow({k: r.get(k, "") for k in LEDGER_COLUMNS})

    cards_path = REPO_ROOT / "ledger" / "mechanism_cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8")) if cards_path.is_file() else {}
    for rec in built_variants:
        card = dict(rec["mechanism_card"])
        card.update(
            {
                "axis": SNAP_AXIS,
                "value": rec["value"],
                "n_dots": rec["n_dots"],
                "pct_moved": rec["snap_details"]["pct_moved"],
                "mean_displacement_px": rec["snap_details"]["mean_displacement_px_all"],
                "max_displacement_px": rec["snap_details"]["max_displacement_px"],
                "window": edge_meta["window"],
                "exclusions": edge_meta["exclusions"],
            }
        )
        cards[rec["id"]] = card
    cards_path.write_text(json.dumps(cards, indent=1) + "\n", encoding="utf-8")

    diagnostics = None
    if not args.skip_diagnostics:
        print("[6/6] Running REPORT-ONLY diagnostics (fold-proper PROXY, canary, SGMC control) ...", flush=True)
        diagnostics = run_snap_report_only_diagnostics(
            static_masks, edge_fields, d28, footprint, catalogue, d_cat
        )
        fp = diagnostics["fold_proper_hide_and_recover_proxy"]
        print(
            f"      Diagnostics done in {diagnostics['elapsed_seconds']}s: "
            f"canary max_sym_auc={diagnostics['leakage_canary']['max_symmetric_auc_observed']} (<=0.90), "
            f"R0_fp PROXY={fp['R0_fp']['dti']:.6f}, SNAPtmi2_fp={fp['SNAPtmi2_fp']['dti']:.6f}, "
            f"SNAPcomb2_fp={fp['SNAPcomb2_fp']['dti']:.6f}",
            flush=True,
        )

    release_manifest = {
        "schema_version": 2,
        "generated_date_utc": SESSION_DATE,
        "git_head_at_build": head_sha,
        "fixed_seed": FIXED_SEED,
        "axis": SNAP_AXIS,
        "snap_operator": edge_meta,
        "manifest_verification": {
            "manifest_path": "registry/data_manifest.json",
            "verified_files_count": manifest_receipt["verified_count"],
        },
        "parent_r0_rebuild_receipt": r0_receipt,
        "variants": built_variants,
        "report_only_diagnostics": diagnostics,
        "total_elapsed_seconds": round(time.time() - t_start, 2),
    }
    (RELEASES_DIR / "manifest-snap.json").write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
    (REPO_ROOT / "evidence" / "snap_build.json").write_text(
        json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Done in {release_manifest['total_elapsed_seconds']}s. Wrote releases/manifest-snap.json, "
        f"evidence/snap_build.json, ledger/submissions.csv, ledger/mechanism_cards.json.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
