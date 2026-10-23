from __future__ import annotations

import unittest

import numpy as np
from scipy.ndimage import distance_transform_edt

from scripts.build_snap_variants import (
    SNAP_MAX_DIST_PX,
    SNAP_MIN_DCAT_PX,
    SNAP_OFFSETS,
    rank_normalise,
    smooth_footprint,
    snap_dots_to_edge,
)


def _env(dots, edge, catalogue=None, footprint=None):
    dots = np.asarray(dots, dtype=bool)
    H, W = dots.shape
    footprint = np.ones((H, W), dtype=bool) if footprint is None else np.asarray(footprint, dtype=bool)
    catalogue = np.zeros((H, W), dtype=bool) if catalogue is None else np.asarray(catalogue, dtype=bool)
    d_cat = distance_transform_edt(~catalogue)
    return dots, np.asarray(edge, dtype=np.float64), footprint, d_cat


class TestSnapOperator(unittest.TestCase):
    def test_window_geometry_is_13_offsets_within_2px(self):
        self.assertEqual(len(SNAP_OFFSETS), 13)
        for dy, dx in SNAP_OFFSETS:
            self.assertLessEqual(np.hypot(dy, dx), SNAP_MAX_DIST_PX)
        self.assertEqual(SNAP_OFFSETS[0], (0, 0))  # own pixel first: ties stay

    def test_count_preserved_and_bijection(self):
        rng = np.random.default_rng(7)
        dots = np.zeros((40, 40), dtype=bool)
        pts = rng.choice(40 * 40, size=60, replace=False)
        dots.flat[pts] = True
        edge = rng.random((40, 40))
        out, stats = snap_dots_to_edge(*_env(dots, edge))
        self.assertEqual(int(out.sum()), int(dots.sum()))
        self.assertEqual(stats["n_dots_out"], stats["n_dots_in"])
        # Count-preserving => vacated source pixels == newly occupied pixels; rotations (dot A lands on
        # dot B's origin while B moves on) make |out \ dots| <= n_moved, with equality only if none occur.
        self.assertEqual(int((out & ~dots).sum()), int((dots & ~out).sum()))
        self.assertLessEqual(int((out & ~dots).sum()), stats["n_moved"])

    def test_displacement_never_exceeds_2px(self):
        rng = np.random.default_rng(11)
        dots = np.zeros((30, 30), dtype=bool)
        dots.flat[rng.choice(900, size=40, replace=False)] = True
        edge = rng.random((30, 30))
        dots_in, edge_f, fp, d_cat = _env(dots, edge)
        out, stats = snap_dots_to_edge(dots_in, edge_f, fp, d_cat)
        self.assertLessEqual(stats["max_displacement_px"], SNAP_MAX_DIST_PX)
        # Every destination is within 2 px of some source (bijection on equal counts).
        src_d = distance_transform_edt(~dots_in)
        self.assertLessEqual(float(src_d[out].max()), SNAP_MAX_DIST_PX)

    def test_exclusions_respected_footprint_and_collar(self):
        dots = np.zeros((20, 20), dtype=bool)
        dots[5, 5] = True
        dots[10, 10] = True
        edge = np.zeros((20, 20))
        edge[4:7, 4:7] = 1.0  # strong block that includes collar and footprint edges
        footprint = np.ones((20, 20), dtype=bool)
        footprint[4, :] = False  # a forbidden row inside the strong block
        catalogue = np.zeros((20, 20), dtype=bool)
        catalogue[6, 5] = True  # a catalogue pixel adjacent to the first dot
        d_cat = distance_transform_edt(~catalogue)
        out, _ = snap_dots_to_edge(dots, edge, footprint, d_cat)
        self.assertEqual(int(out.sum()), 2)
        self.assertFalse(bool((out & ~footprint).any()), "dot landed outside footprint")
        self.assertTrue(bool((out & (d_cat <= SNAP_MIN_DCAT_PX)).sum() == 0), "dot landed at d_cat <= 2 px")

    def test_stay_on_tie_move_to_strictly_better(self):
        dots = np.zeros((9, 9), dtype=bool)
        dots[4, 4] = True
        edge = np.zeros((9, 9))
        # Flat field: dot must stay put.
        out, stats = snap_dots_to_edge(*_env(dots, edge))
        self.assertTrue(out[4, 4])
        self.assertEqual(stats["n_moved"], 0)
        # Single strictly-better neighbour 1 px away: dot must move exactly there.
        edge[4, 5] = 1.0
        out, stats = snap_dots_to_edge(*_env(dots, edge))
        self.assertTrue(out[4, 5])
        self.assertFalse(out[4, 4])
        self.assertEqual(stats["n_moved"], 1)
        self.assertEqual(stats["max_displacement_px"], 1.0)

    def test_deterministic_repeat_runs_identical(self):
        rng = np.random.default_rng(3)
        dots = np.zeros((35, 35), dtype=bool)
        dots.flat[rng.choice(1225, size=50, replace=False)] = True
        edge = rng.random((35, 35))
        a, _ = snap_dots_to_edge(*_env(dots, edge))
        b, _ = snap_dots_to_edge(*_env(dots, edge))
        self.assertTrue(np.array_equal(a, b))

    def test_collision_resolved_to_next_best_free_candidate(self):
        # Two dots 2 px apart, single dominant peak between them: first (row-major) claims it,
        # second must take its next-best free candidate; count preserved, no double-occupancy.
        dots = np.zeros((11, 11), dtype=bool)
        dots[5, 4] = True
        dots[5, 6] = True
        edge = np.zeros((11, 11))
        edge[5, 5] = 10.0  # shared best target for both dots
        edge[5, 7] = 5.0  # next-best for the second dot
        out, stats = snap_dots_to_edge(*_env(dots, edge))
        self.assertEqual(int(out.sum()), 2)
        self.assertTrue(out[5, 5])  # first dot (row-major) wins the peak
        self.assertTrue(out[5, 7])  # second dot falls back to its next-best
        self.assertEqual(stats["n_moved"], 2)


class TestEdgeFieldHelpers(unittest.TestCase):
    def test_smooth_footprint_ignores_outside_pixels(self):
        fp = np.zeros((7, 7), dtype=bool)
        fp[2:5, 2:5] = True
        field = np.zeros((7, 7))
        field[3, 3] = 9.0
        field[0, 0] = 1e6  # outside footprint: must not leak in
        s = smooth_footprint(field, fp, size=3)
        self.assertAlmostEqual(float(s[3, 3]), 1.0, places=6)  # 9.0 / 9 footprint px in window
        # Window at (2,2) holds 4 footprint px (one with value 9.0): footprint-weighted mean = 9/4 = 2.25.
        self.assertAlmostEqual(float(s[2, 2]), 2.25, places=6)

    def test_rank_normalise_bounds_and_order(self):
        fp = np.ones((5, 5), dtype=bool)
        field = np.arange(25, dtype=np.float64).reshape(5, 5)
        r = rank_normalise(field, fp)
        self.assertAlmostEqual(float(r.min()), 0.0, places=12)
        self.assertAlmostEqual(float(r.max()), 1.0, places=12)
        self.assertTrue(np.all(np.diff(r.ravel()) >= 0.0))


if __name__ == "__main__":
    unittest.main()
