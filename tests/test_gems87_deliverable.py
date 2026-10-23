from __future__ import annotations

import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class DeliverableVerificationTests(unittest.TestCase):
    def test_shared_vendor_template_pins_unmodified(self) -> None:
        pins = json.loads((ROOT / "registry/template_pin.json").read_text(encoding="utf-8"))["files"]
        self.assertEqual(len(pins), 13)
        for rel, entry in pins.items():
            expected_sha = entry["sha256"] if isinstance(entry, dict) else entry
            target = (ROOT / "vendor" / "gems57" / rel) if not (ROOT / rel).is_file() else (ROOT / rel)
            self.assertTrue(target.is_file(), f"missing pinned vendor file: {rel}")
            self.assertEqual(_sha256(target), expected_sha, f"private fork detected in {rel}")

    def test_primary_zeros_geotiff_and_zip_are_valid_finite_and_binary(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        tif_path = ROOT / status["download"]["path"]
        zip_path = ROOT / status["download"]["zip_path"]
        nan_path = ROOT / status["download"]["companion_nan_path"]

        self.assertTrue(tif_path.is_file())
        self.assertTrue(zip_path.is_file())
        self.assertTrue(nan_path.is_file())

        sha = _sha256(tif_path)
        self.assertEqual(sha, status["artifact"]["sha256"])
        self.assertEqual(sha, status["validation"]["receipt_sha256"])
        self.assertEqual(sha, card["raster_sha256"])

        with rasterio.open(tif_path) as ds:
            self.assertEqual(ds.count, 1)
            self.assertEqual(ds.dtypes[0], "float32")
            self.assertEqual(ds.crs.to_epsg(), 32611)
            self.assertEqual((ds.height, ds.width), (3730, 3292))
            self.assertEqual(list(tuple(ds.transform)[:6]), [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0])
            arr = ds.read(1, masked=False)

        # Strict guarantee preventing "Predicted values must be in range [0, 1]"
        self.assertTrue(bool(np.isfinite(arr).all()))
        self.assertEqual(int(np.isnan(arr).sum()), 0)
        self.assertEqual(int(np.isinf(arr).sum()), 0)
        self.assertGreaterEqual(float(arr.min()), 0.0)
        self.assertLessEqual(float(arr.max()), 1.0)
        self.assertTrue(bool(np.all((arr == 0.0) | (arr == 1.0))))
        self.assertEqual(int((arr == 1.0).sum()), 37654)

        # Companion -nan.tif must have exact identical positive dot coordinates and NaN exterior
        with rasterio.open(nan_path) as ds_nan:
            arr_nan = ds_nan.read(1, masked=False)
        self.assertEqual(int(np.isnan(arr_nan).sum()), 7111787)
        self.assertTrue(np.array_equal(arr == 1.0, np.isfinite(arr_nan) & (arr_nan == 1.0)))

        # Single-TIFF ZIP round-trip byte identity
        with zipfile.ZipFile(zip_path) as zf:
            self.assertEqual(zf.namelist(), [tif_path.name])
            self.assertEqual(zf.read(tif_path.name), tif_path.read_bytes())

    def test_evidence_receipts_enforce_canary_uniqueness_and_monotone_gain(self) -> None:
        canary = json.loads((ROOT / "evidence/e0_leakage_canary.json").read_text(encoding="utf-8"))
        for seed_key in ("seed_20", "seed_30"):
            self.assertEqual(canary[seed_key]["n_features_tested"], 55)
            self.assertFalse(canary[seed_key]["any_leakage"])
            self.assertLessEqual(canary[seed_key]["max_symmetric_auc"], 0.90)

        holdout = json.loads((ROOT / "evidence/e1_e2_e3_holdout_results.json").read_text(encoding="utf-8"))
        scores = holdout["dual_seed_pooled"]["scores"]
        d_rand = scores["CTRL_RAND"]["dti"]
        d_topo = scores["CTRL_TOPO"]["dti"]
        d_e1 = scores["E1_BLIND_POISSON"]["dti"]
        d_e2 = scores["E2_CSCT_POISSON"]["dti"]
        d_e3 = scores["E3_CSCT_DINKELBACH"]["dti"]
        self.assertLess(d_rand, d_topo)
        self.assertLess(d_topo, d_e1)
        self.assertLess(d_e1, d_e2)
        self.assertLess(d_e2, d_e3)
        self.assertGreater(d_e3, 0.206817)

        uniq = json.loads((ROOT / "evidence/uniqueness_audit_full.json").read_text(encoding="utf-8"))
        self.assertTrue(uniq["pre_placement_surface_gate"]["passed"])
        self.assertLessEqual(uniq["pre_placement_surface_gate"]["max_abs_spearman"], 0.90)
        self.assertTrue(uniq["post_placement_discriminating_dot_gate"]["passed"])
        self.assertEqual(uniq["post_placement_discriminating_dot_gate"]["discriminating_overlap_firings"], 0)
        self.assertLessEqual(uniq["post_placement_discriminating_dot_gate"]["max_forward_3px_overlap"], 0.70)


if __name__ == "__main__":
    unittest.main()
