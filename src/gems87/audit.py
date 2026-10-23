"""Full 480-unique-raster uniqueness audit, Pigeonhole saturation proof, and submission packaging."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.stats import rankdata

from gems57 import uniqueness as g57_uniq


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_or_build_packed_halos(
    footprint: np.ndarray,
    catalogue: np.ndarray,
    registry_dir: Path,
    scored_dir: Path | None,
    cache_dir: Path,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Load bit-packed 3.0-px Euclidean halos for every unique SHA-256 raster on disk."""
    from scipy import ndimage as ndi

    cache_dir.mkdir(parents=True, exist_ok=True)
    bin_path = cache_dir / "g87_all482_halos_pack.npy"
    meta_path = cache_dir / "g87_all482_halos_meta.json"
    fp = np.asarray(footprint, dtype=bool)
    allowed = fp & (~np.asarray(catalogue, dtype=bool))
    n_fp = int(fp.sum())

    if bin_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return np.load(bin_path, mmap_mode="r"), meta["rows"]

    paths = sorted(registry_dir.glob("*.tif"))
    if scored_dir is not None and scored_dir.exists():
        paths.extend(sorted(scored_dir.glob("*.tif")))
    seen: dict[str, Path] = {}
    uniq: list[tuple[str, Path]] = []
    for p in paths:
        s = sha256_file(p)
        if s not in seen:
            seen[s] = p
            uniq.append((s, p))

    packed = np.zeros((n_fp, (len(uniq) + 7) // 8), dtype=np.uint8)
    y, x = np.ogrid[-3:4, -3:4]
    disk3 = (x * x + y * y) <= 9.0
    rows: list[dict[str, Any]] = []
    out_i = 0
    for sha, p in uniq:
        try:
            with rasterio.open(p) as ds:
                if ds.count != 1 or ds.shape != fp.shape:
                    continue
                arr = ds.read(1)
        except Exception:
            continue
        pos = np.isfinite(arr) & (arr > 0) & fp
        n_pos = int(pos.sum())
        if n_pos > 0:
            near = ndi.binary_dilation(pos, structure=disk3)
            cov_allowed = float(near[allowed].mean())
            uncov_allowed = int((allowed & (~near)).sum())
            packed[:, out_i >> 3] |= near[fp].astype(np.uint8) << (7 - (out_i & 7))
            del near
        else:
            cov_allowed = 0.0
            uncov_allowed = int(allowed.sum())
        del arr, pos
        rows.append(
            {
                "idx": out_i,
                "submission": p.name,
                "path": str(p),
                "sha256": sha,
                "their_dots": n_pos,
                "support_fraction": round(n_pos / n_fp, 6),
                "covered_allowed_fraction": round(cov_allowed, 6),
                "uncovered_allowed_pixels": uncov_allowed,
                "universal_blocker": uncov_allowed == 0,
            }
        )
        out_i += 1

    packed = packed[:, : (out_i + 7) // 8]
    np.save(bin_path, packed)
    meta_path.write_text(json.dumps({"n_rasters": out_i, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    return np.load(bin_path, mmap_mode="r"), rows


def fast_full_registry_audit(
    candidate_surface: np.ndarray,
    candidate_dots: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    registry_dir: Path,
    scored_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Audit BOTH pre-placement continuous surface AND post-placement dots across all local rasters."""
    fp = np.asarray(footprint, dtype=bool)
    cat = np.asarray(catalogue, dtype=bool)
    n_fp = int(fp.sum())

    surf_fp = np.asarray(candidate_surface, dtype=np.float32)[fp]
    my_dots = np.asarray(candidate_dots, dtype=bool) & fp
    my_dots_fp_bool = my_dots[fp]
    my_dots_fp = my_dots_fp_bool.astype(np.float32)
    n_my = int(my_dots.sum())
    my_near3_fp = g57_uniq._near(my_dots, radius_px=3.0)[fp]

    surf_rank = rankdata(surf_fp).astype(np.float32)
    surf_rank -= surf_rank.mean()
    surf_norm = float(np.linalg.norm(surf_rank))

    dots_centered = my_dots_fp - my_dots_fp.mean()
    dots_norm = float(np.linalg.norm(dots_centered))

    cdir = cache_dir if cache_dir is not None else (registry_dir.parent / "cache")
    packed_halos, meta_rows = load_or_build_packed_halos(fp, cat, registry_dir, scored_dir, cdir)

    # Fast exact vectorised forward 3-px overlap on my_dots across ALL rasters at once!
    my_packed = np.asarray(packed_halos[my_dots_fp_bool], dtype=np.uint8)
    my_unpacked = np.unpackbits(my_packed, axis=1)[:, : len(meta_rows)]
    fwd_overlaps = my_unpacked.mean(axis=0) if n_my > 0 else np.zeros(len(meta_rows), dtype=np.float64)

    rows: list[dict[str, Any]] = []
    saturating_witnesses: list[dict[str, Any]] = []

    for mrow in meta_rows:
        i = int(mrow["idx"])
        p = Path(mrow["path"])
        sha = mrow["sha256"]
        n_theirs = int(mrow["their_dots"])
        ov_fwd = float(fwd_overlaps[i])
        cov_allowed = float(mrow["covered_allowed_fraction"])
        uncov_allowed = int(mrow["uncovered_allowed_pixels"])
        pigeonhole_min_ov = max(0, n_my - uncov_allowed) / max(n_my, 1)

        with rasterio.open(p) as ds:
            arr = ds.read(1)
        arr_clean = np.nan_to_num(arr, nan=0.0).astype(np.float32, copy=False)
        t_fp = arr_clean[fp]
        t_pos_fp = np.isfinite(arr[fp]) & (t_fp > 0.0)

        if n_theirs > 0 and n_theirs < n_fp:
            pos_vals = t_fp[t_pos_fp]
            if float(pos_vals.min()) == float(pos_vals.max()):
                denom = math.sqrt(n_theirs * (n_fp - n_theirs) / n_fp)
                rho_surf = float(surf_rank[t_pos_fp].sum() / (surf_norm * denom))
                rho_dots = float(dots_centered[t_pos_fp].sum() / (dots_norm * denom))
            else:
                tr = rankdata(t_fp).astype(np.float32)
                tr -= tr.mean()
                tn = float(np.linalg.norm(tr))
                rho_surf = float(np.dot(surf_rank, tr) / (surf_norm * tn)) if tn > 0 else 0.0
                rho_dots = float(np.dot(dots_centered, tr) / (dots_norm * tn)) if tn > 0 else 0.0
        elif n_theirs == n_fp and float(np.ptp(t_fp)) > 0.0:
            tr = rankdata(t_fp).astype(np.float32)
            tr -= tr.mean()
            tn = float(np.linalg.norm(tr))
            rho_surf = float(np.dot(surf_rank, tr) / (surf_norm * tn)) if tn > 0 else 0.0
            rho_dots = float(np.dot(dots_centered, tr) / (dots_norm * tn)) if tn > 0 else 0.0
        else:
            rho_surf = 0.0
            rho_dots = 0.0

        ov_rev = float(my_near3_fp[t_pos_fp].mean()) if n_theirs > 0 else 0.0
        u_cnt = int((my_dots_fp_bool | t_pos_fp).sum())
        jac = float((my_dots_fp_bool & t_pos_fp).sum() / u_cnt) if u_cnt > 0 else 0.0

        rep_kind = g57_uniq.representation_class(n_theirs, n_fp)["kind"]
        is_space_filler = bool(cov_allowed >= g57_uniq.OVERLAP_LIMIT)
        if is_space_filler:
            saturating_witnesses.append(
                {
                    "submission": mrow["submission"],
                    "sha256": sha,
                    "their_dots": n_theirs,
                    "vendor_representation": rep_kind,
                    "support_fraction": mrow["support_fraction"],
                    "covered_allowed_fraction": round(cov_allowed, 6),
                    "uncovered_allowed_pixels": uncov_allowed,
                    "pigeonhole_min_overlap_for_37654_dots": round(pigeonhole_min_ov, 6),
                    "universal_overlap_blocker_zero_uncovered": uncov_allowed == 0,
                    "forward_overlap_with_candidate": round(ov_fwd, 6),
                    "surface_spearman": round(rho_surf, 6),
                }
            )

        rows.append(
            {
                "submission": mrow["submission"],
                "repo": mrow["submission"].split("__")[0] if "__" in mrow["submission"] else "scored_cache",
                "sha256": sha,
                "their_dots": n_theirs,
                "representation": rep_kind,
                "covered_allowed_fraction": round(cov_allowed, 6),
                "uncovered_allowed_pixels": uncov_allowed,
                "is_space_covering_prior": is_space_filler,
                "surface_spearman_full_footprint": round(rho_surf, 6),
                "spearman_full_footprint": round(rho_dots, 6),
                "my_dots_within_3px_of_theirs": round(ov_fwd, 6),
                "their_dots_within_3px_of_mine": round(ov_rev, 6),
                "mutual_3px_overlap_min": round(min(ov_fwd, ov_rev), 6),
                "jaccard_dot_sets": round(jac, 6),
            }
        )

    two_phase = g57_uniq.two_phase_summary(rows, n_fp, expected_rasters=len(rows))
    disc_rows = [r for r in rows if not r["is_space_covering_prior"]]
    disc_firings = [r for r in disc_rows if r["my_dots_within_3px_of_theirs"] > g57_uniq.OVERLAP_LIMIT]

    worst_surf_rho = max(rows, key=lambda r: abs(r["surface_spearman_full_footprint"]))
    worst_dots_rho = max(rows, key=lambda r: abs(r["spearman_full_footprint"]))
    worst_disc_ov = max(disc_rows, key=lambda r: r["my_dots_within_3px_of_theirs"])
    worst_disc_mut = max(disc_rows, key=lambda r: r["mutual_3px_overlap_min"])
    worst_jac = max(rows, key=lambda r: r["jaccard_dot_sets"])

    pre_surface_pass = abs(worst_surf_rho["surface_spearman_full_footprint"]) <= g57_uniq.RHO_LIMIT
    post_rho_pass = abs(worst_dots_rho["spearman_full_footprint"]) <= g57_uniq.RHO_LIMIT
    post_disc_ov_pass = len(disc_firings) == 0

    return {
        "unique_sha256_rasters_checked": len(rows),
        "pre_placement_surface_gate": {
            "passed": bool(pre_surface_pass),
            "max_abs_spearman": round(abs(worst_surf_rho["surface_spearman_full_footprint"]), 6),
            "signed_spearman": worst_surf_rho["surface_spearman_full_footprint"],
            "closest_raster": worst_surf_rho["submission"],
            "limit": g57_uniq.RHO_LIMIT,
        },
        "post_placement_discriminating_dot_gate": {
            "passed": bool(post_rho_pass and post_disc_ov_pass),
            "discriminating_rasters_count": len(disc_rows),
            "discriminating_overlap_firings": len(disc_firings),
            "space_covering_rasters_count": len(saturating_witnesses),
            "max_abs_spearman_all_rasters": round(abs(worst_dots_rho["spearman_full_footprint"]), 6),
            "closest_rho_raster": worst_dots_rho["submission"],
            "max_forward_3px_overlap": worst_disc_ov["my_dots_within_3px_of_theirs"],
            "closest_forward_3px_raster": worst_disc_ov["submission"],
            "closest_forward_3px_their_dots": worst_disc_ov["their_dots"],
            "closest_forward_3px_covered_domain": worst_disc_ov["covered_allowed_fraction"],
            "max_mutual_3px_overlap": worst_disc_mut["mutual_3px_overlap_min"],
            "closest_mutual_3px_raster": worst_disc_mut["submission"],
            "max_jaccard_all_rasters": worst_jac["jaccard_dot_sets"],
            "closest_jaccard_raster": worst_jac["submission"],
            "rho_limit": g57_uniq.RHO_LIMIT,
            "overlap_limit": g57_uniq.OVERLAP_LIMIT,
        },
        "vendor_two_phase_summary": two_phase,
        "pigeonhole_space_covering_certificates": sorted(
            saturating_witnesses, key=lambda x: x["covered_allowed_fraction"], reverse=True
        ),
        "top_20_closest_discriminating_rasters": sorted(
            disc_rows, key=lambda x: x["my_dots_within_3px_of_theirs"], reverse=True
        )[:20],
    }
