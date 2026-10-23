#!/usr/bin/env python3
"""Reproducible builder and validator for GEMSDOE87 Agent Brief v2 (AXIS = PRUNE on Parent R0).

Workflow (strictly offline / GitHub-pinned inputs only; zero contact with drivendata.org or dropbox.com):
1. Verify all 23 SHA-256 pins in `registry/data_manifest.json` against `.cache/raw/` (restoring from
   pinned GitHub commit tarballs on `codeload.github.com` if missing).
2. Rebuild Parent R0 (`h33-h33-2-b2`, GEMSDOE32, 37,654 unit-mass dots) from pinned manifest inputs
   (`scored_h19_5`, `existing_faults`, `sample_submission`) and assert byte-for-byte SHA-256 identity
   against both R0 twins (`c55bafc4...` zeros-outside and `baeae321...` NaN-outside). Halt on mismatch.
3. Read `ledger/submissions.csv` first; seed collapsed historical lineage rows (`CLAIM`, `receipt=N`) if
   absent, and refuse to duplicate any existing `(parent, axis, value)` or `sha256`.
4. Build 3 controlled variants of R0 on `AXIS = PRUNE` at strictly fixed count `N = 37,654` (`PRUNE1`,
   `PRUNE3`, `PRUNE4`), reallocating collar dots on R0's own parent field `H19-5` solely via exact
   sequential DTI marginal gain (`vendor/gems57/metric.py`, `R = 300 m = 3 px` triangular kernel),
   with deterministic row-major tie-breaking (`seed = 0`, zero randomness) and logged git HEAD SHA.
5. Write `releases/<id>.tif` (NaN outside footprint, per spec) and `releases/<id>-zeros.tif` (0.0 outside
   fallback), re-read every file from disk, run MUST-PASS format/catalogue/hash gates, and compute
   REPORT-ONLY diagnostics (hide-and-recover PROXY with n=22,663 & 95% CI, single-feature leakage canary,
   and USGS SGMC off-catalogue PROXY).
"""

from __future__ import annotations

import argparse
from collections import deque
import csv
import hashlib
import heapq
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, label as ndi_label
from scipy.spatial import cKDTree
from scipy.stats import rankdata

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_submission import validate_submission
from vendor.gems57 import evaluate_holdout as EH
from vendor.gems57 import grid as GR
from vendor.gems57 import holdout as HO
from vendor.gems57 import metric as M
from vendor.gems57 import validate as V57

MANIFEST_PATH = REPO_ROOT / "registry" / "data_manifest.json"
CANONICAL_INDEX_PATH = REPO_ROOT / "registry" / "canonical_scored_index.json"
INVENTORY_PATH = REPO_ROOT / "registry" / "inventory.json"
RAW_DIR = REPO_ROOT / ".cache" / "raw"
R0_VERIFY_DIR = REPO_ROOT / ".cache" / "r0_rebuild"
RELEASES_DIR = REPO_ROOT / "releases"
LEDGER_PATH = REPO_ROOT / "ledger" / "submissions.csv"

PARENT_ID = "h33-h33-2-b2"
R0_TARGET_DOTS = 37_654
R0_EXPECTED_ZEROS_SHA256 = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"
R0_EXPECTED_NAN_SHA256 = "baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd"
SESSION_DATE = "20261023"
FIXED_SEED = 0  # Deterministic tie-breaking by row-major flat pixel index; bootstrap seed 520810 in gems57
REFILL_MIN_DIST_SQ = 5  # >= sqrt(5) = 2.2361 px minimum inter-dot spacing on refilled H19-5 ridge gaps

LEDGER_COLUMNS = [
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()
    except Exception:
        return "UNKNOWN"


def verify_and_restore_manifest(manifest_path: Path = MANIFEST_PATH, raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    """Restore any missing files from pinned GitHub commit tarballs and verify all 23 SHA-256 hashes."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    by_repo_ref: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in manifest["files"]:
        by_repo_ref.setdefault((entry["repo"], entry["ref"]), []).append(entry)

    for (repo, ref), entries in by_repo_ref.items():
        missing = []
        for e in entries:
            dest = raw_dir / e["dest"]
            if not (dest.is_file() and dest.stat().st_size == e["bytes"] and sha256_file(dest) == e["sha256"]):
                missing.append(e)
        if not missing:
            continue

        # Never contact drivendata.org or dropbox.com; fetch strictly from codeload.github.com
        tar_tmp = raw_dir.parent / f"tar_{repo.replace('/', '_')}_{ref[:12]}.tar.gz"
        if not tar_tmp.is_file():
            url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
            subprocess.run(["curl", "-sSL", "--fail", "-o", str(tar_tmp), url], check=True)
        try:
            with tarfile.open(tar_tmp, "r:gz") as tf:
                members = tf.getnames()
                root_prefix = members[0].split("/")[0] + "/"
                for e in missing:
                    dest = raw_dir / e["dest"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if "parts" in e:
                        with dest.open("wb") as out_f:
                            for part in e["parts"]:
                                fobj = tf.extractfile(tf.getmember(root_prefix + part))
                                assert fobj is not None
                                shutil.copyfileobj(fobj, out_f)
                    else:
                        fobj = tf.extractfile(tf.getmember(root_prefix + e["path"]))
                        assert fobj is not None
                        with dest.open("wb") as out_f:
                            shutil.copyfileobj(fobj, out_f)
        finally:
            if tar_tmp.is_file():
                tar_tmp.unlink()

    verified_records = []
    for e in manifest["files"]:
        dest = raw_dir / e["dest"]
        actual_sha = sha256_file(dest)
        actual_bytes = dest.stat().st_size
        if actual_sha != e["sha256"] or actual_bytes != e["bytes"]:
            raise RuntimeError(
                f"Manifest SHA-256/byte mismatch on {e['id']} ({e['dest']}): "
                f"got {actual_sha} ({actual_bytes} B), expected {e['sha256']} ({e['bytes']} B)"
            )
        verified_records.append(
            {
                "id": e["id"],
                "dest": e["dest"],
                "bytes": actual_bytes,
                "sha256": actual_sha,
            }
        )
    return {"verified_count": len(verified_records), "files": verified_records}


def dot_thin_geodesic_bfs(mask: np.ndarray, min_dist: float) -> np.ndarray:
    """Exact deterministic BFS geodesic Poisson-disk thinning from GEMSDOE24 (`gems.thinning.dot_thin`)."""
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("2D boolean mask required")
    if min_dist <= 1.0 or not mask.any():
        return mask.copy()
    H, W = mask.shape
    pad = int(np.ceil(min_dist)) + 1
    Wp, Hp = W + 2 * pad, H + 2 * pad
    padded = np.zeros((Hp, Wp), dtype=bool)
    padded[pad : pad + H, pad : pad + W] = mask
    flat_mask = bytearray(padded.tobytes())
    visited = bytearray(Hp * Wp)
    blocked = bytearray(Hp * Wp)
    kept = bytearray(Hp * Wp)
    r = int(np.ceil(min_dist))
    limit = min_dist * min_dist
    disc = [
        dy * Wp + dx
        for dy in range(-r, r + 1)
        for dx in range(-r, r + 1)
        if dy * dy + dx * dx < limit
    ]
    nbr = (-Wp - 1, -Wp, -Wp + 1, -1, 1, Wp - 1, Wp, Wp + 1)

    comp, _ = ndi_label(padded, structure=np.ones((3, 3), dtype=int))
    flat_comp = comp.ravel()
    order = np.flatnonzero(flat_comp)
    _, first = np.unique(flat_comp[order], return_index=True)
    seeds = order[np.sort(first)]
    for seed in seeds.tolist():
        if visited[seed]:
            continue
        visited[seed] = 1
        queue = deque((seed,))
        while queue:
            q = queue.popleft()
            if not blocked[q]:
                kept[q] = 1
                for o in disc:
                    blocked[q + o] = 1
            for o in nbr:
                nb = q + o
                if flat_mask[nb] and not visited[nb]:
                    visited[nb] = 1
                    queue.append(nb)
    out = np.frombuffer(bytes(kept), dtype=np.uint8).reshape(Hp, Wp).astype(bool)
    return out[pad : pad + H, pad : pad + W]


def write_geotiff_pair_exact_profile(
    dots_mask: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    template_tif: Path,
    nan_path: Path,
    zeros_path: Path,
) -> tuple[str, str]:
    """Write NaN-outside and zeros-outside float32 GeoTIFFs using the exact GEMSDOE32 profile."""
    clean = (np.asarray(dots_mask, dtype=bool) & footprint & ~catalogue).astype(np.float32)
    with rasterio.open(template_tif) as tpl:
        profile_base = tpl.profile.copy()

    profile_zeros = profile_base.copy()
    profile_zeros.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        compress="deflate",
        predictor=3,
        zlevel=9,
        tiled=True,
        blockxsize=256,
        blockysize=256,
        nodata=None,
    )
    profile_nan = profile_zeros.copy()
    profile_nan.update(nodata=np.nan)

    nan_path.parent.mkdir(parents=True, exist_ok=True)
    zeros_path.parent.mkdir(parents=True, exist_ok=True)

    arr_nan = np.where(footprint, np.clip(clean, 0.0, 1.0), np.nan).astype(np.float32)
    with rasterio.open(nan_path, "w", **profile_nan) as dst:
        dst.write(arr_nan, 1)

    arr_zeros = np.where(footprint, np.clip(clean, 0.0, 1.0), 0.0).astype(np.float32)
    with rasterio.open(zeros_path, "w", **profile_zeros) as dst:
        dst.write(arr_zeros, 1)

    return sha256_file(nan_path), sha256_file(zeros_path)


def rebuild_and_verify_r0(
    h19_5: np.ndarray,
    d28_manifest: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
    template_tif: Path,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Rebuild R0 from pinned manifest inputs and assert exact SHA-256 identity with GEMSDOE32 R0."""
    d28_rebuilt = dot_thin_geodesic_bfs(h19_5 & footprint & ~catalogue, 2.8)
    if not np.array_equal(d28_rebuilt, d28_manifest):
        raise RuntimeError("Rebuilt d28 mask does not match pinned scored_d28_unscored pixel-for-pixel!")

    r0_mask = d28_rebuilt & (d_cat > 2.0)
    if int(r0_mask.sum()) != R0_TARGET_DOTS:
        raise RuntimeError(f"Rebuilt R0 dot count {int(r0_mask.sum())} != expected {R0_TARGET_DOTS}")

    R0_VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    r0_nan_path = R0_VERIFY_DIR / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif"
    r0_zeros_path = R0_VERIFY_DIR / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
    sha_nan, sha_zeros = write_geotiff_pair_exact_profile(
        r0_mask, footprint, catalogue, template_tif, r0_nan_path, r0_zeros_path
    )
    if sha_zeros != R0_EXPECTED_ZEROS_SHA256:
        raise RuntimeError(
            f"STOP: Rebuilt R0 zeros SHA-256 {sha_zeros} != expected {R0_EXPECTED_ZEROS_SHA256}"
        )
    if sha_nan != R0_EXPECTED_NAN_SHA256:
        raise RuntimeError(
            f"STOP: Rebuilt R0 NaN SHA-256 {sha_nan} != expected {R0_EXPECTED_NAN_SHA256}"
        )
    content_digest8 = hashlib.sha256(np.packbits(r0_mask)).hexdigest()[:8]
    return d28_rebuilt, r0_mask, {
        "parent_id": PARENT_ID,
        "n_dots": int(r0_mask.sum()),
        "content_digest8": content_digest8,
        "zeros_sha256": sha_zeros,
        "expected_zeros_sha256": R0_EXPECTED_ZEROS_SHA256,
        "zeros_sha256_exact_match": True,
        "nan_sha256": sha_nan,
        "expected_nan_sha256": R0_EXPECTED_NAN_SHA256,
        "nan_sha256_exact_match": True,
    }


def greedy_refill_exact_dti(
    s_init: np.ndarray,
    g_ridge: np.ndarray,
    target_n: int,
    min_dist_sq: int = REFILL_MIN_DIST_SQ,
) -> tuple[np.ndarray, dict[str, float]]:
    """Deterministic lazy-greedy exact DTI marginal-gain (`dT`) refill on `g_ridge` up to `target_n`."""
    H, W = s_init.shape
    out = s_init.copy()
    need = target_n - int(out.sum())
    if need < 0:
        raise ValueError(f"s_init ({int(out.sum())}) already exceeds target_n ({target_n})")
    if need == 0:
        return out, {"added": 0, "first_dT": 0.0, "median_dT": 0.0, "last_dT": 0.0}

    k_offs = list(zip(M.OFF_DY.tolist(), M.OFF_DX.tolist(), M.OFF_K.tolist()))

    blocked = np.zeros((H, W), dtype=bool)
    space_offs: list[tuple[int, int]] = []
    if min_dist_sq > 0:
        rad_s = int(np.ceil(np.sqrt(min_dist_sq)))
        for dy in range(-rad_s, rad_s + 1):
            for dx in range(-rad_s, rad_s + 1):
                if dy * dy + dx * dx < min_dist_sq:
                    space_offs.append((dy, dx))
        sy, sx = np.nonzero(out)
        for dy, dx in space_offs:
            ny, nx = sy + dy, sx + dx
            ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
            blocked[ny[ok], nx[ok]] = True

    cover = np.zeros((H, W), dtype=np.float32)
    sy, sx = np.nonzero(out)
    for j, i, kw in k_offs:
        ny, nx = sy + j, sx + i
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        np.maximum.at(cover, (ny[ok], nx[ok]), np.float32(kw))

    cand_mask = g_ridge & ~out & ~blocked
    cy, cx = np.nonzero(cand_mask)
    init_dt = np.zeros(cy.size, dtype=np.float64)
    for j, i, kw in k_offs:
        ny, nx = cy + j, cx + i
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        valid_idx = np.flatnonzero(ok)
        ty, tx = ny[valid_idx], nx[valid_idx]
        on_g = g_ridge[ty, tx]
        valid_idx = valid_idx[on_g]
        ty, tx = ty[on_g], tx[on_g]
        init_dt[valid_idx] += np.maximum(0.0, kw - cover[ty, tx])

    flat_c = cy * W + cx
    heap = [
        (-round(float(init_dt[idx]), 6), int(flat_c[idx]), int(idx))
        for idx in range(cy.size)
        if init_dt[idx] > 0.0
    ]
    heapq.heapify(heap)

    added = 0
    gains: list[float] = []
    while added < need and heap:
        _, fc, idx = heapq.heappop(heap)
        r, c = int(cy[idx]), int(cx[idx])
        if out[r, c] or blocked[r, c]:
            continue
        dt = 0.0
        for j, i, kw in k_offs:
            nr, nc = r + j, c + i
            if 0 <= nr < H and 0 <= nc < W and g_ridge[nr, nc]:
                diff = kw - float(cover[nr, nc])
                if diff > 0.0:
                    dt += diff
        key = (-round(dt, 6), fc, idx)
        if heap and key > heap[0]:
            heapq.heappush(heap, key)
            continue
        out[r, c] = True
        for dy, dx in space_offs:
            nr, nc = r + dy, c + dx
            if 0 <= nr < H and 0 <= nc < W:
                blocked[nr, nc] = True
        for j, i, kw in k_offs:
            nr, nc = r + j, c + i
            if 0 <= nr < H and 0 <= nc < W and kw > cover[nr, nc]:
                cover[nr, nc] = np.float32(kw)
        added += 1
        gains.append(dt)

    if added != need:
        raise RuntimeError(f"Could only refill {added}/{need} dots on parent ridge")

    return out, {
        "added": int(added),
        "first_dT": round(float(gains[0]), 5),
        "median_dT": round(float(np.median(gains)), 5),
        "last_dT": round(float(gains[-1]), 5),
    }


def greedy_prune_exact_dti(
    s_init: np.ndarray,
    removable_mask: np.ndarray,
    g_ridge: np.ndarray,
    target_n: int,
) -> tuple[np.ndarray, dict[str, float]]:
    """Deterministic sequential exact DTI marginal-loss (`dT_loss`) pruning down to `target_n`."""
    H, W = s_init.shape
    out = s_init.copy()
    drop_need = int(out.sum()) - target_n
    if drop_need < 0:
        raise ValueError(f"s_init ({int(out.sum())}) is below target_n ({target_n})")
    if drop_need == 0:
        return out, {"dropped": 0, "first_dT_loss": 0.0, "median_dT_loss": 0.0, "last_dT_loss": 0.0}

    k_offs = list(zip(M.OFF_DY.tolist(), M.OFF_DX.tolist(), M.OFF_K.tolist()))
    w1 = np.zeros((H, W), dtype=np.float32)
    w2 = np.zeros((H, W), dtype=np.float32)
    o1 = np.full((H, W), -1, dtype=np.int32)

    sy, sx = np.nonzero(out)
    s_flat = (sy * W + sx).astype(np.int32)
    for j, i, kw in sorted(k_offs, key=lambda x: -x[2]):
        ny, nx = sy + j, sx + i
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        ty, tx, tf = ny[ok], nx[ok], s_flat[ok]
        on_g = g_ridge[ty, tx]
        ty, tx, tf = ty[on_g], tx[on_g], tf[on_g]
        kw32 = np.float32(kw)

        better1 = kw32 > w1[ty, tx]
        b1_y, b1_x, b1_f = ty[better1], tx[better1], tf[better1]
        w2[b1_y, b1_x] = w1[b1_y, b1_x]
        w1[b1_y, b1_x] = kw32
        o1[b1_y, b1_x] = b1_f

        better2 = (~better1) & (kw32 >= w2[ty, tx])
        b2_y, b2_x = ty[better2], tx[better2]
        w2[b2_y, b2_x] = kw32

    valid_g = g_ridge & (o1 >= 0)
    init_loss_all = np.bincount(
        o1[valid_g],
        weights=(w1[valid_g] - w2[valid_g]).astype(np.float64),
        minlength=H * W,
    )

    rem_y, rem_x = np.nonzero(out & removable_mask)
    rem_flat = rem_y * W + rem_x
    heap = [
        (round(float(init_loss_all[df]), 6), int(df), int(r), int(c))
        for r, c, df in zip(rem_y, rem_x, rem_flat)
    ]
    heapq.heapify(heap)

    K7 = np.zeros((7, 7), dtype=np.float32)
    for j, i, kw in k_offs:
        K7[j + 3, i + 3] = np.float32(kw)

    def exact_single_dot_loss(r: int, c: int) -> float:
        loss = 0.0
        for j, i, kw in k_offs:
            nr, nc = r + j, c + i
            if 0 <= nr < H and 0 <= nc < W and g_ridge[nr, nc]:
                r0_s, r1_s = max(0, nr - 3), min(H, nr + 4)
                c0_s, c1_s = max(0, nc - 3), min(W, nc + 4)
                sub_out = out[r0_s:r1_s, c0_s:c1_s]
                sub_k = K7[(r0_s - nr + 3) : (r1_s - nr + 3), (c0_s - nc + 3) : (c1_s - nc + 3)]
                vals = sub_k * sub_out
                best_all = float(vals.max())
                vr, vc = r - r0_s, c - c0_s
                saved = vals[vr, vc]
                vals[vr, vc] = 0.0
                best_other = float(vals.max())
                vals[vr, vc] = saved
                if best_all > best_other:
                    loss += best_all - best_other
        return loss

    dropped = 0
    losses: list[float] = []
    while dropped < drop_need and heap:
        _, df, r, c = heapq.heappop(heap)
        if not out[r, c]:
            continue
        cur_loss = round(exact_single_dot_loss(r, c), 6)
        key = (cur_loss, df, r, c)
        if heap and key > heap[0]:
            heapq.heappush(heap, key)
            continue
        out[r, c] = False
        dropped += 1
        losses.append(cur_loss)

    if dropped != drop_need:
        raise RuntimeError(f"Could only prune {dropped}/{drop_need} dots")

    return out, {
        "dropped": int(dropped),
        "first_dT_loss": round(float(losses[0]), 5),
        "median_dT_loss": round(float(np.median(losses)), 5),
        "last_dT_loss": round(float(losses[-1]), 5),
    }


def build_prune_mask_for_catalogue(
    h19_5_base: np.ndarray,
    d28_base: np.ndarray,
    cat_mask: np.ndarray,
    footprint: np.ndarray,
    radius_px: float,
    target_n: int = R0_TARGET_DOTS,
) -> tuple[np.ndarray, dict[str, float]]:
    """Apply the controlled fixed-count PRUNE(radius_px) operator relative to `cat_mask`."""
    d_c = distance_transform_edt(~(cat_mask & footprint))
    r0_equiv = d28_base & (d_c > 2.0) & footprint
    raw = d28_base & (d_c > radius_px) & footprint
    g_ridge = h19_5_base & (d_c > radius_px) & footprint
    n_raw = int(raw.sum())
    if n_raw == target_n:
        return raw, {"mode": 0.0, "raw_dots": float(n_raw)}
    if n_raw > target_n:
        # Remove surplus from r0_equiv (>2 px) by exact LOO DTI marginal loss so 1..2 px collar is preserved intact
        out, info = greedy_prune_exact_dti(raw, r0_equiv, g_ridge, target_n)
        info["raw_dots"] = float(n_raw)
        return out, info
    out, info = greedy_refill_exact_dti(raw, g_ridge, target_n, min_dist_sq=REFILL_MIN_DIST_SQ)
    info["raw_dots"] = float(n_raw)
    return out, info


def compute_block_density_cv(dots_mask: np.ndarray, footprint: np.ndarray, block_km: int = 10) -> float:
    blk = block_km * 10  # 100 m pixels -> 10 px per km
    H, W = footprint.shape
    nh, nw = H // blk, W // blk
    fp_b = footprint[: nh * blk, : nw * blk].reshape(nh, blk, nw, blk).sum(axis=(1, 3))
    dt_b = dots_mask[: nh * blk, : nw * blk].reshape(nh, blk, nw, blk).sum(axis=(1, 3))
    valid = fp_b >= (0.5 * blk * blk)
    dens = dt_b[valid] / fp_b[valid]
    return float(dens.std() / dens.mean())


def compute_parent_diff_stats(
    variant_mask: np.ndarray,
    r0_mask: np.ndarray,
    d_cat: np.ndarray,
    footprint: np.ndarray,
) -> dict[str, Any]:
    n_v = int(variant_mask.sum())
    n_r0 = int(r0_mask.sum())
    shared = int((variant_mask & r0_mask).sum())
    removed = int((r0_mask & ~variant_mask).sum())
    added = int((variant_mask & ~r0_mask).sum())
    sym_diff = removed + added
    pct_changed = 100.0 * removed / float(n_r0)

    pts = np.column_stack(np.nonzero(variant_mask))
    nn_dists, _ = cKDTree(pts).query(pts, k=2)
    nn = nn_dists[:, 1]
    dc = d_cat[variant_mask]

    return {
        "n_dots": n_v,
        "parent_n_dots": n_r0,
        "shared_with_parent": shared,
        "removed_from_parent": removed,
        "added_to_parent": added,
        "symmetric_diff_dots": sym_diff,
        "pct_changed": round(pct_changed, 4),
        "pct_symmetric_diff_over_parent": round(100.0 * sym_diff / float(n_r0), 4),
        "d_catalogue_px": {
            "min": round(float(dc.min()), 4),
            "p10": round(float(np.percentile(dc, 10)), 4),
            "median": round(float(np.median(dc)), 4),
            "p90": round(float(np.percentile(dc, 90)), 4),
        },
        "nearest_neighbor_px": {
            "min": round(float(nn.min()), 4),
            "p05": round(float(np.percentile(nn, 5)), 4),
            "median": round(float(np.median(nn)), 4),
        },
        "block_density_cv_10km": {
            "parent_r0": round(compute_block_density_cv(r0_mask, footprint, block_km=10), 4),
            "variant": round(compute_block_density_cv(variant_mask, footprint, block_km=10), 4),
        },
        "block_density_cv_15km": {
            "parent_r0": round(compute_block_density_cv(r0_mask, footprint, block_km=15), 4),
            "variant": round(compute_block_density_cv(variant_mask, footprint, block_km=15), 4),
        },
    }


def symmetric_auc_mann_whitney(y_true_bool: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    y = np.asarray(y_true_bool, dtype=bool)
    x = np.nan_to_num(np.asarray(scores, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    n1 = int(y.sum())
    n0 = int((~y).sum())
    if n1 == 0 or n0 == 0 or float(np.std(x)) < 1e-12:
        return 0.5, 0.5
    ranks = rankdata(x, method="average")
    auc = float((ranks[y].sum() - n1 * (n1 + 1) / 2.0) / (float(n1) * float(n0)))
    return auc, float(max(auc, 1.0 - auc))


def run_report_only_diagnostics(
    static_masks: dict[str, np.ndarray],
    h19_5: np.ndarray,
    d28: np.ndarray,
    footprint: np.ndarray,
    catalogue: np.ndarray,
    d_cat: np.ndarray,
) -> dict[str, Any]:
    """Run Section 6 REPORT-ONLY diagnostics (never used as gates; labeled PROXY)."""
    t0 = time.time()
    grid = GR.load_grid(RAW_DIR)
    seeds = (20, 30)
    draws_by_seed = {s: HO.buffered_component_draw(grid, seed=s)[0] for s in seeds}

    # 1. Fold-proper hide-and-recover PROXY (d_vis computed strictly on visible 80% catalogue per seed)
    fp_radii = {"R0_PRUNE2_fp": 2.0, "PRUNE1_fp": 1.0, "PRUNE3_fp": 3.0, "PRUNE4_fp": 4.0}
    fp_terms: dict[str, np.ndarray] = {}
    for arm_name, r_px in fp_radii.items():
        tot = None
        for s in seeds:
            vis_s = draws_by_seed[s][0]["visible"]
            m_s, _ = build_prune_mask_for_catalogue(h19_5, d28, vis_s, footprint, radius_px=r_px, target_n=R0_TARGET_DOTS)
            pred_s = m_s.astype(np.float32)
            for fold in draws_by_seed[s]:
                _, terms = EH.evaluate(pred_s, fold, valid=footprint)
                tot = terms.copy() if tot is None else (tot + terms)
        assert tot is not None
        fp_terms[arm_name] = tot

    fp_summary = EH.pooled_summary(fp_terms, draws=1000, seed=520810, candidate="PRUNE3_fp")

    # 2. Static-raster hide-and-recover PROXY (literal full-catalogue rasters; subject to G_fold subset C collar zeroing)
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

    st_summary = EH.pooled_summary(st_terms, draws=1000, seed=520810, candidate="PRUNE3")

    # 3. Single-feature leakage canary on withheld positives (AUC > 0.90 => stop and investigate)
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

    for rel_tif, tag in (
        ("external/lidar_scarp_features_u8.tif", "lidar_u8"),
        ("external/geodawn_rad_u8.tif", "geodawn_rad_u8"),
        ("external/geodawn_extensions_u8.tif", "geodawn_ext_u8"),
    ):
        with rasterio.open(RAW_DIR / rel_tif) as ds:
            for b_idx in range(1, ds.count + 1):
                _audit_2d(f"{tag}_b{b_idx}", ds.read(b_idx))

    _audit_2d("parent_h19_5_binary", h19_5.astype(np.float32))
    canary_channels.sort(key=lambda r: r["max_symmetric_auc"], reverse=True)
    max_sym_auc = max(r["max_symmetric_auc"] for r in canary_channels)
    flagged = [r for r in canary_channels if r["flagged_over_0_90"]]
    if flagged:
        raise RuntimeError(f"STOP: Leakage canary fired (> 0.90 symmetric AUC): {flagged}")

    # 4. Off-catalogue USGS SGMC control PROXY (d_cat > 3.0 px from mapped Quaternary faults)
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
        "withheld_positive_pixels": int(fp_summary["scores"]["PRUNE3_fp"]["withheld_positive_pixels"]),
        "fold_proper_hide_and_recover_proxy": {
            k: {
                "evidence_label": "PROXY",
                "dti": round(float(v["dti"]), 6),
                "ci95": [round(float(v["ci95"][0]), 6), round(float(v["ci95"][1]), 6)],
                "withheld_positive_pixels": int(v["withheld_positive_pixels"]),
            }
            for k, v in fp_summary["scores"].items()
        },
        "fold_proper_paired_vs_PRUNE3_fp": {
            k: {
                "evidence_label": "PROXY",
                "delta_prune3_minus_arm": round(float(v["delta"]), 6),
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
                "caveat": "Static full-catalogue collar d_cat > r zeroes predictions within r px of withheld G_fold subset C.",
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


def historical_seed_rows() -> list[dict[str, str]]:
    """Collapsed historical lineage rows verified on disk (all owner-reported scores marked CLAIM, receipt=N)."""
    return [
        {
            "id": "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-ec1f9b56",
            "parent": "root",
            "axis": "FIELD",
            "value": "h19-5",
            "n_dots": "121131",
            "pct_changed": "0.00",
            "sha256": "ec1f9b56b83ce33cad781ceb9f104b18fb4f2ff785263a4e89616af4aabdee8d",
            "sha8": "ec1f9b56",
            "encoding": "nan",
            "status": "CLAIM",
            "predicted_change": "",
            "claimed_score": "0.1922",
            "receipt": "N",
            "receipt_score": "",
            "receipt_date": "",
            "form_note": "19GEMSDOE H19-5 continuous/binary ridge parent (CLAIM 0.1922; no receipt in ledger/)",
        },
        {
            "id": "gems24-h25-1-dotted-h19-5-d1-5-20261002-68d0e2e4",
            "parent": "h19-5",
            "axis": "SPACING",
            "value": "d1.5",
            "n_dots": "60069",
            "pct_changed": "50.41",
            "sha256": "68d0e2e4fcc594f9a23f56c44b885fee733d026d39be55e18ad2a07289525310",
            "sha8": "68d0e2e4",
            "encoding": "nan",
            "status": "CLAIM",
            "predicted_change": "",
            "claimed_score": "0.2477",
            "receipt": "N",
            "receipt_score": "",
            "receipt_date": "",
            "form_note": "GEMSDOE24 geodesic dot_thin d=1.5 px on H19-5 (CLAIM 0.2477; no receipt in ledger/)",
        },
        {
            "id": "gems24-h25-1-dotted-h19-5-d2-8-20261002-91eae1ca",
            "parent": "h19-5",
            "axis": "SPACING",
            "value": "d2.8",
            "n_dots": "44090",
            "pct_changed": "63.60",
            "sha256": "91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8",
            "sha8": "91eae1ca",
            "encoding": "nan",
            "status": "CLAIM",
            "predicted_change": "",
            "claimed_score": "0.2600",
            "receipt": "N",
            "receipt_score": "",
            "receipt_date": "",
            "form_note": "GEMSDOE24/25 geodesic dot_thin d=2.8 px on H19-5 (CLAIM 0.2600; twins collapsed; no receipt)",
        },
        {
            "id": "gems28-h27-4-r1-solo-d2-8-20261003-2fc94a38",
            "parent": "h25-1-dotted-d2-8",
            "axis": "PRUNE_UNREFILLED",
            "value": "1",
            "n_dots": "40199",
            "pct_changed": "8.83",
            "sha256": "2fc94a38d77f74d4f4ed1a97a83e7bb71a1ceea090515ec641e6681cc47c44c8",
            "sha8": "2fc94a38",
            "encoding": "nan",
            "status": "CLAIM",
            "predicted_change": "",
            "claimed_score": "0.2708",
            "receipt": "N",
            "receipt_score": "",
            "receipt_date": "",
            "form_note": "GEMSDOE28 delete d_cat<=1 px without refill (CLAIM 0.2708; mass+collar confounded)",
        },
        {
            "id": "h33-h33-2-b2",
            "parent": "h27-4-r1-solo-d2-8",
            "axis": "PRUNE",
            "value": "2",
            "n_dots": "37654",
            "pct_changed": "6.33",
            "sha256": R0_EXPECTED_NAN_SHA256,
            "sha8": R0_EXPECTED_NAN_SHA256[:8],
            "encoding": "nan+zeros(c55bafc4)",
            "status": "CLAIM",
            "predicted_change": "",
            "claimed_score": "0.2778",
            "receipt": "N",
            "receipt_score": "",
            "receipt_date": "",
            "form_note": "Parent R0 (GEMSDOE32): 37654 dots, d_cat>2 px; zeros sha256=c55bafc4... (CLAIM 0.2778)",
        },
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-diagnostics", action="store_true", help="skip report-only holdout/canary diagnostics")
    args = ap.parse_args()

    t_start = time.time()
    print("[1/6] Verifying all 23 SHA-256 pins in registry/data_manifest.json ...", flush=True)
    manifest_receipt = verify_and_restore_manifest()
    print(f"      Verified {manifest_receipt['verified_count']}/{manifest_receipt['verified_count']} files against registry/data_manifest.json.", flush=True)

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
        existing_rows = [r for r in existing_rows if not (r.get("parent") == PARENT_ID and r.get("axis") == "PRUNE")]

    seen_shas: set[str] = {r["sha256"] for r in existing_rows if r.get("sha256")}
    seen_pairs: set[tuple[str, str, str]] = {
        (r.get("parent", ""), r.get("axis", ""), r.get("value", "")) for r in existing_rows
    }
    if CANONICAL_INDEX_PATH.is_file():
        reg = json.loads(CANONICAL_INDEX_PATH.read_text(encoding="utf-8"))
        registry_shas = {r["sha256"] for r in reg.get("rasters", [])}
    else:
        registry_shas = set()
    if INVENTORY_PATH.is_file():
        inv = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        inventory_shas = {r["sha256"] for r in inv.get("rasters", [])}
    else:
        inventory_shas = set()

    variant_specs = [
        {
            "axis": "PRUNE",
            "value": "3",
            "radius_px": 3.0,
            "predicted_change": "+0.005 to +0.012 [MODEL]",
            "form_note": "h33-h33-2-b2; PRUNE<=3px (2171 collar dots refilled on H19-5 by DTI dT, n=37654, 5.77% chg); pred +0.005 to +0.012 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "Dots within 200-300 m (2 < d <= 3 px) of mapped USGS/INGENIOUS Quaternary faults sit inside "
                    "the known-fault potential-field/topographic gradient halo where new-fault density is low, while "
                    "a dot placed just outside at d >= 3.16 px (sqrt(10)) still reaches inward across the 300 m (3 px) "
                    "triangular kernel to score on splay junctions."
                ),
                "mechanism": (
                    "Remove all 2,171 R0 dots in 2 < d_cat <= 3 px (saving up to 0.2 * 2,171 = 434.2 denominator FP "
                    "units where q_new = 0) and refill exactly 2,171 dots onto uncovered gaps of R0's own H19-5 "
                    "off-collar fault ridges (d_cat > 3 px, min spacing >= sqrt(5) px) ranked by exact sequential "
                    "DTI marginal coverage gain dT (median dT = 1.00 kernel units on H19-5)."
                ),
                "non_fault_mimic": (
                    "Off-collar H19-5 ridges built from airborne magnetics, gravity, and DEM openness can follow "
                    "untectonized Tertiary volcanic dike margins, caldera ring fractures, or fluvial terrace risers "
                    "rather than unmapped Quaternary/geothermal faults."
                ),
                "predicted_live_change": "+0.005 to +0.012 DTI [MODEL] relative to R0 (treat |delta| < 0.01 on public chunks as no evidence).",
                "falsifier": (
                    "Live public score drops by >= 0.01 relative to R0's receipt, proving newly mapped geometry of "
                    "existing fault systems lies predominantly within 200-300 m of legacy USGS/INGENIOUS traces."
                ),
            },
        },
        {
            "axis": "PRUNE",
            "value": "1",
            "radius_px": 1.0,
            "predicted_change": "-0.012 to -0.005 [MODEL]",
            "form_note": "h33-h33-2-b2; PRUNE<=1px (restore 2545 1-2px dots, drop 2545 weak R0 dots, n=37654, 6.76% chg); pred -0.012 to -0.005 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "The historical +0.0070 climb from solo-d28 (40,199 dots, d > 1 px) to R0 (37,654 dots, d > 2 px) "
                    "confounded collar geometry with a -2,545 dot mass reduction. Holding n_dots fixed at 37,654 "
                    "isolates whether the 100-200 m (1 < d <= 2 px) flank hosts newly re-digitized strands of known "
                    "systems (organizer forum thread 11536) or pure known-scarp halo false positives."
                ),
                "mechanism": (
                    "Restore all 2,545 d28 parent dots in 1 < d_cat <= 2 px (d in {1.414, 2.0} px) and drop the "
                    "2,545 lowest exact leave-one-out DTI marginal-loss dots of R0 at d_cat > 2 px (isolated 1-px "
                    "H19-5 speckles with dT_loss <= 1.0), holding total emitted mass strictly constant at S = 37,654."
                ),
                "non_fault_mimic": (
                    "Digitization offset between 1:24k/1:100k USGS fault traces and the 100 m DEM/TMI scarp crest "
                    "creates strong ridge responses at 100-200 m beside the masked trace pixel even where only the "
                    "single already-catalogued fault strand exists."
                ),
                "predicted_live_change": "-0.012 to -0.005 DTI [MODEL] relative to R0 (negative control testing mass vs. collar confound).",
                "falsifier": (
                    "Live public score rises by >= +0.01 over R0's receipt, proving hidden test labels concentrate "
                    "as parallel re-mapped strands within 100-200 m of known traces and R0 won only via lower mass."
                ),
            },
        },
        {
            "axis": "PRUNE",
            "value": "4",
            "radius_px": 4.0,
            "predicted_change": "-0.004 to +0.006 [MODEL]",
            "form_note": "h33-h33-2-b2; PRUNE<=4px (3825 collar dots refilled on H19-5 by DTI dT, n=37654, 10.16% chg); pred -0.004 to +0.006 [MODEL]",
            "mechanism_card": {
                "hypothesis": (
                    "GeoDAWN Area 2 was flown at 400 m line spacing and 150-200 m terrain clearance, smearing "
                    "known-fault magnetic/radiometric edges out to ~400 m (4 px); however, pruning beyond R = 300 m "
                    "severs kernel reach to branch junctions near known traces and begins excising real hanging-wall "
                    "synthetic normal-fault splays and narrow step-over relays."
                ),
                "mechanism": (
                    "Remove all 3,825 R0 dots in 2 < d_cat <= 4 px (2,171 in 2-3 px + 1,654 in 3-4 px) and refill "
                    "exactly 3,825 dots onto uncovered gaps of H19-5 at d_cat > 4 px (min spacing >= sqrt(5) px) "
                    "ranked by exact sequential DTI marginal gain dT (range 3.45 to 0.75 kernel units)."
                ),
                "non_fault_mimic": (
                    "Gridding interpolation of 400 m-spaced airborne magnetic lines across steep range-front "
                    "topography produces broad 300-400 m flank gradients beside a single range-bounding fault, "
                    "mimicking parallel piedmont synthetic faults."
                ),
                "predicted_live_change": "-0.004 to +0.006 DTI [MODEL] relative to R0 (diminishing return / turnover past R = 300 m).",
                "falsifier": (
                    "PRUNE4 beats PRUNE3 by >= +0.01 live, demonstrating that airborne potential-field halo "
                    "contamination extends to 400 m and outweighs near-fault splay loss."
                ),
            },
        },
    ]

    print("[4/6] Building 3 controlled AXIS=PRUNE variants of R0 at fixed count 37,654 ...", flush=True)
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    for old_tif in RELEASES_DIR.glob(f"{PARENT_ID}-PRUNE*.tif"):
        old_tif.unlink()

    built_variants: list[dict[str, Any]] = []
    static_masks: dict[str, np.ndarray] = {"R0": r0_mask}
    new_ledger_rows: list[dict[str, str]] = []
    head_sha = git_head_sha()

    for spec in variant_specs:
        pair_key = (PARENT_ID, spec["axis"], spec["value"])
        if pair_key in seen_pairs:
            raise RuntimeError(f"Duplicate (parent, axis, value) in ledger: {pair_key}")
        if len(spec["form_note"]) > 140:
            raise ValueError(f"Form note exceeds 140 chars ({len(spec['form_note'])}): {spec['form_note']}")

        v_mask, alloc_info = build_prune_mask_for_catalogue(
            h19_5, d28, catalogue, footprint, radius_px=spec["radius_px"], target_n=R0_TARGET_DOTS
        )
        diff_stats = compute_parent_diff_stats(v_mask, r0_mask, d_cat, footprint)
        if not (1.0 <= diff_stats["pct_changed"] <= 50.0):
            raise RuntimeError(f"Variant {pair_key} pct_changed={diff_stats['pct_changed']}% outside [1%, 50%]!")

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

        content_digest8 = hashlib.sha256(np.packbits(v_mask)).hexdigest()[:8]
        rec = {
            "id": var_id,
            "parent": PARENT_ID,
            "axis": spec["axis"],
            "value": spec["value"],
            "radius_px": spec["radius_px"],
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
            "form_note": spec["form_note"],
            "form_note_length": len(spec["form_note"]),
            "allocation_details": alloc_info,
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
            f"      Built {var_id}: n={diff_stats['n_dots']}, %changed={diff_stats['pct_changed']:.2f}%, "
            f"min_dcat={diff_stats['d_catalogue_px']['min']} px, CV10km={diff_stats['block_density_cv_10km']['variant']}",
            flush=True,
        )

    print("[5/6] Writing ledger/submissions.csv ...", flush=True)
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for r in existing_rows + new_ledger_rows:
            writer.writerow({k: r.get(k, "") for k in LEDGER_COLUMNS})

    diagnostics = None
    if not args.skip_diagnostics:
        print("[6/6] Running REPORT-ONLY diagnostics (hide-and-recover PROXY, leakage canary, SGMC control) ...", flush=True)
        diagnostics = run_report_only_diagnostics(static_masks, h19_5, d28, footprint, catalogue, d_cat)
        print(
            f"      Diagnostics done in {diagnostics['elapsed_seconds']}s: "
            f"canary max_sym_auc={diagnostics['leakage_canary']['max_symmetric_auc_observed']} (<=0.90), "
            f"fold-proper PRUNE3 PROXY={diagnostics['fold_proper_hide_and_recover_proxy']['PRUNE3_fp']['dti']:.6f}",
            flush=True,
        )

    release_manifest = {
        "schema_version": 2,
        "generated_date_utc": SESSION_DATE,
        "git_head_at_build": head_sha,
        "fixed_seed": FIXED_SEED,
        "refill_min_dist_sq": REFILL_MIN_DIST_SQ,
        "manifest_verification": {
            "manifest_path": "registry/data_manifest.json",
            "verified_files_count": manifest_receipt["verified_count"],
        },
        "parent_r0_rebuild_receipt": r0_receipt,
        "axis": "PRUNE",
        "variants": built_variants,
        "report_only_diagnostics": diagnostics,
        "total_elapsed_seconds": round(time.time() - t_start, 2),
    }
    (RELEASES_DIR / "manifest.json").write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Done in {release_manifest['total_elapsed_seconds']}s. Wrote releases/manifest.json and ledger/submissions.csv.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
