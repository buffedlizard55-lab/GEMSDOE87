"""Fail-closed, all-finite GeoTIFF submission writer and validator."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from sklearn.ensemble import HistGradientBoostingClassifier

from .data import GridSpec, profile_matches, read_labels, read_template, sha256_file
from .features import FEATURE_NAMES, open_feature_stack
from .holdout import CANDIDATE_FEATURES, EMISSION_FRACTION, MIN_SEPARATION_PX, _feature_indices, _rows_from_flat, nms_select
from .paths import DOWNLOADS, RAW, WORK

WRITER_VERSION = "gems87.submission_writer.v1"


def _utc_tag() -> str:
    # The user-facing run passes an explicit date tag in evidence.  This fallback
    # guarantees a unique filename even when the script is run manually.
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fit_full_h87_frb_model(
    stack: np.ndarray,
    labels: np.ndarray,
    footprint: np.ndarray,
    *,
    seed: int = 87022026,
) -> HistGradientBoostingClassifier:
    """Fit the pre-registered H87-FRB calibration on all visible labels.

    This is only called after the held-out gate promoted the method.  It uses no
    label-distance predictor; labels are the response, not a feature channel.
    """
    rng = np.random.default_rng(seed)
    h, w = footprint.shape
    positive = labels & footprint
    negative = footprint & ~labels
    pflat = np.flatnonzero(positive.ravel())
    nflat_all = np.flatnonzero(negative.ravel())
    if pflat.size == 0 or nflat_all.size == 0:
        raise ValueError("need nonempty visible labels and background to fit final model")
    nflat = rng.choice(nflat_all, size=min(240_000, nflat_all.size), replace=False)
    flat = np.concatenate([pflat, nflat])
    y = np.concatenate([np.ones(pflat.size, dtype=np.uint8), np.zeros(nflat.size, dtype=np.uint8)])
    order = rng.permutation(flat.size)
    x = _rows_from_flat(stack, _feature_indices(CANDIDATE_FEATURES), flat[order], w)
    model = HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_iter=120,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=seed,
    )
    model.fit(x, y[order])
    return model


def build_h87_frb_surface(
    *,
    stack_path: Path | None = None,
    template_path: Path | None = None,
    labels_path: Path | None = None,
    emission_fraction: float = EMISSION_FRACTION,
) -> dict[str, Any]:
    """Fit the promoted model and create a continuous surface, but do not place dots.

    This separation is deliberate: the registry's rank-correlation gate must run
    on the surface before NMS placement is allowed.
    """
    stack_path = stack_path or (WORK / "h87_frb_feature_stack.npy")
    template_path = template_path or (RAW / "sample_submission.tif")
    labels_path = labels_path or (RAW / "labels.tif")
    stack, _ = open_feature_stack(stack_path)
    footprint, grid, _ = read_template(template_path)
    labels = read_labels(labels_path, footprint, grid)
    if stack.shape[1:] != footprint.shape:
        raise ValueError("feature stack and template grid differ")
    model = fit_full_h87_frb_model(stack, labels, footprint)
    _, w = footprint.shape
    active = footprint & ~labels
    flat = np.flatnonzero(active.ravel())
    scores = np.empty(flat.size, dtype=np.float32)
    feature_indices = _feature_indices(CANDIDATE_FEATURES)
    for start in range(0, flat.size, 250_000):
        part = flat[start : start + 250_000]
        x = _rows_from_flat(stack, feature_indices, part, w)
        scores[start : start + part.size] = model.predict_proba(x)[:, 1].astype(np.float32)
    surface = np.zeros(footprint.shape, dtype=np.float32)
    surface.ravel()[flat] = scores
    surface[~footprint] = 0.0
    surface_path = WORK / "h87_frb_final_surface.npy"
    np.save(surface_path, surface)
    return {
        "method": "H87-FRB",
        "writer_version": WRITER_VERSION,
        "grid": grid.as_dict(),
        "surface_path": str(surface_path),
        "emission_fraction": float(emission_fraction),
        "emission_target_pixels": int(round(float(emission_fraction) * int(footprint.sum()))),
        "minimum_separation_pixels": MIN_SEPARATION_PX,
        "feature_names": list(FEATURE_NAMES),
        "labels_as_features": False,
    }


def place_h87_frb_mask(
    surface_path: Path | str,
    *,
    template_path: Path | None = None,
    labels_path: Path | None = None,
    emission_fraction: float = EMISSION_FRACTION,
) -> dict[str, Any]:
    """Place NMS-spaced dots only after the surface duplicate gate passes."""
    template_path = template_path or (RAW / "sample_submission.tif")
    labels_path = labels_path or (RAW / "labels.tif")
    footprint, grid, _ = read_template(template_path)
    labels = read_labels(labels_path, footprint, grid)
    surface = np.load(surface_path, mmap_mode="r")
    if surface.shape != footprint.shape:
        raise ValueError("surface and template grid differ")
    active = footprint & ~labels
    flat = np.flatnonzero(active.ravel())
    scores = np.asarray(surface.ravel()[flat], dtype=np.float32)
    n_target = int(round(float(emission_fraction) * int(footprint.sum())))
    mask = nms_select(flat, scores, footprint.shape, n_target, min_separation_px=MIN_SEPARATION_PX)
    mask &= footprint & ~labels
    return {
        "method": "H87-FRB",
        "grid": grid.as_dict(),
        "mask": mask,
        "emission_fraction": float(emission_fraction),
        "emitted_positive_pixels": int(mask.sum()),
        "visible_catalogue_positive_pixels": int((mask & labels).sum()),
        "minimum_separation_pixels": MIN_SEPARATION_PX,
    }


def build_h87_frb_surface_and_mask(**kwargs: Any) -> dict[str, Any]:
    """Compatibility helper for tests; production must call the two-stage API."""
    surface = build_h87_frb_surface(**kwargs)
    placed = place_h87_frb_mask(surface["surface_path"], emission_fraction=surface["emission_fraction"])
    return {**surface, **placed}


def validate_submission_geotiff(
    geotiff: Path,
    *,
    template_path: Path | None = None,
    labels_path: Path | None = None,
) -> dict[str, Any]:
    """Reopen a written GeoTIFF and enforce portal-safe conditions.

    The strict all-array finite/range check is intentional.  It avoids the
    reported portal error even if the portal validates values outside the nominal
    footprint rather than honoring a NaN nodata convention.
    """
    template_path = template_path or (RAW / "sample_submission.tif")
    labels_path = labels_path or (RAW / "labels.tif")
    footprint, template_spec, _ = read_template(template_path)
    labels = read_labels(labels_path, footprint, template_spec)
    with rasterio.open(geotiff) as ds:
        spec = GridSpec.from_dataset(ds)
        arr = ds.read(1)
        report_tags = ds.tags()
        nodata = ds.nodata
    finite = np.isfinite(arr)
    inside = arr[footprint]
    outside = arr[~footprint]
    profile_ok = profile_matches(spec, template_spec) and spec.count == 1
    checks = {
        "single_band": spec.count == 1,
        "dtype_float32": spec.dtype == "float32",
        "shape_matches_template": (spec.height, spec.width) == (template_spec.height, template_spec.width),
        "crs_matches_template": spec.crs == template_spec.crs,
        "transform_matches_template": bool(np.allclose(spec.transform, template_spec.transform, rtol=0.0, atol=1e-9)),
        "no_nan_or_inf_anywhere": bool(finite.all()),
        "values_in_0_1_anywhere": bool(finite.all() and np.all((arr >= 0.0) & (arr <= 1.0))),
        "values_in_0_1_inside_footprint": bool(np.isfinite(inside).all() and np.all((inside >= 0.0) & (inside <= 1.0))),
        "outside_footprint_zero": bool(np.all(outside == 0.0)),
        "visible_catalogue_masked_pixel_exactly": bool(np.all(arr[labels] == 0.0)),
    }
    passed = bool(profile_ok and all(checks.values()))
    return {
        "validator_version": WRITER_VERSION,
        "file": str(geotiff),
        "sha256": sha256_file(geotiff),
        "bytes": geotiff.stat().st_size,
        "grid": spec.as_dict(),
        "template_grid": template_spec.as_dict(),
        "nodata": None if nodata is None or (isinstance(nodata, float) and np.isnan(nodata)) else float(nodata),
        "tags": report_tags,
        "full_grid": {
            "finite_pixels": int(finite.sum()),
            "nan_or_inf_pixels": int((~finite).sum()),
            "min": float(np.min(arr)) if finite.any() else None,
            "max": float(np.max(arr)) if finite.any() else None,
            "out_of_range_pixels": int((~finite | (arr < 0.0) | (arr > 1.0)).sum()),
        },
        "footprint": {
            "pixels": int(footprint.sum()),
            "finite_pixels": int(np.isfinite(inside).sum()),
            "positive_pixels": int((inside > 0.5).sum()),
            "visible_catalogue_positive_pixels": int((arr[labels] > 0.0).sum()),
        },
        "checks": checks,
        "passed": passed,
        "portal_safety_statement": (
            "PASS: all raster cells are finite float32 values in [0,1], exact template CRS/shape/transform, and visible catalogue pixels are zero."
            if passed
            else "FAIL: do not upload this GeoTIFF."
        ),
    }


def write_submission(
    mask: np.ndarray,
    *,
    out_dir: Path | None = None,
    slug: str = "h87-frb",
    timestamp_tag: str | None = None,
    template_path: Path | None = None,
    labels_path: Path | None = None,
) -> dict[str, Any]:
    """Write an all-finite zero-outside `float32` GeoTIFF and independently validate it."""
    out_dir = out_dir or DOWNLOADS
    template_path = template_path or (RAW / "sample_submission.tif")
    labels_path = labels_path or (RAW / "labels.tif")
    out_dir.mkdir(parents=True, exist_ok=True)
    footprint, template_spec, profile = read_template(template_path)
    labels = read_labels(labels_path, footprint, template_spec)
    clean = np.asarray(mask, dtype=bool)
    if clean.shape != footprint.shape:
        raise ValueError("mask and template shape differ")
    clean &= footprint & ~labels
    arr = np.where(footprint, clean.astype(np.float32), np.float32(0.0))
    arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0).clip(0.0, 1.0).astype(np.float32)
    # Content digest makes the filename self-identifying while avoiding a claim
    # that it has an organizer score.
    digest = hashlib.sha256(np.packbits(clean.ravel()).tobytes()).hexdigest()[:10]
    timestamp_tag = timestamp_tag or _utc_tag()
    path = out_dir / f"gemsdoe87-{slug}-{timestamp_tag}-{digest}-zeros.tif"
    # A content digest identifies the dot mask, not merely the file container.
    # Refuse to mint a differently named local reissue of the same predictions.
    # Re-running the exact same release path is allowed only after byte-level
    # validation and an array equality check; it updates evidence without
    # silently overwriting the TIFF.
    for prior in out_dir.glob("gemsdoe87-*.tif"):
        if prior == path:
            continue
        try:
            with rasterio.open(prior) as ds:
                if ds.tags().get("GEMS87_CONTENT_DIGEST") == digest:
                    raise FileExistsError(
                        f"refusing to mint duplicate prediction content; existing local release is {prior.name}"
                    )
        except rasterio.errors.RasterioError:
            # An unrelated corrupt file must not make an otherwise valid release
            # look unique; the desired path still receives its own validation.
            continue
    if path.exists():
        existing = validate_submission_geotiff(path, template_path=template_path, labels_path=labels_path)
        with rasterio.open(path) as ds:
            existing_array = ds.read(1)
            same_array = existing_array.shape == arr.shape and np.array_equal(existing_array, arr)
            same_digest = ds.tags().get("GEMS87_CONTENT_DIGEST") == digest
        if not (existing["passed"] and same_array and same_digest):
            raise FileExistsError(f"refusing to overwrite non-identical existing release {path}")
        existing["content_digest"] = digest
        existing["submission_name"] = path.name
        return existing
    write_profile = profile.copy()
    write_profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=None,
        compress="deflate",
        predictor=3,
        zlevel=9,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(path, "w", **write_profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(
            GEMS87_STATUS="candidate; no organizer score or acceptance receipt",
            GEMS87_WRITER=WRITER_VERSION,
            GEMS87_CONTENT_DIGEST=digest,
        )
    report = validate_submission_geotiff(path, template_path=template_path, labels_path=labels_path)
    if not report["passed"]:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"writer produced an invalid submission: {json.dumps(report['checks'], sort_keys=True)}")
    report["content_digest"] = digest
    report["submission_name"] = path.name
    return report
