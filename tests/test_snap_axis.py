"""SNAP-axis unit tests and release invariants (Agent Brief v2, session `AXIS = SNAP`).

Two blocks:
  * synthetic operator tests - the snap must preserve the dot count, cap displacement at the
    Chebyshev radius, never share a destination, never gain catalogue mass, be exactly
    reproducible, and never move a dot that already sits on an edge crest;
  * release invariants - the three BUILT SNAP rows, their files, hashes and mechanism cards.
"""

from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

try:  # CI installs requirements-lock.txt, which pins rasterio
    import rasterio
except Exception:  # pragma: no cover
    rasterio = None

ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_snap_variants import (  # noqa: E402
    ARGMAX_GAIN_MARGIN_Z,
    SNAP_RADIUS_PX,
    crest_mask,
    nearest_neighbour_stats,
    residual_edge_field,
    snap_dots,
)


def synthetic_field() -> tuple[np.ndarray, np.ndarray]:
    """A 40x40 field with one smooth crest ridge at column 20 (no zero-valued plateau)."""
    cols = np.arange(40, dtype=np.float64)
    score = np.tile(np.maximum(0.0, 3.0 - 0.6 * np.abs(cols - 20.0)), (40, 1))
    allowed = np.ones((40, 40), bool)
    return score, allowed


def synthetic_dots() -> np.ndarray:
    dots = np.zeros((40, 40), bool)
    for y in range(4, 36, 4):
        dots[y, 18] = True  # exactly two pixels left of the crest (inside the snap window)
        dots[y, 30] = True  # far from the crest, no admissible move
    return dots


class SnapOperatorTests(unittest.TestCase):
    def test_count_preserved_and_displacement_capped(self) -> None:
        score, allowed = synthetic_field()
        dots = synthetic_dots()
        out, info = snap_dots(dots, score, allowed, rule="crest")
        self.assertEqual(int(out.sum()), int(dots.sum()))
        self.assertTrue(info["count_preserved"])
        self.assertGreater(info["n_moved"], 0)
        self.assertLessEqual(info["max_displacement_px"], float(np.sqrt(2 * SNAP_RADIUS_PX ** 2)))

    def test_destinations_are_unique_and_no_catalogue_mass(self) -> None:
        score, allowed = synthetic_field()
        dots = synthetic_dots()
        catalogue = np.zeros_like(dots)
        catalogue[:, 19:22] = True  # the crest itself is a "catalogue" pixel: must stay empty
        allowed = allowed & ~catalogue
        out, _ = snap_dots(dots, score, allowed, rule="crest")
        self.assertEqual(int((out & catalogue).sum()), 0, "SNAP put mass on catalogue pixels")
        pts = np.column_stack(np.nonzero(out))
        self.assertEqual(len(pts), len({tuple(p) for p in pts}), "two dots share a destination")

    def test_dot_already_on_crest_never_moves(self) -> None:
        score, allowed = synthetic_field()
        dots = np.zeros((40, 40), bool)
        dots[10, 20] = True  # exactly on the crest
        out, info = snap_dots(dots, score, allowed, rule="crest")
        self.assertEqual(int(info["n_dots_on_crest_at_parent"]), 1)
        self.assertEqual(int(info["n_moved"]), 0)
        self.assertTrue(bool(out[10, 20]))

    def test_operator_is_exactly_reproducible(self) -> None:
        score, allowed = synthetic_field()
        dots = synthetic_dots()
        a, _ = snap_dots(dots, score, allowed, rule="crest")
        b, _ = snap_dots(dots, score, allowed, rule="crest")
        self.assertTrue(np.array_equal(a, b))

    def test_argmax_rule_respects_gain_margin(self) -> None:
        score = np.zeros((20, 20), np.float64)
        score[5, 5] = 1.0
        score[5, 6] = 0.9  # below the margin from 1.0 back to a weak dot
        dots = np.zeros((20, 20), bool)
        dots[5, 3] = True  # 2 px away, own score 0 -> gain 1.0 >= margin
        allowed = np.ones((20, 20), bool)
        out, info = snap_dots(dots, score, allowed, rule="argmax_gain")
        self.assertEqual(int(info["n_moved"]), 1)
        self.assertTrue(bool(out[5, 5]))
        self.assertEqual(info["gain_margin_z"], ARGMAX_GAIN_MARGIN_Z)

    def test_crest_mask_requires_local_maximum_above_zero(self) -> None:
        score = np.zeros((10, 10), np.float64)
        score[4, 4] = 2.0
        score[7, 7] = -1.0
        allowed = np.ones((10, 10), bool)
        crest = crest_mask(score, allowed)
        self.assertTrue(bool(crest[4, 4]))
        self.assertFalse(bool(crest[7, 7]), "a trough must not count as an edge crest")

    def test_residual_field_removes_regional_trend(self) -> None:
        # A pure ramp has no local crest: after the 2 km high-pass the interior residual is ~flat
        # (the array border carries reflect-padding edge effects and is excluded here).
        ramp = np.tile(np.arange(600, dtype=np.float64), (120, 1))
        fp = np.ones_like(ramp, bool)
        resid, info = residual_edge_field(ramp, fp, sigma_px=20.0)
        # Residual that survives the 2 km high-pass is < 1% of the input spread: the ramp trend is gone.
        self.assertLess(info["raw_residual_over_z_std"], 0.01)
        self.assertGreater(info["trend_fraction_of_variance"], 0.99)

    def test_nearest_neighbour_census_detects_new_pairs(self) -> None:
        dots = np.zeros((20, 20), bool)
        dots[5, 5] = True
        dots[5, 7] = True
        self.assertEqual(nearest_neighbour_stats(dots)["n_with_nn_lt_2px"], 0)
        dots[5, 6] = True
        self.assertGreaterEqual(nearest_neighbour_stats(dots)["n_with_nn_lt_2px"], 2)


class SnapReleaseTests(unittest.TestCase):
    """Invariants of the written artifacts, independent of the raster library."""

    def _rows(self) -> list[dict[str, str]]:
        with (ROOT / "ledger" / "submissions.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_three_snap_rows_are_unique_and_complete(self) -> None:
        rows = self._rows()
        snap = [r for r in rows if r["axis"] == "SNAP"]
        # Union ledger: this session's 3 crest-snap arms plus the parallel edge-argmax session's
        # arms (tmi2/grav2/comb2) coexist; (parent, axis, value) and sha256 stay unique below.
        self.assertGreaterEqual(len(snap), 3, "expected at least this session's 3 BUILT SNAP variants")
        self.assertLessEqual({"tmi-hg", "scarp", "grav-argmax"}, {r["value"] for r in snap})
        self.assertEqual(len({r["sha256"] for r in rows}), len(rows), "duplicate sha256 in the ledger")
        pairs = {(r["parent"], r["axis"], r["value"]) for r in rows}
        self.assertEqual(len(pairs), len(rows), "duplicate (parent, axis, value) in the ledger")
        for r in snap:
            self.assertEqual(r["parent"], "h33-h33-2-b2")
            self.assertEqual(r["n_dots"], "37654")
            self.assertEqual(r["status"], "BUILT")
            self.assertEqual(r["receipt_score"], "", "the human fills receipt_score, never the builder")
            self.assertEqual(len(r["sha256"]), 64)
            self.assertEqual(len(r["sha256_zeros"]), 64)
            self.assertTrue(0.0 < float(r["pct_changed"]) <= 100.0)
            self.assertLessEqual(len(r["description"]), 140)
            for suffix in (".tif", "-zeros.tif"):
                self.assertTrue((ROOT / "releases" / f"{r['id']}{suffix}").is_file(), r["id"] + suffix)

    def test_release_manifest_and_cards(self) -> None:
        man = json.loads((ROOT / "releases" / "manifest_SNAP.json").read_text(encoding="utf-8"))
        self.assertEqual(man["axis"], "SNAP")
        self.assertTrue(man["parent_r0_rebuild_receipt"]["nan_sha256_exact_match"])
        self.assertTrue(man["parent_r0_rebuild_receipt"]["zeros_sha256_exact_match"])
        self.assertEqual(len(man["variants"]), 3)
        cards = json.loads((ROOT / "ledger" / "mechanism_cards_snap.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cards), 3)
        for rec in man["variants"]:
            self.assertLessEqual(rec["form_note_length"], 140)
            self.assertEqual(rec["n_dots"], 37654)
            self.assertLessEqual(rec["snap_operator"]["mean_displacement_px"], 2.8285)
            self.assertEqual(rec["parent_diff"]["d_catalogue_px"]["min"], 2.2361)
            self.assertEqual(rec["parent_diff"]["nearest_neighbour_parent"]["n_with_nn_lt_2px"], 0)
            self.assertIn("leakage_canary", man["report_only_diagnostics"])
        for card in cards.values():
            for key in ("hypothesis", "mechanism", "non_fault_mimic", "predicted_live_change", "falsifier"):
                self.assertIn(key, card)

    @unittest.skipIf(rasterio is None, "install requirements-lock.txt")
    def test_files_re_read_from_disk_match_the_ledger_and_stay_off_the_catalogue(self) -> None:
        raw = ROOT / ".cache" / "raw"
        template = raw / "sample_submission.tif"
        catalogue_tif = raw / "existing_faults.tif"
        if not (template.is_file() and catalogue_tif.is_file()):
            self.skipTest("pinned competition inputs not restored in this checkout")
        with rasterio.open(template) as ds:
            footprint = np.isfinite(ds.read(1))
            ref_profile = ds.profile
        with rasterio.open(catalogue_tif) as ds:
            catalogue = (ds.read(1) > 0) & footprint

        for r in [x for x in self._rows() if x["axis"] == "SNAP"]:
            for suffix, key in ((".tif", "sha256"), ("-zeros.tif", "sha256_zeros")):
                path = ROOT / "releases" / f"{r['id']}{suffix}"
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(digest, r[key], f"ledger hash mismatch for {path.name}")
                with rasterio.open(path) as ds:
                    self.assertEqual(ds.crs.to_string(), "EPSG:32611")
                    self.assertEqual((ds.height, ds.width), (ref_profile["height"], ref_profile["width"]))
                    self.assertEqual(ds.dtypes[0], "float32")
                    self.assertEqual(ds.count, 1)
                    arr = ds.read(1)
                self.assertEqual(int((arr[catalogue] > 0).sum()), 0)
                self.assertEqual(int(np.isnan(arr[footprint]).sum()) if "zeros" not in suffix else 0, 0)
                inner = arr[footprint]
                self.assertTrue(np.isfinite(inner).all() or "nan" in suffix)
                self.assertGreaterEqual(float(np.nanmin(inner)), 0.0)
                self.assertLessEqual(float(np.nanmax(inner)), 1.0)
                self.assertEqual(int((inner > 0.5).sum()), 37654)


if __name__ == "__main__":
    unittest.main()
