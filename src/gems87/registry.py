"""Public sibling-raster registry and duplicate-lane checks.

This module never uses a registry raster to train or place predictions.  Its sole
purpose is to enforce the parallel-run requirement that a candidate not silently
reproduce an existing lane.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from scipy.stats import rankdata

from .data import sha256_file
from .paths import REGISTRY, WORK

REGISTRY_VERSION = "gems87.registry.v2"
OWNER = "buffedlizard55-lab"
# Selected public candidates total ~O(10^2 MB); accepting up to 64 MB keeps even
# continuous/ring candidate GeoTIFFs in the uniqueness check while excluding no
# known selected artifact.
MAX_SUBMISSION_BYTES = 64_000_000
CORRELATION_THRESHOLD = 0.90
OVERLAP_THRESHOLD = 0.70


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gh_json(endpoint: str) -> Any:
    result = subprocess.run(["gh", "api", endpoint], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def _is_gems_repo(name: str) -> bool:
    return bool(re.fullmatch(r"(?:GEMSDOE\d*|\d+GEMSDOE)", name))


def _looks_like_submission(path: str) -> bool:
    """Conservative selection of published candidate rasters, not data products.

    Binary `-zeros` twins are preferred because their dot support is identical to
    the paired `-nan` files while they are cheap to inspect.  A submission/candidate
    file without a zeros twin remains eligible.  Diagnostic and internal-work
    rasters are deliberately not called a registry submission.
    """
    lower = path.lower()
    if not lower.endswith((".tif", ".tiff")):
        return False
    forbidden = (
        "training_features", "sample_submission", "labels.tif", "existing_fault", "feature_stack",
        "/data/", "/work/", "quarantine", "diagnostic", "evidence/", "audit", "checks/",
        "/inputs/", "parallel_session", "scratch", "candidate-surface", "format_test",
    )
    if any(token in lower for token in forbidden):
        return False
    allowed_place = lower.startswith("docs/downloads/") or lower.startswith("downloads/") or "/downloads/" in lower or "/submission" in lower or "/candidate" in lower or "/submissions/" in lower
    if not allowed_place:
        return False
    # Avoid duplicate NaN twins when a portal-safe zeros twin is normally present.
    if lower.endswith("-nan.tif") or lower.endswith("_nan.tif") or "nan-outside" in lower:
        return False
    filename = lower.rsplit("/", 1)[-1]
    return filename.endswith("-zeros.tif") or filename.endswith("_zeros.tif") or "submission" in filename or "candidate" in filename


def _canonicalize_artifacts(artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep one path per Git blob, preferring direct docs/downloads locations."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in artifacts:
        grouped.setdefault(item["git_blob_sha"], []).append(item)
    canonical: list[dict[str, Any]] = []
    for _, group in grouped.items():
        group.sort(key=lambda x: (not x["path"].lower().startswith("docs/downloads/"), len(x["path"]), x["path"]))
        canonical.append(group[0])
    canonical.sort(key=lambda x: (x["repo"].lower(), x["path"].lower()))
    return canonical, len(artifacts) - len(canonical)


def discover_registry_catalog(*, owner: str = OWNER) -> dict[str, Any]:
    """Discover public GEMS-named repositories and their small submission TIFFs."""
    repos: list[dict[str, Any]] = []
    for page in range(1, 5):
        values = _gh_json(f"users/{owner}/repos?per_page=100&page={page}&type=owner")
        if not values:
            break
        repos.extend(v for v in values if _is_gems_repo(v["name"]))
    artifacts: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for repo in sorted(repos, key=lambda x: x["name"].lower()):
        name = repo["name"]
        branch = repo.get("default_branch") or "main"
        try:
            tree = _gh_json(f"repos/{owner}/{name}/git/trees/{branch}?recursive=1")
        except subprocess.CalledProcessError as exc:
            failures.append({"repo": name, "error": exc.stderr.strip()[-300:]})
            continue
        if tree.get("truncated"):
            failures.append({"repo": name, "error": "GitHub tree response is truncated; catalog cannot claim complete coverage."})
            continue
        for node in tree.get("tree", []):
            if node.get("type") != "blob" or not _looks_like_submission(node["path"]):
                continue
            artifacts.append(
                {
                    "repo": f"{owner}/{name}",
                    "ref": branch,
                    "path": node["path"],
                    "git_blob_sha": node["sha"],
                    "bytes": int(node.get("size", 0)),
                    "eligible_for_download": int(node.get("size", 0)) <= MAX_SUBMISSION_BYTES,
                    "source_url": f"https://github.com/{owner}/{name}/blob/{branch}/{node['path']}",
                }
            )
    canonical, deduplicated = _canonicalize_artifacts(artifacts)
    return {
        "registry_version": REGISTRY_VERSION,
        "generated_utc": _utc_now(),
        "owner": owner,
        "repository_count": len(repos),
        "artifacts": canonical,
        "raw_candidate_paths_before_blob_deduplication": len(artifacts),
        "duplicate_paths_collapsed_by_git_blob": deduplicated,
        "failures": failures,
        "complete_discovery": not failures,
        "selection_rule": "public, non-diagnostic, upload-shaped TIFF candidates in GEMS-named repositories; data/work/diagnostic TIFFs excluded; paired NaN twins and byte-identical paths collapsed",
    }


def save_catalog(catalog: dict[str, Any], path: Path | None = None) -> Path:
    path = path or (REGISTRY / "registry_catalog.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return path


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    path = path or (REGISTRY / "registry_catalog.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_cache_name(item: dict[str, Any]) -> str:
    raw = f"{item['repo']}__{item['path']}__{item['git_blob_sha']}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{item['repo'].split('/')[-1]}-{digest}.tif"


def _git_blob_sha1_file(path: Path) -> str:
    """Calculate the Git SHA-1 object id for a materialized blob without RAM-loading it."""
    digest = hashlib.sha1()
    digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _prior_cache_by_blob() -> dict[str, dict[str, Any]]:
    """Reuse already-inspected local bytes when a prior interrupted sync exists."""
    prior = WORK.parent / "evidence" / "registry_materialization.json"
    if not prior.is_file():
        return {}
    try:
        records = json.loads(prior.read_text(encoding="utf-8")).get("materialized", [])
        return {x["git_blob_sha"]: x for x in records if Path(x.get("cache_path", "")).is_file()}
    except (OSError, ValueError, KeyError):
        return {}


def _download_repo_archive(repo: str, ref: str, destination: Path) -> tuple[bool, str]:
    """Fetch one codeload archive for a repository, avoiding hundreds of raw API calls."""
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{ref}"
    result = subprocess.run(
        ["curl", "--fail", "--location", "--retry", "2", "--connect-timeout", "20", "--max-time", "900", "-o", str(destination), url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 0, result.stderr.decode(errors="replace")[-400:]


def materialize_registry(catalog: dict[str, Any], *, cache_dir: Path | None = None) -> dict[str, Any]:
    """Materialize each canonical registry TIFF, fail closed on incomplete coverage.

    Candidate files are grouped by repository and extracted from GitHub's codeload
    archive.  This avoids triggering GitHub's anti-scraping controls by issuing a
    raw-content API request per TIFF.  The archive is discarded after its selected
    files are copied to the ignored cache.
    """
    cache_dir = cache_dir or (WORK / "registry_rasters")
    cache_dir.mkdir(parents=True, exist_ok=True)
    prior = _prior_cache_by_blob()
    materialized: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    pending_by_repo: dict[tuple[str, str], list[tuple[dict[str, Any], Path]]] = {}

    for item in catalog.get("artifacts", []):
        label = f"{item['repo']}:{item['path']}"
        if not item.get("eligible_for_download", False):
            failures.append({"artifact": label, "error": f"oversize ({item.get('bytes')} bytes)"})
            continue
        path = cache_dir / _safe_cache_name(item)
        old = prior.get(item["git_blob_sha"])
        if not path.is_file() and old and Path(old["cache_path"]).is_file() and Path(old["cache_path"]).stat().st_size == int(item["bytes"]):
            # Hard-link when possible; copy fallback keeps work cache self-contained.
            try:
                path.hardlink_to(Path(old["cache_path"]))
            except OSError:
                path.write_bytes(Path(old["cache_path"]).read_bytes())
        if not path.is_file() or path.stat().st_size != int(item["bytes"]):
            pending_by_repo.setdefault((item["repo"], item["ref"]), []).append((item, path))

    archive_dir = cache_dir / ".archives"
    archive_dir.mkdir(exist_ok=True)
    for (repo, ref), pending in pending_by_repo.items():
        archive = archive_dir / (repo.replace("/", "__") + "-" + ref + ".zip")
        archive.unlink(missing_ok=True)
        ok, error = _download_repo_archive(repo, ref, archive)
        if not ok:
            for item, _ in pending:
                failures.append({"artifact": f"{item['repo']}:{item['path']}", "error": f"codeload failure: {error}"})
            continue
        try:
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
                for item, path in pending:
                    suffix = "/" + item["path"]
                    match = next((name for name in names if name.endswith(suffix)), None)
                    if match is None:
                        failures.append({"artifact": f"{item['repo']}:{item['path']}", "error": "file absent from codeload archive"})
                        continue
                    with zf.open(match) as source, path.open("wb") as dest:
                        while block := source.read(1 << 20):
                            dest.write(block)
                    if path.stat().st_size != int(item["bytes"]):
                        path.unlink(missing_ok=True)
                        failures.append({"artifact": f"{item['repo']}:{item['path']}", "error": "archive byte count differs from Git tree"})
        except (OSError, zipfile.BadZipFile) as exc:
            for item, _ in pending:
                failures.append({"artifact": f"{item['repo']}:{item['path']}", "error": f"archive read failure: {exc}"})
        finally:
            archive.unlink(missing_ok=True)

    for item in catalog.get("artifacts", []):
        path = cache_dir / _safe_cache_name(item)
        label = f"{item['repo']}:{item['path']}"
        if not path.is_file():
            continue
        expected_blob = str(item.get("git_blob_sha", ""))
        # GitHub tree object IDs are SHA-1 blob IDs. Verifying the object header
        # plus bytes protects against a ref changing between discovery and archive
        # retrieval and against a stale/corrupt cache with a coincident size.
        if len(expected_blob) != 40 or _git_blob_sha1_file(path) != expected_blob:
            path.unlink(missing_ok=True)
            failures.append({"artifact": label, "error": "materialized bytes do not match catalog Git blob SHA-1"})
            continue
        try:
            with rasterio.open(path) as ds:
                shape = [ds.height, ds.width]
                count = ds.count
                crs = ds.crs.to_string() if ds.crs else None
                transform = [float(x) for x in tuple(ds.transform)[:6]]
            materialized.append({**item, "cache_path": str(path), "sha256": sha256_file(path), "shape": shape, "count": count, "crs": crs, "transform": transform})
        except Exception as exc:
            failures.append({"artifact": label, "error": f"rasterio-read-failure: {exc}"})

    return {
        "registry_version": REGISTRY_VERSION,
        "catalog_generated_utc": catalog.get("generated_utc"),
        "complete_discovery": bool(catalog.get("complete_discovery", False)),
        "registry_artifacts_discovered": len(catalog.get("artifacts", [])),
        "registry_artifacts_materialized": len(materialized),
        "materialized": materialized,
        "failures": failures,
        "complete_materialization": not failures and len(materialized) == len(catalog.get("artifacts", [])),
        "retrieval": "GitHub codeload archives with local byte-count checks; selected Git blobs are deduplicated in the catalog.",
    }


def _binary_spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    """Exact Spearman for binary inputs (midranks are affine in 0/1 values)."""
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    if aa.size == 0 or aa.std() == 0.0 or bb.std() == 0.0:
        return None
    return float(np.corrcoef(aa, bb)[0, 1])


def _pearson_correlation(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson correlation without materialising a two-row `corrcoef` array."""
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    if aa.size == 0 or aa.size != bb.size:
        raise ValueError("correlation inputs must be equally sized and nonempty")
    aa = aa - aa.mean()
    bb = bb - bb.mean()
    denominator = float(np.sqrt(np.dot(aa, aa) * np.dot(bb, bb)))
    return None if denominator == 0.0 else float(np.dot(aa, bb) / denominator)


def compare_surface(surface: np.ndarray, footprint: np.ndarray, registry: dict[str, Any]) -> dict[str, Any]:
    """Exact pre-placement Spearman screen against every materialized raster.

    The candidate rank vector is computed once over every footprint pixel.  A
    binary reference's rank is affine in its 0/1 values, so its exact Spearman is
    the correlation of that vector with the binary values.  Nonbinary references
    receive their own full tie-aware rank vector.  This is stricter than a sample
    screen and directly enforces the written 0.90 stop rule.
    """
    if surface.shape != footprint.shape:
        raise ValueError("surface/footprint mismatch")
    candidate = np.asarray(surface[footprint], dtype=np.float64)
    candidate_ranks = rankdata(candidate, method="average")
    if _pearson_correlation(candidate_ranks, candidate_ranks) is None:
        raise ValueError("candidate surface is constant inside the footprint")
    comparisons: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for item in registry.get("materialized", []):
        path = Path(item["cache_path"])
        try:
            with rasterio.open(path) as ds:
                if (ds.height, ds.width) != footprint.shape or ds.count != 1:
                    failures.append({"artifact": item["source_url"], "error": "grid/count mismatch"})
                    continue
                arr = ds.read(1)
            other = np.nan_to_num(arr[footprint], nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64, copy=False)
            binary = bool(np.all((other == 0.0) | (other == 1.0)))
            comparison_values = other if binary else rankdata(other, method="average")
            corr = _pearson_correlation(candidate_ranks, comparison_values)
            comparisons.append({
                "source_url": item["source_url"],
                "sha256": item["sha256"],
                "exact_spearman_rank_correlation": corr,
                "comparison_pixels": int(candidate.size),
                "reference_is_binary": binary,
                "duplicate_threshold": CORRELATION_THRESHOLD,
                "duplicate": bool(corr is not None and corr >= CORRELATION_THRESHOLD),
            })
        except Exception as exc:
            failures.append({"artifact": item["source_url"], "error": str(exc)})
    offenders = [x for x in comparisons if x["duplicate"]]
    return {
        "stage": "surface_before_placement",
        "registry_version": REGISTRY_VERSION,
        "comparison_method": "exact tie-aware Spearman across every footprint pixel",
        "comparisons": comparisons,
        "read_failures": failures,
        "max_exact_spearman": max((x["exact_spearman_rank_correlation"] for x in comparisons if x["exact_spearman_rank_correlation"] is not None), default=None),
        "verdict": "DUPLICATE" if offenders else ("UNRESOLVED" if failures or not registry.get("complete_discovery") or not registry.get("complete_materialization") else "UNIQUE"),
        "offenders": offenders,
    }


def compare_final_dots(mask: np.ndarray, footprint: np.ndarray, registry: dict[str, Any]) -> dict[str, Any]:
    """Final exact binary-rank and 3-pixel-overlap duplicate screen."""
    if mask.shape != footprint.shape:
        raise ValueError("mask/footprint mismatch")
    candidate = np.asarray(mask, dtype=bool) & footprint
    n_candidate = int(candidate.sum())
    if n_candidate == 0:
        raise ValueError("cannot duplicate-check an empty final mask")
    comparisons: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    f = footprint
    for item in registry.get("materialized", []):
        path = Path(item["cache_path"])
        try:
            with rasterio.open(path) as ds:
                if (ds.height, ds.width) != mask.shape or ds.count != 1:
                    failures.append({"artifact": item["source_url"], "error": "grid/count mismatch"})
                    continue
                arr = ds.read(1)
            other = np.isfinite(arr) & (arr > 0.5) & f
            corr = _binary_spearman(candidate[f], other[f])
            if other.any():
                distance = distance_transform_edt(~other)
                overlap = float(np.mean(distance[candidate] <= MIN_DISTANCE_FOR_DUPLICATE_PX))
            else:
                overlap = 0.0
            is_dup = bool((corr is not None and corr >= CORRELATION_THRESHOLD) or overlap > OVERLAP_THRESHOLD)
            comparisons.append({
                "source_url": item["source_url"],
                "sha256": item["sha256"],
                "exact_binary_spearman_rank_correlation": corr,
                "candidate_dots_within_3px_fraction": overlap,
                "registry_positive_pixels": int(other.sum()),
                "rank_correlation_threshold": CORRELATION_THRESHOLD,
                "overlap_threshold_strictly_greater_than": OVERLAP_THRESHOLD,
                "duplicate": is_dup,
            })
        except Exception as exc:
            failures.append({"artifact": item["source_url"], "error": str(exc)})
    offenders = [x for x in comparisons if x["duplicate"]]
    return {
        "stage": "final_dots",
        "registry_version": REGISTRY_VERSION,
        "candidate_positive_pixels": n_candidate,
        "comparisons": comparisons,
        "read_failures": failures,
        "max_exact_binary_spearman": max((x["exact_binary_spearman_rank_correlation"] for x in comparisons if x["exact_binary_spearman_rank_correlation"] is not None), default=None),
        "max_dot_overlap_within_3px": max((x["candidate_dots_within_3px_fraction"] for x in comparisons), default=None),
        "verdict": "DUPLICATE" if offenders else ("UNRESOLVED" if failures or not registry.get("complete_discovery") or not registry.get("complete_materialization") else "UNIQUE"),
        "offenders": offenders,
    }


# Named constant makes the protocol threshold explicit at each call site.
MIN_DISTANCE_FOR_DUPLICATE_PX = 3.0
