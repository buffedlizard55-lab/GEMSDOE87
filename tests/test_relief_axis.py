"""Unit and release tests for Agent Brief v2 (`AXIS = RELIEF`, `src/gems87/relief.py`)."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

try:
    import rasterio
except Exception:  # pragma: no cover
    rasterio = None

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src", ROOT / "vendor"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gems57.metric import ALPHA, BETA, EPS, dti_binary, kernel, marginal_accept
from gems87.relief import (
    compute_relief_terciles,
    hessian_ridge_crest_quantile,
    shift_relief_mass,
)
from scipy.ndimage import distance_transform_edt


class DtiAlgebraAndMarginalTests(unittest.TestCase):
    """Brief §2: verify DTI = T / (0.2T + 0.2(S-M) + 0.8|G|) on isolated & line-like truth."""

    def _algebra_dti(self, pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float, int, int]:
        dp = distance_transform_edt(~pred)
        dg = distance_transform_edt(~truth)
        t_val = float(kernel(dp[truth]).sum())
        m_val = float(kernel(dg[pred]).sum())
        s_val = int(pred.sum())
        g_cnt = int(truth.sum())
        denom = ALPHA * t_val + ALPHA * (s_val - m_val) + BETA * g_cnt + EPS
        return float(t_val / denom), t_val, m_val, s_val, g_cnt

    def test_algebra_matches_metric_on_isolated_and_line_truth(self) -> None:
        for line_mode in (False, True):
            truth = np.zeros((32, 32), dtype=bool)
            pred = np.zeros((32, 32), dtype=bool)
            if not line_mode:
                truth[8, 8] = True
                truth[22, 24] = True
                # Clustered dots around (8, 8) make M > T so T != M must hold!
                pred[8, 7] = True
                pred[8, 9] = True
                pred[7, 8] = True
                pred[20, 20] = True
            else:
                truth[15, 5:27] = True  # 22-pixel strike-continuous fault trace
                for c in range(6, 26, 3):
                    pred[14, c] = True
                    pred[16, c] = True

            alg_dti, t_v, m_v, s_v, g_v = self._algebra_dti(pred, truth)
            ref = dti_binary(pred, truth)
            self.assertAlmostEqual(alg_dti, ref["dti"], places=11)

            # Check exact marginal gain of candidate dot at (15, 15) vs full recomputation
            cand = (15, 15) if line_mode else (22, 23)
            pred2 = pred.copy()
            pred2[cand] = True
            alg_dti2, t_v2, m_v2, _, _ = self._algebra_dti(pred2, truth)
            dT = t_v2 - t_v
            k_self = m_v2 - m_v
            self.assertEqual(
                marginal_accept(dT, k_self, t_v, m_v, s_v, float(g_v)),
                alg_dti2 > alg_dti,
            )


class ReliefOperatorTests(unittest.TestCase):
    """Synthetic unit tests for `src/gems87/relief.py`."""

    def _synthetic_scene(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        h, w = 60, 90
        fp = np.ones((h, w), dtype=bool)
        fp[:2, :] = False  # outside-footprint border strip
        cols = np.arange(w, dtype=np.float32)[None, :]
        rows = np.arange(h, dtype=np.float32)[:, None]
        det_elev = np.broadcast_to((cols - 45.0) * 10.0, (h, w)).copy()
        det_slope = np.broadcast_to(0.2 * cols + 0.05 * (rows % 7), (h, w)).copy()
        terc = compute_relief_terciles(det_elev, det_slope, fp)["tercile"]

        # H19-5 ridges running across all three terciles
        h19 = np.zeros((h, w), dtype=bool)
        for r in range(6, 56, 6):
            h19[r, 4:86] = True

        catalogue = np.zeros((h, w), dtype=bool)
        catalogue[58, 10:80] = True
        allowed = fp & ~catalogue

        # Parent dots spaced >= 3 px (>= sqrt(8)) along rows 6, 12, ..., 54
        parent = np.zeros((h, w), dtype=bool)
        for r in range(6, 56, 6):
            for c in range(6, 84, 6):
                parent[r, c] = True

        rng = np.random.default_rng(7)
        sub_score = rng.uniform(0.0, 1.0, size=(h, w)).astype(np.float32)
        return parent, h19, terc, allowed, catalogue, sub_score

    def test_tercile_partition_and_outside_mask(self) -> None:
        _, _, terc, _, _, _ = self._synthetic_scene()
        self.assertTrue(np.all(terc[:2, :] == -1))
        counts = [int((terc == t).sum()) for t in (0, 1, 2)]
        self.assertEqual(sum(counts), 58 * 90)
        for c in counts:
            self.assertAlmostEqual(c / float(58 * 90), 1.0 / 3.0, delta=0.02)

    def test_hessian_crest_rejects_convex_ramp_and_detects_ridge(self) -> None:
        yy, xx = np.mgrid[0:80, 0:80].astype(np.float32)
        valid = np.ones((80, 80), dtype=bool)
        # Convex background ramp + weak periodic ripples + strong Gaussian fault-step ridge at x=55
        ramp = 0.002 * (xx ** 2) + 0.04 * np.sin(0.5 * yy)
        ridge = 4.0 * np.exp(-0.5 * ((xx - 55.0) / 1.5) ** 2)
        q = hessian_ridge_crest_quantile(ramp + ridge, valid, smooth_sigma=1.2)
        self.assertGreater(float(q[40, 55]), 0.90)
        self.assertLess(float(q[40, 20]), 0.75)

    def test_shift_preserves_count_spacing_untouched_tercile_and_catalogue(self) -> None:
        parent, h19, terc, allowed, catalogue, sub_score = self._synthetic_scene()
        n_parent = int(parent.sum())
        out, info = shift_relief_mass(
            parent,
            h19,
            terc,
            allowed,
            sub_score,
            src_tercile=2,
            dst_tercile=1,
            n_shift=15,
            min_sep2=8,
        )
        self.assertEqual(int(out.sum()), n_parent)
        self.assertEqual(int((out & catalogue).sum()), 0)
        self.assertTrue(info["untouched_tercile_unchanged"])
        self.assertTrue(np.array_equal(parent & (terc == 0), out & (terc == 0)))
        self.assertEqual(
            info["variant_terciles"]["counts"]["range_front"],
            info["parent_terciles"]["counts"]["range_front"] - 15,
        )
        self.assertEqual(
            info["variant_terciles"]["counts"]["piedmont"],
            info["parent_terciles"]["counts"]["piedmont"] + 15,
        )

        pts = np.column_stack(np.nonzero(out)).astype(np.float64)
        dists, _ = cKDTree(pts).query(pts, k=2)
        self.assertGreaterEqual(float(dists[:, 1].min()), float(np.sqrt(8.0)) - 1e-6)

        # Deterministic across repeated calls
        out2, _ = shift_relief_mass(
            parent,
            h19,
            terc,
            allowed,
            sub_score,
            src_tercile=2,
            dst_tercile=1,
            n_shift=15,
            min_sep2=8,
        )
        self.assertTrue(np.array_equal(out, out2))


class ReliefReleaseAndLedgerTests(unittest.TestCase):
    """Verify written `AXIS = RELIEF` artifacts, ledger uniqueness, and re-read GeoTIFF gates."""

    def _rows(self) -> list[dict[str, str]]:
        with (ROOT / "ledger" / "submissions.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_ledger_relief_rows_and_global_deduplication(self) -> None:
        rows = self._rows()
        self.assertGreaterEqual(len(rows), 15)
        self.assertEqual(len({r["sha256"] for r in rows}), len(rows))
        self.assertEqual(len({r["sha256_zeros"] for r in rows}), len(rows))
        self.assertEqual(
            len({(r["parent"], r["axis"], r["value"]) for r in rows}),
            len(rows),
        )

        relief_rows = [r for r in rows if r["axis"] == "RELIEF"]
        self.assertEqual(len(relief_rows), 3)
        self.assertEqual({r["value"] for r in relief_rows}, {"r2p12", "r2b10", "b2r15"})
        for r in relief_rows:
            self.assertEqual(r["parent"], "h33-h33-2-b2")
            self.assertEqual(r["n_dots"], "37654")
            self.assertEqual(r["status"], "BUILT")
            self.assertEqual(r["receipt_score"], "")
            self.assertEqual(r["date"], "")
            pct = float(r["pct_changed"])
            self.assertGreaterEqual(pct, 10.0)
            self.assertLessEqual(pct, 15.0)
            self.assertLessEqual(len(r["description"]), 140)
            for suffix in (".tif", "-zeros.tif"):
                self.assertTrue((ROOT / "releases" / f"{r['id']}{suffix}").is_file())

    def test_manifest_and_mechanism_cards(self) -> None:
        man = json.loads((ROOT / "releases" / "manifest_RELIEF.json").read_text(encoding="utf-8"))
        self.assertEqual(man["axis"], "RELIEF")
        self.assertTrue(man["parent_r0_rebuild_receipt"]["nan_sha256_exact_match"])
        self.assertTrue(man["parent_r0_rebuild_receipt"]["zeros_sha256_exact_match"])
        self.assertFalse(man["relief_partition"]["external_lidar_used"])
        self.assertEqual(len(man["variants"]), 3)
        self.assertEqual(
            man["report_only_diagnostics"]["leakage_canary"]["n_flagged_over_0_90"], 0
        )

        cards = json.loads(
            (ROOT / "ledger" / "mechanism_cards_relief.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(cards), 3)
        for rec in man["variants"]:
            self.assertEqual(rec["n_dots"], 37654)
            self.assertLessEqual(rec["form_note_length"], 140)
            self.assertTrue(rec["relief_operator"]["untouched_tercile_unchanged"])
            self.assertAlmostEqual(
                rec["parent_diff"]["nearest_neighbor_px"]["min"], 2.8284, places=3
            )
            self.assertAlmostEqual(
                rec["parent_diff"]["d_catalogue_px"]["min"], 2.2361, places=3
            )
        for card in cards.values():
            for key in (
                "hypothesis",
                "mechanism",
                "non_fault_mimic",
                "predicted_live_change",
                "falsifier",
            ):
                self.assertTrue(card.get(key))

    @unittest.skipIf(rasterio is None, "rasterio not installed")
    def test_relief_geotiffs_reread_from_disk(self) -> None:
        raw = ROOT / ".cache" / "raw"
        tpl = raw / "sample_submission.tif"
        cat_tif = raw / "existing_faults.tif"
        if not (tpl.is_file() and cat_tif.is_file()):
            # Check data/raw fallback used by GitHub Actions CI
            tpl = ROOT / "data" / "raw" / "sample_submission.tif"
            cat_tif = ROOT / "data" / "raw" / "existing_faults.tif"
        if not (tpl.is_file() and cat_tif.is_file()):
            self.skipTest("sample_submission.tif / existing_faults.tif not available")

        with rasterio.open(tpl) as ds:
            footprint = np.isfinite(ds.read(1))
            ref_h, ref_w = ds.height, ds.width
        with rasterio.open(cat_tif) as ds:
            catalogue = (ds.read(1) > 0) & footprint

        for r in [x for x in self._rows() if x["axis"] == "RELIEF"]:
            for suffix, sha_col in ((".tif", "sha256"), ("-zeros.tif", "sha256_zeros")):
                p = ROOT / "releases" / f"{r['id']}{suffix}"
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), r[sha_col])
                with rasterio.open(p) as ds:
                    self.assertEqual(ds.crs.to_string(), "EPSG:32611")
                    self.assertEqual((ds.height, ds.width), (ref_h, ref_w))
                    self.assertEqual(ds.dtypes[0], "float32")
                    self.assertEqual(ds.count, 1)
                    arr = ds.read(1)
                inner = arr[footprint]
                self.assertEqual(int(np.isnan(inner).sum()), 0)
                self.assertGreaterEqual(float(inner.min()), 0.0)
                self.assertLessEqual(float(inner.max()), 1.0)
                self.assertEqual(int((inner > 0.5).sum()), 37654)
                self.assertEqual(int((arr[catalogue] > 0).sum()), 0)
                if suffix == ".tif":
                    self.assertTrue(np.all(np.isnan(arr[~footprint])))
                else:
                    self.assertTrue(np.all(arr[~footprint] == 0.0))


if __name__ == "__main__":
    unittest.main()
