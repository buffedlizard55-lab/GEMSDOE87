#!/usr/bin/env python3
"""Reproducible builder and validator for GEMSDOE87 Agent Brief v2 (AXIS = SNAP on Parent R0).

Workflow (strictly offline / GitHub-pinned inputs only; zero contact with drivendata.org or dropbox.com):

1. Verify every SHA-256 pin in ``registry/data_manifest.json`` against ``.cache/raw/`` and halt on
   any mismatch (restoring missing files only from pinned GitHub commits).
2. Rebuild Parent R0 (``h33-h33-2-b2``, GEMSDOE32, 37,654 unit-mass dots) from pinned manifest inputs
   (``scored_h19_5``, ``sample_submission``, ``existing_faults``) and assert byte-for-byte SHA-256
   identity with both R0 twins. Halt on mismatch; never approximate the parent.
3. Load the two *provided* potential-field gradient bands from ``training_features.tif``
   (band 03 ``tmi_hg``, band 18 ``iso_grav_anom_hg``), remove their regional trend with a 2 km
   Gaussian high-pass, robust-z score inside the footprint, and build an edge-crest mask
   (3x3 local maximum of the residual field, ``>= 0`` above the footprint median).
4. Snap every R0 dot that is *not* already on a crest to the strongest unclaimed crest pixel within a
   5x5 window (Chebyshev radius 2 px = 200 m). Count, exclusions (``d_cat > 2 px``, zero catalogue
   mass) and the parent's dot set are preserved: dots on crests stay, movers never displace a stayer,
   and every destination is a distinct pixel, so the emitted mass is exactly 37,654.
5. Write ``releases/<id>.tif`` (NaN outside footprint) and ``releases/<id>-zeros.tif`` (0.0 outside),
   re-read both from disk, run the MUST-PASS gates, and compute the REPORT-ONLY diagnostics
   (fold-proper hide-and-recover PROXY with 95% CI, single-feature leakage canary, SGMC control).

Nothing here contacts a competition server: the human uploads from their own account.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, gaussian_filter, maximum_filter

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_prune_variants import (  # noqa: E402  (shared, already-tested helpers)
    LEDGER_COLUMNS,
    PARENT_ID,
    R0_TARGET_DOTS,
    compute_parent_diff_stats,
    dot_thin_geodesic_bfs,
    git_head_sha,
    rebuild_and_verify_r0,
    sha256_file,
    symmetric_auc_mann_whitney,
    verify_and_restore_manifest,
    write_geotiff_pair_exact_profile,
)
from scripts.validate_submission import validate_submission  # noqa: E402
from vendor.gems57 import evaluate_holdout as EH  # noqa: E402
from vendor.gems57 import grid as GR  # noqa: E402
from vendor.gems57 import holdout as HO  # noqa: E402
from vendor.gems57 import metric as M  # noqa: E402
from vendor.gems57 import validate as V57  # noqa: E402

RAW_DIR = REPO_ROOT / ".cache" / "raw"
RELEASES_DIR = REPO_ROOT / "releases"
LEDGER_PATH = REPO_ROOT / "ledger" / "submissions.csv"
CARDS_PATH = REPO_ROOT / "ledger" / "mechanism_cards_snap.json"
RELEASE_MANIFEST_PATH = RELEASES_DIR / "manifest_SNAP.json"

SESSION_DATE = "20261023"
FIXED_SEED = 0  # zero randomness: every tie-break is row-major flat index
AXIS = "SNAP"

# --- SNAP operator parameters (fixed a priori, recorded in the mechanism card) -------------------
SNAP_RADIUS_PX = 2            # Chebyshev radius: <= 2 px = 200 m displacement cap
TREND_SIGMA_PX = 20.0         # 2 km Gaussian high-pass removes the regional potential-field trend
CREST_WINDOW_PX = 3           # 3x3 local maximum = edge crest
MIN_D_CAT_PX = 2.0            # R0's own exclusion, kept identical ("same exclusions")
MIN_CREST_RESIDUAL_Z = 0.0    # a destination must stand above the footprint-median edge response
ARGMAX_GAIN_MARGIN_Z = 0.25   # window-argmax fallback: destination must beat the dot by >= 0.25 robust z
R0_MIN_SEP_PX = float(np.sqrt(8.0))  # R0's own minimum separation (2.8284 px = 283 m); reported, not enforced
BAND_TMI_HG = 3               # training_features.tif band 03  ("tmi_hg")
BAND_GRAV_HG = 18             # training_features.tif band 18  ("iso_grav_anom_hg")
BAND_ELEV_SLOPE = 19          # training_features.tif band 19  ("det_elev_slope", DEM scarp response)
SENTINEL_ABS = 1e18           # |value| above this is the stack's nodata sentinel


# ------------------------------------------------------------------------------------------------
# Field construction
# ------------------------------------------------------------------------------------------------
def robust_z_in_footprint(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Median/MAD z-score inside ``valid``, clipped to +/-10 and zeroed outside."""
    v = values[valid]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)) * 1.4826)
    if not np.isfinite(mad) or mad <= 0:
        mad = max(float(np.std(v)), 1e-6)
    z = np.zeros(values.shape, np.float64)
    zz = (values - med) / mad
    np.clip(zz, -10.0, 10.0, out=zz)
    z[valid] = zz[valid]
    return z


def residual_edge_field(
    raw_band: np.ndarray,
    footprint: np.ndarray,
    sigma_px: float = TREND_SIGMA_PX,
) -> tuple[np.ndarray, dict[str, float]]:
    """Robust-z of the band, high-passed by ``sigma_px`` to remove its regional trend.

    A raw horizontal-gradient magnitude always increases toward the regional field maximum, so a
    naive window maximum rides that trend instead of an edge. Subtracting the 2 km Gaussian trend
    leaves the local gradient ridge that a fault/contact scarp produces.
    """
    valid = footprint & np.isfinite(raw_band) & (np.abs(raw_band) < SENTINEL_ABS)
    z = robust_z_in_footprint(raw_band.astype(np.float64), valid)
    trend = gaussian_filter(z, sigma_px, mode="nearest")
    resid = np.where(valid, z - trend, 0.0)
    out = robust_z_in_footprint(np.where(valid, resid, 0.0), valid)
    out[~valid] = 0.0
    info = {
        "sigma_px": float(sigma_px),
        "valid_pixels": int(valid.sum()),
        "z_std_in_footprint": round(float(np.std(z[valid])), 6),
        "raw_residual_std_in_footprint": round(float(np.std(resid[valid])), 6),
        "raw_residual_over_z_std": round(
            float(np.std(resid[valid]) / max(float(np.std(z[valid])), 1e-30)), 9
        ),
        "residual_z_median_in_footprint": round(float(np.median(out[valid])), 6),
        "residual_z_p95_in_footprint": round(float(np.percentile(out[valid], 95)), 6),
        "trend_fraction_of_variance": round(
            float(np.var(trend[valid]) / max(np.var(z[valid]), 1e-12)), 6
        ),
    }
    return out, info


def combine_fields(name: str, fields: dict[str, np.ndarray]) -> np.ndarray:
    """Variant-specific edge score plane."""
    if name in fields:
        return fields[name]
    raise KeyError(f"unknown SNAP field {name}")


def crest_mask(score: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """3x3 local maximum of the residual edge field that clears ``MIN_CREST_RESIDUAL_Z``."""
    peak = maximum_filter(score, size=CREST_WINDOW_PX, mode="nearest")
    return valid & np.isclose(score, peak, atol=1e-9) & (score >= MIN_CREST_RESIDUAL_Z)


# ------------------------------------------------------------------------------------------------
# The SNAP operator
# ------------------------------------------------------------------------------------------------
def nearest_neighbour_stats(mask: np.ndarray) -> dict[str, float]:
    """Nearest-neighbour spacing census, including any new near-duplicate pairs the snap creates."""
    from scipy.spatial import cKDTree

    pts = np.column_stack(np.nonzero(mask))
    nn, _ = cKDTree(pts).query(pts, k=2)
    nn = nn[:, 1]
    return {
        "min_px": round(float(nn.min()), 4),
        "p01_px": round(float(np.percentile(nn, 1)), 4),
        "p05_px": round(float(np.percentile(nn, 5)), 4),
        "median_px": round(float(np.median(nn)), 4),
        "mean_px": round(float(nn.mean()), 4),
        "n_with_nn_lt_2px": int((nn < 2.0).sum()),
        "n_with_nn_lt_1px_and_half": int((nn < 1.5).sum()),
    }


def snap_dots(
    dots: np.ndarray,
    score: np.ndarray,
    allowed: np.ndarray,
    radius_px: int = SNAP_RADIUS_PX,
    rule: str = "crest",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Move R0 dots <= ``radius_px`` onto the strongest admissible edge response in their window.

    Rules (all deterministic, zero randomness):
      * ``rule="crest"``: destinations are 3x3 edge crests of the residual field (the operator the
        SNAP mechanism card specifies). Dots already sitting on a crest never move.
      * ``rule="argmax_gain"``: fallback for a field that resolves almost no crest at 100 m; the
        destination is the window maximum of the residual field, which must beat the dot's own
        position by ``ARGMAX_GAIN_MARGIN_Z``. Used only where the crest census makes ``crest`` a
        no-op (documented per arm).
      * Destinations must be ``allowed`` and not occupied by any parent dot, so no two dots can
        share a destination and no mover can displace a stayer.
      * Movers are served in descending score gain (destination minus own position), ties by
        row-major flat index; each takes its best-ranked free candidate else stays put.
      * The dot count therefore returns exactly the input count.
    """
    dots = np.asarray(dots, bool)
    score = np.asarray(score, np.float64)
    allowed = np.asarray(allowed, bool)
    h, w = dots.shape
    if rule == "crest":
        dest_pool = crest_mask(score, allowed)
        dots_on_crest = dots & dest_pool
    elif rule == "argmax_gain":
        dest_pool = allowed & (score >= MIN_CREST_RESIDUAL_Z)
        dots_on_crest = np.zeros_like(dots)
    else:
        raise ValueError(f"unknown snap rule {rule!r}")
    free = dest_pool & ~dots  # unclaimed destinations

    # NOTE (measured, not enforced): R0 is already packed at its own minimum separation of
    # sqrt(8) = 2.8284 px (median nearest neighbour 3.0 px). A set packed that tightly has no hole
    # >= 2.8284 px from every dot, so requiring the parent's packing inside a <= 2 px snap would
    # forbid the operator entirely (measured: 0 admissible moves for all three arms). The snap
    # therefore only forbids *identical* destinations and reports the resulting nearest-neighbour
    # distribution, including any new sub-283 m pairs, in the parent-diff receipt.

    ri, ci = np.nonzero(dots & ~dest_pool) if rule == "crest" else np.nonzero(dots)
    out = dots.copy()
    info: dict[str, Any] = {
        "radius_px": int(radius_px),
        "n_parent_dots": int(dots.sum()),
        "n_dots_on_crest_at_parent": int(dots_on_crest.sum()),
        "gain_margin_z": ARGMAX_GAIN_MARGIN_Z if rule == "argmax_gain" else None,
        "r0_min_separation_px": round(R0_MIN_SEP_PX, 4),
        "n_off_crest_candidates_for_movement": int(ri.size),
        "rule": rule,
        "n_free_destinations": int(free.sum()),
    }
    if ri.size == 0:
        info.update({"n_moved": 0, "mean_displacement_px": 0.0, "median_displacement_px": 0.0,
                     "n_dots_after": int(out.sum()), "count_preserved": True})
        return out, info

    # Rank candidates for every off-crest dot: (-score, chebyshev, manhattan, dy, dx).
    cand: list[list[tuple[float, int, int, int, int]]] = []
    best_gain = np.full(ri.size, -np.inf, np.float64)
    for k in range(ri.size):
        y, x = int(ri[k]), int(ci[k])
        own = float(score[y, x])
        rows: list[tuple[float, int, int, int, int]] = []
        for dy in range(-radius_px, radius_px + 1):
            yy = y + dy
            if yy < 0 or yy >= h:
                continue
            for dx in range(-radius_px, radius_px + 1):
                xx = x + dx
                if xx < 0 or xx >= w or (dy == 0 and dx == 0):
                    continue
                if not free[yy, xx]:
                    continue
                gain = float(score[yy, xx]) - own
                if rule == "argmax_gain" and gain < ARGMAX_GAIN_MARGIN_Z:
                    continue
                rows.append(
                    (
                        -float(score[yy, xx]),
                        max(abs(dy), abs(dx)),
                        abs(dy) + abs(dx),
                        dy,
                        dx,
                    )
                )
        rows.sort()
        cand.append(rows)
        if rows:
            best_gain[k] = float(score[y + rows[0][3], x + rows[0][4]]) - own

    # Serve highest-gain dots first; ties broken by row-major flat index.
    order = np.lexsort((ri * w + ci, -best_gain))
    claimed = np.zeros((h, w), bool)
    moved = 0
    disp: list[float] = []
    blocked_no_candidate = 0
    blocked_all_claimed = 0
    for k in order.tolist():
        y, x = int(ri[k]), int(ci[k])
        if not cand[k]:
            blocked_no_candidate += 1
            continue
        placed = False
        for _, _, _, dy, dx in cand[k]:
            yy, xx = y + dy, x + dx
            if claimed[yy, xx]:
                continue
            claimed[yy, xx] = True
            out[y, x] = False
            out[yy, xx] = True
            moved += 1
            disp.append(float(np.hypot(dy, dx)))
            placed = True
            break
        if not placed:
            blocked_all_claimed += 1

    n_dots = int(dots.sum())
    info.update(
        {
            "n_moved": int(moved),
            "pct_moved_of_parent": round(100.0 * moved / float(n_dots), 4),
            "mean_displacement_px": round(float(np.mean(disp)), 4) if disp else 0.0,
            "median_displacement_px": round(float(np.median(disp)), 4) if disp else 0.0,
            "max_displacement_px": round(float(np.max(disp)), 4) if disp else 0.0,
            "mean_displacement_m": round(100.0 * float(np.mean(disp)), 2) if disp else 0.0,
            "n_stay_no_free_candidate": int(blocked_no_candidate),
            "n_stay_all_candidates_claimed": int(blocked_all_claimed),
            "n_dots_after": int(out.sum()),
            "count_preserved": bool(int(out.sum()) == n_dots),
        }
    )
    if int(out.sum()) != n_dots:
        raise RuntimeError(f"SNAP changed the dot count: {int(out.sum())} != {n_dots}")
    return out, info


# ------------------------------------------------------------------------------------------------
# Axis specification
# ------------------------------------------------------------------------------------------------
def variant_specs() -> list[dict[str, Any]]:
    """Three controlled SNAP arms: magnetic edge, topographic scarp, gravity control.

    Sensor choice is dictated by a crest census run on the pinned stack (recorded in
    ``releases/manifest_SNAP.json`` ``field_statistics``):
      * band 03 ``tmi_hg`` (2 km high-pass) -> 94,769 crest px: resolves crests, use ``crest``.
      * band 19 ``det_elev_slope`` (2 km high-pass) -> 264,859 crest px: resolves scarps, use ``crest``.
      * band 18 ``iso_grav_anom_hg`` (2 km high-pass) -> 3,330 crest px: resolves essentially no crest
        at the 100 m grid, so the ``crest`` operator moves 363 dots (0.96%) and cannot test the
        mechanism. That arm therefore uses the literal window-argmax rule with a 0.25 robust-z gain
        margin and is reported as a *misplacement-cost control*, not as a gravity-edge test.
    """
    return [
        {
            "axis": AXIS,
            "value": "tmi-hg",
            "field": "tmi_hg",
            "rule": "crest",
            "predicted_change": "-0.006 to +0.008 [MODEL]",
            "form_note": (
                "h33-h33-2-b2; SNAP<=2px off-crest dots to magnetic-HGM crest (bd03 hp2km), "
                "8132 moved; pred -0.006 to +0.008 [MODEL]"
            ),
            "mechanism_card": {
                "hypothesis": (
                    "R0's dot positions inherit the GeoDAWN survey geometry: Area 2 was flown at 400 m "
                    "line spacing and 150-200 m above terrain "
                    "(https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7), so an H19-5 "
                    "lineament pixel can sit 1-2 px (100-200 m) off the basement edge it came from. "
                    "Re-seating the dots that are NOT already on a magnetic horizontal-gradient ridge onto "
                    "the nearest free ridge should raise kernel credit T on new-fault truth at unchanged "
                    "emitted mass."
                ),
                "mechanism": (
                    "DTI = T/(0.2T + 0.2(S-M) + 0.8|G|) with the 300 m triangular kernel. For an isolated "
                    "truth pixel a dot pays iff its credit exceeds ~0.2*DTI (about 0.056 at DTI 0.28), so a "
                    "100-200 m reposition is small against the kernel radius but not negligible for "
                    "line-like truth, where a misplaced dot can duplicate another dot's truth cell. The "
                    "operator high-passes band 03 tmi_hg at 2 km (removing the regional gradient trend that "
                    "would otherwise drag every window maximum toward the regional high), robust-z scores "
                    "it, extracts 3x3 crests at or above the footprint median, and moves each off-crest dot "
                    "to the strongest FREE crest within 5x5 px (<=200 m), highest-gain dots served first. "
                    "Count, zero catalogue mass, the d_cat > 2 px exclusion and every dot already on a "
                    "crest are held fixed, so the only changed variable is cross-strike position."
                ),
                "non_fault_mimic": (
                    "Magnetic horizontal-gradient ridges also follow reversely magnetised Tertiary basalt "
                    "flows, buried pluton contacts, caldera ring fractures and rail/road corridors; the 2 km "
                    "high-pass further promotes shallow volcanic terrain texture with no Quaternary slip."
                ),
                "predicted_live_change": (
                    "MODEL -0.006 to +0.008 DTI vs R0. 8,132 of 37,654 dots (21.6%) move a mean of 1.95 px "
                    "(195 m), inside the 3 px kernel, so the effect must be small. Fold-proper hide-and-"
                    "recover PROXY = +0.0012 [-0.0002, +0.0024] and the off-catalogue SGMC PROXY = -0.0006 "
                    "vs R0: two proxies that disagree in sign, so the arm is predicted neutral and must be "
                    "read from a live receipt, not from either proxy."
                ),
                "falsifier": (
                    "A live RECEIPT gain >= +0.01 shows magnetic-crest position, not H19-5 lineament "
                    "texture, carries the new-fault signal; a drop <= -0.01 falsifies the airborne-offset "
                    "hypothesis for magnetics at this scale (|delta| < 0.01 on public chunks = no evidence)."
                ),
            },
        },
        {
            "axis": AXIS,
            "value": "scarp",
            "field": "det_elev_slope",
            "rule": "crest",
            "predicted_change": "-0.008 to +0.006 [MODEL]",
            "form_note": (
                "h33-h33-2-b2; SNAP<=2px to DEM scarp crest (bd19 det_elev_slope hp2km), "
                "23861 moved; pred -0.008 to +0.006 [MODEL]"
            ),
            "mechanism_card": {
                "hypothesis": (
                    "New Quaternary faults in the Great Basin are expressed first as range-front scarps and "
                    "faceted spurs, which the provided detrended-elevation slope band resolves at the 100 m "
                    "grid. If R0's H19-5 lineaments are offset from the scarp crest they represent, moving "
                    "each off-crest dot <= 200 m onto the free scarp crest should buy more kernel credit per "
                    "dot than the current position does."
                ),
                "mechanism": (
                    "Same operator as SNAP-tmi-hg driven by band 19 det_elev_slope high-passed at 2 km and "
                    "robust-z scored: 264,859 crest px, so 23,861 dots (63.4%) move a mean of 1.97 px "
                    "(197 m). Topographic slope, not potential-field gradient, is the sensor; both are "
                    "organizer-provided bands, neither is lidar-derived. Count, exclusions and all dots "
                    "already on a scarp crest are fixed."
                ),
                "non_fault_mimic": (
                    "DEM slope ridges also follow fluvial terrace risers, alluvial-fan toes, landslide "
                    "headwalls, playa shorelines (Lake Lahontan benches) and hillslope-aspect artefacts of "
                    "the 2 km high-pass; those are exactly the landforms that mimic scarps in a 30 m DEM "
                    "smoothed to 100 m."
                ),
                "predicted_live_change": (
                    "MODEL -0.008 to +0.006 DTI vs R0. This is the only arm that images surface rupture "
                    "directly and the only one that moves a majority of the mass, but the fold-proper PROXY "
                    "= -0.0007 [-0.0033, +0.0021] and the SGMC PROXY = -0.0022 vs R0 both lean slightly "
                    "negative, so the prediction is neutral-to-slightly-negative."
                ),
                "falsifier": (
                    "A live RECEIPT drop <= -0.01 means R0's airborne-geophysics lineaments are better fault "
                    "proxies than the topographic scarp crest within 200 m, i.e. the H19-5 texture is not "
                    "merely a displaced scarp map."
                ),
            },
        },
        {
            "axis": AXIS,
            "value": "grav-argmax",
            "field": "grav_hg",
            "rule": "argmax_gain",
            "predicted_change": "-0.010 to +0.008 [MODEL]",
            "form_note": (
                "h33-h33-2-b2; SNAP<=2px gravity-HGM window-argmax control (bd18 hp2km), "
                "7799 moved; pred -0.010 to +0.008 [MODEL]"
            ),
            "mechanism_card": {
                "hypothesis": (
                    "Null/calibration arm: how much live DTI does 200 m of unjustified relocation cost? The "
                    "provided isostatic-gravity gradient is interpolated from sparse regional stations, so at "
                    "the 100 m grid it resolves almost no crest (3,330 crest px in 5.17 M footprint px; the "
                    "crest operator moves only 363 dots). This arm instead takes the literal window maximum "
                    "of its 2 km residual with a 0.25 robust-z gain margin, which relocates mass without a "
                    "fault-position warrant."
                ),
                "mechanism": (
                    "Each dot moves <= 2 px toward the strongest residual gravity-gradient cell in its 5x5 "
                    "window provided that cell beats the dot's own position by >= 0.25 robust-z units; "
                    "destinations are unique, stayers cannot be displaced, and the count, exclusions and "
                    "zero-catalogue-mass rule are unchanged. Because the residual is nearly flat, the gain "
                    "margin is only met at window corners, so 7,799 dots (20.7%) move a mean of 2.69 px "
                    "(269 m) - an intentional maximal-misplacement control rather than a gravity-edge test."
                ),
                "non_fault_mimic": (
                    "Every residual crest in this field is a candidate mimic: with a km-scale interpolated "
                    "input, the residual is dominated by gridding/station geometry, and a dot driven by it "
                    "moves off the H19-5 lineament toward a gravity-shading maximum."
                ),
                "predicted_live_change": (
                    "MODEL -0.010 to +0.008 DTI vs R0. The two proxies disagree sharply: fold-proper PROXY "
                    "+0.0046 [+0.0013, +0.0085] (relocation de-clumps near-duplicate dots) but off-"
                    "catalogue SGMC PROXY -0.0036 (relocation leaves mapped bedrock faults). A live |delta| "
                    "< 0.01 means 270 m of positional error is invisible to this metric and the whole SNAP "
                    "axis is worth no further slots."
                ),
                "falsifier": (
                    "A live RECEIPT gain >= +0.01 on this arm would mean the interpolated gravity gradient "
                    "locates faults better than the H19-5 field - contradicted by the crest census, so it "
                    "would instead indicate a leak or a mis-scored submission and must be investigated "
                    "before anything is concluded."
                ),
            },
        },
    ]


# ------------------------------------------------------------------------------------------------
# Report-only diagnostics (never gates)
# ------------------------------------------------------------------------------------------------
def run_report_only_diagnostics(
    static_masks: dict[str, np.ndarray],
    r0_mask: np.ndarray,
    h19_5: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
    fields: dict[str, np.ndarray],
    valid_features: np.ndarray,
) -> dict[str, Any]:
    t0 = time.time()
    grid = GR.load_grid(RAW_DIR)
    seeds = (20, 30)
    draws_by_seed = {s: HO.buffered_component_draw(grid, seed=s)[0] for s in seeds}

    def fold_fair_base(visible: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d_vis = distance_transform_edt(~(visible & footprint))
        base = dot_thin_geodesic_bfs(h19_5 & footprint & ~visible, 2.8) & (d_vis > MIN_D_CAT_PX)
        return base, d_vis

    # 1. Fold-proper hide-and-recover PROXY: snap is rebuilt inside every fold on the fold-visible
    #    catalogue, so a withheld component cannot be nulled by the full-catalogue collar.
    fp_terms: dict[str, np.ndarray] = {}
    fp_moved: dict[str, list[float]] = {}
    for arm_name, spec in [(s["value"], s) for s in variant_specs()] + [("R0_fold_fair", None)]:
        score = combine_fields(spec["field"], fields) if spec else None
        tot = None
        moved_px: list[float] = []
        for s in seeds:
            visible = draws_by_seed[s][0]["visible"]
            base, d_vis = fold_fair_base(visible)
            allowed = valid_features & (d_vis > MIN_D_CAT_PX) & footprint & ~visible
            arm = base if spec is None else snap_dots(base, score, allowed, rule=spec["rule"])[0]
            pred = arm.astype(np.float32)
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred, fold, valid=footprint)
                tot = terms.copy() if tot is None else (tot + terms)
            if spec is not None:
                moved_px.append(100.0 * float((base & ~arm).sum()) / max(int(base.sum()), 1))
        assert tot is not None
        fp_terms[arm_name] = tot
        fp_moved[arm_name] = moved_px

    fp_summary = EH.pooled_summary(fp_terms, draws=1000, seed=520810, candidate="R0_fold_fair")

    # 2. Static-raster PROXY (the literal files; caveat: the full-catalogue collar zeroes predictions
    #    within 2 px of withheld truth, which is why the fold-proper arm above is the primary proxy).
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
    st_summary = EH.pooled_summary(st_terms, draws=1000, seed=520810, candidate="tmi-hg")

    # 3. Single-feature leakage canary (AUC > 0.90 means stop and investigate).
    rng = np.random.default_rng(20261023)
    eval_masks: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for s in seeds:
        vis_s = draws_by_seed[s][0]["visible"]
        hid_s = np.zeros_like(footprint)
        for fold in draws_by_seed[s]:
            hid_s |= (fold["truth"] & fold["region"] & footprint & ~vis_s)
        pos_idx = np.flatnonzero(hid_s[footprint])
        neg_pool = np.flatnonzero((~hid_s & ~vis_s & footprint)[footprint])
        neg_idx = rng.choice(neg_pool, size=min(80_000, neg_pool.size), replace=False)
        idx_all = np.concatenate([pos_idx, neg_idx])
        y_all = np.concatenate([np.ones(pos_idx.size, bool), np.zeros(neg_idx.size, bool)])
        eval_masks[s] = (idx_all, y_all)

    canary: list[dict[str, Any]] = []

    def audit(name: str, arr2d: np.ndarray) -> None:
        v_fp = np.asarray(arr2d, np.float64)[footprint]
        sym_by_s, auc_by_s = {}, {}
        for s, (idx_all, y_all) in eval_masks.items():
            vals = np.where(v_fp[idx_all] < -1e20, 0.0, v_fp[idx_all])
            auc, sym = symmetric_auc_mann_whitney(y_all, vals)
            auc_by_s[str(s)] = round(auc, 5)
            sym_by_s[str(s)] = round(sym, 5)
        mx = max(sym_by_s.values())
        canary.append(
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
            audit(f"training_b{b_idx:02d}_{desc}", ds.read(b_idx))
    for fname, arr in fields.items():
        audit(f"snap_residual_{fname}", arr)
    audit("parent_h19_5_binary", h19_5.astype(np.float32))
    canary.sort(key=lambda r: r["max_symmetric_auc"], reverse=True)
    flagged = [r for r in canary if r["flagged_over_0_90"]]
    if flagged:
        raise RuntimeError(f"STOP: leakage canary fired (> 0.90 symmetric AUC): {flagged}")

    # 4. Off-catalogue USGS SGMC control PROXY.
    with rasterio.open(RAW_DIR / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    sgmc_offcat = sgmc & ~catalogue & (d_cat > 3.0)
    sgmc_scores = {}
    for arm_name, m in list(static_masks.items()) + [("R0_parent", r0_mask)]:
        res = M.dti_binary(m, sgmc_offcat, valid=footprint, known=catalogue)
        sgmc_scores[arm_name] = {
            "evidence_label": "PROXY",
            "dti": round(float(res["dti"]), 6),
            "coverage": round(float(res["coverage"]), 6),
            "n_sgmc_offcat_pixels": int(res["n_truth"]),
            "n_emitted": int(res["n_emitted"]),
        }

    return {
        "evidence_label": "PROXY",
        "note": "REPORT ONLY - never used as promotion/rejection gates (Brief v2 Section 6).",
        "evaluator_version": EH.VERSION,
        "synthetic_fold_rebuild_pct_moved": fp_moved,
        "fold_proper_hide_and_recover_proxy": {
            k: {
                "evidence_label": "PROXY",
                "dti": round(float(v["dti"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
                "withheld_positive_pixels": int(v["withheld_positive_pixels"]),
            }
            for k, v in fp_summary["scores"].items()
        },
        "fold_proper_paired_vs_R0_fold_fair": {
            k: {
                "evidence_label": "PROXY",
                "delta_arm_minus_R0": round(float(v["delta"]), 6),
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
                "caveat": "Static file: the d_cat > 2 px collar removes prediction within 2 px of withheld truth.",
            }
            for k, v in st_summary["scores"].items()
        },
        "leakage_canary": {
            "evidence_label": "PROXY",
            "channels_audited": len(canary),
            "limit_symmetric_auc": 0.90,
            "max_symmetric_auc_observed": round(max(r["max_symmetric_auc"] for r in canary), 5),
            "flagged_channels": flagged,
            "passed_investigation_check": len(flagged) == 0,
            "top_10_channels": canary[:10],
        },
        "sgmc_offcatalogue_control_proxy": sgmc_scores,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ------------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-diagnostics", action="store_true")
    args = ap.parse_args()
    t_start = time.time()

    print("[1/6] Verifying every SHA-256 pin in registry/data_manifest.json ...", flush=True)
    manifest_receipt = verify_and_restore_manifest()
    n_files = manifest_receipt["verified_count"]
    print(f"      {n_files}/{n_files} pinned files verified.", flush=True)

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

    print("[2/6] Rebuilding Parent R0 and verifying exact SHA-256 ...", flush=True)
    d28, r0_mask, r0_receipt = rebuild_and_verify_r0(
        h19_5, d28_manifest, footprint, catalogue, d_cat, template_tif
    )
    print(
        f"      R0 exact: n={r0_receipt['n_dots']} zeros={r0_receipt['zeros_sha256'][:16]}... "
        f"nan={r0_receipt['nan_sha256'][:16]}...",
        flush=True,
    )

    print("[3/6] Building residual edge fields and crest masks ...", flush=True)
    with rasterio.open(RAW_DIR / "training_features.tif") as ds:
        raw_bands = {
            "tmi_hg": ds.read(BAND_TMI_HG).astype(np.float64),
            "grav_hg": ds.read(BAND_GRAV_HG).astype(np.float64),
            "det_elev_slope": ds.read(BAND_ELEV_SLOPE).astype(np.float64),
        }
    valid_features = footprint.copy()
    for raw in raw_bands.values():
        valid_features &= np.isfinite(raw) & (np.abs(raw) < SENTINEL_ABS)
    fields: dict[str, np.ndarray] = {}
    field_info: dict[str, Any] = {}
    for name, raw in raw_bands.items():
        fields[name], field_info[name] = residual_edge_field(raw, valid_features)
    for name, f in fields.items():
        crest = crest_mask(f, valid_features & (d_cat > MIN_D_CAT_PX) & footprint)
        field_info[name]["crest_pixels"] = int(crest.sum())
        field_info[name]["crest_pixels_free_of_parent_dots"] = int((crest & ~r0_mask).sum())
        field_info[name]["parent_dots_already_on_crest"] = int((crest & r0_mask).sum())

    print("[4/6] Snapping and writing releases ...", flush=True)
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    if LEDGER_PATH.is_file():
        with LEDGER_PATH.open("r", encoding="utf-8", newline="") as f:
            existing_rows = [r for r in csv.DictReader(f) if r.get("status") and r["axis"] != AXIS]
    seen_shas = {r["sha256"] for r in existing_rows if r.get("sha256")}
    seen_shas |= {r.get("sha256_zeros", "") for r in existing_rows if r.get("sha256_zeros")}
    seen_pairs = {(r.get("parent", ""), r.get("axis", ""), r.get("value", "")) for r in existing_rows}
    hist_shas: set[str] = set()
    for rel in ("registry/canonical_scored_index.json", "registry/inventory.json"):
        p = REPO_ROOT / rel
        if p.is_file():
            reg = json.loads(p.read_text(encoding="utf-8"))
            hist_shas |= {r["sha256"] for r in reg.get("rasters", [])}

    allowed = valid_features & (d_cat > MIN_D_CAT_PX) & footprint
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    built: list[dict[str, Any]] = []
    new_rows: list[dict[str, str]] = []
    static_masks: dict[str, np.ndarray] = {}
    cards: dict[str, Any] = {}

    for spec in variant_specs():
        pair = (PARENT_ID, spec["axis"], spec["value"])
        if pair in seen_pairs:
            raise RuntimeError(f"(parent, axis, value) already built: {pair}")
        score = combine_fields(spec["field"], fields)
        v_mask, snap_info = snap_dots(r0_mask, score, allowed, rule=spec["rule"])
        if int((v_mask & catalogue).sum()) != 0:
            raise RuntimeError("SNAP placed mass on catalogue pixels")
        if int(v_mask.sum()) != R0_TARGET_DOTS:
            raise RuntimeError("SNAP changed the dot count")

        diff_stats = compute_parent_diff_stats(v_mask, r0_mask, d_cat, footprint)
        diff_stats["nearest_neighbour_parent"] = nearest_neighbour_stats(r0_mask)
        diff_stats["nearest_neighbour_variant"] = nearest_neighbour_stats(v_mask)
        tmp_nan = RELEASES_DIR / "_snap_tmp_nan.tif"
        tmp_zeros = RELEASES_DIR / "_snap_tmp_zeros.tif"
        sha_nan_tmp, sha_zeros_tmp = write_geotiff_pair_exact_profile(
            v_mask, footprint, catalogue, template_tif, tmp_nan, tmp_zeros
        )
        sha8 = sha_nan_tmp[:8]
        var_id = f"{PARENT_ID}-{spec['axis']}{spec['value']}-{SESSION_DATE}-{sha8}"
        final_nan = RELEASES_DIR / f"{var_id}.tif"
        final_zeros = RELEASES_DIR / f"{var_id}-zeros.tif"
        tmp_nan.replace(final_nan)
        tmp_zeros.replace(final_zeros)

        # MUST-PASS gate 1: re-read from disk, hash + pixel identity + zero catalogue mass.
        sha_nan, sha_zeros = sha256_file(final_nan), sha256_file(final_zeros)
        if sha_nan != sha_nan_tmp or sha_nan[:8] != sha8:
            raise RuntimeError("re-read SHA mismatch on the NaN file")
        if sha_zeros != sha_zeros_tmp:
            raise RuntimeError("re-read SHA mismatch on the zeros file")
        with rasterio.open(final_nan) as ds_n, rasterio.open(final_zeros) as ds_z:
            arr_n, arr_z = ds_n.read(1), ds_z.read(1)
        for arr, label in ((arr_n, "nan"), (arr_z, "zeros")):
            if not np.array_equal(arr[footprint] > 0.5, v_mask[footprint]):
                raise RuntimeError(f"pixel identity lost on re-read ({label})")
            if int((arr[catalogue] > 0).sum()) != 0:
                raise RuntimeError(f"non-zero catalogue mass in the {label} file")
        if int(np.isnan(arr_n[footprint]).sum()) != 0:
            raise RuntimeError("NaN inside the footprint")

        # MUST-PASS gate 2: spec validator on the NaN file, gems57 validator on the zeros twin.
        val_nan = validate_submission(final_nan, template_tif)
        if not val_nan["ready"] or val_nan["errors"]:
            raise RuntimeError(f"validate_submission failed: {val_nan['errors']}")
        val_zeros = V57.validate(final_zeros, footprint=footprint, catalogue=catalogue)
        if not val_zeros["all_checks_passed"]:
            raise RuntimeError(f"gems57.validate failed: {val_zeros['checks']}")

        # MUST-PASS gate 3: exact-SHA dedupe against the ledger and the historical registries.
        for s_chk in (sha_nan, sha_zeros):
            if s_chk in seen_shas:
                raise RuntimeError(f"SHA-256 {s_chk} already in ledger/submissions.csv")
            if s_chk in hist_shas:
                raise RuntimeError(f"SHA-256 {s_chk} collides with a historical registry raster")
        seen_shas |= {sha_nan, sha_zeros}
        seen_pairs.add(pair)
        static_masks[spec["value"]] = v_mask

        rec = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": spec["axis"],
            "value": spec["value"],
            "field": spec["field"],
            "n_dots": diff_stats["n_dots"],
            "pct_changed": round(diff_stats["pct_changed"], 2),
            "sha256": sha_nan,
            "sha8": sha8,
            "zeros_sha256": sha_zeros,
            "content_digest8": hashlib.sha256(np.packbits(v_mask)).hexdigest()[:8],
            "primary_file": f"releases/{final_nan.name}",
            "primary_bytes": final_nan.stat().st_size,
            "zeros_fallback_file": f"releases/{final_zeros.name}",
            "zeros_bytes": final_zeros.stat().st_size,
            "status": "BUILT",
            "predicted_change": spec["predicted_change"],
            "form_note": spec["form_note"],
            "form_note_length": len(spec["form_note"]),
            "snap_operator": snap_info,
            "parent_diff": diff_stats,
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
        built.append(rec)
        cards[var_id] = {
            **spec["mechanism_card"],
            "axis": spec["axis"],
            "value": spec["value"],
            "field": spec["field"],
            "n_moved": snap_info["n_moved"],
            "mean_displacement_px": snap_info["mean_displacement_px"],
            "mean_displacement_m": snap_info["mean_displacement_m"],
            "pct_changed": round(diff_stats["pct_changed"], 2),
        }
        new_rows.append(
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
                "description": spec["form_note"],
            }
        )
        print(
            f"      {var_id}: moved={snap_info['n_moved']} "
            f"(mean {snap_info['mean_displacement_px']} px), "
            f"pct_changed={diff_stats['pct_changed']:.2f}%, "
            f"min_dcat={diff_stats['d_catalogue_px']['min']} px, "
            f"CV10km={diff_stats['block_density_cv_10km']['variant']}",
            flush=True,
        )

    print("[5/6] Writing ledger, mechanism cards and release manifest ...", flush=True)
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in existing_rows + new_rows:
            writer.writerow({k: r.get(k, "") for k in LEDGER_COLUMNS})
    CARDS_PATH.write_text(json.dumps(cards, indent=2) + "\n", encoding="utf-8")

    diagnostics = None
    if not args.skip_diagnostics:
        print("[6/6] REPORT-ONLY diagnostics (PROXY holdout, canary, SGMC control) ...", flush=True)
        diagnostics = run_report_only_diagnostics(
            static_masks, r0_mask, h19_5, footprint, catalogue, d_cat, fields, valid_features
        )
        print(
            f"      done in {diagnostics['elapsed_seconds']}s; canary max_sym_auc="
            f"{diagnostics['leakage_canary']['max_symmetric_auc_observed']}, "
            f"fold-proper R0 PROXY="
            f"{diagnostics['fold_proper_hide_and_recover_proxy']['R0_fold_fair']['dti']:.6f}",
            flush=True,
        )

    manifest = {
        "schema_version": 1,
        "generated_date_utc": SESSION_DATE,
        "git_head_at_build": git_head_sha(),
        "fixed_seed": FIXED_SEED,
        "axis": AXIS,
        "operator": {
            "radius_px": SNAP_RADIUS_PX,
            "radius_m": SNAP_RADIUS_PX * M.PIXEL_M,
            "trend_high_pass_sigma_px": TREND_SIGMA_PX,
            "crest_window_px": CREST_WINDOW_PX,
            "min_d_cat_px": MIN_D_CAT_PX,
            "min_crest_residual_z": MIN_CREST_RESIDUAL_Z,
            "argmax_gain_margin_z": ARGMAX_GAIN_MARGIN_Z,
            "r0_min_separation_px": round(R0_MIN_SEP_PX, 4),
            "bands": {
                "tmi_hg": BAND_TMI_HG,
                "iso_grav_anom_hg": BAND_GRAV_HG,
                "det_elev_slope": BAND_ELEV_SLOPE,
            },
        },
        "manifest_verification": {
            "manifest_path": "registry/data_manifest.json",
            "verified_files_count": n_files,
        },
        "field_statistics": field_info,
        "parent_r0_rebuild_receipt": r0_receipt,
        "variants": built,
        "report_only_diagnostics": diagnostics,
        "total_elapsed_seconds": round(time.time() - t_start, 2),
    }
    RELEASE_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Done in {manifest['total_elapsed_seconds']}s.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
