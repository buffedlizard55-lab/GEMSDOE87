#!/usr/bin/env python3
"""Build CONCENTRATION variants of R0 (h33-h33-2-b2) per GEMS agent brief v2.

AXIS=CONCENTRATION. MASS was already built in GEMSDOE88 (ledger-deduped).
Parent ranking at km-scale is H19-5 block mass (the recorded parent field).
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor"))
from gems87.concentration import (  # noqa: E402
    BLOCK_PX,
    MIN_SEP2,
    bincount_blocks,
    block_index,
    density_cv,
    relocate,
)

# Pinned inputs (sha256 of restored bytes). R0 zeros is the named parent.
PINS = {
    "sample_submission": (
        ROOT / "data/bridge/sample_submission.tif",
        "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    ),
    "existing_faults": (
        ROOT / "data/bridge/existing_faults.tif",
        "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    ),
    "r0_zeros": (
        ROOT / ".cache/raw/scored/GEMSDOE32__h33-2-b2-zeros.tif",
        "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
    ),
    "r0_nan": (
        ROOT / ".cache/raw/scored/GEMSDOE32__h33-2-b2-nan.tif",
        "baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd",
    ),
    "p25_nan": (
        ROOT / ".cache/raw/scored/GEMSDOE25__dotted-h19-5-d2-8-nan.tif",
        "91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8",
    ),
    "h19_5": (
        ROOT / ".cache/raw/scored/H19-5-nan.tif",
        "ec1f9b56b83ce33cad781ceb9f104b18fb4f2ff785263a4e89616af4aabdee8d",
    ),
}

PARENT_ID = "h33-h33-2-b2"
PARENT_SHA = PINS["r0_zeros"][1]
DATE_STR = datetime.now(timezone.utc).strftime("%Y%m%d")
COLLAR_PX = 2.0  # inherit parent R0 (see IRREGULARITIES.md); brief default is 3 px for non-PRUNE
AXIS = "CONCENTRATION"
FRACS = (("c10", 0.10, +0.004), ("c15", 0.15, +0.002), ("c20", 0.20, -0.006))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "UNVERIFIED"


def verify_pins() -> None:
    missing = []
    mismatch = []
    for name, (path, expected) in PINS.items():
        if not path.is_file():
            missing.append(f"{name}: {path}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatch.append(f"{name}: {actual} != {expected}")
    if missing or mismatch:
        raise SystemExit(
            "pinned input verification failed\n"
            + "\n".join(f"  missing {m}" for m in missing)
            + "\n".join(f"  sha {m}" for m in mismatch)
        )


def load_band(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        return src.read(1), src.profile.copy()


def rebuild_r0(p25: np.ndarray, dist: np.ndarray) -> np.ndarray:
    return (np.nan_to_num(p25) > 0.5) & (dist > COLLAR_PX)


def write_geotiff(path: Path, array: np.ndarray, profile: dict, nodata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prof = profile.copy()
    prof.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=nodata,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
        interleave="band",
    )
    prof.pop("predictor", None)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(array.astype(np.float32, copy=False), 1)
        dst.update_tags(AREA_OR_POINT="Area")


def reread_check(
    path: Path,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    dist: np.ndarray,
    expect_nan_outside: bool,
    expect_dots: int,
) -> dict:
    with rasterio.open(path) as src:
        arr = src.read(1)
        meta = {
            "crs": str(src.crs),
            "shape": [src.height, src.width],
            "dtype": src.dtypes[0],
            "count": src.count,
            "transform": [float(v) for v in tuple(src.transform)[:6]],
            "nodata": None
            if src.nodata is None or (isinstance(src.nodata, float) and np.isnan(src.nodata))
            else float(src.nodata),
            "nodata_is_nan": bool(
                src.nodata is not None
                and isinstance(src.nodata, float)
                and np.isnan(src.nodata)
            ),
        }
    inside = arr[footprint]
    outside = arr[~footprint]
    dots = np.nan_to_num(arr) > 0.5
    finite_inside = np.isfinite(inside)
    report = {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "meta": meta,
        "n_dots": int(dots.sum()),
        "n_on_catalogue": int((dots & catalogue).sum()),
        "n_le_2px": int((dist[dots] <= COLLAR_PX).sum()) if dots.any() else 0,
        "n_le_3px": int((dist[dots] <= 3.0).sum()) if dots.any() else 0,
        "min_dist_px": float(dist[dots].min()) if dots.any() else None,
        "nan_inside": int((~finite_inside).sum()),
        "outside_nan": int(np.isnan(outside).sum()) if outside.size else 0,
        "outside_zero": int((outside == 0).sum()) if outside.size else 0,
        "inside_01": bool(
            finite_inside.all()
            and ((inside >= 0.0) & (inside <= 1.0)).all()
        ),
        "inside_binary": bool(
            finite_inside.all()
            and np.isin(inside, [0.0, 1.0]).all()
        ),
    }
    errors = []
    if meta["count"] != 1:
        errors.append("not single band")
    if meta["dtype"] != "float32":
        errors.append("dtype")
    if meta["shape"] != [3730, 3292]:
        errors.append("shape")
    if meta["crs"] not in ("EPSG:32611", "EPSG:32611"):
        if "32611" not in (meta["crs"] or ""):
            errors.append(f"crs {meta['crs']}")
    if meta["transform"] != [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]:
        errors.append("transform")
    if report["n_dots"] != expect_dots:
        errors.append(f"n_dots {report['n_dots']} != {expect_dots}")
    if report["n_on_catalogue"] != 0:
        errors.append("catalogue mass")
    if report["n_le_2px"] != 0:
        errors.append("collar 2px")
    if report["nan_inside"] != 0:
        errors.append("nan inside")
    if not report["inside_01"]:
        errors.append("range")
    if expect_nan_outside:
        if report["outside_nan"] != int((~footprint).sum()):
            errors.append("outside not all NaN")
    else:
        if report["outside_zero"] != int((~footprint).sum()):
            errors.append("outside not all 0")
        if np.isnan(arr).any():
            errors.append("zeros file contains NaN")
    report["errors"] = errors
    report["ok"] = not errors
    return report


def write_zip(tif_path: Path, zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(tif_path.name, date_time=(2026, 10, 23, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, tif_path.read_bytes())
    return sha256_file(zip_path)


def mass_in_top_decile(dots: np.ndarray, prior_counts: np.ndarray, idx: np.ndarray) -> float:
    n_blocks = prior_counts.size
    order = np.argsort(-prior_counts)
    n_top = max(1, n_blocks // 10)
    top = np.zeros(n_blocks, dtype=bool)
    top[order[:n_top]] = True
    return float(top[idx[dots]].mean()) if dots.any() else 0.0


def mechanism_card(value: str, stats: dict) -> dict:
    cv0 = stats["cv_before"]["cv_count_occupied"]
    cv1 = stats["cv_after"]["cv_count_occupied"]
    common = {
        "block_px": BLOCK_PX,
        "block_m": BLOCK_PX * 100,
        "prior": "H19-5 block sum (parent field mass)",
        "cv_count_occupied_before": cv0,
        "cv_count_occupied_after": cv1,
        "pct_changed": stats["pct_changed"],
        "n_dots": stats["n_dots"],
        "frac_mass_top_decile_before": stats["frac_top_before"],
        "frac_mass_top_decile_after": stats["frac_top_after"],
        "n_added_on_h19": stats["n_added_on_prior_field"],
        "mean_displacement_px": stats["mean_displacement_px"],
    }
    if value == "c10":
        return {
            **common,
            "hypothesis": (
                "Unmapped geothermal-indicative faults cluster at ~1 km with the same "
                "H19-5 lineament corridors that already host R0. Relocating the lowest "
                "10% of R0 dots (H19-5-poor blocks) onto unused H19-5 pixels in H19-5-rich "
                "blocks raises triangular-kernel credit on line-like new-fault truth."
            ),
            "mechanism": (
                "DTI = T/(0.2T + 0.2(S-M) + 0.8|G|), R=300 m. Line-like truth lowers the "
                "isolated-dot bar (~0.056 at DTI 0.28). Km-scale concentration matches "
                "Great Basin segment length and GeoDAWN ~400 m line-spacing uncertainty. "
                "Count, 2 px collar, and sqrt(8) spacing are held fixed so only allocation "
                "changes."
            ),
            "non_fault_mimic": (
                "Pleistocene Lahontan benches, Miocene caldera rings, and unfaulted "
                "intrusive contacts also form km-scale H19-5 ridges; concentrating onto "
                "those adds FP_w with no T."
            ),
            "predicted_sign_size": (
                "MODEL predicted live delta +0.004 (range -0.010 to +0.012). Parent "
                f"occupied-block CV is {cv0:.3f} vs reported best-file band 0.51-0.59; "
                f"after c10 CV={cv1:.3f}. Small because only 10% of dots move."
            ),
            "falsifier": (
                "If live RECEIPT drops <= -0.01, km-scale H19-5 concentration is dominated "
                "by non-fault ridges or parent allocation is already sufficient. If live "
                "rises >= +0.01, advance to c15/c20."
            ),
        }
    if value == "c15":
        return {
            **common,
            "hypothesis": (
                "A 15% relocation is large enough to show whether geothermal new-fault "
                "mass is km-clustered without emptying entire low-prior corridors that "
                "may still host isolated blind splays."
            ),
            "mechanism": (
                "Same DTI kernel and H19-5 block prior as c10; 15% is the midpoint of the "
                "brief's 10-20% window. Low-prior singleton 1 km blocks (parent density 1) "
                "are drained first; high-prior blocks receive unused H19-5 pixels first."
            ),
            "non_fault_mimic": (
                "Playal shorelines and E-W GeoDAWN flight-line corrugation that survive "
                "H19-5 will be amplified 1.5x relative to c10."
            ),
            "predicted_sign_size": (
                "MODEL predicted live delta +0.002 (range -0.014 to +0.012). Near-null "
                f"because parent CV {cv0:.3f} already sits above 0.51-0.59; after "
                f"c15 CV={cv1:.3f}."
            ),
            "falsifier": (
                "If live RECEIPT on c15 exceeds c10 by >= +0.01, the axis is unsaturated "
                "and c20 is justified. If it underperforms c10 by >= 0.01, stop increasing "
                "concentration."
            ),
        }
    return {
        **common,
        "hypothesis": (
            "Doubling the relocation to 20% over-concentrates onto the strongest H19-5 "
            "corridors, pushing occupied-block CV well above the 0.51-0.59 band of the "
            "best historical files and starving isolated new-fault tips."
        ),
        "mechanism": (
            "Each relocated dot still costs 0.2 in the DTI denominator. Beyond ~15% the "
            "marginal T from packing more dots into already-covered 300 m kernels falls "
            "below that cost unless private truth is more clustered than the parent field."
        ),
        "non_fault_mimic": (
            "Range-front lithologic contacts (gravity/magnetic edges without slip) that "
            "H19-5 already over-weights; 20% concentration piles FP_w onto those contacts."
        ),
        "predicted_sign_size": (
            "MODEL predicted live delta -0.006 (range -0.020 to +0.006). Negative because "
            f"occupied-block CV goes {cv0:.3f} -> {cv1:.3f}, outside the 0.51-0.59 band."
        ),
        "falsifier": (
            "If live RECEIPT improves >= +0.01, private new-fault density is more clustered "
            "than the public catalogue and MASS-add / further CONC is warranted."
        ),
    }


def form_note(value: str, n_dots: int, pct: float, pred: float) -> str:
    sign = f"{pred:+.3f}"
    note = (
        f"h33-2-b2 CONC{value} {n_dots} move{pct:.0f}% lo->hi 1km; "
        f"pred {sign} MODEL; parent 0.2778 CLAIM"
    )
    if len(note) > 140:
        raise ValueError(f"note {len(note)} > 140: {note}")
    return note


def main() -> int:
    verify_pins()
    git = git_sha()
    sample, sample_prof = load_band(PINS["sample_submission"][0])
    existing, _ = load_band(PINS["existing_faults"][0])
    r0_zeros, r0z_prof = load_band(PINS["r0_zeros"][0])
    r0_nan, r0n_prof = load_band(PINS["r0_nan"][0])
    p25, _ = load_band(PINS["p25_nan"][0])
    h19, _ = load_band(PINS["h19_5"][0])

    footprint = np.isfinite(sample)
    catalogue = existing == 1
    dist = distance_transform_edt(~catalogue).astype(np.float32)
    parent = r0_zeros > 0.5
    parent_nan = np.nan_to_num(r0_nan) > 0.5
    if not np.array_equal(parent, parent_nan):
        raise SystemExit("R0 zeros/nan supports differ")
    rebuilt = rebuild_r0(p25, dist)
    if not np.array_equal(rebuilt, parent):
        extra = int((rebuilt & ~parent).sum())
        missing = int((~rebuilt & parent).sum())
        raise SystemExit(
            f"R0 rebuild pixel identity failed extra={extra} missing={missing}; "
            "refusing to approximate the parent"
        )
    n_parent = int(parent.sum())
    if n_parent != 37654:
        raise SystemExit(f"unexpected parent n_dots {n_parent}")
    parent_d = dist[parent]
    if (parent_d <= COLLAR_PX).any() or (parent & catalogue).any() or (parent & ~footprint).any():
        raise SystemExit("parent violates collar/catalogue/footprint")

    h19_pos = np.nan_to_num(h19) > 0.5
    if (parent & ~h19_pos).any():
        raise SystemExit("parent is not a subset of H19-5; ranking recipe broken")
    allowed = footprint & (dist > COLLAR_PX) & ~catalogue
    idx, nby, nbx = block_index(parent.shape, BLOCK_PX)
    n_blocks = nby * nbx
    prior_counts = bincount_blocks(idx, h19_pos, n_blocks)
    foot_counts = bincount_blocks(idx, footprint, n_blocks)
    parent_counts = bincount_blocks(idx, parent, n_blocks)
    cv_parent = density_cv(parent_counts, foot_counts)
    print(
        json.dumps(
            {
                "parent_n": n_parent,
                "rebuild_pixel_identity": True,
                "parent_sha256": PARENT_SHA,
                "parent_min_dist": float(parent_d.min()),
                "parent_n_le3": int((parent_d <= 3).sum()),
                "cv_parent": cv_parent,
                "git": git,
            },
            indent=2,
        )
    )

    releases = ROOT / "releases"
    ledger_dir = ROOT / "ledger"
    evidence_dir = ROOT / "docs" / "evidence"
    releases.mkdir(exist_ok=True)
    ledger_dir.mkdir(exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    cards = {}
    build_receipts = []
    known_shas = {
        PARENT_SHA,
        PINS["r0_nan"][1],
        "7132935e1210208cfbc5dc02d0d393816b7e6b35a706fce44020a3513b7fa201",
        "82673b574213e45cce34f26f6c8918f99ba78ef04f1a41ec420f1a8559329474",
        "6c73303cd5055a5af1dc0801a78821db66d8dcd28ab9244d34341c73836e2c4d",
        "1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69",
        "f6833b831d91618577f73522f4a269f1f878a982cc38ba2bbb27d942396b2403",
    }

    for value, frac, pred in FRACS:
        n_move = int(round(n_parent * frac))
        result = relocate(
            parent, h19_pos, allowed, n_move, block_px=BLOCK_PX, min_sep2=MIN_SEP2
        )
        dots = result["dots"]
        after_counts = bincount_blocks(idx, dots, n_blocks)
        cv_after = density_cv(after_counts, foot_counts)
        rem = np.column_stack([result["removed_rows"], result["removed_cols"]]).astype(np.float64)
        add = np.column_stack([result["added_rows"], result["added_cols"]]).astype(np.float64)
        # Mean nearest-neighbour displacement of relocated pairs (removed -> added, greedy by order).
        # Order is not a physical pairing; report RMS shift of added vs removed centroids plus
        # mean |Δ| of matched order as a descriptive statistic.
        mean_disp = float(np.linalg.norm(add - rem, axis=1).mean()) if n_move else 0.0
        frac_top_before = mass_in_top_decile(parent, prior_counts, idx)
        frac_top_after = mass_in_top_decile(dots, prior_counts, idx)
        changed = parent ^ dots
        pct = 100.0 * int(changed.sum()) / (2 * n_parent) * 2  # each move touches 1 parent slot
        pct = float(result["pct_changed"])
        if not (1.0 <= pct <= 50.0):
            raise SystemExit(f"{value} pct_changed {pct} outside 1-50%")
        if int(dots.sum()) != n_parent:
            raise SystemExit("count not fixed")
        if (dots & catalogue).any() or (dist[dots] <= COLLAR_PX).any():
            raise SystemExit("collar/catalogue violated")

        nan_arr = np.full(parent.shape, np.nan, dtype=np.float32)
        nan_arr[footprint] = 0.0
        nan_arr[dots] = 1.0
        zeros_arr = np.zeros(parent.shape, dtype=np.float32)
        zeros_arr[dots] = 1.0

        # Temporary names until sha8 of the NaN file is known.
        tmp_nan = releases / f".tmp-{value}-nan.tif"
        tmp_zeros = releases / f".tmp-{value}-zeros.tif"
        write_geotiff(tmp_nan, nan_arr, r0n_prof, nodata=float("nan"))
        write_geotiff(tmp_zeros, zeros_arr, r0z_prof, nodata=None)
        nan_rep = reread_check(tmp_nan, footprint, catalogue, dist, True, n_parent)
        z_rep = reread_check(tmp_zeros, footprint, catalogue, dist, False, n_parent)
        if not nan_rep["ok"] or not z_rep["ok"]:
            raise SystemExit(f"reread failed {value}: {nan_rep['errors']} {z_rep['errors']}")
        sha_nan = nan_rep["sha256"]
        sha_z = z_rep["sha256"]
        if sha_nan in known_shas or sha_z in known_shas:
            raise SystemExit(f"sha already in ledger {sha_nan[:8]}")
        known_shas.add(sha_nan)
        known_shas.add(sha_z)
        sha8 = sha_nan[:8]
        stem = f"{PARENT_ID}-{AXIS[:4]}{value}-{DATE_STR}-{sha8}"
        nan_path = releases / f"{stem}.tif"
        zeros_path = releases / f"{stem}-zeros.tif"
        tmp_nan.replace(nan_path)
        tmp_zeros.replace(zeros_path)
        # Re-read after rename (same bytes).
        nan_rep = reread_check(nan_path, footprint, catalogue, dist, True, n_parent)
        z_rep = reread_check(zeros_path, footprint, catalogue, dist, False, n_parent)
        if nan_rep["sha256"] != sha_nan or z_rep["sha256"] != sha_z:
            raise SystemExit("sha changed after rename")

        nan_zip = releases / f"{stem}.zip"
        zeros_zip = releases / f"{stem}-zeros.zip"
        zip_sha = write_zip(nan_path, nan_zip)
        zzip_sha = write_zip(zeros_path, zeros_zip)
        note = form_note(value, n_parent, pct, pred)
        stats = {
            "id": stem,
            "value": value,
            "n_dots": n_parent,
            "n_move": n_move,
            "pct_changed": round(pct, 4),
            "cv_before": cv_parent,
            "cv_after": cv_after,
            "frac_top_before": frac_top_before,
            "frac_top_after": frac_top_after,
            "n_added_on_prior_field": int(result["n_added_on_prior_field"]),
            "ordered_pair_displacement_px_descriptive_only": mean_disp,
            "note": note,
            "note_len": len(note),
            "predicted_change": pred,
            "sha256": sha_nan,
            "sha256_zeros": sha_z,
            "nan_reread": nan_rep,
            "zeros_reread": z_rep,
            "zip_sha256": zip_sha,
            "zeros_zip_sha256": zzip_sha,
        }
        cards[stem] = mechanism_card(value, stats)
        rows.append(
            {
                "id": stem,
                "parent": PARENT_ID,
                "axis": AXIS,
                "value": value,
                "n_dots": n_parent,
                "pct_changed": f"{pct:.2f}",
                "sha256": sha_nan,
                "sha256_zeros": sha_z,
                "status": "BUILT",
                "predicted_change": f"{pred:+.3f}",
                "receipt_score": "",
                "date": "",
                "description": (
                    f"Move {pct:.0f}% of R0 dots from lowest-H19-5 1 km blocks to "
                    f"highest-H19-5 blocks; count fixed; CV_occ {cv_parent['cv_count_occupied']:.3f}"
                    f"->{cv_after['cv_count_occupied']:.3f}."
                ),
            }
        )
        build_receipts.append(stats)
        print(
            f"{stem} dots={n_parent} moved={n_move} pct={pct:.2f} "
            f"cv {cv_parent['cv_count_occupied']:.4f}->{cv_after['cv_count_occupied']:.4f} "
            f"topdec {frac_top_before:.3f}->{frac_top_after:.3f} "
            f"h19add={result['n_added_on_prior_field']} disp={mean_disp:.2f} "
            f"sha8={sha8} note={len(note)}"
        )

        # Repo-local validators (NaN file vs sample; zeros file vs gems57 if importable).
        from scripts.validate_submission import validate_submission

        v = validate_submission(nan_path, PINS["sample_submission"][0])
        if not v["ready"]:
            raise SystemExit(f"validate_submission failed {value}: {v['errors']}")
        stats["validate_submission_ready"] = True

        try:
            from gems57.validate import validate as g57_validate

            g57 = g57_validate(zeros_path, footprint, catalogue)
            stats["gems57_all_checks_passed"] = bool(g57.get("all_checks_passed"))
            if not g57.get("all_checks_passed"):
                raise SystemExit(f"gems57 validate failed {value}: {g57.get('checks')}")
        except ImportError:
            sys.path.insert(0, str(ROOT / "vendor"))
            from gems57.validate import validate as g57_validate

            g57 = g57_validate(zeros_path, footprint, catalogue)
            stats["gems57_all_checks_passed"] = bool(g57.get("all_checks_passed"))
            if not g57.get("all_checks_passed"):
                raise SystemExit(f"gems57 validate failed {value}: {g57.get('checks')}")

    # Ledger: MASS rows from GEMSDOE88 (dedupe) + this session.
    mass_rows = [
        {
            "id": "h33-h33-2-b2-MASSm10minus-20261023-7132935e",
            "parent": PARENT_ID,
            "axis": "MASS",
            "value": "m10minus",
            "n_dots": 33889,
            "pct_changed": "10.00",
            "sha256": "7132935e1210208cfbc5dc02d0d393816b7e6b35a706fce44020a3513b7fa201",
            "sha256_zeros": "58d9ebdbdd9234d5bbe8e248c1b385d7b7ffb03461c94f9624c2eb02d13ac412",
            "status": "BUILT",
            "predicted_change": "-0.008",
            "receipt_score": "",
            "date": "",
            "description": "GEMSDOE88 MASS drop 10%; not rebuilt this session (axis,value unique).",
        },
        {
            "id": "h33-h33-2-b2-MASSm10plus-20261023-82673b57",
            "parent": PARENT_ID,
            "axis": "MASS",
            "value": "m10plus",
            "n_dots": 41419,
            "pct_changed": "10.00",
            "sha256": "82673b574213e45cce34f26f6c8918f99ba78ef04f1a41ec420f1a8559329474",
            "sha256_zeros": "384f2a3c802b12823ee4510215d6fe825140ed3842b57e80278fe940c37bc6df",
            "status": "BUILT",
            "predicted_change": "+0.004",
            "receipt_score": "",
            "date": "",
            "description": "GEMSDOE88 MASS add 10%; not rebuilt this session (axis,value unique).",
        },
        {
            "id": "h33-h33-2-b2-MASSm20minus-20261023-6c73303c",
            "parent": PARENT_ID,
            "axis": "MASS",
            "value": "m20minus",
            "n_dots": 30123,
            "pct_changed": "20.00",
            "sha256": "6c73303cd5055a5af1dc0801a78821db66d8dcd28ab9244d34341c73836e2c4d",
            "sha256_zeros": "c31659134bf513a768a1566c0527dc111df60e209ad14eecf7291adab67864f2",
            "status": "BUILT",
            "predicted_change": "-0.018",
            "receipt_score": "",
            "date": "",
            "description": "GEMSDOE88 MASS drop 20%; not rebuilt this session (axis,value unique).",
        },
    ]
    fieldnames = [
        "id",
        "parent",
        "axis",
        "value",
        "n_dots",
        "pct_changed",
        "sha256",
        "sha256_zeros",
        "status",
        "predicted_change",
        "receipt_score",
        "date",
        "description",
    ]
    with (ledger_dir / "submissions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in mass_rows + rows:
            writer.writerow(row)
    (ledger_dir / "mechanism_cards.json").write_text(
        json.dumps(cards, indent=2) + "\n", encoding="utf-8"
    )
    (evidence_dir / "exp87_concentration_build.json").write_text(
            json.dumps(
            {
                "session_utc": datetime.now(timezone.utc).isoformat(),
                "git_sha": git,
                "axis": AXIS,
                "parent_id": PARENT_ID,
                "parent_sha256": PARENT_SHA,
                "parent_rebuild_pixel_identity": True,
                "parent_reencode_sha_matched": False,
                "collar_px": COLLAR_PX,
                "block_px": BLOCK_PX,
                "min_sep2": MIN_SEP2,
                "cv_parent": cv_parent,
                "variants": build_receipts,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("wrote ledger, mechanism cards, evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
