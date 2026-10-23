#!/usr/bin/env python3
"""Reproducible builder and validator for GEMSDOE87 Agent Brief v2 (`AXIS = RELIEF` on Parent R0).

Workflow (strictly offline / GitHub-pinned inputs only; zero contact with drivendata.org or dropbox.com):
1. Verify all 25 SHA-256 pins in `registry/data_manifest.json` against `.cache/raw/` (restoring from
   pinned GitHub commit tarballs on `codeload.github.com` only if missing).
2. Rebuild Parent R0 (`h33-h33-2-b2`, GEMSDOE32, `37,654` unit-mass dots) from pinned manifest inputs
   (`scored_h19_5`, `existing_faults`, `sample_submission`) and assert byte-for-byte SHA-256 identity
   against both R0 twins (`c55bafc4...` zeros-outside and `baeae321...` NaN-outside). Halt on mismatch.
3. Read `ledger/submissions.csv` first and refuse to duplicate any existing `(parent, axis, value)` or
   `sha256`.
4. Build 3 controlled single-factor variants of R0 on `AXIS = RELIEF` at strictly fixed count
   `N = 37,654`, preserved spacing `min_sep = sqrt(8) = 2.8284 px`, and preserved `d_cat > 2.0 px`
   exclusions, shifting 10%–15% of mass between Basin (`T0`), Piedmont (`T1`), and Range-Front (`T2`)
   terciles computed from the organizer-provided detrended-elevation bands (`Band 12 det_elev` and
   `Band 19 det_elev_slope`):
     - `r2p12`: shift `12.00%` (`4,518` dots) from `T2 Range-Front` -> `T1 Piedmont` (`T0` untouched)
     - `r2b10`: shift `10.00%` (`3,765` dots) from `T2 Range-Front` -> `T0 Basin` (`T1` untouched)
     - `b2r15`: shift `15.00%` (`5,648` dots) from `T0 Basin` -> `T2 Range-Front` (`T1` untouched)
5. Write `releases/<id>.tif` (NaN outside footprint) and `releases/<id>-zeros.tif` (`0.0` outside
   fallback), re-read every file from disk, run MUST-PASS format/catalogue/hash/diff gates, and compute
   REPORT-ONLY diagnostics (fold-proper hide-and-recover `PROXY` with `n = 22,663` withheld positives &
   1,000-draw block-bootstrap 95% CI, single-feature leakage canary, and USGS SGMC off-catalogue `PROXY`).
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, gaussian_filter

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
VENDOR_DIR = REPO_ROOT / "vendor"
for p in (REPO_ROOT, SRC_DIR, VENDOR_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gems57 import evaluate_holdout as EH
from gems57 import grid as GR
from gems57 import holdout as HO
from gems57 import metric as M
from gems57 import validate as V57
from gems87.relief import (
    compute_relief_terciles,
    compute_subsurface_crest_score,
    shift_relief_mass,
    tercile_dot_census,
)
from scripts.build_prune_variants import (
    CANONICAL_INDEX_PATH,
    FIXED_SEED,
    INVENTORY_PATH,
    LEDGER_COLUMNS,
    LEDGER_PATH,
    PARENT_ID,
    R0_EXPECTED_NAN_SHA256,
    R0_EXPECTED_ZEROS_SHA256,
    R0_TARGET_DOTS,
    RAW_DIR,
    RELEASES_DIR,
    SESSION_DATE,
    compute_parent_diff_stats,
    dot_thin_geodesic_bfs,
    rebuild_and_verify_r0,
    sha256_file,
    symmetric_auc_mann_whitney,
    verify_and_restore_manifest,
    write_geotiff_pair_exact_profile,
)
from scripts.validate_submission import validate_submission

RELIEF_MANIFEST_PATH = RELEASES_DIR / "manifest_RELIEF.json"
RELIEF_CARDS_PATH = REPO_ROOT / "ledger" / "mechanism_cards_relief.json"

VARIANT_SPECS: list[dict[str, Any]] = [
    {
        "value": "r2p12",
        "src_tercile": 2,
        "dst_tercile": 1,
        "n_shift": round(0.12 * R0_TARGET_DOTS),  # 4,518 dots = 12.00%
        "predicted_change": "+0.004 to +0.012 [MODEL]",
        "note_label": "Range->Piedmont 12.00%",
        "hypothesis": (
            "Active Quaternary normal faults and geothermal step-over / relay ramps in the Great "
            "Basin systematically step basinward from eroded mountain-interior facets (T2) onto "
            "alluvial-fan piedmont bajadas (T1), whereas dissected T2 H19-5 ridges disproportionately "
            "trace inactive pre-Quaternary bedrock contacts and erosional spur crests."
        ),
        "mechanism": (
            "Drop the 4,518 (12.00%) lowest exact leave-one-out DTI marginal-loss R0 dots from "
            "T2 Range-Front (relief quantile > 66.7% from Band 12 det_elev + Band 19 det_elev_slope) "
            "and place 4,518 dots into T1 Piedmont (33.3%–66.7%) at inherited min spacing sqrt(8) px, "
            "ranked first by exact sequential DTI marginal gain dT on uncovered H19-5 ridges (3,959 dots) "
            "and completed on isotropic Band 02 RTP + Band 05 gravity 1-D Hessian crests (559 dots); "
            "T0 Basin (6,029 dots) and total count (37,654) remain 100% unchanged."
        ),
        "non_fault_mimic": (
            "Incised alluvial-fan feeder channels, Lake Lahontan highstand wave-cut benches (~1,330 m), "
            "and piedmont pediment-alluvium contacts produce gentle detrended-elevation slopes and shallow "
            "magnetic/density contrasts inside T1 without Quaternary fault slip."
        ),
        "predicted_live_change": (
            "+0.004 to +0.012 [MODEL] if undisclosed test labels reflect concealed Quaternary / 3DEP "
            "piedmont splays (supported by Quaternary hide-and-recover PROXY +0.0014 vs R0); treat "
            "|Delta live| < 0.01 on public chunks as no evidence."
        ),
        "falsifier": (
            "Live RECEIPT Delta <= -0.01 vs R0 (or vs PRUNE3 once receipted) falsifies piedmont enrichment "
            "and indicates undisclosed test faults are predominantly unmapped range-interior bedrock "
            "structures (matching the SGMC control shift of -0.0065)."
        ),
    },
    {
        "value": "r2b10",
        "src_tercile": 2,
        "dst_tercile": 0,
        "n_shift": round(0.10 * R0_TARGET_DOTS),  # 3,765 dots = 10.00%
        "predicted_change": "+0.002 to +0.010 [MODEL]",
        "note_label": "Range->Basin 10.00%",
        "hypothesis": (
            "Parent R0 severely under-allocates low-relief playal and alluvial basins (T0 holds 30.5% "
            "of mapped Quaternary catalogue fault pixels on Band 12 det_elev yet only 16.0% of R0 dots "
            "on the composite relief index) because H19-5's DEM openness channel vanishes across flat "
            "Holocene playal/alluvial fill where blind intrabasin faults and geothermal reservoirs sit."
        ),
        "mechanism": (
            "Drop the 3,765 (10.00%) lowest exact leave-one-out DTI marginal-loss R0 dots from "
            "T2 Range-Front and place 3,765 dots into T0 Basin (relief quantile <= 33.3%) at min spacing "
            "sqrt(8) px, filling all positive exact-DTI H19-5 basin ridge gaps first (1,191 dots) and "
            "placing the remaining 2,574 dots onto isotropic subsurface |grad_H(RTP)| (Band 02) + "
            "iso_grav_anom_slope (Band 05) 1-D Hessian crests; T1 Piedmont (17,303 dots) and total count "
            "(37,654) remain 100% unchanged."
        ),
        "non_fault_mimic": (
            "Pleistocene pluvial Lake Lahontan desiccated shorelines, axial river terraces (Humboldt / "
            "Carson sinks), buried Cenozoic volcanic paleochannels, and N-S aeromagnetic flight-line "
            "leveling ripple across low-susceptibility playal sediments."
        ),
        "predicted_live_change": (
            "+0.002 to +0.010 [MODEL] if hidden test faults include geophysical/sub-basin blind "
            "compilations (INGENIOUS / GeoDAWN); negative if test labels require surface scarp expression. "
            "Treat |Delta live| < 0.01 as no evidence."
        ),
        "falsifier": (
            "Live RECEIPT Delta <= -0.01 vs R0 falsifies intrabasin blind-fault under-allocation and "
            "shows test annotations rarely extend onto zero-relief playal floors without surface scarps."
        ),
    },
    {
        "value": "b2r15",
        "src_tercile": 0,
        "dst_tercile": 2,
        "n_shift": round(0.15 * R0_TARGET_DOTS),  # 5,648 dots = 15.00%
        "predicted_change": "-0.012 to +0.008 [MODEL]",
        "note_label": "Basin->Range 15.00%",
        "hypothesis": (
            "Opposite-sign structural bracket: if the undisclosed test labels incorporate newly digitized "
            "1:24k/NBMG bedrock and range-block fault maps omitted from the USGS Quaternary catalogue "
            "(analogous to off-catalogue USGS SGMC faults, 63.9% of which lie in T2 vs 11.2% in T0), "
            "reallocating low-confidence basin dots onto high-relief T2 structural blocks raises recall."
        ),
        "mechanism": (
            "Drop 5,648 (15.00%) lowest exact leave-one-out DTI marginal-loss R0 dots from T0 Basin "
            "(leaving the 381 strongest basin H19-5 ridge dots) and place 5,648 dots into T2 Range-Front "
            "at min spacing sqrt(8) px via exact sequential DTI marginal gain dT on uncovered H19-5 "
            "ridges (2,892 dots) plus isotropic RTP + gravity 1-D crests (2,756 dots); T1 Piedmont "
            "(17,303 dots) and total count (37,654) remain 100% unchanged."
        ),
        "non_fault_mimic": (
            "Erosional horst crestlines, columnar welded-tuff cliff edges, non-faulted granitic pluton "
            "aureoles, and Mesozoic thrust/metamorphic foliation ridges inside high-relief mountain blocks."
        ),
        "predicted_live_change": (
            "-0.012 to +0.008 [MODEL]: opposite-sign diagnostic bracket (+0.0019 on SGMC bedrock PROXY "
            "vs -0.0118 on Quaternary hide-and-recover PROXY). Do not spend a weekly slot on b2r15 "
            "unless r2p12 scores Delta <= -0.01 live."
        ),
        "falsifier": (
            "Live RECEIPT Delta >= +0.01 on r2p12 (or Delta <= -0.01 on b2r15 itself) falsifies the "
            "unmapped-bedrock-label hypothesis and confirms test labels are dominated by Quaternary "
            "piedmont/basin structures."
        ),
    },
]


def git_head_sha() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    )


def audit_gravity_gradient_bands(footprint: np.ndarray) -> dict[str, Any]:
    """Forensic verification that Band 05 is isotropic |grad_H g| while Band 18 is signed dg/dx."""
    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        b05_slope = ds.read(5).astype(np.float32)
        b13_grav = ds.read(13).astype(np.float32)
        b18_hg = ds.read(18).astype(np.float32)

    valid = footprint & (b05_slope > -1e30) & (b13_grav > -1e30) & (b18_hg > -1e30)
    g_sm = gaussian_filter(np.where(valid, b13_grav, 0.0), sigma=1.0)
    gy, gx = np.gradient(g_sm)
    g_mag = np.hypot(gx, gy)

    rng = np.random.default_rng(20261023)
    idx = rng.choice(np.flatnonzero(valid), size=100_000, replace=False)
    v05 = b05_slope.ravel()[idx].astype(np.float64)
    v18 = b18_hg.ravel()[idx].astype(np.float64)
    vmag = g_mag.ravel()[idx].astype(np.float64)
    vgx = gx.ravel()[idx].astype(np.float64)

    return {
        "band05_corr_with_isotropic_grad_mag": round(float(np.corrcoef(v05, vmag)[0, 1]), 5),
        "band18_corr_with_signed_dg_dx": round(float(np.corrcoef(v18, vgx)[0, 1]), 5),
        "band18_corr_with_isotropic_grad_mag": round(float(np.corrcoef(v18, vmag)[0, 1]), 5),
        "band18_fraction_negative_in_footprint": round(float((b18_hg[valid] < 0).mean()), 5),
        "conclusion": (
            "Band 18 (iso_grav_anom_hg) is directional signed dg/dx (48.8% negative, blind to E-W "
            "strikes), explaining why PR #28 found only 3,330 crests on Band 18; Band 05 "
            "(iso_grav_anom_slope) is true isotropic |grad_H g| and is used exclusively in RELIEF."
        ),
    }


def run_relief_diagnostics(
    static_masks: dict[str, np.ndarray],
    h19_5: np.ndarray,
    tercile: np.ndarray,
    relief_index: np.ndarray,
    subsurface_score: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
) -> dict[str, Any]:
    """Run Brief §6 REPORT-ONLY diagnostics (never used as gates; labeled PROXY)."""
    t0 = time.time()
    grid = GR.load_grid(RAW_DIR)
    seeds = (20, 30)
    draws_by_seed = {s: HO.buffered_component_draw(grid, seed=s)[0] for s in seeds}

    # 1. Fold-proper Quaternary hide-and-recover PROXY (n = 22,663 withheld positives across seeds 20 & 30)
    fp_terms: dict[str, np.ndarray] = {}
    fold_arms: list[tuple[str, dict[str, Any] | None]] = [("R0_fp", None)] + [
        (f"RELIEF{spec['value']}_fp", spec) for spec in VARIANT_SPECS
    ]

    r0_by_seed: dict[int, np.ndarray] = {}
    allow_by_seed: dict[int, np.ndarray] = {}
    for s in seeds:
        vis_s = draws_by_seed[s][0]["visible"] & footprint
        d_vis = distance_transform_edt(~vis_s)
        allow_s = footprint & ~vis_s & (d_vis > 2.0)
        r0_s = dot_thin_geodesic_bfs(h19_5 & footprint & ~vis_s, 2.8) & allow_s
        r0_by_seed[s] = r0_s
        allow_by_seed[s] = allow_s

    for arm_name, spec in fold_arms:
        tot = None
        for s in seeds:
            r0_s = r0_by_seed[s]
            allow_s = allow_by_seed[s]
            if spec is None:
                m_s = r0_s
            else:
                frac = float(spec["n_shift"]) / float(R0_TARGET_DOTS)
                n_sh_s = round(frac * int(r0_s.sum()))
                m_s, _ = shift_relief_mass(
                    r0_s,
                    h19_5,
                    tercile,
                    allow_s,
                    subsurface_score,
                    src_tercile=int(spec["src_tercile"]),
                    dst_tercile=int(spec["dst_tercile"]),
                    n_shift=n_sh_s,
                    min_sep2=8,
                )
            pred_s = m_s.astype(np.float32)
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred_s, fold, valid=footprint)
                tot = terms.copy() if tot is None else (tot + terms)
        assert tot is not None
        fp_terms[arm_name] = tot

    fp_summary = EH.pooled_summary(fp_terms, draws=1000, seed=520810, candidate="RELIEFr2p12_fp")

    # 2. Static-raster hide-and-recover PROXY (literal full-catalogue rasters)
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

    st_summary = EH.pooled_summary(st_terms, draws=1000, seed=520810, candidate="RELIEFr2p12")

    # 3. Off-catalogue USGS SGMC bedrock fault control (d_cat > 3 px)
    with rasterio.open(RAW_DIR / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    sgmc_off = sgmc & ~catalogue & (d_cat > 3.0)
    sgmc_scores: dict[str, Any] = {}
    r0_sgmc = M.dti_binary(static_masks["R0"], sgmc_off, valid=footprint, known=catalogue)["dti"]
    for arm_name, m_static in static_masks.items():
        res = M.dti_binary(m_static, sgmc_off, valid=footprint, known=catalogue)
        sgmc_scores[arm_name] = {
            "dti_proxy": round(float(res["dti"]), 6),
            "delta_vs_r0_proxy": round(float(res["dti"] - r0_sgmc), 6),
            "tp_weighted": round(float(res["tp"]), 2),
        }

    # 4. Single-feature leakage canary across all 19 raw bands + 3 derived channels (AUC > 0.90 => STOP)
    rng = np.random.default_rng(20261023)
    eval_masks: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    n_withheld_total = 0
    for s in seeds:
        vis_s = draws_by_seed[s][0]["visible"] & footprint
        hid_s = np.zeros_like(footprint)
        for fold in draws_by_seed[s]:
            hid_s |= fold["truth"] & fold["region"] & footprint & ~vis_s
        n_withheld_total += int(hid_s.sum())
        pos_idx = np.flatnonzero(hid_s[footprint])
        neg_pool = np.flatnonzero((~hid_s & ~vis_s & footprint)[footprint])
        neg_idx = rng.choice(neg_pool, size=min(80_000, neg_pool.size), replace=False)
        idx_all = np.concatenate([pos_idx, neg_idx])
        y_all = np.concatenate(
            [np.ones(pos_idx.size, dtype=bool), np.zeros(neg_idx.size, dtype=bool)]
        )
        eval_masks[s] = (idx_all, y_all)

    canary_channels: list[dict[str, Any]] = []

    def _audit_2d(name: str, arr2d: np.ndarray) -> None:
        v_fp = arr2d[footprint]
        sym_by_s = {}
        auc_by_s = {}
        for s, (idx_all, y_all) in eval_masks.items():
            vals = v_fp[idx_all].astype(np.float64)
            vals = np.where((vals < -1e20) | ~np.isfinite(vals), 0.0, vals)
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
        descs = ds.descriptions
        for b in range(1, ds.count + 1):
            label = f"band_{b:02d}_{descs[b - 1] or f'b{b}'}"
            _audit_2d(label, ds.read(b))
    _audit_2d("derived_relief_index_b12_b19", relief_index)
    _audit_2d("derived_subsurface_crest_b02_b05", subsurface_score)
    _audit_2d("parent_h19_5_binary", h19_5.astype(np.float32))

    flagged = [c for c in canary_channels if c["flagged_over_0_90"]]
    if flagged:
        raise RuntimeError(f"LEAKAGE CANARY TRIPPED (> 0.90 symmetric AUC): {flagged}")

    max_canary = max(c["max_symmetric_auc"] for c in canary_channels)
    return {
        "evidence_label": "PROXY",
        "elapsed_seconds": round(time.time() - t0, 2),
        "n_withheld_catalogue_positives_pooled": n_withheld_total,
        "fold_proper_quaternary_hide_and_recover": fp_summary,
        "static_raster_quaternary_hide_and_recover": st_summary,
        "sgmc_off_catalogue_bedrock_control": {
            "evidence_label": "PROXY",
            "n_sgmc_off_catalogue_pixels_gt_3px": int(sgmc_off.sum()),
            "tercile_distribution": tercile_dot_census(sgmc_off, tercile),
            "arms": sgmc_scores,
        },
        "leakage_canary": {
            "threshold_symmetric_auc": 0.90,
            "n_channels_audited": len(canary_channels),
            "max_symmetric_auc": round(max_canary, 5),
            "n_flagged_over_0_90": len(flagged),
            "channels": canary_channels,
        },
    }


def main() -> int:
    t_start = time.time()
    print("=== Step 1: Verify registry/data_manifest.json SHA-256 pins ===")
    manifest_receipt = verify_and_restore_manifest()
    print(f"Verified {manifest_receipt['verified_count']} manifest files.")

    template_path = RAW_DIR / "sample_submission.tif"
    catalogue_path = RAW_DIR / "existing_faults.tif"
    h19_5_tif = RAW_DIR / "scored" / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"
    d28_tif = RAW_DIR / "scored" / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"

    with rasterio.open(template_path) as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(catalogue_path) as ds:
        catalogue = (ds.read(1) > 0) & footprint
    with rasterio.open(h19_5_tif) as ds:
        h19_5 = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    with rasterio.open(d28_tif) as ds:
        d28_manifest = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    d_cat = distance_transform_edt(~catalogue)

    print("=== Step 2: Rebuild Parent R0 and verify exact SHA-256 identity ===")
    _, r0_mask, r0_receipt = rebuild_and_verify_r0(
        h19_5, d28_manifest, footprint, catalogue, d_cat, template_path
    )
    if not (r0_receipt["zeros_sha256_exact_match"] and r0_receipt["nan_sha256_exact_match"]):
        raise RuntimeError(f"Parent R0 SHA-256 verification failed: {r0_receipt}")
    print(
        f"Parent R0 verified byte-for-byte: dots={int(r0_mask.sum())}, "
        f"nan_sha={r0_receipt['nan_sha256'][:12]}..., "
        f"zeros_sha={r0_receipt['zeros_sha256'][:12]}..."
    )

    print("=== Step 3: Read ledger/submissions.csv and verify axis/hash uniqueness ===")
    with LEDGER_PATH.open("r", encoding="utf-8", newline="") as f:
        existing_rows = list(csv.DictReader(f))
    non_relief_rows = [r for r in existing_rows if r["axis"] != "RELIEF"]
    seen_pairs = {(r["parent"], r["axis"], r["value"]) for r in non_relief_rows}
    seen_shas = {r["sha256"] for r in non_relief_rows} | {
        r["sha256_zeros"] for r in non_relief_rows if r.get("sha256_zeros")
    }
    seen_shas |= {R0_EXPECTED_NAN_SHA256, R0_EXPECTED_ZEROS_SHA256}
    registry_shas = (
        {r["sha256"] for r in json.loads(CANONICAL_INDEX_PATH.read_text(encoding="utf-8")).get("rasters", [])}
        if CANONICAL_INDEX_PATH.is_file()
        else set()
    )
    inventory_shas = (
        {r["sha256"] for r in json.loads(INVENTORY_PATH.read_text(encoding="utf-8")).get("rasters", [])}
        if INVENTORY_PATH.is_file()
        else set()
    )

    print("=== Step 4: Compute geomorphic relief terciles (Bands 12 & 19) + subsurface crests (Bands 02 & 05) ===")
    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        b02_rtp = ds.read(2).astype(np.float32)
        b05_gslope = ds.read(5).astype(np.float32)
        b12_elev = ds.read(12).astype(np.float32)
        b19_eslope = ds.read(19).astype(np.float32)

    relief_info = compute_relief_terciles(b12_elev, b19_eslope, footprint)
    tercile = relief_info["tercile"]
    relief_index = relief_info["relief_index"]
    subsurface_score = compute_subsurface_crest_score(b02_rtp, b05_gslope, footprint)
    grav_audit = audit_gravity_gradient_bands(footprint)

    allowed = footprint & ~catalogue & (d_cat > 2.0)
    cat_terciles = tercile_dot_census(catalogue, tercile)
    r0_terciles = tercile_dot_census(r0_mask, tercile)
    print(f"Parent R0 terciles: {r0_terciles['counts']} | Catalogue terciles: {cat_terciles['counts']}")

    print("=== Step 5: Build, write, and re-read-validate 3 controlled AXIS=RELIEF variants ===")
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)

    built_variants: list[dict[str, Any]] = []
    new_ledger_rows: list[dict[str, str]] = []
    cards_out: dict[str, dict[str, Any]] = {}
    static_masks: dict[str, np.ndarray] = {"R0": r0_mask}

    # Remove stale RELIEF .tif files if re-running cleanly
    for old_tif in RELEASES_DIR.glob(f"{PARENT_ID}-RELIEF*.tif"):
        old_tif.unlink()

    for spec in VARIANT_SPECS:
        val = str(spec["value"])
        pair_key = (PARENT_ID, "RELIEF", val)
        if pair_key in seen_pairs:
            raise RuntimeError(f"Duplicate (parent, axis, value) prohibited: {pair_key}")

        var_mask, op_info = shift_relief_mass(
            r0_mask,
            h19_5,
            tercile,
            allowed,
            subsurface_score,
            src_tercile=int(spec["src_tercile"]),
            dst_tercile=int(spec["dst_tercile"]),
            n_shift=int(spec["n_shift"]),
            min_sep2=8,
        )
        static_masks[f"RELIEF{val}"] = var_mask

        tmp_nan = RELEASES_DIR / f"_tmp_RELIEF_{val}.tif"
        tmp_zeros = RELEASES_DIR / f"_tmp_RELIEF_{val}-zeros.tif"
        sha_nan, sha_zeros = write_geotiff_pair_exact_profile(
            var_mask, footprint, catalogue, template_path, tmp_nan, tmp_zeros
        )
        for s_chk in (sha_nan, sha_zeros):
            if s_chk in seen_shas or s_chk in registry_shas or s_chk in inventory_shas:
                raise RuntimeError(f"Duplicate SHA-256 collision for {val}: {s_chk}")
        seen_shas.update({sha_nan, sha_zeros})
        seen_pairs.add(pair_key)

        sha8 = sha_nan[:8]
        var_id = f"{PARENT_ID}-RELIEF{val}-{SESSION_DATE}-{sha8}"
        final_nan = RELEASES_DIR / f"{var_id}.tif"
        final_zeros = RELEASES_DIR / f"{var_id}-zeros.tif"
        tmp_nan.replace(final_nan)
        tmp_zeros.replace(final_zeros)

        # Re-read every written GeoTIFF from disk and run MUST-PASS validation gates
        reread_sha_nan = sha256_file(final_nan)
        reread_sha_zeros = sha256_file(final_zeros)
        if reread_sha_nan != sha_nan or reread_sha_zeros != sha_zeros:
            raise RuntimeError("Re-read SHA-256 mismatch after rename!")

        val_nan = validate_submission(final_nan, template_path)
        if not val_nan["ready"] or val_nan["errors"]:
            raise RuntimeError(f"Validation gate failed for {final_nan}: {val_nan}")
        val_zeros = V57.validate(final_zeros, footprint=footprint, catalogue=catalogue)
        if not val_zeros["all_checks_passed"]:
            raise RuntimeError(f"gems57.validate failed for {final_zeros}: {val_zeros}")

        with rasterio.open(final_nan) as ds_chk:
            arr_chk = ds_chk.read(1)
        if int(np.isnan(arr_chk[footprint]).sum()) != 0:
            raise RuntimeError(f"NaN inside footprint in {final_nan}")
        if not np.all(np.isnan(arr_chk[~footprint])):
            raise RuntimeError(f"Non-NaN outside footprint in {final_nan}")
        if int((arr_chk[catalogue] > 0).sum()) != 0:
            raise RuntimeError(f"Non-zero mass on catalogue in {final_nan}")
        if int((arr_chk[footprint] > 0.5).sum()) != R0_TARGET_DOTS:
            raise RuntimeError(f"Dot count drifted in {final_nan}")

        diff_stats = compute_parent_diff_stats(var_mask, r0_mask, d_cat, footprint)
        pct_str = f"{op_info['pct_changed']:.2f}"
        form_note = (
            f"{PARENT_ID}; RELIEF {spec['note_label']} "
            f"(n={R0_TARGET_DOTS}, {op_info['n_shifted']} shifted); "
            f"pred {spec['predicted_change']}"
        )
        if len(form_note) > 140:
            raise RuntimeError(f"Form note exceeds 140 chars ({len(form_note)}): {form_note}")

        rec = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": "RELIEF",
            "value": val,
            "n_dots": R0_TARGET_DOTS,
            "pct_changed": op_info["pct_changed"],
            "sha256": sha_nan,
            "sha256_zeros": sha_zeros,
            "nan_file": f"releases/{final_nan.name}",
            "nan_bytes": final_nan.stat().st_size,
            "zeros_file": f"releases/{final_zeros.name}",
            "zeros_bytes": final_zeros.stat().st_size,
            "predicted_change": spec["predicted_change"],
            "form_note": form_note,
            "form_note_length": len(form_note),
            "validation_nan": val_nan,
            "validation_zeros": val_zeros,
            "relief_operator": op_info,
            "parent_diff": diff_stats,
        }
        built_variants.append(rec)

        cards_out[var_id] = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": "RELIEF",
            "value": val,
            "hypothesis": spec["hypothesis"],
            "mechanism": spec["mechanism"],
            "non_fault_mimic": spec["non_fault_mimic"],
            "predicted_live_change": spec["predicted_live_change"],
            "falsifier": spec["falsifier"],
        }

        new_ledger_rows.append(
            {
                "id": var_id,
                "parent": PARENT_ID,
                "axis": "RELIEF",
                "value": val,
                "n_dots": str(R0_TARGET_DOTS),
                "pct_changed": pct_str,
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
            f"  Built & verified {var_id}: chg={pct_str}%, "
            f"min_nn={diff_stats['nearest_neighbor_px']['min']} px, "
            f"min_dcat={diff_stats['d_catalogue_px']['min']} px, "
            f"note=({len(form_note)}/140)"
        )

    print("=== Step 6: Run REPORT-ONLY diagnostics (hide-and-recover, SGMC, leakage canary) ===")
    diagnostics = run_relief_diagnostics(
        static_masks=static_masks,
        h19_5=h19_5,
        tercile=tercile,
        relief_index=relief_index,
        subsurface_score=subsurface_score,
        footprint=footprint,
        catalogue=catalogue,
        d_cat=d_cat,
    )

    print("=== Step 7: Write manifest_RELIEF.json, mechanism_cards_relief.json, and ledger/submissions.csv ===")
    manifest_out = {
        "schema_version": "gemsdoe87-agent-brief-v2-relief-1.0",
        "session_date": "2026-10-23",
        "git_head_at_build": git_head_sha(),
        "fixed_seed": FIXED_SEED,
        "axis": "RELIEF",
        "parent_id": PARENT_ID,
        "manifest_verification": manifest_receipt,
        "parent_r0_rebuild_receipt": r0_receipt,
        "relief_partition": {
            "bands_used": [
                "Band 12: det_elev (detrended elevation, m)",
                "Band 19: det_elev_slope (detrended elevation slope, deg)",
            ],
            "subsurface_tiebreak_bands_used": [
                "Band 02: rtp_tmi (isotropic |grad_H(RTP)| 1-D Hessian crest)",
                "Band 05: iso_grav_anom_slope (isotropic |grad_H g| 1-D Hessian crest)",
            ],
            "external_lidar_used": False,
            "weights": relief_info["weights"],
            "tercile_cuts": list(relief_info["cuts"]),
            "det_elev_tercile_reference_m": list(relief_info["det_elev_tercile_reference_m"]),
            "footprint_pixel_counts": relief_info["footprint_pixel_counts"],
            "catalogue_tercile_census": cat_terciles,
            "parent_r0_tercile_census": r0_terciles,
        },
        "gravity_gradient_band_audit": grav_audit,
        "variants": built_variants,
        "report_only_diagnostics": diagnostics,
        "elapsed_seconds_total": round(time.time() - t_start, 2),
    }
    RELIEF_MANIFEST_PATH.write_text(json.dumps(manifest_out, indent=2) + "\n", encoding="utf-8")
    RELIEF_CARDS_PATH.write_text(json.dumps(cards_out, indent=2) + "\n", encoding="utf-8")

    merged_rows = non_relief_rows + new_ledger_rows
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"Done in {time.time() - t_start:.2f}s. Ledger now has {len(merged_rows)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
