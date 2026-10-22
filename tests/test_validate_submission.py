from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from affine import Affine
except ImportError:
    np = None
    rasterio = None
    Affine = None

from scripts.validate_submission import validate_submission


@unittest.skipIf(rasterio is None or np is None, "install requirements-validation.txt")
class ValidateSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.reference = self.root / "sample_submission.tif"
        self.prediction = self.root / "candidate.tif"
        self.transform = Affine(100, 0, 500000, 0, -100, 4100000)
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
        nodata=np.nan,
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
        shifted = Affine(100, 0, 500100, 0, -100, 4100000)
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
        wrong_transform = Affine(50, 0, 500000, 0, -50, 4100000)
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
