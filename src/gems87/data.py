"""Data receipts and GeoTIFF grid helpers.

The downloader's SHA-256 checks establish that local bytes match a recorded owner
mirror.  They do not claim organizer authentication, which requires an authorized
comparison against the official competition download.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from .paths import RAW, REGISTRY


@dataclass(frozen=True)
class GridSpec:
    height: int
    width: int
    count: int
    dtype: str
    crs: str | None
    transform: tuple[float, float, float, float, float, float]

    @classmethod
    def from_dataset(cls, ds: rasterio.io.DatasetReader) -> "GridSpec":
        return cls(
            height=ds.height,
            width=ds.width,
            count=ds.count,
            dtype=ds.dtypes[0],
            crs=ds.crs.to_string() if ds.crs else None,
            transform=tuple(float(x) for x in tuple(ds.transform)[:6]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "height": self.height,
            "width": self.width,
            "count": self.count,
            "dtype": self.dtype,
            "crs": self.crs,
            "transform": list(self.transform),
        }


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def core_manifest(path: Path | None = None) -> dict[str, Any]:
    path = path or (REGISTRY / "data_manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def profile_matches(a: GridSpec, b: GridSpec, *, compare_count: bool = False) -> bool:
    return (
        a.height == b.height
        and a.width == b.width
        and (not compare_count or a.count == b.count)
        and a.crs == b.crs
        and np.allclose(a.transform, b.transform, rtol=0.0, atol=1e-9)
    )


def read_template(template: Path | None = None) -> tuple[np.ndarray, GridSpec, dict[str, Any]]:
    """Return footprint, exact grid specification, and writable base profile."""
    template = template or (RAW / "sample_submission.tif")
    with rasterio.open(template) as ds:
        spec = GridSpec.from_dataset(ds)
        if spec.count != 1:
            raise ValueError(f"submission template must have exactly one band, got {spec.count} at {template}")
        a = ds.read(1)
        footprint = np.isfinite(a)
        profile = ds.profile.copy()
    return footprint, spec, profile


def read_labels(
    labels_path: Path | None = None,
    footprint: np.ndarray | None = None,
    reference_grid: GridSpec | None = None,
) -> np.ndarray:
    """Read a one-band label raster, optionally requiring the template grid."""
    labels_path = labels_path or (RAW / "labels.tif")
    with rasterio.open(labels_path) as ds:
        spec = GridSpec.from_dataset(ds)
        if spec.count != 1:
            raise ValueError(f"labels raster must have exactly one band, got {spec.count} at {labels_path}")
        if reference_grid is not None and not profile_matches(spec, reference_grid, compare_count=True):
            raise ValueError(f"labels grid does not match template grid at {labels_path}")
        values = ds.read(1)
    labels = np.isfinite(values) & (values > 0)
    if footprint is not None and labels.shape != footprint.shape:
        raise ValueError(f"labels shape {labels.shape} does not match template footprint {footprint.shape}")
    return labels if footprint is None else labels & footprint


def read_band_clean(
    features_path: Path,
    index: int,
    footprint: np.ndarray,
) -> np.ndarray:
    """Read one numerical band and replace sentinels/invalid values with its in-footprint median."""
    with rasterio.open(features_path) as ds:
        raw = ds.read(index).astype(np.float32, copy=False)
        nodata = ds.nodata
    invalid = ~np.isfinite(raw)
    if nodata is not None and np.isfinite(nodata):
        # The source uses a very negative float32 sentinel.  A half-sentinel
        # threshold remains robust if TIFF metadata round-trips slightly.
        invalid |= raw <= np.float32(nodata * 0.5)
    valid = footprint & ~invalid
    if not valid.any():
        raise ValueError(f"band {index} has no finite values in the submission footprint")
    fill = np.float32(np.median(raw[valid]))
    out = raw.copy()
    out[invalid] = fill
    # Outside-footprint values must never carry structural signal into filter edges.
    out[~footprint] = fill
    return out


def inspect_core_data(
    raw_dir: Path | None = None,
    manifest_path: Path | None = None,
    *,
    verify_hashes: bool = True,
) -> dict[str, Any]:
    """Hash-check and structurally inspect the core source files.

    Raises rather than silently accepting a wrong grid, missing footprint, or a
    label/template mismatch.  This is deliberately stricter than merely opening
    the files so that later validation has a trustworthy reference grid.
    """
    raw_dir = raw_dir or RAW
    manifest = core_manifest(manifest_path)
    entries: list[dict[str, Any]] = []
    by_id = {f["id"]: f for f in manifest["files"]}
    for item in manifest["files"]:
        path = raw_dir / Path(item["dest"]).name
        rec: dict[str, Any] = {
            "id": item["id"],
            "path": str(path),
            "exists": path.is_file(),
            "expected_bytes": int(item["bytes"]),
            "expected_sha256": item["sha256"],
            "provenance": item["provenance"],
        }
        if not path.is_file():
            rec["passed"] = False
            entries.append(rec)
            continue
        rec["bytes"] = path.stat().st_size
        rec["sha256"] = sha256_file(path) if verify_hashes else None
        rec["size_match"] = rec["bytes"] == rec["expected_bytes"]
        rec["hash_match"] = (rec["sha256"] == rec["expected_sha256"]) if verify_hashes else None
        rec["passed"] = bool(rec["size_match"] and (rec["hash_match"] is not False))
        entries.append(rec)

    required = [raw_dir / "training_features.tif", raw_dir / "labels.tif", raw_dir / "sample_submission.tif"]
    if not all(p.is_file() for p in required):
        return {
            "status": "MISSING_CORE_DATA",
            "files": entries,
            "all_pins_passed": False,
            "organizer_authentication": "NOT ESTABLISHED (mirror pins only)",
        }

    with rasterio.open(raw_dir / "training_features.tif") as ds:
        feature_spec = GridSpec.from_dataset(ds)
        descriptions = list(ds.descriptions)
        feature_nodata = ds.nodata
        feature_count = ds.count
    with rasterio.open(raw_dir / "labels.tif") as ds:
        label_spec = GridSpec.from_dataset(ds)
        label_values = ds.read(1)
        label_nodata = ds.nodata
    footprint, template_spec, _ = read_template(raw_dir / "sample_submission.tif")
    labels = np.isfinite(label_values) & (label_values > 0)

    structural_checks = {
        "features_match_template_grid": profile_matches(feature_spec, template_spec),
        "labels_match_template_grid": profile_matches(label_spec, template_spec),
        "features_have_19_bands": feature_count == 19,
        "template_has_single_band": template_spec.count == 1,
        "nonempty_footprint": bool(footprint.any()),
        "labels_inside_footprint": bool(np.all(~labels | footprint)),
    }
    pin_passed = all(x["passed"] for x in entries)
    status = "PASS" if pin_passed and all(structural_checks.values()) else "FAIL"
    return {
        "status": status,
        "files": entries,
        "all_pins_passed": pin_passed,
        "organizer_authentication": "NOT ESTABLISHED (mirror pins only)",
        "grid": template_spec.as_dict(),
        "features": {
            "count": feature_count,
            "nodata": feature_nodata,
            "descriptions": descriptions,
        },
        "labels": {
            "nodata": label_nodata,
            "positive_pixels": int(labels.sum()),
        },
        "template": {
            "footprint_pixels": int(footprint.sum()),
            "outside_footprint_pixels": int((~footprint).sum()),
        },
        "structural_checks": structural_checks,
        "required_hashes": {k: by_id[k]["sha256"] for k in by_id},
    }
