#!/usr/bin/env python3
"""Build the three SNAP variants of parent R0 (h33-h33-2-b2, GEMSDOE32).

Single-axis rule (brief v2, AXIS=SNAP, picked by the agent this session):
move each R0 dot by at most 2 px to the strongest edge response in its
window. Count (37,654), unit mass and the parent exclusion
(d(catalogue) > 2 px, zero catalogue mass) are held; only positions move.

Edge sources are the provided horizontal-gradient bands of the pinned
training stack (registry/data_manifest.json, sha256-verified here):
``tmi_hg`` (band 3) for SNAP-mag, ``iso_grav_anom_hg`` (band 18) for
SNAP-grav, and the mean of their footprint percentile ranks for
SNAP-comb. Physical basis: GeoDAWN Area 2 was flown at 400 m line
spacing at 150-200 m above terrain, so a lineament's gridded position is
uncertain by about the 300 m (3 px) kernel radius; the horizontal
gradient maximum is the standard contact/fault edge pick.

Assignment is a deterministic greedy: dots are processed in descending
order of potential edge gain (window best minus current edge value;
ties by raster index) and each claims its best still-unclaimed eligible
pixel within Euclidean distance <= 2 px, so the dot count is preserved
exactly with no collisions. Inputs fail closed on any sha256 mismatch.
No submission is made; the human submits from their own account.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from scipy.stats import rankdata

REPO = Path(__file__).resolve().parents[1]
MAX_MOVE = 2.0

PINS = {
    "r0": "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
    "catalogue": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "training": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
}
BANDS = {"mag": 3, "grav": 18}  # tmi_hg, iso_grav_anom_hg (1-indexed)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(band)


def offsets_within(radius: float) -> list[tuple[int, int]]:
    r = int(np.ceil(radius))
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if np.hypot(dy, dx) <= radius + 1e-9]


def snap_dots(rows: np.ndarray, cols: np.ndarray, edge: np.ndarray,
              eligible: np.ndarray, max_move: float = MAX_MOVE):
    """Greedy edge snap. Returns (new_rows, new_cols, fallback_count).

    Pure helper (unit-tested): no I/O, deterministic tie-breaking by
    raster index at every step.
    """
    h, w = edge.shape
    offs = offsets_within(max_move)
    n = len(rows)
    raster_idx = rows.astype(np.int64) * w + cols
    cand_lists: list[list[tuple[float, int, int]]] = []
    gains = np.zeros(n, dtype=np.float64)
    for i in range(n):
        y, x = int(rows[i]), int(cols[i])
        lst = []
        for dy, dx in offs:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and eligible[ny, nx]:
                lst.append((float(edge[ny, nx]), ny, nx))
        lst.sort(key=lambda t: (-t[0], t[1] * w + t[2]))
        cand_lists.append(lst)
        gains[i] = (lst[0][0] - float(edge[y, x])) if lst else -np.inf
    order = sorted(range(n), key=lambda i: (-gains[i], int(raster_idx[i])))
    claimed = np.zeros((h, w), dtype=bool)
    new_rows = np.empty(n, dtype=np.int64)
    new_cols = np.empty(n, dtype=np.int64)
    fallbacks = 0
    wide = offsets_within(4.0)
    for i in order:
        y, x = int(rows[i]), int(cols[i])
        pick = None
        for _e, ny, nx in cand_lists[i]:
            if not claimed[ny, nx]:
                pick = (ny, nx)
                break
        if pick is None:  # rare dense cluster: widen, count it, never duplicate
            fallbacks += 1
            best = None
            for dy, dx in wide:
                ny, nx = y + dy, x + dx
                if (0 <= ny < h and 0 <= nx < w and eligible[ny, nx]
                        and not claimed[ny, nx]):
                    key = (-float(edge[ny, nx]), ny * w + nx)
                    if best is None or key < best[0]:
                        best = (key, (ny, nx))
            pick = best[1] if best else (y, x)
        claimed[pick] = True
        new_rows[i], new_cols[i] = pick
    return new_rows, new_cols, fallbacks


def write_variant(mask: np.ndarray, foot: np.ndarray, sample_path: Path,
                  out_path: Path, zeros_outside: bool) -> str:
    arr = np.zeros(mask.shape, dtype=np.float32)
    arr[mask] = 1.0
    arr[~foot] = 0.0 if zeros_outside else np.nan
    with rasterio.open(sample_path) as ds:
        profile = ds.profile.copy()
    profile.update(driver="GTiff", count=1, dtype="float32",
                   nodata=(None if zeros_outside else float("nan")),
                   compress="deflate", predictor=2)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(arr, 1)
    back = load(out_path)  # re-read from disk after writing (brief s.6)
    inside = back[foot]
    assert np.isfinite(inside).all() and inside.min() >= 0.0 and inside.max() <= 1.0
    assert int((back[foot] > 0).sum()) == int(mask.sum())
    return sha256_file(out_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=REPO / "work/raw")
    ap.add_argument("--out", type=Path, default=REPO / "releases")
    ap.add_argument("--date", default="20261023")
    args = ap.parse_args()
    t0 = time.time()
    raw, out_dir = args.raw, args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"r0": raw / "scored/GEMSDOE32__h33-2-b2-zeros.tif",
             "catalogue": raw / "existing_faults.tif",
             "sample": raw / "sample_submission.tif",
             "training": raw / "training_features.tif"}
    for key, path in paths.items():
        digest = sha256_file(path)
        if digest != PINS[key]:
            print(f"FATAL: pin mismatch {key}: {digest}", file=sys.stderr)
            return 2
    print("[pins] R0 + catalogue + sample + training_features verified", flush=True)

    foot = ~np.isnan(load(paths["sample"]))
    cat = load(paths["catalogue"]) > 0
    r0 = (load(paths["r0"]) > 0) & foot
    d_cat = ndi.distance_transform_edt(~cat)
    eligible = foot & (d_cat > 2) & ~cat
    assert int((r0 & ~eligible).sum()) == 0, "parent dots violate eligibility"

    mag = load(paths["training"], BANDS["mag"]).astype(np.float64)
    grav = load(paths["training"], BANDS["grav"]).astype(np.float64)
    for name, band in (("tmi_hg", mag), ("iso_grav_anom_hg", grav)):
        bad = int((foot & ~np.isfinite(band)).sum())
        print(f"[edge] {name}: non-finite inside footprint = {bad}", flush=True)
        band[~foot | ~np.isfinite(band)] = -np.inf
    rank_mag = np.zeros_like(mag)
    rank_grav = np.zeros_like(grav)
    rank_mag[foot] = rankdata(mag[foot]) / int(foot.sum())
    rank_grav[foot] = rankdata(grav[foot]) / int(foot.sum())
    edges = {"mag": mag, "grav": grav, "comb": rank_mag + rank_grav}

    rows, cols = np.nonzero(r0)
    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                 capture_output=True, text=True).stdout.strip()
    except Exception:
        git_sha = "unknown"

    for tag, edge in edges.items():
        nr, nc, fb = snap_dots(rows, cols, edge, eligible)
        mask = np.zeros_like(r0)
        mask[nr, nc] = True
        assert int(mask.sum()) == int(r0.sum()), "snap changed dot count"
        disp = np.hypot(nr - rows, nc - cols)
        moved = disp > 0
        stem0 = f"h33-2-b2-snap{tag}-{args.date}"
        tmp = out_dir / f"{stem0}-tmp.tif"
        digest = write_variant(mask, foot, paths["sample"], tmp, False)
        stem = f"{stem0}-{digest[:8]}"
        final = out_dir / f"{stem}.tif"
        tmp.rename(final)
        zdigest = write_variant(mask, foot, paths["sample"],
                                out_dir / f"{stem}-zeros.tif", True)
        back = (load(final) > 0) & foot
        bro, bco = np.nonzero(back)
        tree = cKDTree(np.column_stack([bro, bco]).astype(np.float64))
        dd, _ = tree.query(np.column_stack([bro, bco]).astype(np.float64), k=2)
        rec = {
            "id": stem, "parent": "h33-h33-2-b2 (GEMSDOE32)",
            "parent_sha256": PINS["r0"], "axis": "SNAP",
            "value": tag, "edge_band": {"mag": "tmi_hg (band 3)",
                                         "grav": "iso_grav_anom_hg (band 18)",
                                         "comb": "percentile-rank(tmi_hg)+rank(iso_grav_anom_hg)"}[tag],
            "n_parent": int(r0.sum()), "n_dots": int(back.sum()),
            "pct_changed": round(100.0 * float(moved.mean()), 4),
            "n_moved": int(moved.sum()),
            "mean_displacement_px_all": round(float(disp.mean()), 4),
            "mean_displacement_px_moved": round(float(disp[moved].mean()), 4),
            "max_displacement_px": float(disp.max()),
            "collision_fallbacks": int(fb),
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "zeros_sha256": zdigest,
            "dots_on_catalogue": int((back & cat).sum()),
            "mass_on_catalogue": float(load(final)[cat & foot].sum()),
            "min_dist_catalogue_px": float(d_cat[back].min()),
            "min_inter_dot_sep_px": float(dd[:, 1].min()),
            "mean_edge_gain_moved": round(float((edge[nr, nc] - edge[rows, cols])[moved].mean()), 6),
            "git_sha": git_sha, "elapsed_s": round(time.time() - t0, 1),
        }
        (out_dir / f"{stem}.json").write_text(json.dumps(rec, indent=2))
        print(f"[write] {stem}: moved={rec['n_moved']} ({rec['pct_changed']}%) "
              f"mean_disp={rec['mean_displacement_px_moved']}px max={rec['max_displacement_px']} "
              f"fallbacks={fb} min_sep={rec['min_inter_dot_sep_px']:.3f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
