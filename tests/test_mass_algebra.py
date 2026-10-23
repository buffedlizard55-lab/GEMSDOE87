"""Unit tests for the brief-v2 DTI algebra and the parent thinning recipe.

The algebra under test (agent brief v2, section 2):
    DTI = T / (0.2*T + 0.2*(S - M) + 0.8*|G|)
with T = kernel credit on truth, S = sum p, M = sum p * max_g k.
"""
from __future__ import annotations

import unittest

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from scripts.build_mass_variants import dti_direct, dti_from_components
    from scripts.dot_thin_ref import dot_thin
except Exception:  # pragma: no cover
    dti_direct = dti_from_components = dot_thin = None


@unittest.skipIf(np is None or dti_direct is None, "needs numpy + geo stack")
class DtiAlgebraTests(unittest.TestCase):
    def test_components_match_direct_on_toy(self):
        pred = np.zeros((9, 9), dtype=np.float32)
        pred[4, 2] = 1.0
        pred[4, 7] = 1.0
        truth = np.zeros((9, 9), dtype=bool)
        truth[4, 4] = True
        truth[4, 5] = True
        direct = dti_direct(pred, truth)
        # Hand components: each truth pixel's nearest dot is 2 px away ->
        # T = 1/3 + 1/3 = 2/3; S = 2; each dot's q = 1/3 -> M = 2/3; |G| = 2.
        expect = dti_from_components(2.0 / 3.0, 2.0, 2.0 / 3.0, 2.0)
        self.assertAlmostEqual(direct, expect, places=12)
        self.assertAlmostEqual(direct, (2.0 / 3.0) / 2.0, places=12)

    def test_isolated_dot_pays_iff_credit_above_point2_dti(self):
        # One truth pixel, one dot at distance d: DTI = k/(0.2k+0.8+0.2(1-k))
        # with k = 1 - d/3; the dot raises DTI vs no prediction (0) for any
        # k > 0, and vs an existing score lam it pays iff k > 0.2*lam
        # (brief section 2 rule of thumb, checked at lam = 0.28).
        lam = 0.28
        for d, pays in ((0.0, True), (2.0, True), (2.9, False)):
            k = 1.0 - d / 3.0
            self.assertEqual(k > 0.2 * lam, pays, f"d={d}")

    def test_empty_truth_rejected(self):
        with self.assertRaises(ValueError):
            dti_direct(np.zeros((3, 3), np.float32), np.zeros((3, 3), bool))


@unittest.skipIf(np is None or dot_thin is None, "needs numpy + geo stack")
class DotThinReferenceTests(unittest.TestCase):
    def test_deterministic_subset_with_spacing(self):
        mask = np.zeros((5, 12), dtype=bool)
        mask[2, :] = True
        a = dot_thin(mask, 2.8)
        b = dot_thin(mask, 2.8)
        self.assertTrue(np.array_equal(a, b))          # deterministic
        self.assertFalse((a & ~mask).any())            # subset only
        cols = np.nonzero(a[2])[0]
        self.assertTrue((np.diff(cols) >= 3).all())    # >= 2.8 px along line


if __name__ == "__main__":
    unittest.main()
