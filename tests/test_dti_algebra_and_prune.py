from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

try:
    import numpy as np
    import rasterio
except ImportError:
    np = None
    rasterio = None

try:
    from vendor.gems57 import metric as gems_metric
except ImportError:
    gems_metric = None

ROOT = Path(__file__).resolve().parents[1]
ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0


def _pure_numpy_dti_components(pred: "np.ndarray", truth: "np.ndarray", radius: float = RADIUS_PX) -> dict[str, float]:
    """Pure-NumPy exact transcription of the official DTI definition and Section 2 algebra."""
    p = np.asarray(pred, dtype=np.float64)
    g = np.asarray(truth, dtype=bool)
    gs = np.argwhere(g)
    xs = np.argwhere(p > 0.0)
    n_g = float(len(gs))
    s_mass = float(p[p > 0.0].sum())

    if len(gs) == 0 or len(xs) == 0:
        return {
            "T": 0.0,
            "S": s_mass,
            "M": 0.0,
            "G": n_g,
            "tp": 0.0,
            "fp": s_mass,
            "fn": n_g,
            "dti_official": 0.0,
            "dti_algebra": 0.0,
        }

    # Pairwise Euclidean distance matrix (|X|, |G|)
    diff = xs[:, None, :].astype(np.float64) - gs[None, :, :].astype(np.float64)
    dist = np.hypot(diff[:, :, 0], diff[:, :, 1])
    k_mat = np.maximum(0.0, 1.0 - dist / radius)  # (|X|, |G|)
    p_vec = p[xs[:, 0], xs[:, 1]][:, None]        # (|X|, 1)

    # T = sum_{g in G} max_{x} p(x) * k(x, g)
    t_per_g = (p_vec * k_mat).max(axis=0)
    T = float(t_per_g.sum())

    # M = sum_{x} p(x) * max_{g in G} k(x, g)
    k_max_per_x = k_mat.max(axis=1)
    M = float((p_vec[:, 0] * k_max_per_x).sum())

    tp = T
    fp = float((p_vec[:, 0] * (1.0 - k_max_per_x)).sum())
    fn = n_g - T

    denom_official = tp + ALPHA * fp + BETA * fn
    denom_algebra = ALPHA * T + ALPHA * (s_mass - M) + BETA * n_g
    return {
        "T": T,
        "S": s_mass,
        "M": M,
        "G": n_g,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "dti_official": float(tp / denom_official),
        "dti_algebra": float(T / denom_algebra),
    }


@unittest.skipIf(np is None, "numpy required")
class DtiAlgebraTests(unittest.TestCase):
    def test_derived_algebra_matches_official_definition_for_binary_clustered_and_soft_fields(self) -> None:
        rng = np.random.default_rng(20261023)
        for trial in range(8):
            truth = rng.random((18, 20)) < 0.08
            truth[9, 10] = True
            if trial % 2 == 0:
                pred = (rng.random((18, 20)) < 0.07).astype(np.float64)
                # Force clustered dots around (9, 10) so M > T
                pred[9, 9] = 1.0
                pred[9, 11] = 1.0
                pred[8, 10] = 1.0
            else:
                pred = np.where(rng.random((18, 20)) < 0.12, rng.uniform(0.1, 1.0, size=(18, 20)), 0.0)

            comp = _pure_numpy_dti_components(pred, truth)
            self.assertAlmostEqual(comp["fp"], comp["S"] - comp["M"], places=12)
            self.assertAlmostEqual(comp["dti_official"], comp["dti_algebra"], places=12)
            if trial == 0:
                self.assertGreater(comp["M"], comp["T"], "Clustered dots around one truth cell must satisfy M > T")

            if gems_metric is not None:
                exact = gems_metric.dti_exact(pred, truth)
                brute = gems_metric.dti_bruteforce(pred, truth)
                self.assertAlmostEqual(comp["dti_algebra"], exact["dti"], places=10)
                self.assertAlmostEqual(comp["dti_algebra"], brute["dti"], places=10)

    def test_isolated_truth_pixel_payoff_threshold_is_alpha_times_dti(self) -> None:
        # Construct baseline state with exact DTI0 = 0.28:
        # Let |G| = 100 isolated truth cells spaced > 6 px apart; 35 covered at k=1 -> T=35, S=35, M=35
        # Wait: T / (0.2*T + 0.8*G) = 0.28 => T * (1 - 0.056) = 0.224 * G => T / G = 0.224 / 0.944
        # Test exact algebraic condition on concrete grid with isolated uncovered truth pixel at (20, 20)
        grid_h, grid_w = 30, 60
        truth = np.zeros((grid_h, grid_w), dtype=bool)
        pred = np.zeros((grid_h, grid_w), dtype=np.float64)
        # Place 10 well-separated truth cells along row 5
        for k in range(10):
            truth[5, 3 + 5 * k] = True
        # Cover 3 of them exactly and add 2 false-positive dots far away -> DTI ~ 3 / (0.6 + 0.4 + 8.0) = 0.3333
        for k in range(3):
            pred[5, 3 + 5 * k] = 1.0
        pred[28, 2] = 1.0
        pred[28, 10] = 1.0
        # Isolated uncovered truth cell at (18, 45)
        truth[18, 45] = True

        base = _pure_numpy_dti_components(pred, truth)
        bar = ALPHA * base["dti_algebra"]  # ~ 0.06122

        # Soft dot directly on isolated truth cell with mass=1 at distance d where k < bar vs k > bar:
        # At distance d = sqrt(8) = 2.8284 px, k = 1 - 2.8284/3 = 0.05719 < bar (0.06122) -> lowers DTI!
        pred_below = pred.copy()
        pred_below[18 + 2, 45 + 2] = 1.0  # d = sqrt(8), k = 0.05719 < bar
        below = _pure_numpy_dti_components(pred_below, truth)
        self.assertLess(below["dti_algebra"], base["dti_algebra"])

        # At distance d = 2.0 px, k = 1 - 2/3 = 0.3333 > bar -> raises DTI!
        pred_above = pred.copy()
        pred_above[18 + 2, 45] = 1.0
        above = _pure_numpy_dti_components(pred_above, truth)
        self.assertGreater(above["dti_algebra"], base["dti_algebra"])

    def test_line_like_truth_lowers_self_credit_bar_via_multi_pixel_marginal_gain(self) -> None:
        # Construct baseline DTI0 ~ 0.375 so isolated bar alpha * DTI0 = 0.075.
        # Place a 3-pixel horizontal line segment of uncovered truth at row 20, cols 29..31.
        # A dot at (22, 30) sits at d=2.0 from (20,30) [k=0.333] or even better:
        # Place TWO parallel truth pixels at (20, 29) and (20, 31) with NO pixel at (20, 30),
        # and test a dot at (22, 30): distance to BOTH truth pixels is sqrt(5)=2.2361 -> k_self = 0.2546, dT = 2*0.2546 = 0.5093!
        # Even stronger: test d = sqrt(8) = 2.8284 px to TWO diagonal truth pixels (18, 28) and (18, 32) from (20, 30):
        # k_self = 1 - sqrt(8)/3 = 0.05719 < alpha * DTI0 (0.075), YET dT = 2 * 0.05719 = 0.11438!
        # Check exact inequality: dT > alpha * DTI0 * (dT + 1 - k_self) <=> 0.11438 > 0.075 * (0.11438 + 0.94281) = 0.07929 -> PAYS!
        truth = np.zeros((30, 50), dtype=bool)
        pred = np.zeros((30, 50), dtype=np.float64)
        for k in range(8):
            truth[4, 3 + 5 * k] = True
        for k in range(3):
            pred[4, 3 + 5 * k] = 1.0
        # Two truth pixels on a line/step separated by 4 px, uncovered:
        truth[18, 28] = True
        truth[18, 32] = True

        base = _pure_numpy_dti_components(pred, truth)
        isolated_bar = ALPHA * base["dti_algebra"]  # 3 / (0.6 + 8.0) * 0.2 = 3/8.6 * 0.2 = 0.06977

        # Candidate dot at (20, 30): distance sqrt(8) to BOTH (18, 28) and (18, 32), so k_self = 0.05719 < isolated_bar (0.06977)!
        k_self = 1.0 - np.hypot(2.0, 2.0) / 3.0
        self.assertLess(k_self, isolated_bar, "Self-credit k_self is strictly below isolated-pixel shortcut 0.2*DTI")

        pred_line = pred.copy()
        pred_line[20, 30] = 1.0
        after = _pure_numpy_dti_components(pred_line, truth)
        self.assertGreater(
            after["dti_algebra"],
            base["dti_algebra"],
            "Exact metric marginal gain raises DTI even though k_self < 0.2*DTI!",
        )


@unittest.skipIf(rasterio is None or np is None, "install requirements-validation.txt")
class PruneReleaseAndLedgerTests(unittest.TestCase):
    def test_ledger_and_releases_pass_invariants_and_re_read_gates(self) -> None:
        ledger_path = ROOT / "ledger" / "submissions.csv"
        manifest_path = ROOT / "releases" / "manifest.json"
        self.assertTrue(ledger_path.is_file(), "Missing ledger/submissions.csv")
        self.assertTrue(manifest_path.is_file(), "Missing releases/manifest.json")

        with ledger_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        built_rows = [r for r in rows if r["status"] == "BUILT"]
        self.assertEqual(len(built_rows), 3, "Expected exactly 3 BUILT variants for this session")

        # Deduplication on sha256 and (parent, axis, value)
        shas = [r["sha256"] for r in rows]
        self.assertEqual(len(shas), len(set(shas)), "Duplicate sha256 in ledger/submissions.csv")
        pairs = [(r["parent"], r["axis"], r["value"]) for r in rows]
        self.assertEqual(len(pairs), len(set(pairs)), "Duplicate (parent, axis, value) in ledger/submissions.csv")

        rel_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(rel_manifest["parent_r0_rebuild_receipt"]["zeros_sha256_exact_match"])
        self.assertTrue(rel_manifest["parent_r0_rebuild_receipt"]["nan_sha256_exact_match"])

        for rec in rel_manifest["variants"]:
            self.assertLessEqual(len(rec["form_note"]), 140)
            self.assertGreaterEqual(rec["pct_changed"], 1.0)
            self.assertLessEqual(rec["pct_changed"], 50.0)
            self.assertEqual(rec["n_dots"], 37654)

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
                self.assertEqual(ds_z.crs.to_epsg(), 32611)
                self.assertEqual((ds_n.height, ds_n.width), (3730, 3292))
                self.assertEqual((ds_z.height, ds_z.width), (3730, 3292))
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


if __name__ == "__main__":
    unittest.main()
