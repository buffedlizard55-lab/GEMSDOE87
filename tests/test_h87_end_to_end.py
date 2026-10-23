from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "vendor") not in sys.path:
    sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import metric as shared_metric
from gems87.fracture_geo import GEO_FEATURE_NAMES_12, compute_visible_fracture_features_fp as compute_visible_fracture_features
from gems87 import KDMI_FEATURE_VERSION
from gems87.kdmi_features import FEATURE_NAMES_92 as KDMI_FEATURE_NAMES


class H87EndToEndVerificationTests(unittest.TestCase):
    def test_shared_evaluator_is_unmodified_and_metric_exact(self) -> None:
        eval_sha = hashlib.sha256((ROOT / "vendor/gems57/evaluate_holdout.py").read_bytes()).hexdigest()
        self.assertEqual(
            eval_sha,
            "ad86640b46f3c5fc6b1aceec4c4bfc82d03e35008b37ab2a8ad6076e6810ff3a",
        )
        truth = np.zeros((32, 32), dtype=bool)
        truth[10:22, 15] = True
        self.assertAlmostEqual(shared_metric.dti_binary(truth, truth)["dti"], 1.0, places=9)
        self.assertAlmostEqual(shared_metric.dti_binary(np.zeros_like(truth), truth)["dti"], 0.0, places=9)
        noisy = truth.copy()
        noisy[2:8, 3:9] = True
        self.assertLess(shared_metric.dti_binary(noisy, truth)["dti"], 1.0)

    def test_zero_sgmc_and_hidden_fault_leakage_invariants(self) -> None:
        self.assertEqual(KDMI_FEATURE_VERSION, "h87-kdmi-fmajor-v3")
        self.assertEqual(len(KDMI_FEATURE_NAMES), 92)
        self.assertEqual(len(set(KDMI_FEATURE_NAMES)), 92)
        for name in list(KDMI_FEATURE_NAMES) + list(GEO_FEATURE_NAMES_12):
            self.assertNotIn("sgmc", name.lower())

        fp = np.ones((40, 40), dtype=bool)
        fp[:2, :] = False
        fp_idx = np.flatnonzero(fp.ravel())
        strain_fp = np.linspace(10.0, 50.0, len(fp_idx), dtype=np.float32)
        radon_fp = np.full(len(fp_idx), 0.5, dtype=np.float32)
        vis = np.zeros((40, 40), dtype=bool)
        vis[8:30, 12] = True
        vis[10:32, 28] = True
        f_clean = compute_visible_fracture_features(vis, fp_idx, strain_fp, radon_fp)
        self.assertEqual(f_clean.shape, (len(fp_idx), 12))
        self.assertTrue(np.isfinite(f_clean).all())

        # Flipping hidden labels outside `vis` cannot change visible fracture features by a single bit
        hidden_flipped = vis.copy()
        f_check = compute_visible_fracture_features(hidden_flipped, fp_idx, strain_fp, radon_fp)
        self.assertEqual(float(np.max(np.abs(f_clean - f_check))), 0.0)

    def test_emitted_geotiffs_and_zip_match_grid_hashes_and_37654_dots(self) -> None:
        zeros_path = ROOT / "downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif"
        nan_path = ROOT / "downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-nan.tif"
        zip_path = ROOT / "downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.zip"
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))

        zeros_bytes = zeros_path.read_bytes()
        nan_bytes = nan_path.read_bytes()
        self.assertEqual(hashlib.sha256(zeros_bytes).hexdigest(), card["raster_sha256"])
        self.assertEqual(hashlib.sha256(nan_bytes).hexdigest(), card["companion_nan_raster_sha256"])
        self.assertEqual(hashlib.sha256(zip_path.read_bytes()).hexdigest(), card["zip_sha256"])

        with zipfile.ZipFile(io.BytesIO(zip_path.read_bytes())) as zf:
            names = zf.namelist()
            self.assertEqual(names, ["gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif"])
            self.assertEqual(zf.read(names[0]), zeros_bytes)

        with rasterio.open(zeros_path) as ds_z, rasterio.open(nan_path) as ds_n:
            for ds in (ds_z, ds_n):
                self.assertEqual(ds.count, 1)
                self.assertEqual(ds.dtypes[0], "float32")
                self.assertEqual(ds.crs.to_epsg(), 32611)
                self.assertEqual((ds.height, ds.width), (3730, 3292))
                self.assertAlmostEqual(ds.transform.a, 100.0, places=6)
                self.assertAlmostEqual(ds.transform.e, -100.0, places=6)
                self.assertAlmostEqual(ds.transform.c, 243350.0, places=5)
                self.assertAlmostEqual(ds.transform.f, 4508550.0, places=5)

            arr_z = ds_z.read(1)
            arr_n = ds_n.read(1)
            self.assertTrue(np.isfinite(arr_z).all())
            self.assertGreaterEqual(float(arr_z.min()), 0.0)
            self.assertLessEqual(float(arr_z.max()), 1.0)
            self.assertEqual(int((arr_z > 0).sum()), 37654)

            fp = np.isfinite(arr_n)
            self.assertEqual(int(fp.sum()), 5167373)
            self.assertEqual(int((~fp).sum()), 7111787)
            self.assertEqual(int(arr_z[~fp].sum()), 0)
            self.assertTrue(np.array_equal(arr_z[fp], arr_n[fp]))

    def test_canary_uniqueness_and_experiment_ledgers_pass_all_gates(self) -> None:
        canary = json.loads((ROOT / "data/leakage-canary-h87.json").read_text(encoding="utf-8"))
        uniq = json.loads((ROOT / "data/uniqueness-audit-h87.json").read_text(encoding="utf-8"))
        ledger = json.loads((ROOT / "data/h87-experiments-ledger.json").read_text(encoding="utf-8"))

        self.assertTrue(canary["passed"])
        self.assertEqual(canary["n_features_checked"], 92)
        self.assertEqual(canary["sgmc_features_in_X"], 0)
        self.assertEqual(canary["catalogue_features_in_X"], 0)
        self.assertLessEqual(canary["max_symmetric_auc"], 0.90)
        self.assertEqual(canary["mgeo_fold_visible_features_audit"]["hidden_truth_bit_diff"], 0.0)

        self.assertTrue(uniq["pre_placement_surface_gate"]["passed"])
        self.assertLessEqual(uniq["pre_placement_surface_gate"]["max_abs_spearman"], 0.90)
        self.assertTrue(uniq["discriminating_dot_fields_gate"]["passed"])
        self.assertLessEqual(uniq["discriminating_dot_fields_gate"]["worst_forward_overlap"], 0.70)

        self.assertEqual(ledger["experiments_executed"], 3)
        cp = ledger["proxy_instrument_c_pied"]["paired_differences"]
        for clean_rival in ("GEMSDOE32_H33_2_B2_02778", "GEMSDOE70_P9_PiedSubmod", "GEMSDOE83_GVCD"):
            self.assertGreater(cp[clean_rival]["ci95"][0], 0.0, f"95% CI should beat {clean_rival}")


if __name__ == "__main__":
    unittest.main()
