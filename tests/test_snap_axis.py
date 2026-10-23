from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems87.snap import crest_mask, disk_offsets, snap_dots  # noqa: E402

try:
    import rasterio
except Exception:  # pragma: no cover
    rasterio = None


class SnapOperatorTests(unittest.TestCase):
    def test_disk_offsets_radius2_has_13_cells(self) -> None:
        offs = disk_offsets(2.0)
        self.assertEqual(len(offs), 13)
        self.assertIn((0, 2), offs)
        self.assertNotIn((1, 2), offs)  # d^2 = 5 > 4

    def test_crest_mask_finds_ridge_line_not_flanks(self) -> None:
        y, x = np.mgrid[0:21, 0:21]
        e = -np.abs(x - 10).astype(float)  # N-S ridge at column 10
        crest = crest_mask(e, min_dirs=2)
        self.assertTrue(crest[5:15, 10].all())
        self.assertFalse(crest[:, 9].any())
        self.assertFalse(crest[:, 11].any())

    def test_crest_mask_ignores_nan(self) -> None:
        e = np.full((5, 5), np.nan)
        e[2, 2] = 1.0
        self.assertTrue(crest_mask(e, 2)[2, 2])
        self.assertEqual(int(crest_mask(e, 2).sum()), 1)

    def test_snap_moves_onto_crest_and_preserves_count_and_spacing(self) -> None:
        h, w = 30, 30
        y, x = np.mgrid[0:h, 0:w]
        e = -np.abs(x - 15).astype(float)
        crest = crest_mask(e, 2)
        allowed = np.ones((h, w), bool)
        dots = np.zeros((h, w), bool)
        dots[5, 13] = True  # 2 px west of the ridge
        dots[12, 16] = True  # 1 px east
        dots[20, 15] = True  # already on the ridge
        dots[25, 5] = True  # 10 px away: no crest in window
        out, st = snap_dots(dots, e, crest, allowed, radius=2.0, min_dist_sq=5)
        self.assertEqual(int(out.sum()), 4)
        self.assertTrue(out[5, 15] and out[12, 15] and out[20, 15] and out[25, 5])
        self.assertEqual(st["n_moved"], 2)
        self.assertAlmostEqual(st["mean_displacement_px_all_dots"], 0.75)
        pts = np.argwhere(out)
        d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, 99)
        self.assertGreaterEqual(int(d2.min()), 5)

    def test_snap_respects_allowed_mask_and_spacing_conflicts(self) -> None:
        h, w = 20, 20
        y, x = np.mgrid[0:h, 0:w]
        e = -np.abs(x - 10).astype(float)
        crest = crest_mask(e, 2)
        allowed = np.ones((h, w), bool)
        allowed[:, 10] = False  # ridge forbidden (e.g. catalogue collar)
        dots = np.zeros((h, w), bool)
        dots[5, 9] = True
        out, st = snap_dots(dots, e, crest, allowed, 2.0, 5)
        self.assertFalse(out[:, 10].any())
        self.assertTrue(out[5, 9])  # no allowed crest -> stays
        # Two dots competing for the same crest neighbourhood: one must be refused by spacing.
        allowed[:] = True
        dots = np.zeros((h, w), bool)
        dots[5, 8] = True
        dots[6, 12] = True
        out, st = snap_dots(dots, e, crest, allowed, 2.0, 5)
        self.assertEqual(int(out.sum()), 2)
        pts = np.argwhere(out)
        self.assertGreaterEqual(int(((pts[0] - pts[1]) ** 2).sum()), 5)
        self.assertEqual(st["n_moved"] + st["n_blocked_by_spacing"], st["n_with_better_crest"])

    def test_snap_is_deterministic(self) -> None:
        rng = np.random.default_rng(0)
        e = rng.random((40, 40))
        crest = crest_mask(e, 2)
        dots = np.zeros((40, 40), bool)
        dots[::3, ::3] = True
        a, _ = snap_dots(dots, e, crest, np.ones_like(dots), 2.0, 5)
        b, _ = snap_dots(dots, e, crest, np.ones_like(dots), 2.0, 5)
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(int(a.sum()), int(dots.sum()))


class SnapLedgerAndReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        with (ROOT / "ledger/submissions.csv").open(encoding="utf-8", newline="") as f:
            self.rows = list(csv.DictReader(f))
        self.snap = [r for r in self.rows if r["axis"] == "SNAP"]
        self.manifest = json.loads((ROOT / "releases/snap_manifest.json").read_text(encoding="utf-8"))

    def test_three_unique_snap_rows(self) -> None:
        self.assertEqual({r["value"] for r in self.snap}, {"tmihg", "gravhg", "slope"})
        shas = [r["sha256"] for r in self.rows] + [r["sha256_zeros"] for r in self.rows if r["sha256_zeros"]]
        self.assertEqual(len(shas), len(set(shas)))
        pairs = [(r["parent"], r["axis"], r["value"]) for r in self.rows]
        self.assertEqual(len(pairs), len(set(pairs)))
        for r in self.snap:
            self.assertEqual(r["parent"], "h33-h33-2-b2")
            self.assertEqual(r["n_dots"], "37654")
            self.assertEqual(r["status"], "BUILT")
            self.assertEqual(r["receipt_score"], "")
            self.assertLessEqual(len(r["description"]), 140)

    def test_manifest_records_exact_r0_rebuild_and_mechanism_cards(self) -> None:
        rr = self.manifest["parent_r0_rebuild_receipt"]
        self.assertTrue(rr["nan_sha256_exact_match"] and rr["zeros_sha256_exact_match"])
        for v in self.manifest["variants"]:
            for key in ("hypothesis", "mechanism", "non_fault_mimic", "predicted_live_change", "falsifier"):
                self.assertIn(key, v["mechanism_card"])
            self.assertIn("mean_displacement_px_all_dots", v["snap_stats"])
            self.assertEqual(v["parent_diff"]["d_catalogue_px"]["min"] > 2.0, True)

    @unittest.skipIf(rasterio is None, "rasterio missing")
    def test_release_files_reread_and_match(self) -> None:
        for v in self.manifest["variants"]:
            pn, pz = ROOT / v["primary_file"], ROOT / v["zeros_fallback_file"]
            self.assertEqual(hashlib.sha256(pn.read_bytes()).hexdigest(), v["sha256"])
            self.assertEqual(hashlib.sha256(pz.read_bytes()).hexdigest(), v["zeros_sha256"])
            self.assertTrue(v["id"].endswith(v["sha256"][:8]))
            with rasterio.open(pn) as a, rasterio.open(pz) as b:
                self.assertEqual(a.crs.to_epsg(), 32611)
                self.assertEqual((a.height, a.width, a.count, a.dtypes[0]), (3730, 3292, 1, "float32"))
                self.assertEqual(tuple(a.transform)[:6], (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))
                an, az = a.read(1), b.read(1)
            fp = np.isfinite(an)
            self.assertEqual(int(fp.sum()), 5_167_373)
            self.assertTrue(np.array_equal(an[fp], az[fp]))
            self.assertTrue((az[~fp] == 0).all())
            self.assertEqual(int((an[fp] > 0.5).sum()), 37_654)
            self.assertTrue(((an[fp] == 0) | (an[fp] == 1)).all())


if __name__ == "__main__":
    unittest.main()
