#!/usr/bin/env python3
"""Build the two MASS variants of parent R0 (h33-h33-2-b2, GEMSDOE32).

Single-axis rule (brief v2, AXIS=MASS): change ONLY the dot count, by the
parent's own ranking. The parent stored no continuous ranking: the pinned
H19-5 artifact (sha256 ec1f9b56...) is binary (121,131 px at 1.0) and the
recorded dotting recipe is the label-free geodesic BFS thinning
``dot_thin(H19-5 & footprint & ~catalogue, d=2.8)`` (GEMSDOE24
``src/gems/thinning.py``), verified here to reproduce the 44,090-dot
emission byte-exactly before any edit is made. The ranking is therefore
rebuilt exactly as the brief's metric algebra prescribes (brief section 2:
"rank dots by exact marginal gain from the metric code"):

* every R0 dot is scored by its exact leave-one-out (LOO) marginal loss in
  R0's own triangular-kernel (R = 3 px) max-coverage surface;
* MASS-10 drops the 3,765 dots (floor of 10% of 37,654) with the smallest
  LOO loss (most redundant first; ties by raster index);
* MASS+10 adds 3,765 dots by exact lazy-greedy marginal coverage gain from
  the parent pool (H19-5 mask & footprint & d(catalogue) > 2 px & not in
  R0). The parent emission is a saturated maximal Poisson disk, so +10%
  cannot also hold the >= 2.8 px spacing (only 609 further dots fit);
  spacing is therefore not blocked in the greedy, and the resulting
  spacing shift is measured and disclosed as a side-effect in the receipt
  and mechanism card rather than hidden.

Inputs are sha256-pinned (registry/data_manifest.json + the canonical
scored index); the script fails closed on any hash mismatch. It never
submits anything; the human submits from their own account.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
KERNEL_R = 3.0          # 300 m triangular kernel radius, px (brief section 2)
ALPHA, BETA = 0.2, 0.8  # DTI weights (brief section 2)
MIN_SEP = 2.8           # parent emitter spacing (dot_thin d=2.8), px
FRAC = 0.10             # MASS value for this session: +/-10%

PINS = {
    "r0": "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
    "h19_5": "ec1f9b56b83ce33cad781ceb9f104b18fb4f2ff785263a4e89616af4aabdee8d",
    "dotted28": "91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8",
    "solo28": "ab02300152248fdda04e988e2cd2a0c13f35eec42fcf670a15e8b76b19e24a73",
    "catalogue": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dti_from_components(t_credit: float, s_mass: float, m_weighted: float,
                        n_truth: float) -> float:
    """DTI = T / (0.2*T + 0.2*(S - M) + 0.8*|G|)  (brief section 2 algebra)."""
    return t_credit / (ALPHA * t_credit + ALPHA * (s_mass - m_weighted)
                       + BETA * n_truth)


def dti_direct(pred: np.ndarray, truth: np.ndarray) -> float:
    """Reference DTI from rasters, used only to unit-test the algebra."""
    pred = np.asarray(pred, dtype=np.float64)
    truth = np.asarray(truth, dtype=bool)
    if not truth.any():
        raise ValueError("truth must be non-empty")
    # q(x): max triangular-kernel credit of the prediction around truth,
    # computed exactly on the (small) arrays this is used with in tests.
    coords_p = np.column_stack(np.nonzero(pred > 0))
    coords_g = np.column_stack(np.nonzero(truth))
    tree = cKDTree(coords_p) if len(coords_p) else None
    t_credit = 0.0
    m_weighted = 0.0
    if tree is not None:
        d_g, _ = tree.query(coords_g, k=1)
        t_credit = float(np.clip(1.0 - d_g / KERNEL_R, 0.0, None).sum())
        tree_g = cKDTree(coords_g)
        d_p, _ = tree_g.query(coords_p, k=1)
        q_p = np.clip(1.0 - d_p / KERNEL_R, 0.0, None)
        m_weighted = float((pred[pred > 0] * q_p).sum())
    s_mass = float(pred.sum())
    return dti_from_components(t_credit, s_mass, m_weighted, float(truth.sum()))


def load(path: Path) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(1)


def write_variant(mask: np.ndarray, foot: np.ndarray, sample_path: Path,
                  out_path: Path, zeros_outside: bool) -> str:
    arr = np.where(foot, 0.0, 0.0).astype(np.float32)
    arr[mask] = 1.0
    if zeros_outside:
        arr[~foot] = 0.0
    else:
        arr[~foot] = np.nan
    with rasterio.open(sample_path) as ds:
        profile = ds.profile.copy()
    profile.update(driver="GTiff", count=1, dtype="float32",
                   nodata=(None if zeros_outside else float("nan")),
                   compress="deflate", predictor=2)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(arr, 1)
    # Re-read from disk after writing (brief section 6).
    back = load(out_path)
    inside = back[foot]
    assert np.isfinite(inside).all(), "NaN/Inf inside footprint after re-read"
    assert inside.min() >= 0.0 and inside.max() <= 1.0, "range violation"
    assert int((back[foot] > 0).sum()) == int(mask.sum()), "dot count changed on disk"
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
    paths = {
        "r0": raw / "scored/GEMSDOE32__h33-2-b2-zeros.tif",
        "h19_5": raw / "scored/gems19-h19-5-nan.tif",
        "dotted28": raw / "scored/GEMSDOE25__dotted-d28-nan.tif",
        "solo28": raw / "scored/GEMSDOE28__solo-d28-nan.tif",
        "catalogue": raw / "existing_faults.tif",
        "sample": raw / "sample_submission.tif",
    }
    for key, path in paths.items():
        digest = sha256_file(path)
        if digest != PINS[key]:
            print(f"FATAL: pin mismatch for {key}: {digest} != {PINS[key]}",
                  file=sys.stderr)
            return 2
    print("[pins] all 6 input hashes verified", flush=True)

    sample = load(paths["sample"])
    foot = ~np.isnan(sample)
    cat = load(paths["catalogue"]) > 0
    r0 = load(paths["r0"]) > 0
    r0 &= foot
    h19 = (load(paths["h19_5"]) > 0) & foot
    dotted = load(paths["dotted28"]) > 0
    solo = load(paths["solo28"]) > 0
    d_cat = ndi.distance_transform_edt(~cat)

    # --- Parent-recipe reproduction checks (fail closed) -------------------
    sys.path.insert(0, str(REPO))  # local dot_thin copy below, not /tmp
    from scripts.dot_thin_ref import dot_thin  # vendored reference algorithm
    repro = dot_thin(h19 & foot & ~cat, MIN_SEP)
    assert np.array_equal(repro, dotted), "dot_thin reproduction of d2.8 failed"
    assert np.array_equal(solo, dotted & (d_cat > 1)), "solo != dotted & d>1"
    assert np.array_equal(r0, solo & (d_cat > 2)), "R0 != solo & d>2"
    n_r0 = int(r0.sum())
    print(f"[parent] recipe reproduced exactly; R0 dots = {n_r0}", flush=True)

    # --- Exact LOO marginal-coverage ranking of R0 dots --------------------
    rows, cols = np.nonzero(r0)
    raster_idx = (rows.astype(np.int64) * r0.shape[1] + cols).astype(np.int64)
    d1, (orow, ocol) = ndi.distance_transform_edt(
        ~r0, return_distances=True, return_indices=True)
    cov = np.clip(1.0 - d1 / KERNEL_R, 0.0, None).astype(np.float64)
    owner = orow.astype(np.int64) * r0.shape[1] + ocol
    dot_pos = {int(v): i for i, v in enumerate(raster_idx)}
    covered = (d1 < KERNEL_R) & foot
    cy, cx = np.nonzero(covered)
    tree = cKDTree(np.column_stack([rows, cols]).astype(np.float64))
    d_kdt, _ = tree.query(np.column_stack([cy, cx]).astype(np.float64), k=2)
    assert np.allclose(d_kdt[:, 0], d1[covered], atol=1e-6), "EDT/KDTree mismatch"
    gain_here = np.clip(1.0 - d1[covered] / KERNEL_R, 0.0, None)
    gain_next = np.clip(1.0 - d_kdt[:, 1] / KERNEL_R, 0.0, None)
    loo = np.zeros(n_r0, dtype=np.float64)
    owner_here = np.array([dot_pos[int(v)] for v in owner[covered]], dtype=np.int64)
    np.add.at(loo, owner_here, gain_here - gain_next)
    print(f"[rank] LOO loss: min={loo.min():.4f} p10={np.percentile(loo, 10):.4f} "
          f"median={np.median(loo):.4f} max={loo.max():.4f}", flush=True)

    k = int(n_r0 * FRAC)  # 3,765
    order = np.lexsort((raster_idx, loo))  # ascending LOO, ties by raster index
    drop_local = order[:k]
    drop_mask = np.zeros_like(r0)
    drop_mask[rows[drop_local], cols[drop_local]] = True
    minus = r0 & ~drop_mask

    # --- Exact lazy-greedy marginal-gain additions --------------------------
    # No spacing block (see docstring): the saturated parent disk admits
    # only 609 extra dots at >= 2.8 px, so +10% ranked purely by gain.
    pool = h19 & foot & (d_cat > 2) & ~r0
    headroom = 1.0 - cov
    kernel = np.zeros((7, 7), dtype=np.float64)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            d = float(np.hypot(dy, dx))
            if d < KERNEL_R:
                kernel[dy + 3, dx + 3] = 1.0 - d / KERNEL_R
    bound = ndi.convolve(headroom, kernel, mode="constant", cval=0.0)
    py, px = np.nonzero(pool)
    p_idx = (py.astype(np.int64) * r0.shape[1] + px).astype(np.int64)
    # Heap keys are upper bounds (convolution bound); an entry re-pushed
    # with is_exact=True carries its true gain and may be accepted when it
    # surfaces, because it then dominates every remaining bound.
    heap = [(-float(bound[y, x]), int(i), int(y), int(x), False)
            for y, x, i in zip(py, px, p_idx)]
    heapq.heapify(heap)
    blocked = ~pool.copy()
    cov_cur = np.pad(cov, 3, mode="constant", constant_values=1.0)
    picked: list[tuple[int, int]] = []

    yy, xx = np.mgrid[-3:4, -3:4]
    disk28 = (yy * yy + xx * xx) < (MIN_SEP * MIN_SEP - 1e-6)

    def exact_gain(y: int, x: int) -> float:
        sub_cov = cov_cur[y:y + 7, x:x + 7]  # cov_cur is padded by 3
        return float(np.maximum(kernel - sub_cov, 0.0).sum())

    while heap and len(picked) < k:
        _negb, _i, y, x, is_exact = heapq.heappop(heap)
        if blocked[y, x]:
            continue
        if not is_exact:
            heapq.heappush(heap, (-exact_gain(y, x), _i, y, x, True))
            continue
        picked.append((y, x))
        blocked[y, x] = True
        sub = cov_cur[y:y + 7, x:x + 7]
        cov_cur[y:y + 7, x:x + 7] = np.maximum(sub, kernel)
    add_mask = np.zeros_like(r0)
    for y, x in picked:
        add_mask[y, x] = True
    plus = r0 | add_mask
    print(f"[mass] drop={k} add={int(add_mask.sum())}", flush=True)

    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                 capture_output=True, text=True).stdout.strip()
    except Exception:
        git_sha = "unknown"

    variants = [
        ("minus10", minus, -k, "drop the 3,765 lowest-LOO (most redundant) dots"),
        ("plus10", plus, int(add_mask.sum()), "add the 3,765 highest marginal-gain parent-pool dots"),
    ]
    receipts = {}
    for tag, mask, delta, desc in variants:
        stem0 = f"h33-2-b2-mass{tag}-{args.date}"
        tmp = out_dir / f"{stem0}-tmp.tif"
        digest = write_variant(mask, foot, paths["sample"], tmp, zeros_outside=False)
        sha8 = digest[:8]
        stem = f"{stem0}-{sha8}"
        final = out_dir / f"{stem}.tif"
        tmp.rename(final)
        zdigest = write_variant(mask, foot, paths["sample"],
                                out_dir / f"{stem}-zeros.tif", zeros_outside=True)
        # Parent-diff + geometry statistics, re-read from disk.
        back = load(final) > 0
        vrows, vcols = np.nonzero(back & foot)
        vtree = cKDTree(np.column_stack([vrows, vcols]).astype(np.float64))
        dd, _ = vtree.query(np.column_stack([vrows, vcols]).astype(np.float64), k=2)
        rec = {
            "id": stem,
            "parent": "h33-h33-2-b2 (GEMSDOE32)",
            "parent_sha256": PINS["r0"],
            "axis": "MASS",
            "value": ("-10%" if tag == "minus10" else "+10%"),
            "change": desc,
            "n_parent": n_r0,
            "n_dots": int((back & foot).sum()),
            "delta_dots": int(delta),
            "pct_changed": round(100.0 * int((back ^ r0).sum()) / n_r0, 4),
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "zeros_sha256": zdigest,
            "dots_on_catalogue": int((back & cat).sum()),
            "mass_on_catalogue": float(load(final)[cat & foot].sum()),
            "min_dist_catalogue_px": float(d_cat[back & foot].min()),
            "min_inter_dot_sep_px": float(dd[:, 1].min()),
            "git_sha": git_sha,
            "elapsed_s": round(time.time() - t0, 1),
        }
        (out_dir / f"{stem}.json").write_text(json.dumps(rec, indent=2))
        receipts[tag] = rec
        print(f"[write] {stem}.tif n={rec['n_dots']} changed={rec['pct_changed']}% "
              f"min_dcat={rec['min_dist_catalogue_px']:.4f} min_sep={rec['min_inter_dot_sep_px']:.4f}",
              flush=True)

    work = REPO / "work"
    work.mkdir(exist_ok=True)
    np.savez_compressed(work / "mass_ranking.npz", rows=rows, cols=cols, loo=loo,
                        dropped=drop_local, added=np.array(picked, dtype=np.int64))
    summary = {"parent_dots": n_r0, "k": k,
               "loo_quantiles": {q: float(np.percentile(loo, q))
                                 for q in (0, 10, 25, 50, 75, 90, 100)},
               "variants": receipts}
    (work / "mass_build_receipt.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
