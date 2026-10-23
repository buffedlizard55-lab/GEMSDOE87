"""Unit tests for the SNAP greedy assignment (brief v2, AXIS=SNAP)."""
from __future__ import annotations

import unittest

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from scripts.build_snap_variants import snap_dots
except Exception:  # pragma: no cover
    snap_dots = None


@unittest.skipIf(np is None or snap_dots is None, "needs numpy + geo stack")
class SnapDotsTests(unittest.TestCase):
    def setUp(self):
        self.edge = np.zeros((9, 9))
        self.edge[4, 6] = 10.0   # strong edge 2 px right of both dots
        self.edge[4, 5] = 5.0    # second-best fallback
        self.eligible = np.ones((9, 9), dtype=bool)

    def test_moves_within_2px_and_preserves_count(self):
        rows = np.array([4, 2])
        cols = np.array([4, 2])
        nr, nc, fb = snap_dots(rows, cols, self.edge, self.eligible)
        self.assertEqual(len(nr), 2)                       # count held
        disp = np.hypot(nr - rows, nc - cols)
        self.assertTrue((disp <= 2.0 + 1e-9).all())        # <= 2 px rule
        self.assertEqual(int(nr[0]), 4)
        self.assertEqual(int(nc[0]), 6)                    # dot 0 reaches peak

    def test_no_duplicate_claims(self):
        rows = np.array([4, 4])
        cols = np.array([4, 5])   # dot 1 sits on the second-best pixel
        nr, nc, fb = snap_dots(rows, cols, self.edge, self.eligible)
        claimed = set(zip(nr.tolist(), nc.tolist()))
        self.assertEqual(len(claimed), 2)                  # unique pixels
        self.assertIn((4, 6), claimed)                     # peak is claimed

    def test_ineligible_pixels_never_chosen(self):
        elig = self.eligible.copy()
        elig[4, 6] = False
        nr, nc, fb = snap_dots(np.array([4]), np.array([4]), self.edge, elig)
        self.assertFalse((int(nr[0]), int(nc[0])) == (4, 6))
        self.assertEqual((int(nr[0]), int(nc[0])), (4, 5))


if __name__ == "__main__":
    unittest.main()
