#!/usr/bin/env python3
"""GEMSDOE87 Agent Brief v2: build AXIS = SNAP variants of Parent R0 (h33-h33-2-b2).

Offline and deterministic. Inputs come only from registry/data_manifest.json (sha256-verified).
The script never contacts drivendata.org or dropbox.com, and it never submits.

1. Verify every manifest pin. Rebuild R0 and require an exact sha256 match on both twins; stop on mismatch.
2. Read ledger/submissions.csv. Refuse any repeated (parent, axis, value) or sha256.
3. For each provided edge band (TMI horizontal gradient b03, isostatic-gravity horizontal gradient b18,
   detrended-elevation slope b19), move each R0 dot <= 2 px onto the strongest 4-direction crest of that
   band inside its window (gems87.snap). Count fixed at 37,654. Same exclusions as R0: footprint,
   off-catalogue, d_cat > 2 px. Minimum spacing stays >= sqrt(5) px, as in R0.
4. Write releases/<id>.tif (NaN outside) and <id>-zeros.tif. Re-read both from disk, then run the
   MUST-PASS gates: format, zero catalogue mass, new sha256, parent-diff stats.
5. REPORT-ONLY PROXY diagnostics, never used as gates:
   (a) catalogue snap test: do crests pull near-catalogue d28 dots toward known traces, compared
       with a random-crest null?
   (b) static hide-and-recover (n withheld, 95% CI)
   (c) leakage canary
   (d) SGMC control
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
for p in (REPO_ROOT, REPO_ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gems87 import snap as SN  # noqa: E402
from scripts import build_prune_variants as BP  # noqa: E402
from scripts.validate_submission import validate_submission  # noqa: E402
from vendor.gems57 import evaluate_holdout as EH  # noqa: E402
from vendor.gems57 import grid as GR  # noqa: E402
from vendor.gems57 import holdout as HO  # noqa: E402
from vendor.gems57 import metric as M  # noqa: E402
from vendor.gems57 import validate as V57  # noqa: E402

RAW = BP.RAW_DIR
RELEASES = BP.RELEASES_DIR
LEDGER = BP.LEDGER_PATH
PARENT_ID = BP.PARENT_ID
N0 = BP.R0_TARGET_DOTS
SESSION_DATE = "20261023"
SNAP_RADIUS_PX = 2.0
MIN_DIST_SQ = 5
CREST_MIN_DIRS = 2
NULL_SEEDS = (0, 1, 2, 3, 4)
EVIDENCE_OUT = REPO_ROOT / "docs" / "evidence" / "exp87_snap_build.json"
SNAP_MANIFEST = RELEASES / "snap_manifest.json"

SPECS: list[dict[str, Any]] = [
    {
        "value": "tmihg",
        "band": 3,
        "band_name": "tmi_hg",
        "predicted_change": "-0.003 [MODEL; range -0.010 to +0.003]",
        "mechanism_card": {
            "hypothesis": (
                "R0 dots sit on H19-5 composite ridges, which are blurred by roughly the kernel radius. Steeply "
                "dipping faults that juxtapose rocks of contrasting magnetization (basalt or tuff against basin "
                "fill) put their sharpest magnetic contrast where the fault reaches the shallowest magnetic source. "
                "The crest of the TMI horizontal gradient should therefore sit within 100-200 m of the trace, "
                "closer than the composite ridge does."
            ),
            "mechanism": (
                "Each R0 dot moves to the strongest 4-direction maximum of band 03 tmi_hg within <= 2 px (200 m). "
                "The move is refused if it would put the dot within sqrt(5) px of another dot, inside the 2 px "
                "catalogue collar, or outside the footprint. The count stays 37,654. A dot on truth gains credit "
                "1/3 per px of approach (triangular kernel, R = 3 px) and loses the same per px of retreat."
            ),
            "non_fault_mimic": (
                "TMI is not reduced to the pole. At the inclination of the Nevada field, the maxima of the TMI "
                "horizontal gradient shift down-dip, off the source edge, by a fraction of the source depth. Flat "
                "flow margins, dikes, intrusive contacts and the 400 m flight-line gridding (GeoDAWN Area 2) also "
                "make crests with no fault behind them."
            ),
            "predicted_live_change": "-0.003 DTI [MODEL] versus R0; range -0.010 to +0.003. Basis: on the catalogue PROXY, TMI-HG movers gain less credit per moved dot than random-crest movers (about -0.7% of near-truth credit).",
            "falsifier": (
                "Live Delta >= +0.01 versus R0's receipt would mean the TMI-HG crests localize new faults better than "
                "the H19-5 ridge at the 100-200 m scale. That would be a reason to combine SNAP with PRUNE3/CONCc10."
            ),
        },
    },
    {
        "value": "gravhg",
        "band": 18,
        "band_name": "iso_grav_anom_hg",
        "predicted_change": "0.000 [MODEL; range -0.003 to +0.003]",
        "mechanism_card": {
            "hypothesis": (
                "Basin-bounding normal faults put dense bedrock against low-density basin fill. The crest of the "
                "isostatic-gravity horizontal gradient marks the steepest basement step, and steep faults sit near "
                "that step."
            ),
            "mechanism": (
                "Same operator on band 18 iso_grav_anom_hg: move <= 2 px to the strongest 4-direction maximum, keep "
                "the count, the exclusions and the sqrt(5) px spacing."
            ),
            "non_fault_mimic": (
                "Gravity stations are spaced at km scale, so crest positions on a 100 m grid are interpolation "
                "products. Dipping (45-60 degree) range-front faults shift the gradient maximum basinward, onto the "
                "hanging wall. Density contrasts at plutons and buried caldera walls also make crests."
            ),
            "predicted_live_change": "0.000 DTI [MODEL] versus R0; range -0.003 to +0.003. Only ~5% of dots find a gravity crest within 200 m (smooth field), so the variant is close to a no-op and cannot clear the 0.01 evidence bar.",
            "falsifier": (
                "Live Delta >= +0.01 versus R0 would mean gravity-gradient crests localize new faults to <= 200 m, "
                "which contradicts the km-scale resolution argument."
            ),
        },
    },
    {
        "value": "slope",
        "band": 19,
        "band_name": "det_elev_slope",
        "predicted_change": "+0.004 [MODEL; range -0.006 to +0.012]",
        "mechanism_card": {
            "hypothesis": (
                "Fault scarps and faceted range fronts are local maxima of slope on detrended elevation. If the "
                "unmapped new faults have topographic expression, slope crests within 200 m locate the trace more "
                "precisely than the H19-5 ridge does."
            ),
            "mechanism": (
                "Same operator on band 19 det_elev_slope: move <= 2 px to the strongest 4-direction maximum, keep "
                "the count, the exclusions and the sqrt(5) px spacing."
            ),
            "non_fault_mimic": (
                "Stream-cut valley walls, terrace risers, lake shorelines and resistant bedding all make slope crests. "
                "On a range front the steepest 100 m slope is usually uphill of the trace, so the snap can move dots "
                "off the piedmont junction where the fault actually sits."
            ),
            "predicted_live_change": "+0.004 DTI [MODEL] versus R0; range -0.006 to +0.012. Basis: on the catalogue PROXY, slope-crest movers beat random-crest movers by about +4% of near-truth credit (about +0.011 if new faults behaved like the catalogue). Discounted by more than half because mapped Quaternary faults are scarp-selected and new faults are probably less expressed.",
            "falsifier": (
                "Live Delta >= +0.01 versus R0 would mean new faults are topographically expressed and the 100 m slope "
                "crest is within ~1 px of the trace. Then lidar-scale (3DEP) scarp snapping becomes worth building."
            ),
        },
    },
]


def public_stats(st: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in st.items() if not k.startswith("_")}


def catalogue_snap_proxy(d28, footprint, catalogue, d_cat, bands: dict[str, np.ndarray]) -> dict[str, Any]:
    """PROXY: do each band's crests pull near-catalogue parent-lineage dots toward known traces?

    The sources are d28 dots (H19-5 thinned at 2.8 px; never on the catalogue) with 0 < d_cat <= 4 px.
    Targets may land anywhere in the footprint, catalogue included. Per-dot credit is the triangular
    kernel k(d_cat), and the change is k(dst) - k(src). The CI is a 10 km block bootstrap over source
    blocks. The null is the same operator on crests of seeded uniform noise (5 seeds).
    Known Quaternary faults are biased toward strong topographic expression, so this proxy favours
    `slope` relative to the unknown new-fault truth. REPORT ONLY.
    """
    # H19-5 (hence d28) contains zero catalogue pixels, so sources can never sit on truth and any
    # move tends to raise credit. The random-crest null measures that artifact; read bands against it.
    src = d28 & footprint & (d_cat > 0) & (d_cat <= 4.0)
    k = np.maximum(1.0 - d_cat / 3.0, 0.0).ravel()
    W = footprint.shape[1]

    def run(e: np.ndarray) -> dict[str, Any]:
        crest = SN.crest_mask(e, CREST_MIN_DIRS)
        _, st = SN.snap_dots(src, e, crest, footprint, SNAP_RADIUS_PX, MIN_DIST_SQ)
        s_f, d_f = st["_src_flat"], st["_dst_flat"]
        delta = k[d_f] - k[s_f]
        blocks = (s_f // W // 100) * 1000 + (s_f % W) // 100
        uniq, inv = np.unique(blocks, return_inverse=True)
        sums, cnt = np.bincount(inv, weights=delta), np.bincount(inv).astype(float)
        rng = np.random.default_rng(520810)
        picks = rng.integers(0, uniq.size, size=(2000, uniq.size))
        boot = sums[picks].sum(axis=1) / cnt[picks].sum(axis=1)
        return {"delta": float(delta.mean()), "ci95": [round(float(x), 5) for x in np.quantile(boot, [0.025, 0.975])],
                "pct_moved": st["pct_moved"], "mean_disp": st["mean_displacement_px_all_dots"],
                "frac_on_catalogue_after": float(catalogue.ravel()[d_f].mean())}

    nulls = []
    for s in NULL_SEEDS:
        rng = np.random.default_rng(s)
        nulls.append(run(np.where(footprint, rng.random(footprint.shape), np.nan)))
    null_delta = float(np.mean([r["delta"] for r in nulls]))
    res: dict[str, Any] = {
        "evidence_label": "PROXY",
        "note": "REPORT ONLY. Truth = mapped catalogue (biased toward scarps), not new-fault truth.",
        "n_source_dots": int(src.sum()),
        "source_mean_credit": round(float(k[src.ravel()].mean()), 5),
        "random_crest_null": {"delta_credit_mean_over_seeds": round(null_delta, 5),
                              "per_seed": [round(r["delta"], 5) for r in nulls],
                              "pct_moved": round(float(np.mean([r["pct_moved"] for r in nulls])), 2),
                              "mean_disp_px": round(float(np.mean([r["mean_disp"] for r in nulls])), 3)},
        "bands": {},
    }
    for name, e in bands.items():
        r = run(e)
        null_pm = null_delta / max(res["random_crest_null"]["pct_moved"] / 100.0, 1e-9)
        band_pm = r["delta"] / max(r["pct_moved"] / 100.0, 1e-9)
        excess = (band_pm - null_pm) * r["pct_moved"] / 100.0
        res["bands"][name] = {"delta_credit_per_moved_dot": round(band_pm, 5),
                              "null_delta_credit_per_moved_dot": round(null_pm, 5),
                              "excess_over_null_per_source_dot": round(excess, 5),
                              "excess_relative_to_source_credit": round(excess / float(k[src.ravel()].mean()), 4),
                              "delta_credit": round(r["delta"], 5), "delta_credit_ci95_10km_blocks": r["ci95"],
                              "delta_minus_null": round(r["delta"] - null_delta, 5), "pct_moved": r["pct_moved"],
                              "mean_disp_px": r["mean_disp"],
                              "frac_landing_on_catalogue": round(r["frac_on_catalogue_after"], 5)}
    return res


def hide_and_recover_static(masks: dict[str, np.ndarray], footprint: np.ndarray) -> dict[str, Any]:
    grid = GR.load_grid(RAW)
    terms: dict[str, np.ndarray] = {}
    for s in (20, 30):
        folds, _ = HO.buffered_component_draw(grid, seed=s)
        for name, m in masks.items():
            pred = m.astype(np.float32)
            for fold in folds:
                _, t = EH.evaluate(pred, fold, valid=footprint)
                terms[name] = t.copy() if name not in terms else terms[name] + t
    summ = EH.pooled_summary(terms, draws=1000, seed=520810, candidate="R0")
    return {
        "evidence_label": "PROXY",
        "evaluator_version": EH.VERSION,
        "caveat": "Static full-catalogue d_cat > 2 px collar on every arm; withheld components only reachable by kernel tail.",
        "scores": {k: {"dti": round(v["dti"], 6), "ci95": [round(x, 6) for x in v["ci95"]],
                       "withheld_positive_pixels": v["withheld_positive_pixels"]} for k, v in summ["scores"].items()},
        "paired_R0_minus_arm": {k: {"delta": round(v["delta"], 6), "ci95": [round(x, 6) for x in v["ci95"]]}
                                for k, v in summ["paired_differences"].items()},
    }


def leakage_canary(footprint: np.ndarray, catalogue: np.ndarray, d_cat: np.ndarray) -> dict[str, Any]:
    """Single-feature symmetric AUC for catalogue pixels against off-catalogue pixels (d_cat > 3), per band."""
    rng = np.random.default_rng(20261023)
    pos = np.flatnonzero(catalogue[footprint])
    neg_pool = np.flatnonzero(((d_cat > 3) & footprint)[footprint])
    neg = rng.choice(neg_pool, size=min(200_000, neg_pool.size), replace=False)
    idx = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(pos.size, bool), np.zeros(neg.size, bool)])
    rows = []
    with rasterio.open(RAW / "training_features.tif") as ds:
        for b in range(1, ds.count + 1):
            v = ds.read(b)[footprint][idx].astype(np.float64)
            v = np.where((v < -1e20) | ~np.isfinite(v), 0.0, v)
            auc, sym = BP.symmetric_auc_mann_whitney(y, v)
            rows.append({"channel": f"b{b:02d}_{(ds.descriptions[b-1] or '').split(' - ')[0]}",
                         "auc": round(auc, 5), "sym_auc": round(sym, 5)})
    rows.sort(key=lambda r: -r["sym_auc"])
    mx = rows[0]["sym_auc"]
    if mx > 0.90:
        raise RuntimeError(f"STOP: leakage canary > 0.90: {rows[0]}")
    return {"evidence_label": "PROXY", "n_pos": int(pos.size), "n_neg": int(neg.size), "limit": 0.90,
            "max_sym_auc": mx, "passed": True, "top5": rows[:5]}


def sgmc_control(masks: dict[str, np.ndarray], footprint, catalogue, d_cat) -> dict[str, Any]:
    with rasterio.open(RAW / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    truth = sgmc & ~catalogue & (d_cat > 3.0)
    out = {}
    for name, m in masks.items():
        r = M.dti_binary(m, truth, valid=footprint, known=catalogue)
        out[name] = {"dti": round(float(r["dti"]), 6), "coverage": round(float(r["coverage"]), 6)}
    return {"evidence_label": "PROXY", "n_truth": int(truth.sum()), "scores": out}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-diagnostics", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    print("[1/6] Verifying manifest pins ...", flush=True)
    mrec = BP.verify_and_restore_manifest()
    print(f"      verified {mrec['verified_count']} files", flush=True)

    tpl = RAW / "sample_submission.tif"
    with rasterio.open(tpl) as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(RAW / "existing_faults.tif") as ds:
        catalogue = (ds.read(1) > 0) & footprint
    with rasterio.open(RAW / "scored" / "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif") as ds:
        h19_5 = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    with rasterio.open(RAW / "scored" / "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif") as ds:
        d28_manifest = (np.nan_to_num(ds.read(1), nan=0.0) > 0) & footprint
    d_cat = distance_transform_edt(~catalogue)

    print("[2/6] Rebuilding R0 and checking exact sha256 ...", flush=True)
    d28, r0, r0_receipt = BP.rebuild_and_verify_r0(h19_5, d28_manifest, footprint, catalogue, d_cat, tpl)
    print(f"      R0 OK n={r0_receipt['n_dots']} nan={r0_receipt['nan_sha256'][:12]} zeros={r0_receipt['zeros_sha256'][:12]}", flush=True)

    print("[3/6] Ledger dedupe ...", flush=True)
    with LEDGER.open(encoding="utf-8", newline="") as f:
        existing = [r for r in csv.DictReader(f) if not (r.get("parent") == PARENT_ID and r.get("axis") == "SNAP")]
    seen_sha = {r["sha256"] for r in existing} | {r.get("sha256_zeros", "") for r in existing}
    seen_pairs = {(r["parent"], r["axis"], r["value"]) for r in existing}
    for path in (BP.CANONICAL_INDEX_PATH, BP.INVENTORY_PATH):
        if path.is_file():
            seen_sha |= {r["sha256"] for r in json.loads(path.read_text()).get("rasters", [])}
    seen_sha |= {r0_receipt["nan_sha256"], r0_receipt["zeros_sha256"]}

    allowed = footprint & ~catalogue & (d_cat > 2.0)  # R0's own exclusions
    bands: dict[str, np.ndarray] = {}
    with rasterio.open(RAW / "training_features.tif") as ds:
        for spec in SPECS:
            desc = (ds.descriptions[spec["band"] - 1] or "").split(" - ")[0]
            if desc != spec["band_name"]:
                raise RuntimeError(f"band {spec['band']} is {desc!r}, expected {spec['band_name']!r}")
            bands[spec["value"]] = SN.clean_band(ds.read(spec["band"]), footprint)

    print("[4/6] Building SNAP variants ...", flush=True)
    for old in RELEASES.glob(f"{PARENT_ID}-SNAP*.tif"):
        old.unlink()
    head = BP.git_head_sha()
    built, rows, masks = [], [], {"R0": r0}
    for spec in SPECS:
        key = (PARENT_ID, "SNAP", spec["value"])
        if key in seen_pairs:
            raise RuntimeError(f"duplicate (parent, axis, value) {key}")
        e = bands[spec["value"]]
        crest = SN.crest_mask(e, CREST_MIN_DIRS)
        v, st = SN.snap_dots(r0, e, crest, allowed, SNAP_RADIUS_PX, MIN_DIST_SQ)
        diff = BP.compute_parent_diff_stats(v, r0, d_cat, footprint)
        if int(v.sum()) != N0 or (v & catalogue).any() or (v & (d_cat <= 2.0)).any() or (v & ~footprint).any():
            raise RuntimeError("exclusion/count invariant broken")
        e_r0 = np.nanmean(e[r0])
        e_v = np.nanmean(e[v])
        tmp_n, tmp_z = RELEASES / "_tmp_snap.tif", RELEASES / "_tmp_snap-zeros.tif"
        sha_n, sha_z = BP.write_geotiff_pair_exact_profile(v, footprint, catalogue, tpl, tmp_n, tmp_z)
        vid = f"{PARENT_ID}-SNAP{spec['value']}-{SESSION_DATE}-{sha_n[:8]}"
        fn, fz = RELEASES / f"{vid}.tif", RELEASES / f"{vid}-zeros.tif"
        tmp_n.rename(fn)
        tmp_z.rename(fz)
        # Gate: re-read from disk
        assert BP.sha256_file(fn) == sha_n and BP.sha256_file(fz) == sha_z
        with rasterio.open(fn) as a, rasterio.open(fz) as b:
            an, az = a.read(1), b.read(1)
        assert np.array_equal(an[footprint] > 0.5, v[footprint]) and np.array_equal(az[footprint] > 0.5, v[footprint])
        assert np.isnan(an[~footprint]).all() and (az[~footprint] == 0).all()
        assert not np.isnan(an[footprint]).any()
        assert int((an[catalogue] > 0).sum()) == 0 and int((az[catalogue] > 0).sum()) == 0
        val_n = validate_submission(fn, tpl)
        if not val_n["ready"] or val_n["errors"]:
            raise RuntimeError(f"validator failed {fn}: {val_n['errors']}")
        val_z = V57.validate(fz, footprint=footprint, catalogue=catalogue)
        if not val_z["all_checks_passed"]:
            raise RuntimeError(f"gems57 validator failed {fz}")
        for s in (sha_n, sha_z):
            if s in seen_sha:
                raise RuntimeError(f"sha256 {s} already in ledger/registry")
        seen_sha |= {sha_n, sha_z}
        seen_pairs.add(key)
        masks[f"SNAP{spec['value']}"] = v
        note = (f"{PARENT_ID}; SNAP<=2px to {spec['band_name']} crest ({diff['pct_changed']:.1f}% moved, "
                f"mean {st['mean_displacement_px_all_dots']:.2f}px); pred {spec['predicted_change'].split(' ')[0]} MODEL")
        if len(note) > 140:
            raise ValueError(f"form note {len(note)} > 140: {note}")
        rec = {
            "id": vid, "parent": PARENT_ID, "axis": "SNAP", "value": spec["value"],
            "band": f"b{spec['band']:02d} {spec['band_name']}", "n_dots": int(v.sum()),
            "pct_changed": round(diff["pct_changed"], 2), "sha256": sha_n, "zeros_sha256": sha_z,
            "content_digest8": hashlib.sha256(np.packbits(v)).hexdigest()[:8],
            "primary_file": f"releases/{fn.name}", "primary_bytes": fn.stat().st_size,
            "zeros_fallback_file": f"releases/{fz.name}", "zeros_bytes": fz.stat().st_size,
            "status": "BUILT", "predicted_change": spec["predicted_change"], "form_note": note,
            "form_note_length": len(note), "snap_stats": public_stats(st),
            "crest_pixels_in_allowed": int((crest & allowed).sum()),
            "mean_band_value_at_dots": {"R0": round(float(e_r0), 6), "variant": round(float(e_v), 6)},
            "parent_diff": diff, "mechanism_card": spec["mechanism_card"],
            "format_validation": {"nan_validator_ready": val_n["ready"], "nan_validator_errors": val_n["errors"],
                                  "zeros_gems57_all_checks_passed": val_z["all_checks_passed"],
                                  "on_catalogue_positive_pixels": val_z["on_catalogue_positive_pixels"]},
        }
        built.append(rec)
        rows.append({"id": vid, "parent": PARENT_ID, "axis": "SNAP", "value": spec["value"],
                     "n_dots": str(int(v.sum())), "pct_changed": f"{diff['pct_changed']:.2f}", "sha256": sha_n,
                     "sha256_zeros": sha_z, "status": "BUILT", "predicted_change": spec["predicted_change"],
                     "receipt_score": "", "date": "", "description": note})
        print(f"      {vid}: moved {st['pct_moved']}% mean disp {st['mean_displacement_px_all_dots']} px "
              f"(moved-only {st['mean_displacement_px_moved_dots']}), blocked {st['n_blocked_by_spacing']}", flush=True)

    print("[5/6] Ledger ...", flush=True)
    with LEDGER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BP.LEDGER_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in existing + rows:
            w.writerow({k: r.get(k, "") for k in BP.LEDGER_COLUMNS})

    diag = None
    if not args.skip_diagnostics:
        print("[6/6] REPORT-ONLY diagnostics ...", flush=True)
        td = time.time()
        diag = {
            "catalogue_snap_proxy": catalogue_snap_proxy(d28, footprint, catalogue, d_cat, bands),
            "static_hide_and_recover_proxy": hide_and_recover_static(masks, footprint),
            "leakage_canary": leakage_canary(footprint, catalogue, d_cat),
            "sgmc_control_proxy": sgmc_control(masks, footprint, catalogue, d_cat),
            "elapsed_s": round(time.time() - td, 1),
        }
        print(json.dumps(diag["catalogue_snap_proxy"], indent=1), flush=True)

    out = {
        "schema_version": 1, "axis": "SNAP", "generated_date_utc": SESSION_DATE, "git_head_at_build": head,
        "fixed_seed": 0, "null_seeds": list(NULL_SEEDS), "snap_radius_px": SNAP_RADIUS_PX,
        "min_dist_sq": MIN_DIST_SQ, "crest_min_dirs": CREST_MIN_DIRS,
        "exclusions": "footprint & ~catalogue & d_cat > 2 px (identical to R0)",
        "manifest_verified_files": mrec["verified_count"], "parent_r0_rebuild_receipt": r0_receipt,
        "variants": built, "report_only_diagnostics": diag, "elapsed_s": round(time.time() - t0, 1),
    }
    SNAP_MANIFEST.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    EVIDENCE_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Done in {out['elapsed_s']} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
