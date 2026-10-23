from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
except ImportError:
    np = None
    rasterio = None
    from_origin = None

from scripts.validate_submission import main, validate_submission


@unittest.skipIf(rasterio is None or np is None, "install requirements-validation.txt")
class ValidateSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.reference = self.root / "sample_submission.tif"
        self.prediction = self.root / "candidate.tif"
        self.transform = from_origin(500000, 4100000, 100, 100)
        self.reference_values = np.array(
            [
                [0.0, 0.0, 0.0, np.nan],
                [0.0, 0.0, 0.0, np.nan],
                [0.0, 0.0, 0.0, np.nan],
            ],
            dtype="float32",
        )
        self.valid = np.array(
            [
                [0.2, 0.0, 0.7, np.nan],
                [0.0, 0.4, 1.0, np.nan],
                [0.5, 0.0, 0.1, np.nan],
            ],
            dtype="float32",
        )
        self._write(self.reference, self.reference_values, nodata=np.nan)
        self._write(self.prediction, self.valid, nodata=np.nan)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(
        self,
        path: Path,
        values,
        *,
        crs="EPSG:32611",
        transform=None,
        dtype="float32",
        nodata=float("nan"),
    ) -> None:
        if transform is None:
            transform = self.transform
        values = np.asarray(values, dtype=dtype)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=values.shape[0],
            width=values.shape[1],
            count=1,
            dtype=dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
        ) as dst:
            dst.write(values, 1)

    def test_valid_tiff_passes_and_returns_sha256(self) -> None:
        result = validate_submission(self.prediction, self.reference)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(len(result["sha256"]), 64)
        self.assertTrue(result["checks"]["no_nan_inside_footprint"]["passed"])
        self.assertTrue(result["checks"]["finite_values_in_0_1"]["passed"])
        self.assertTrue(result["checks"]["crs_matches_reference"]["passed"])
        self.assertTrue(result["checks"]["transform_matches_reference"]["passed"])
        self.assertTrue(result["checks"]["crs_shape_transform_match"]["passed"])

    def test_cli_writes_json_report_without_changing_prediction(self) -> None:
        report = self.root / "evidence" / "validation.json"
        before = self.prediction.read_bytes()
        stdout = StringIO()
        with redirect_stdout(stdout):
            result_code = main([
                "--prediction", str(self.prediction),
                "--reference", str(self.reference),
                "--report", str(report),
            ])
        self.assertEqual(result_code, 0)
        self.assertEqual(self.prediction.read_bytes(), before)
        report_data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(report_data["ready"])
        self.assertEqual(report_data["sha256"], validate_submission(self.prediction, self.reference)["sha256"])

    def test_cli_refuses_report_path_that_would_overwrite_prediction(self) -> None:
        before = self.prediction.read_bytes()
        stderr = StringIO()
        with redirect_stderr(stderr):
            result_code = main([
                "--prediction", str(self.prediction),
                "--reference", str(self.reference),
                "--report", str(self.prediction),
            ])
        self.assertEqual(result_code, 2)
        self.assertIn("refusing to overwrite", stderr.getvalue())
        self.assertEqual(self.prediction.read_bytes(), before)
        with rasterio.open(self.prediction) as ds:
            self.assertEqual(ds.count, 1)

    def test_cli_refuses_hardlink_alias_of_reference_as_report(self) -> None:
        report_alias = self.root / "report-alias.json"
        try:
            report_alias.hardlink_to(self.reference)
        except OSError as exc:
            self.skipTest(f"hard links unavailable on this filesystem: {exc}")
        before = self.reference.read_bytes()
        stderr = StringIO()
        with redirect_stderr(stderr):
            result_code = main([
                "--prediction", str(self.prediction),
                "--reference", str(self.reference),
                "--report", str(report_alias),
            ])
        self.assertEqual(result_code, 2)
        self.assertIn("refusing to overwrite", stderr.getvalue())
        self.assertEqual(self.reference.read_bytes(), before)

    def test_out_of_range_finite_value_fails_even_outside_footprint(self) -> None:
        bad = self.valid.copy()
        bad[0, 3] = -9999.0
        self._write(self.prediction, bad, nodata=-9999.0)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["finite_values_in_0_1"]["passed"])

    def test_nan_inside_footprint_fails(self) -> None:
        bad = self.valid.copy()
        bad[0, 0] = np.nan
        self._write(self.prediction, bad, nodata=np.nan)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["no_nan_inside_footprint"]["passed"])

    def test_finite_non_nodata_outside_footprint_fails(self) -> None:
        finite_outside = np.nan_to_num(self.valid, nan=0.0)
        self._write(self.prediction, finite_outside, nodata=None)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["outside_footprint_is_null_or_nodata"]["passed"])

    def test_wrong_shape_fails(self) -> None:
        self._write(self.prediction, np.zeros((3, 3), dtype="float32"), nodata=np.nan)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["shape_matches_reference"]["passed"])

    def test_wrong_transform_fails(self) -> None:
        shifted = from_origin(500100, 4100000, 100, 100)
        self._write(self.prediction, self.valid, transform=shifted, nodata=np.nan)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["transform_matches_reference"]["passed"])

    def test_wrong_crs_fails(self) -> None:
        self._write(self.prediction, self.valid, crs="EPSG:4326", nodata=np.nan)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["crs_matches_reference"]["passed"])

    def test_non_float32_fails(self) -> None:
        self._write(self.prediction, self.valid, dtype="float64", nodata=np.nan)
        result = validate_submission(self.prediction, self.reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["float32"]["passed"])

    def test_reference_with_wrong_resolution_fails_closed(self) -> None:
        wrong_reference = self.root / "wrong_resolution.tif"
        wrong_transform = from_origin(500000, 4100000, 50, 50)
        self._write(wrong_reference, self.reference_values, transform=wrong_transform, nodata=np.nan)
        result = validate_submission(self.prediction, wrong_reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["reference_100m_resolution"]["passed"])

    def test_matching_but_wrong_reference_crs_fails_closed(self) -> None:
        wrong_reference = self.root / "wrong_crs_sample.tif"
        self._write(wrong_reference, self.reference_values, crs="EPSG:4326", nodata=np.nan)
        self._write(self.prediction, self.valid, crs="EPSG:4326", nodata=np.nan)
        result = validate_submission(self.prediction, wrong_reference)
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["reference_epsg_32611"]["passed"])
        self.assertFalse(result["checks"]["crs_shape_transform_match"]["passed"])


if __name__ == "__main__":
    unittest.main()
