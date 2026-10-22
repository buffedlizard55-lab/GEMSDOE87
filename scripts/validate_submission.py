#!/usr/bin/env python3
"""Read-only GeoTIFF preflight against the official sample grid.

The validator never writes or repairs a prediction. It fails closed on grid
mismatches, finite values outside [0, 1], NaN/Inf inside the target footprint,
and values that are not null/nodata outside the footprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def _import_raster_libs() -> tuple[Any, Any]:
    try:
        import numpy as np
        import rasterio
    except ImportError as exc:
        raise RuntimeError(
            "GeoTIFF validation requires numpy and rasterio; install "
            "requirements-validation.txt first."
        ) from exc
    return np, rasterio


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _distinct_output_path(output_path: Path, protected_paths: list[tuple[str, Path]]) -> Path:
    """Reject report paths that alias any input raster, including symlinks/hardlinks."""
    output = output_path.expanduser()
    output_resolved = output.resolve(strict=False)
    for label, protected in protected_paths:
        protected = protected.expanduser()
        aliases = output_resolved == protected.resolve(strict=False)
        if not aliases and output.exists() and protected.exists():
            try:
                aliases = output.samefile(protected)
            except OSError:
                aliases = False
        if aliases:
            raise ValueError(f"report path aliases the {label} input; refusing to overwrite it")
    return output


def _write_json_report(path: Path, content: str) -> None:
    """Atomically write a report so an interrupted write cannot leave partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _grid_signature(dataset: Any) -> dict[str, Any]:
    return {
        "width": int(dataset.width),
        "height": int(dataset.height),
        "count": int(dataset.count),
        "crs": dataset.crs.to_string() if dataset.crs else None,
        "transform": [float(value) for value in tuple(dataset.transform)[:6]],
        "bounds": [float(value) for value in tuple(dataset.bounds)],
    }


def _close_transform(first: list[float], second: list[float], tolerance: float = 1e-9) -> bool:
    return len(first) == len(second) and all(abs(a - b) <= tolerance for a, b in zip(first, second))


def validate_submission(
    prediction_path: str | Path,
    reference_path: str | Path,
    footprint_mask_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate prediction metadata and pixel values against a reference grid.

    The sample/reference raster defines the expected CRS, dimensions, and affine
    transform. Its valid-data mask defines the footprint unless an explicit
    footprint raster is passed. Pass an explicit mask only after independently
    verifying it represents the exact competition footprint; a feature-raster mask
    is not assumed to be equivalent to the sample mask.
    """
    np, rasterio = _import_raster_libs()
    prediction = Path(prediction_path)
    reference = Path(reference_path)
    footprint_path = Path(footprint_mask_path) if footprint_mask_path else None

    report: dict[str, Any] = {
        "ready": False,
        "prediction": str(prediction),
        "reference": str(reference),
        "footprint_source": str(footprint_path or reference),
        "sha256": None,
        "checks": {},
        "errors": [],
    }

    for label, path in (("prediction", prediction), ("reference", reference)):
        if not path.is_file():
            report["errors"].append(f"{label} file does not exist: {path}")
    if footprint_path is not None and not footprint_path.is_file():
        report["errors"].append(f"footprint mask file does not exist: {footprint_path}")
    if report["errors"]:
        return report

    if prediction.suffix.lower() not in {".tif", ".tiff"}:
        report["errors"].append("prediction file must have a .tif or .tiff extension")

    try:
        with rasterio.open(reference) as ref, rasterio.open(prediction) as pred:
            reference_grid = _grid_signature(ref)
            prediction_grid = _grid_signature(pred)
            if ref.count < 1:
                report["errors"].append("reference raster contains no bands")
                return report
            reference_mask = ref.read_masks(1) > 0
            reference_values = ref.read(1, masked=False)
            reference_valid = reference_mask & np.isfinite(reference_values)
            reference_single_band = ref.count == 1
            reference_epsg_ok = ref.crs is not None and ref.crs.to_epsg() == 32611
            reference_resolution_ok = (
                abs(abs(float(ref.transform.a)) - 100.0) <= 1e-6
                and abs(abs(float(ref.transform.e)) - 100.0) <= 1e-6
            )
            report["checks"]["reference_single_band"] = {"passed": bool(reference_single_band), "actual": int(ref.count)}
            report["checks"]["reference_epsg_32611"] = {
                "passed": bool(reference_epsg_ok),
                "actual": reference_grid["crs"],
            }
            report["checks"]["reference_100m_resolution"] = {
                "passed": bool(reference_resolution_ok),
                "pixel_size": [float(ref.transform.a), float(ref.transform.e)],
            }
            if not reference_single_band:
                report["errors"].append("reference sample raster must contain exactly one band")
            if not reference_epsg_ok:
                report["errors"].append("reference CRS must be EPSG:32611")
            if not reference_resolution_ok:
                report["errors"].append("reference sample raster must use 100 m pixels")

            if footprint_path is None:
                footprint = reference_valid
            else:
                with rasterio.open(footprint_path) as mask_ds:
                    mask_grid = _grid_signature(mask_ds)
                    mask_grid_matches = (
                        mask_ds.width == ref.width
                        and mask_ds.height == ref.height
                        and mask_ds.crs == ref.crs
                        and _close_transform(
                            [float(value) for value in tuple(mask_ds.transform)[:6]],
                            reference_grid["transform"],
                        )
                    )
                    report["checks"]["footprint_mask_grid_matches_reference"] = {
                        "passed": bool(mask_grid_matches),
                        "grid": mask_grid,
                    }
                    if not mask_grid_matches:
                        report["errors"].append("footprint mask CRS, shape, or transform differs from the reference grid")
                    mask_values = mask_ds.read(1, masked=False)
                    footprint = (mask_ds.read_masks(1) > 0) & np.isfinite(mask_values)

            if not np.any(footprint):
                report["errors"].append("footprint mask has no valid pixels")

            single_band = pred.count == 1
            dtype_ok = pred.dtypes[0] == "float32" if pred.count >= 1 else False
            crs_ok = pred.crs == ref.crs
            shape_ok = pred.width == ref.width and pred.height == ref.height
            transform_ok = _close_transform(
                prediction_grid["transform"], reference_grid["transform"]
            )
            bounds_ok = len(prediction_grid["bounds"]) == len(reference_grid["bounds"]) and all(
                abs(a - b) <= 1e-7 for a, b in zip(prediction_grid["bounds"], reference_grid["bounds"])
            )

            crs_shape_transform_ok = bool(
                crs_ok and reference_epsg_ok and reference_resolution_ok and shape_ok and transform_ok and bounds_ok
            )
            report["checks"].update(
                {
                    "crs_shape_transform_match": {"passed": crs_shape_transform_ok},
                    "single_band": {"passed": bool(single_band), "actual": int(pred.count)},
                    "float32": {"passed": bool(dtype_ok), "actual": list(pred.dtypes)},
                    "crs_matches_reference": {
                        "passed": bool(crs_ok and reference_epsg_ok),
                        "actual": prediction_grid["crs"],
                        "expected": reference_grid["crs"],
                    },
                    "shape_matches_reference": {
                        "passed": bool(shape_ok),
                        "actual": [int(pred.height), int(pred.width)],
                        "expected": [int(ref.height), int(ref.width)],
                    },
                    "transform_matches_reference": {
                        "passed": bool(transform_ok),
                        "actual": prediction_grid["transform"],
                        "expected": reference_grid["transform"],
                    },
                    "bounds_match_reference": {
                        "passed": bool(bounds_ok),
                        "actual": prediction_grid["bounds"],
                        "expected": reference_grid["bounds"],
                    },
                }
            )
            for key, passed, message in (
                ("single_band", single_band, "prediction must contain exactly one raster band"),
                ("float32", dtype_ok, "prediction band must have float32 datatype"),
                ("crs_matches_reference", crs_ok, "prediction CRS differs from the reference CRS"),
                ("shape_matches_reference", shape_ok, "prediction width/height differ from the reference"),
                ("transform_matches_reference", transform_ok, "prediction affine transform differs from the reference"),
                ("bounds_match_reference", bounds_ok, "prediction bounds differ from the reference"),
            ):
                if not passed:
                    report["errors"].append(message)

            if pred.count < 1:
                report["errors"].append("prediction contains no raster bands")
                values = np.empty((0, 0), dtype="float32")
            else:
                values = pred.read(1, masked=False)

            if values.shape == footprint.shape:
                nan_inside = int(np.count_nonzero(np.isnan(values) & footprint))
                nonfinite_inside = int(np.count_nonzero((~np.isfinite(values)) & footprint))
                finite = np.isfinite(values)
                out_of_range = finite & ((values < 0.0) | (values > 1.0))
                out_of_range_count = int(np.count_nonzero(out_of_range))
                infinities = int(np.count_nonzero(np.isinf(values)))
                outside = ~footprint
                nodata = pred.nodata
                outside_is_null = np.isnan(values)
                if nodata is not None:
                    try:
                        if math.isnan(float(nodata)):
                            outside_is_null = outside_is_null | np.isnan(values)
                        else:
                            outside_is_null = outside_is_null | (values == nodata)
                    except (TypeError, ValueError):
                        pass
                nonnull_outside_count = int(np.count_nonzero(outside & ~outside_is_null))
                finite_values = values[finite]
                minimum = float(np.min(finite_values)) if finite_values.size else None
                maximum = float(np.max(finite_values)) if finite_values.size else None

                no_nan_inside = nan_inside == 0
                no_nonfinite_inside = nonfinite_inside == 0
                range_ok = out_of_range_count == 0
                no_inf = infinities == 0
                outside_null_ok = nonnull_outside_count == 0
                report["checks"].update(
                    {
                        "no_nan_inside_footprint": {
                            "passed": bool(no_nan_inside),
                            "count": nan_inside,
                            "footprint_pixels": int(np.count_nonzero(footprint)),
                        },
                        "all_finite_inside_footprint": {
                            "passed": bool(no_nonfinite_inside),
                            "nonfinite_count": nonfinite_inside,
                        },
                        "finite_values_in_0_1": {
                            "passed": bool(range_ok),
                            "min": minimum,
                            "max": maximum,
                            "out_of_range_count": out_of_range_count,
                        },
                        "no_infinity": {"passed": bool(no_inf), "count": infinities},
                        "outside_footprint_is_null_or_nodata": {
                            "passed": bool(outside_null_ok),
                            "nonnull_count": nonnull_outside_count,
                            "outside_pixels": int(np.count_nonzero(outside)),
                            "nodata_tag": None if nodata is None else str(nodata),
                        },
                    }
                )
                for passed, message in (
                    (no_nan_inside, "prediction contains NaN inside the target footprint"),
                    (no_nonfinite_inside, "prediction contains non-finite values inside the target footprint"),
                    (range_ok, "finite prediction values must all be in [0, 1], including finite nodata sentinels"),
                    (no_inf, "prediction contains infinite values"),
                    (outside_null_ok, "outside-footprint pixels must be null/NaN or an in-range nodata value"),
                ):
                    if not passed:
                        report["errors"].append(message)
            else:
                report["errors"].append("prediction and footprint arrays do not have the same shape")

            report["grid"] = {
                "reference": reference_grid,
                "prediction": prediction_grid,
            }

        report["sha256"] = _sha256(prediction)
    except Exception as exc:
        report["errors"].append(f"could not read or validate GeoTIFF: {type(exc).__name__}: {exc}")

    report["ready"] = not report["errors"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", required=True, type=Path, help="candidate single-band GeoTIFF")
    parser.add_argument("--reference", required=True, type=Path, help="official sample submission GeoTIFF")
    parser.add_argument(
        "--footprint-mask",
        type=Path,
        help="optional raster on the same grid; valid pixels define the submission footprint",
    )
    parser.add_argument("--report", type=Path, help="optional path to write the JSON receipt")
    args = parser.parse_args(argv)

    report_path: Path | None = None
    try:
        if args.report:
            protected_paths = [("prediction", args.prediction), ("reference", args.reference)]
            if args.footprint_mask is not None:
                protected_paths.append(("footprint-mask", args.footprint_mask))
            report_path = _distinct_output_path(args.report, protected_paths)
        result = validate_submission(args.prediction, args.reference, args.footprint_mask)
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({"ready": False, "errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if report_path is not None:
        try:
            _write_json_report(report_path, rendered)
        except OSError as exc:
            print(json.dumps({"ready": False, "errors": [f"could not write report: {exc}"]}, indent=2), file=sys.stderr)
            return 2
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
