from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems87.concentration import (  # noqa: E402
    MIN_SEP2,
    exclusion_offsets,
    relocate,
)


class ConcentrationAxisTests(unittest.TestCase):
    def test_exclusion_offsets_match_parent_sqrt8_rule(self) -> None:
        offs = {tuple(map(int, row)) for row in exclusion_offsets(8)}
        self.assertIn((0, 0), offs)
        self.assertIn((1, 2), offs)  # d^2 = 5 < 8
        self.assertNotIn((2, 2), offs)  # d^2 = 8 is allowed (parent min)

    def test_relocate_preserves_count_and_moves_requested_fraction(self) -> None:
        h, w = 40, 40
        prior = np.zeros((h, w), dtype=bool)
        prior[:10, :10] = True  # high-prior 10 px block at NW
        parent = np.zeros((h, w), dtype=bool)
        # 20 parent dots in the SE (low prior), 4-separated so spacing holds.
        coords = [(r, c) for r in range(22, 38, 4) for c in range(22, 38, 4)]
        for r, c in coords[:16]:
            parent[r, c] = True
        allowed = np.ones((h, w), dtype=bool)
        allowed[:2, :] = False  # fake collar strip
        n_parent = int(parent.sum())
        n_move = 4
        result = relocate(parent, prior, allowed, n_move, block_px=10, min_sep2=MIN_SEP2)
        out = result["dots"]
        self.assertEqual(int(out.sum()), n_parent)
        self.assertEqual(result["n_removed"], n_move)
        self.assertEqual(result["n_added"], n_move)
        self.assertAlmostEqual(result["pct_changed"], 100.0 * n_move / n_parent)
        # Mass should increase in the high-prior NW block.
        self.assertGreater(int(out[:10, :10].sum()), int(parent[:10, :10].sum()))
        self.assertLess(int(out[20:, 20:].sum()), int(parent[20:, 20:].sum()))
        # No two output dots closer than sqrt(8).
        rows, cols = np.where(out)
        xy = np.column_stack([rows, cols]).astype(np.float64)
        dmin = np.inf
        for i in range(len(xy)):
            for j in range(i + 1, len(xy)):
                dmin = min(dmin, float(np.sum((xy[i] - xy[j]) ** 2)))
        self.assertGreaterEqual(dmin, 8.0)

    def test_relocate_rejects_parent_outside_allowed_and_oversize_move(self) -> None:
        parent = np.zeros((12, 12), dtype=bool)
        parent[6, 6] = True
        parent[6, 9] = True
        prior = np.zeros((12, 12), dtype=bool)
        allowed = np.zeros((12, 12), dtype=bool)
        allowed[6, 6] = True  # second parent dot is not allowed
        with self.assertRaises(ValueError):
            relocate(parent, prior, allowed, 1, block_px=10, min_sep2=MIN_SEP2)
        allowed[6, 9] = True
        with self.assertRaises(ValueError):
            relocate(parent, prior, allowed, 2, block_px=10, min_sep2=MIN_SEP2)


if __name__ == "__main__":
    unittest.main()
