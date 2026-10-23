from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from scipy.stats import rankdata
except ImportError:
    np = None
    rasterio = None
    rankdata = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gems87.snap import (  # noqa: E402
    DEFAULT_MIN_SEP_SQ,
    compute_cross_strike_frame,
    empirical_quantile_map,
    hessian_crest_quantile,
    isotropic_horizontal_gradient,
    snap_dots,
    snap_window_offsets,
)


@unittest.skipIf(np is None, "numpy required")
class SnapOperatorUnitTests(unittest.TestCase):
    def test_empirical_quantile_matches_scipy_midrank_with_ties(self) -> None:
        arr = np.array([[10.0, 20.0, 20.0], [5.0, -999.0, 30.0]], dtype=np.float32)
        valid = arr > -100.0
        q_map = empirical_quantile_map(arr, valid)
        self.assertTrue(np.isneginf(q_map[1, 1]))
        expected = rankdata(arr[valid], method="average") / float(valid.sum())
        np.testing.assert_allclose(q_map[valid], expected, rtol=1e-6, atol=1e-6)

    def test_hessian_crest_vanishes_on_planar_ramp_and_peaks_on_1d_ridge(self) -> None:
        yy, xx = np.mgrid[0:32, 0:48].astype(np.float32)
        valid = np.ones((32, 48), dtype=bool)
        # Left half (cols 0..20): convex regional ramp -> -lambda_min == 0.0 identically
        # Right half (cols 22..47): periodic background ripples + sharp fault ridge at x = 36
        ramp_part = np.where(xx <= 20.0, np.exp(0.12 * xx + 0.04 * yy), 0.0)
        bg_ripples = np.where(xx >= 22.0, 2.0 * (1.0 + np.cos(0.9 * xx)), 0.0)
        ridge_part = 30.0 * np.exp(-0.5 * ((xx - 36.0) / 1.0) ** 2)
        combined_grad = (ramp_part + bg_ripples + ridge_part).astype(np.float32)

        q_map, v_int = hessian_crest_quantile(combined_grad, valid)
        self.assertTrue(bool(v_int[16, 10]))
        self.assertTrue(bool(v_int[16, 36]))
        # Planar ramp interior sits strictly below the 0.75 SNAP prominence floor (zero uphill drift)
        self.assertLess(float(q_map[4:-4, 4:18].max()), 0.75)
        # 1-D ridge centerline at x = 36 must peak sharply above 0.90 and exceed flanking cols 34 & 38
        self.assertGreater(float(q_map[16, 36]), 0.90)
        self.assertGreater(float(q_map[16, 36]), float(q_map[16, 34]))
        self.assertGreater(float(q_map[16, 36]), float(q_map[16, 38]))

    def test_nodata_boundary_erosion_blocks_border_step_artifacts(self) -> None:
        field = np.ones((20, 20), dtype=np.float32) * 50.0
        valid = np.ones((20, 20), dtype=bool)
        valid[:, :4] = False
        field[~valid] = -3.4e38
        grad, v_int = isotropic_horizontal_gradient(field, valid)
        # Column 4 touches nodata column 3, so v_int must mask column 4 out
        self.assertFalse(bool(v_int[10, 4]))
        self.assertTrue(bool(v_int[10, 5]))
        self.assertEqual(float(grad[10, 5]), 0.0)

    def test_snap_dots_preserves_count_exclusions_spacing_and_cross_strike_direction(self) -> None:
        h, w = 40, 40
        # Parent N-S ribbon on cols 14..15; true geophysical crest sits 2 px east on col 16
        ridge = np.zeros((h, w), dtype=bool)
        ridge[5:35, 14:16] = True
        nx_n, ny_n, coh = compute_cross_strike_frame(ridge)

        parent = np.zeros((h, w), dtype=bool)
        for r in range(6, 34, 4):  # 7 dots spaced 4 px apart along col 14
            parent[r, 14] = True

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        crest = np.exp(-0.5 * ((xx - 16.0) / 0.8) ** 2).astype(np.float32)
        valid = np.ones((h, w), dtype=bool)
        q_crest = empirical_quantile_map(crest, valid)

        allowed = np.ones((h, w), dtype=bool)
        allowed[6, 16] = False  # Block east crest for first dot to verify exclusion enforcement

        res = snap_dots(
            parent,
            q_crest,
            allowed,
            valid,
            nx_n,
            ny_n,
            coh,
            max_radius_px=2.0,
            min_sep_sq=DEFAULT_MIN_SEP_SQ,
            min_peak_q=0.75,
            min_gain_q=0.05,
        )
        out = res["dots"]
        self.assertEqual(int(out.sum()), int(parent.sum()))
        self.assertEqual(int((out & ~allowed).sum()), 0)
        self.assertLessEqual(res["max_displacement_px"], 2.0)
        # Unblocked dots at r = 10..30 should snap 2 px east onto col 16 without N-S drift
        for r in range(10, 34, 4):
            self.assertTrue(bool(out[r, 16]), f"Expected dot at ({r}, 16)")

        # Pairwise spacing >= sqrt(8)
        pts = np.argwhere(out).astype(np.float64)
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d2 = float(np.sum((pts[i] - pts[j]) ** 2))
                self.assertGreaterEqual(d2, float(DEFAULT_MIN_SEP_SQ) - 1e-9)

    def test_snap_rejects_radius_above_2px_and_disallowed_parent(self) -> None:
        with self.assertRaises(ValueError):
            snap_window_offsets(2.5)
        parent = np.zeros((10, 10), dtype=bool)
        parent[5, 5] = True
        allowed = np.zeros((10, 10), dtype=bool)
        valid = np.ones((10, 10), dtype=bool)
        z = np.zeros((10, 10), dtype=np.float32)
        with self.assertRaises(ValueError):
            snap_dots(parent, z, allowed, valid, z, z, z)


@unittest.skipIf(rasterio is None or np is None, "install requirements-validation.txt")
class SnapReleaseAndLedgerTests(unittest.TestCase):
    def test_snap_releases_manifest_cards_and_ledger_pass_all_gates(self) -> None:
        ledger_path = ROOT / "ledger" / "submissions.csv"
        snap_manifest_path = ROOT / "releases" / "snap_manifest.json"
        snap_cards_path = ROOT / "ledger" / "snap_mechanism_cards.json"
        self.assertTrue(ledger_path.is_file())
        self.assertTrue(snap_manifest_path.is_file())
        self.assertTrue(snap_cards_path.is_file())

        with ledger_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        snap_rows = [r for r in rows if r["axis"] == "SNAP" and r["status"] == "BUILT"]
        self.assertEqual(len(snap_rows), 3)
        self.assertEqual({r["value"] for r in snap_rows}, {"rtp2", "tg2", "scarp2"})

        shas = [r["sha256"] for r in rows]
        self.assertEqual(len(shas), len(set(shas)), "Duplicate sha256 in ledger/submissions.csv")
        pairs = [(r["parent"], r["axis"], r["value"]) for r in rows]
        self.assertEqual(len(pairs), len(set(pairs)), "Duplicate (parent, axis, value) in ledger/submissions.csv")

        manifest = json.loads(snap_manifest_path.read_text(encoding="utf-8"))
        self.assertFalse(manifest["external_lidar_used"])
        self.assertEqual(manifest["manifest_verification"]["verified_files_count"], 25)
        self.assertTrue(manifest["parent_r0_rebuild_receipt"]["zeros_sha256_exact_match"])
        self.assertTrue(manifest["parent_r0_rebuild_receipt"]["nan_sha256_exact_match"])

        cards = json.loads(snap_cards_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cards), 3)
        for card in cards.values():
            for key in ("hypothesis", "mechanism", "non_fault_mimic", "predicted_live_change", "falsifier"):
                self.assertIn(key, card)

        cat_mask = None
        for cand_cat in (ROOT / "data" / "raw" / "existing_faults.tif", ROOT / ".cache" / "raw" / "existing_faults.tif"):
            if cand_cat.is_file():
                with rasterio.open(cand_cat) as ds_c:
                    cat_mask = ds_c.read(1) > 0
                break

        for rec in manifest["variants"]:
            self.assertEqual(rec["n_dots"], 37654)
            self.assertLessEqual(len(rec["form_note"]), 140)
            disp = rec["displacement_stats"]
            self.assertLessEqual(disp["max_displacement_px"], 2.0)
            self.assertGreater(disp["mean_displacement_all_px"], 0.0)
            self.assertLessEqual(disp["mean_displacement_all_px"], 2.0)

            p_nan = ROOT / rec["primary_file"]
            p_zer = ROOT / rec["zeros_fallback_file"]
            self.assertTrue(p_nan.is_file(), f"Missing {p_nan}")
            self.assertTrue(p_zer.is_file(), f"Missing {p_zer}")

            actual_nan_sha = hashlib.sha256(p_nan.read_bytes()).hexdigest()
            actual_zer_sha = hashlib.sha256(p_zer.read_bytes()).hexdigest()
            self.assertEqual(actual_nan_sha, rec["sha256"])
            self.assertEqual(actual_zer_sha, rec["zeros_sha256"])
            self.assertTrue(rec["id"].endswith(actual_nan_sha[:8]))

            with rasterio.open(p_nan) as ds_n, rasterio.open(p_zer) as ds_z:
                self.assertEqual(ds_n.count, 1)
                self.assertEqual(ds_z.count, 1)
                self.assertEqual(ds_n.dtypes[0], "float32")
                self.assertEqual(ds_z.dtypes[0], "float32")
                self.assertEqual(ds_n.crs.to_epsg(), 32611)
                self.assertEqual((ds_n.height, ds_n.width), (3730, 3292))
                self.assertEqual(tuple(ds_n.transform)[:6], (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))

                arr_n = ds_n.read(1)
                arr_z = ds_z.read(1)
                fp = np.isfinite(arr_n)
                self.assertEqual(int(fp.sum()), 5_167_373)
                self.assertTrue(np.all((arr_n[fp] >= 0.0) & (arr_n[fp] <= 1.0)))
                self.assertTrue(np.all(np.isnan(arr_n[~fp])))
                self.assertTrue(np.all(np.isfinite(arr_z)))
                self.assertTrue(np.all(arr_z[~fp] == 0.0))
                self.assertTrue(np.array_equal(arr_n[fp], arr_z[fp]))
                self.assertEqual(int((arr_n[fp] > 0.5).sum()), 37_654)
                if cat_mask is not None:
                    self.assertEqual(int((arr_n[cat_mask & fp] > 0).sum()), 0)
                    self.assertEqual(int((arr_z[cat_mask & fp] > 0).sum()), 0)


if __name__ == "__main__":
    unittest.main()
