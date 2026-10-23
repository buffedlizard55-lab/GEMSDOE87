#!/usr/bin/env python3
"""Reproducible builder and validator for GEMSDOE87 Agent Brief v2 (AXIS = SNAP on Parent R0).

Workflow (strictly offline / GitHub-pinned inputs only; zero contact with drivendata.org or dropbox.com):
1. Verify all 25 SHA-256 pins in `registry/data_manifest.json` against `.cache/raw/` (restoring from
   pinned GitHub commit tarballs on `codeload.github.com` if missing).
2. Rebuild Parent R0 (`h33-h33-2-b2`, GEMSDOE32, 37,654 unit-mass dots) from pinned manifest inputs
   (`scored_h19_5`, `existing_faults`, `sample_submission`) and assert byte-for-byte SHA-256 identity
   against both R0 twins (`c55bafc4...` zeros-outside and `baeae321...` NaN-outside). Halt on mismatch.
3. Read `ledger/submissions.csv` first; refuse to duplicate any existing `(parent, axis, value)` or
   `sha256` across `ledger/submissions.csv`, `registry/canonical_scored_index.json`, and `registry/inventory.json`.
4. Audit provided gravity gradient bands (`Band 05 iso_grav_anom_slope` isotropic |grad_H g| r=+0.9620 vs
   `Band 18 iso_grav_anom_hg` directional dg/dx r=+0.9482) and build 3 controlled `AXIS = SNAP` variants
   of R0 (`SNAPrtp2`, `SNAPtg2`, `SNAPscarp2`) strictly from organizer-provided `training_features.tif`
   bands (zero external lidar rasters used), holding count (`37,654`), R0 exclusions (`d_cat > 2 px`,
   footprint, zero catalogue mass), and inter-dot spacing (`min_sep >= sqrt(8)`) fixed, moving each dot
   `<= 2.0 px` cross-strike (`FIXED_SEED = 0`, deterministic tie-breaking, logged git HEAD SHA).
5. Write `releases/<id>.tif` (NaN outside footprint, per spec) and `releases/<id>-zeros.tif` (0.0 outside
   fallback), re-read every file from disk, run MUST-PASS format/catalogue/hash gates, record displacement
   and parent-diff statistics, update `ledger/submissions.csv` and `ledger/snap_mechanism_cards.json`, and
   compute REPORT-ONLY `PROXY` diagnostics (fold-proper hide-and-recover with n=22,663 & 95% CI, single-feature
   leakage canary across provided channels, and USGS SGMC off-catalogue control).
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
from scipy.ndimage import distance_transform_edt

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from gems87.snap import (
    DEFAULT_COHERENCE_FLOOR,
    DEFAULT_CROSS_STRIKE_COS,
    DEFAULT_MAX_RADIUS_PX,
    DEFAULT_MIN_SEP_SQ,
    compute_cross_strike_frame,
    empirical_quantile_map,
    hessian_crest_quantile,
    isotropic_horizontal_gradient,
    snap_dots,
)
from scripts.build_prune_variants import (
    CANONICAL_INDEX_PATH,
    FIXED_SEED,
    INVENTORY_PATH,
    LEDGER_COLUMNS,
    LEDGER_PATH,
    PARENT_ID,
    R0_TARGET_DOTS,
    RAW_DIR,
    RELEASES_DIR,
    SESSION_DATE,
    compute_parent_diff_stats,
    git_head_sha,
    rebuild_and_verify_r0,
    sha256_file,
    verify_and_restore_manifest,
    write_geotiff_pair_exact_profile,
)
from scripts.validate_submission import validate_submission
from vendor.gems57 import evaluate_holdout as EH
from vendor.gems57 import grid as GR
from vendor.gems57 import holdout as HO
from vendor.gems57 import metric as M
from vendor.gems57 import validate as V57

SNAP_MANIFEST_PATH = RELEASES_DIR / "snap_manifest.json"
SNAP_CARDS_PATH = REPO_ROOT / "ledger" / "snap_mechanism_cards.json"


def fast_symmetric_auc(y_true_bool: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Exact Mann-Whitney ROC AUC using midranks via `searchsorted`."""
    y = np.asarray(y_true_bool, dtype=bool)
    x = np.nan_to_num(np.asarray(scores, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    n1 = int(y.sum())
    n0 = int((~y).sum())
    if n1 == 0 or n0 == 0 or float(np.std(x)) < 1e-12:
        return 0.5, 0.5
    sx = np.sort(x)
    lo = np.searchsorted(sx, x, side="left")
    hi = np.searchsorted(sx, x, side="right")
    ranks = (lo + hi + 1) * 0.5
    auc = float((ranks[y].sum() - n1 * (n1 + 1) / 2.0) / (float(n1) * float(n0)))
    return auc, float(max(auc, 1.0 - auc))


def load_provided_edge_crests(raw_dir: Path, footprint: np.ndarray) -> dict[str, Any]:
    """Load strictly organizer-provided `training_features.tif` channels and verify gravity gradient isotropy."""
    tf_path = raw_dir / "training_features.tif"
    with rasterio.open(tf_path) as ds:
        b02_rtp = ds.read(2).astype(np.float32)         # rtp
        b03_tmi_hg = ds.read(3).astype(np.float32)      # tmi_hg (isotropic |grad_H TMI|)
        b05_grav_slope = ds.read(5).astype(np.float32)  # iso_grav_anom_slope (isotropic |grad_H g|)
        b13_grav = ds.read(13).astype(np.float32)       # iso_grav_anom
        b18_grav_hg = ds.read(18).astype(np.float32)    # iso_grav_anom_hg (signed E-W dg/dx!)
        b19_elev_slope = ds.read(19).astype(np.float32) # det_elev_slope

    valid_base = (
        footprint
        & np.isfinite(b02_rtp) & (b02_rtp > -1e30)
        & np.isfinite(b03_tmi_hg) & (b03_tmi_hg > -1e30)
        & np.isfinite(b05_grav_slope) & (b05_grav_slope > -1e30)
        & np.isfinite(b13_grav) & (b13_grav > -1e30)
        & np.isfinite(b18_grav_hg) & (b18_grav_hg > -1e30)
        & np.isfinite(b19_elev_slope) & (b19_elev_slope > -1e30)
    )

    # Forensic verification: Band 05 vs Band 18 relative to Band 13 (iso_grav_anom)
    grav_mag, v_grav_num = isotropic_horizontal_gradient(b13_grav, valid_base)
    p13 = np.pad(np.where(valid_base, b13_grav, 0.0), 1, mode="edge")
    gx13 = 0.5 * (p13[1:-1, 2:] - p13[1:-1, :-2])
    gy13 = 0.5 * (p13[2:, 1:-1] - p13[:-2, 1:-1])
    corr_b05_mag = float(np.corrcoef(b05_grav_slope[v_grav_num], grav_mag[v_grav_num])[0, 1])
    corr_b18_mag = float(np.corrcoef(b18_grav_hg[v_grav_num], grav_mag[v_grav_num])[0, 1])
    corr_b18_gx = float(np.corrcoef(b18_grav_hg[v_grav_num], gx13[v_grav_num])[0, 1])
    corr_b18_gy = float(np.corrcoef(b18_grav_hg[v_grav_num], gy13[v_grav_num])[0, 1])

    # 1. RTP horizontal gradient magnitude from provided Band 02 (`rtp`) + Hessian 1-D crest
    rtp_hg, v_rtp = isotropic_horizontal_gradient(b02_rtp, valid_base)
    q_rtp_crest, v_rtp_crest = hessian_crest_quantile(rtp_hg, v_rtp)

    # 2. Provided TMI horizontal gradient (`Band 03 tmi_hg`) Hessian 1-D crest
    q_tmi_crest, v_tmi_crest = hessian_crest_quantile(b03_tmi_hg, valid_base)

    # 3. Provided isotropic gravity gradient (`Band 05 iso_grav_anom_slope`) Hessian 1-D crest
    q_grav_crest, v_grav_crest = hessian_crest_quantile(b05_grav_slope, valid_base)

    # 4. Provided detrended-elevation slope (`Band 19 det_elev_slope`) Hessian 1-D scarp crest
    q_scarp_crest, v_scarp_crest = hessian_crest_quantile(b19_elev_slope, valid_base)

    valid_all_crests = v_rtp_crest & v_tmi_crest & v_grav_crest & v_scarp_crest

    return {
        "valid_base": valid_base,
        "valid_crest": valid_all_crests,
        "score_rtp2": np.where(valid_all_crests, np.maximum(q_rtp_crest, q_grav_crest), -np.inf).astype(np.float32),
        "score_tg2": np.where(valid_all_crests, np.maximum(q_tmi_crest, q_grav_crest), -np.inf).astype(np.float32),
        "score_scarp2": np.where(
            valid_all_crests,
            np.maximum.reduce([q_rtp_crest, q_grav_crest, q_scarp_crest]),
            -np.inf,
        ).astype(np.float32),
        "gravity_band_audit": {
            "band_05_iso_grav_anom_slope_corr_with_isotropic_grad_mag": round(corr_b05__ := corr_b05_mag, 6),
            "band_18_iso_grav_anom_hg_corr_with_isotropic_grad_mag": round(corr_b18_mag, 6),
            "band_18_iso_grav_anom_hg_corr_with_east_west_dg_dx": round(corr_b18_gx, 6),
            "band_18_iso_grav_anom_hg_corr_with_north_south_dg_dy": round(corr_b18_gy, 6),
            "band_18_min": round(float(b18_grav_hg[valid_base].min()), 4),
            "band_18_max": round(float(b18_grav_hg[valid_base].max()), 4),
            "band_05_min": round(float(b05_grav_slope[valid_base].min()), 6),
            "band_05_max": round(float(b05_grav_slope[valid_base].max()), 6),
            "valid_crest_pixels": int(valid_all_crests.sum()),
        },
        "external_lidar_used": False,
        "provided_bands_used": [
            "Band 02 (rtp)",
            "Band 03 (tmi_hg)",
            "Band 05 (iso_grav_anom_slope)",
            "Band 19 (det_elev_slope)",
        ],
    }


def run_report_only_snap_diagnostics(
    static_masks: dict[str, np.ndarray],
    crest_bundle: dict[str, Any],
    variant_cfgs: list[dict[str, Any]],
    h19_5: np.ndarray,
    d28: np.ndarray,
    nx_norm: np.ndarray,
    ny_norm: np.ndarray,
    coherence: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
) -> dict[str, Any]:
    """Run Section 6 REPORT-ONLY diagnostics (never used as gates; all values labeled PROXY)."""
    t0 = time.time()
    grid = GR.load_grid(RAW_DIR)
    seeds = (20, 30)
    draws_by_seed = {s: HO.buffered_component_draw(grid, seed=s)[0] for s in seeds}

    # 1. Fold-proper hide-and-recover PROXY (`d_vis > 2.0` computed strictly on visible 80% catalogue per seed)
    fp_terms: dict[str, np.ndarray] = {}
    fold_arms: list[tuple[str, dict[str, Any] | None]] = [("R0_fp", None)] + [
        (f"SNAP{cfg['value']}_fp", cfg) for cfg in variant_cfgs
    ]
    for arm_name, cfg in fold_arms:
        tot = None
        for s in seeds:
            vis_s = draws_by_seed[s][0]["visible"]
            d_vis = distance_transform_edt(~(vis_s & footprint))
            r0_vis = d28 & (d_vis > 2.0) & footprint
            allow_vis = footprint & ~vis_s & (d_vis > 2.0)
            if cfg is None:
                m_s = r0_vis
            else:
                snap_res = snap_dots(
                    r0_vis,
                    crest_bundle[cfg["score_key"]],
                    allow_vis,
                    crest_bundle["valid_crest"],
                    nx_norm,
                    ny_norm,
                    coherence,
                    max_radius_px=DEFAULT_MAX_RADIUS_PX,
                    min_sep_sq=DEFAULT_MIN_SEP_SQ,
                    min_peak_q=cfg["min_peak_q"],
                    min_gain_q=cfg["min_gain_q"],
                    cross_strike_cos=DEFAULT_CROSS_STRIKE_COS,
                    coherence_floor=DEFAULT_COHERENCE_FLOOR,
                )
                m_s = snap_res["dots"]
            pred_s = m_s.astype(np.float32)
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred_s, fold, valid=footprint)
                tot = terms.copy() if tot is None else (tot + terms)
        assert tot is not None
        fp_terms[arm_name] = tot

    fp_summary = EH.pooled_summary(fp_terms, draws=1000, seed=520810, candidate="SNAPrtp2_fp")

    # 2. Single-feature leakage canary across all 19 organizer-provided bands + 3 SNAP crest maps + H19-5
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
        v_fp = arr2d[footprint]
        sym_by_s = {}
        auc_by_s = {}
        for s, (idx_all, y_all) in eval_masks.items():
            vals = v_fp[idx_all].astype(np.float32)
            vals = np.where((~np.isfinite(vals)) | (vals < -1e20), 0.0, vals)
            auc, sym = fast_symmetric_auc(y_all, vals)
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

    for skey in ("score_rtp2", "score_tg2", "score_scarp2"):
        _audit_2d(f"snap_crest_{skey}", crest_bundle[skey])
    _audit_2d("parent_h19_5_binary", h19_5.astype(np.float32))

    canary_channels.sort(key=lambda r: r["max_symmetric_auc"], reverse=True)
    max_sym_auc = max(r["max_symmetric_auc"] for r in canary_channels)
    flagged = [r for r in canary_channels if r["flagged_over_0_90"]]
    if flagged:
        raise RuntimeError(f"STOP: Leakage canary fired (> 0.90 symmetric AUC): {flagged}")

    # 3. Off-catalogue USGS SGMC control PROXY (62,122 bedrock fault pixels at d_cat > 3.0 px)
    with rasterio.open(RAW_DIR / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    sgmc_offcat = sgmc & ~catalogue & (d_cat > 3.0)
    sgmc_scores = {}
    for arm_name, m_static in static_masks.items():
        res = M.dti_binary(m_static, sgmc_offcat, valid=footprint, known=catalogue)
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
        "withheld_positive_pixels": int(fp_summary["scores"]["SNAPrtp2_fp"]["withheld_positive_pixels"]),
        "fold_proper_hide_and_recover_proxy": {
            k: {
                "evidence_label": "PROXY",
                "dti": round(float(v["dti"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
                "withheld_positive_pixels": int(v["withheld_positive_pixels"]),
            }
            for k, v in fp_summary["scores"].items()
        },
        "fold_proper_paired_vs_SNAPrtp2_fp": {
            k: {
                "evidence_label": "PROXY",
                "delta_snaprtp2_minus_arm": round(float(v["delta"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
            }
            for k, v in fp_summary["paired_differences"].items()
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
    print("[1/6] Verifying all 25 SHA-256 pins in registry/data_manifest.json ...", flush=True)
    manifest_receipt = verify_and_restore_manifest()
    print(
        f"      Verified {manifest_receipt['verified_count']}/{manifest_receipt['verified_count']} files against registry/data_manifest.json.",
        flush=True,
    )

    template_tif = RAW_DIR / "sample_submission.tif"
    catalogue_tif = RAW_DIR / "existing_faults.tif"
    h19_5_tif = RAW_DIR / "scored" / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"
    d28_tif = RAW_DIR / "scored" / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"

    with rasterio.open(template_tif) as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(catalogue_tif) as ds:
        catalogue = (ds.read(1) > 0) & footprint
    with rasterio.open(h19_5_tif) as ds:
        h19_5 = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    with rasterio.open(d28_tif) as ds:
        d28_manifest = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint

    d_cat = distance_transform_edt(~catalogue)
    allowed_r0 = footprint & ~catalogue & (d_cat > 2.0)

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
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    if LEDGER_PATH.is_file():
        with LEDGER_PATH.open("r", encoding="utf-8", newline="") as f:
            existing_rows = list(csv.DictReader(f))
        # Allow idempotent re-run of this script by replacing only our own (h33-h33-2-b2, SNAP, *) rows
        existing_rows = [r for r in existing_rows if not (r.get("parent") == PARENT_ID and r.get("axis") == "SNAP")]

    seen_shas: set[str] = set()
    for r in existing_rows:
        if r.get("sha256"):
            seen_shas.add(r["sha256"])
        if r.get("sha256_zeros"):
            seen_shas.add(r["sha256_zeros"])
    seen_pairs: set[tuple[str, str, str]] = {
        (r.get("parent", ""), r.get("axis", ""), r.get("value", "")) for r in existing_rows
    }

    registry_shas: set[str] = set()
    if CANONICAL_INDEX_PATH.is_file():
        reg = json.loads(CANONICAL_INDEX_PATH.read_text(encoding="utf-8"))
        registry_shas = {r["sha256"] for r in reg.get("rasters", [])}
    inventory_shas: set[str] = set()
    if INVENTORY_PATH.is_file():
        inv = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        inventory_shas = {r["sha256"] for r in inv.get("rasters", [])}

    print("[4/6] Computing provided potential-field & scarp 1-D Hessian crests and building 3 AXIS=SNAP variants ...", flush=True)
    crest_bundle = load_provided_edge_crests(RAW_DIR, footprint)
    nx_norm, ny_norm, coherence = compute_cross_strike_frame(h19_5)

    variant_specs = [
        {
            "axis": "SNAP",
            "value": "rtp2",
            "score_key": "score_rtp2",
            "min_peak_q": 0.75,
            "min_gain_q": 0.10,
            "predicted_change": "+0.004 to +0.011 [MODEL]",
            "note_prefix": "h33-h33-2-b2; SNAP<=2px x-strike RTP+grav crest",
            "mechanism_card": {
                "hypothesis": (
                    "GeoDAWN Area 2's 400 m flight-line gridding, unweighted BFS dot_thin(2.8) placement along the "
                    "northern/western edge of 2-4 px wide H19-5 ribbons, and Nevada's ~64 deg geomagnetic inclination "
                    "leave R0 dots offset by 100-200 m from steep subsurface fault contacts. Snapping <=2 px cross-strike "
                    "onto Reduced-to-Pole (Band 02) and isotropic gravity (Band 05) 1-D Hessian crests centers the 300 m "
                    "DTI kernel directly over concealed basement/volcanic fault steps."
                ),
                "mechanism": (
                    "Compute 1-D Blakely-Simpson Hessian ridge crests -lambda_min(nabla^2 log(1 + G)) on |grad_H(RTP)| "
                    "(provided Band 02, removing dipolar inclination skew) and isotropic |grad_H g| (provided Band 05 "
                    "iso_grav_anom_slope; byte audit proves Band 18 is directional dg/dx only). Move each R0 dot <=2.0 px "
                    "cross-strike (|u . n_perp| >= 0.80) iff a crest in the top quartile (q >= 0.75) improves local crest "
                    "quantile by >= +0.10 while holding count (37,654), R0 exclusions (d_cat > 2 px), and sqrt(8) spacing fixed."
                ),
                "non_fault_mimic": (
                    "Unfaulted Tertiary basalt/rhyolite flow edges, shallow dike swarms, or Miocene caldera ring margins "
                    "produce sharp RTP horizontal-gradient crests within 200 m of smoothed H19-5 corridors without "
                    "Quaternary or geothermal slip."
                ),
                "predicted_live_change": "+0.004 to +0.011 DTI [MODEL] relative to R0 (treat |delta| < 0.01 on public chunks as no evidence).",
                "falsifier": (
                    "Live RECEIPT drops >= 0.01 below R0, showing R0's smoothed multi-channel H19-5 centerline sits closer "
                    "to mapped fault traces than subsurface RTP/gravity contacts (e.g., dipping hanging-wall offset)."
                ),
            },
        },
        {
            "axis": "SNAP",
            "value": "tg2",
            "score_key": "score_tg2",
            "min_peak_q": 0.75,
            "min_gain_q": 0.10,
            "predicted_change": "+0.002 to +0.008 [MODEL]",
            "note_prefix": "h33-h33-2-b2; SNAP<=2px x-strike tmi_hg+grav crest",
            "mechanism_card": {
                "hypothesis": (
                    "Direct provided-gradient control against SNAPrtp2: tests whether snapping <=2 px cross-strike onto "
                    "the organizer-provided raw TMI horizontal gradient (Band 03 tmi_hg) and isotropic gravity slope "
                    "(Band 05 iso_grav_anom_slope) 1-D crests captures the airborne gridding correction without RTP "
                    "phase transformation, or loses kernel credit from ~100-250 m southward dipolar TMI shift."
                ),
                "mechanism": (
                    "Identical operator, <=2.0 px cross-strike window, d_cat > 2 px exclusions, sqrt(8) spacing, and "
                    "(q >= 0.75, delta_q >= +0.10) prominence filter as SNAPrtp2, substituting provided Band 03 (tmi_hg) "
                    "for |grad_H(Band 02 rtp)| alongside Band 05 (iso_grav_anom_slope); zero external lidar rasters used."
                ),
                "non_fault_mimic": (
                    "Remanently magnetized Neogene volcanics and oblique geomagnetic inclination shift tmi_hg peaks "
                    "100-300 m south-southwest of steep contacts, plus E-W 400 m flight-line leveling corrugation."
                ),
                "predicted_live_change": "+0.002 to +0.008 DTI [MODEL] relative to R0 (expected +0.000 to -0.004 below SNAPrtp2).",
                "falsifier": (
                    "SNAPtg2 beats SNAPrtp2 by >= +0.01 live, indicating remanent magnetization invalidates constant-"
                    "inclination RTP centering across the test chunks."
                ),
            },
        },
        {
            "axis": "SNAP",
            "value": "scarp2",
            "score_key": "score_scarp2",
            "min_peak_q": 0.80,
            "min_gain_q": 0.10,
            "predicted_change": "+0.005 to +0.012 [MODEL]",
            "note_prefix": "h33-h33-2-b2; SNAP<=2px x-strike RTP+grav+scarp crest",
            "mechanism_card": {
                "hypothesis": (
                    "Range-front and piedmont normal faults dip 45-60 deg basinward, shifting subsurface magnetic/gravity "
                    "gradients into the hanging wall while the mapped surface fault trace sits on the 100 m topographic "
                    "break-in-slope (Band 19 det_elev_slope); conversely, concealed basin faults lack relief and express "
                    "only in RTP/gravity crests. Combining both aligns surface scarps and blind basin structures."
                ),
                "mechanism": (
                    "Compute max(q_rtp_crest, q_grav_crest, q_scarp_crest) strictly from organizer-provided Bands 02, 05, "
                    "and 19 (det_elev_slope; no external lidar rasters) and snap each R0 dot <=2.0 px cross-strike when "
                    "q >= 0.80 and delta_q >= +0.10, preserving exact n_dots = 37,654, d_cat > 2 px, and sqrt(8) spacing."
                ),
                "non_fault_mimic": (
                    "Pleistocene Lake Lahontan wave-cut shorelines, incised fan-head trench walls, and erosional "
                    "range-front facet spurs retreated 100-200 m footwall-ward from the active piedmont fault trace."
                ),
                "predicted_live_change": "+0.005 to +0.012 DTI [MODEL] relative to R0 (treat |delta| < 0.01 on public chunks as no evidence).",
                "falsifier": (
                    "Live RECEIPT underperforms SNAPrtp2 by >= 0.01, proving footwall erosional scarp retreat and "
                    "pluvial shoreline terraces pull dots away from true fault traces."
                ),
            },
        },
    ]

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    for old_tif in RELEASES_DIR.glob(f"{PARENT_ID}-SNAP*.tif"):
        old_tif.unlink()

    built_variants: list[dict[str, Any]] = []
    static_masks: dict[str, np.ndarray] = {"R0": r0_mask}
    new_ledger_rows: list[dict[str, str]] = []
    snap_cards_dict: dict[str, Any] = {}
    head_sha = git_head_sha()

    for spec in variant_specs:
        pair_key = (PARENT_ID, spec["axis"], spec["value"])
        if pair_key in seen_pairs:
            raise RuntimeError(f"Duplicate (parent, axis, value) in ledger: {pair_key}")

        snap_res = snap_dots(
            r0_mask,
            crest_bundle[spec["score_key"]],
            allowed_r0,
            crest_bundle["valid_crest"],
            nx_norm,
            ny_norm,
            coherence,
            max_radius_px=DEFAULT_MAX_RADIUS_PX,
            min_sep_sq=DEFAULT_MIN_SEP_SQ,
            min_peak_q=spec["min_peak_q"],
            min_gain_q=spec["min_gain_q"],
            cross_strike_cos=DEFAULT_CROSS_STRIKE_COS,
            coherence_floor=DEFAULT_COHERENCE_FLOOR,
        )
        v_mask = snap_res["dots"]
        diff_stats = compute_parent_diff_stats(v_mask, r0_mask, d_cat, footprint)

        # Verify exact R0 exclusion & spacing invariants
        assert diff_stats["n_dots"] == R0_TARGET_DOTS
        assert int((v_mask & ~allowed_r0).sum()) == 0
        assert diff_stats["d_catalogue_px"]["min"] > 2.0
        assert diff_stats["nearest_neighbor_px"]["min"] >= np.sqrt(DEFAULT_MIN_SEP_SQ) - 1e-4

        form_note = (
            f"{spec['note_prefix']} "
            f"(n={diff_stats['n_dots']}, {diff_stats['pct_changed']:.2f}% chg, "
            f"mean d={snap_res['mean_displacement_all_px']:.2f}px); "
            f"pred {spec['predicted_change']}"
        )
        if len(form_note) > 140:
            raise ValueError(f"Form note exceeds 140 chars ({len(form_note)}): {form_note}")

        tmp_nan = RELEASES_DIR / f"_tmp_{spec['axis']}{spec['value']}.tif"
        tmp_zeros = RELEASES_DIR / f"_tmp_{spec['axis']}{spec['value']}-zeros.tif"
        sha_nan_tmp, sha_zeros_tmp = write_geotiff_pair_exact_profile(
            v_mask, footprint, catalogue, template_tif, tmp_nan, tmp_zeros
        )
        sha8 = sha_nan_tmp[:8]
        var_id = f"{PARENT_ID}-{spec['axis']}{spec['value']}-{SESSION_DATE}-{sha8}"
        final_nan = RELEASES_DIR / f"{var_id}.tif"
        final_zeros = RELEASES_DIR / f"{var_id}-zeros.tif"
        tmp_nan.rename(final_nan)
        tmp_zeros.rename(final_zeros)

        # MUST-PASS Gate 1: Re-read both written files from disk and verify SHA-256 + pixel identity
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

        # MUST-PASS Gate 2: Official spec validator on NaN-outside & gems57 validator on zeros-outside
        val_nan = validate_submission(final_nan, template_tif)
        if not val_nan["ready"] or val_nan["errors"]:
            raise RuntimeError(f"validate_submission failed on {final_nan}: {val_nan['errors']}")
        val_zeros = V57.validate(final_zeros, footprint=footprint, catalogue=catalogue)
        if not val_zeros["all_checks_passed"]:
            raise RuntimeError(f"gems57.validate failed on {final_zeros}: {val_zeros['checks']}")

        # MUST-PASS Gate 3: Exact SHA-256 deduplication against ledger + 202 canonical + 999 inventory
        for s_chk in (sha_nan, sha_zeros):
            if s_chk in seen_shas:
                raise RuntimeError(f"SHA-256 {s_chk} already exists in ledger/submissions.csv!")
            if s_chk in registry_shas or s_chk in inventory_shas:
                raise RuntimeError(f"SHA-256 {s_chk} collides with historical registry raster!")

        seen_shas.update({sha_nan, sha_zeros})
        seen_pairs.add(pair_key)
        key_label = f"{spec['axis']}{spec['value']}"
        static_masks[key_label] = v_mask

        disp_summary = {
            "max_window_radius_px": DEFAULT_MAX_RADIUS_PX,
            "min_sep_sq_px2": DEFAULT_MIN_SEP_SQ,
            "min_peak_quantile": spec["min_peak_q"],
            "min_gain_quantile": spec["min_gain_q"],
            "cross_strike_cos_threshold": DEFAULT_CROSS_STRIKE_COS,
            "n_moved_bijective": snap_res["n_moved_bijective"],
            "pct_moved_bijective": snap_res["pct_moved_bijective"],
            "mean_displacement_all_px": snap_res["mean_displacement_all_px"],
            "mean_displacement_all_m": snap_res["mean_displacement_all_m"],
            "mean_displacement_moved_px": snap_res["mean_displacement_moved_px"],
            "mean_displacement_moved_m": snap_res["mean_displacement_moved_m"],
            "median_displacement_moved_px": snap_res["median_displacement_moved_px"],
            "p95_displacement_all_px": snap_res["p95_displacement_all_px"],
            "max_displacement_px": snap_res["max_displacement_px"],
            "step_counts": snap_res["step_counts"],
        }

        content_digest8 = hashlib.sha256(np.packbits(v_mask)).hexdigest()[:8]
        rec = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": spec["axis"],
            "value": spec["value"],
            "n_dots": diff_stats["n_dots"],
            "pct_changed": round(diff_stats["pct_changed"], 2),
            "sha256": sha_nan,
            "sha8": sha8,
            "zeros_sha256": sha_zeros,
            "zeros_sha8": sha_zeros[:8],
            "content_digest8": content_digest8,
            "primary_file": f"releases/{final_nan.name}",
            "primary_bytes": final_nan.stat().st_size,
            "zeros_fallback_file": f"releases/{final_zeros.name}",
            "zeros_bytes": final_zeros.stat().st_size,
            "status": "BUILT",
            "predicted_change": spec["predicted_change"],
            "form_note": form_note,
            "form_note_length": len(form_note),
            "displacement_stats": disp_summary,
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
        snap_cards_dict[var_id] = {
            **disp_summary,
            "n_dots": diff_stats["n_dots"],
            "pct_changed": diff_stats["pct_changed"],
            **spec["mechanism_card"],
        }
        new_ledger_rows.append(
            {
                "id": var_id,
                "parent": PARENT_ID,
                "axis": spec["axis"],
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
            f"      Built {var_id}: n={diff_stats['n_dots']}, %changed={diff_stats['pct_changed']:.2f}%, "
            f"mean_disp={snap_res['mean_displacement_all_px']:.4f} px (moved={snap_res['mean_displacement_moved_px']:.4f} px), "
            f"min_dcat={diff_stats['d_catalogue_px']['min']} px, min_nn={diff_stats['nearest_neighbor_px']['min']} px",
            flush=True,
        )

    print("[5/6] Writing ledger/submissions.csv and ledger/snap_mechanism_cards.json ...", flush=True)
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in existing_rows + new_ledger_rows:
            writer.writerow({k: r.get(k, "") for k in LEDGER_COLUMNS})
    SNAP_CARDS_PATH.write_text(json.dumps(snap_cards_dict, indent=2) + "\n", encoding="utf-8")

    diagnostics = None
    if not args.skip_diagnostics:
        print("[6/6] Running REPORT-ONLY diagnostics (hide-and-recover PROXY, leakage canary, SGMC control) ...", flush=True)
        diagnostics = run_report_only_snap_diagnostics(
            static_masks,
            crest_bundle,
            variant_specs,
            h19_5,
            d28,
            nx_norm,
            ny_norm,
            coherence,
            footprint,
            catalogue,
            d_cat,
        )
        print(
            f"      Diagnostics done in {diagnostics['elapsed_seconds']}s: "
            f"canary max_sym_auc={diagnostics['leakage_canary']['max_symmetric_auc_observed']} (<=0.90), "
            f"SGMC SNAPrtp2={diagnostics['sgmc_offcatalogue_control_proxy']['SNAPrtp2']['dti']:.6f} "
            f"(vs R0={diagnostics['sgmc_offcatalogue_control_proxy']['R0']['dti']:.6f}), "
            f"fold-proper SNAPrtp2_fp={diagnostics['fold_proper_hide_and_recover_proxy']['SNAPrtp2_fp']['dti']:.6f}",
            flush=True,
        )

    snap_manifest = {
        "schema_version": 2,
        "generated_date_utc": SESSION_DATE,
        "git_head_at_build": head_sha,
        "fixed_seed": FIXED_SEED,
        "external_lidar_used": crest_bundle["external_lidar_used"],
        "provided_bands_used": crest_bundle["provided_bands_used"],
        "gravity_band_audit": crest_bundle["gravity_band_audit"],
        "manifest_verification": {
            "manifest_path": "registry/data_manifest.json",
            "verified_files_count": manifest_receipt["verified_count"],
        },
        "parent_r0_rebuild_receipt": r0_receipt,
        "axis": "SNAP",
        "variants": built_variants,
        "report_only_diagnostics": diagnostics,
        "total_elapsed_seconds": round(time.time() - t_start, 2),
    }
    SNAP_MANIFEST_PATH.write_text(json.dumps(snap_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Done in {snap_manifest['total_elapsed_seconds']}s. Wrote {SNAP_MANIFEST_PATH.name} and ledger/submissions.csv.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
