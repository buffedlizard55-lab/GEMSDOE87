from __future__ import annotations

import numpy as np

from gems87.metric import score_binary, score_bruteforce


def test_distance_metric_matches_bruteforce_on_small_random_grids() -> None:
    rng = np.random.default_rng(87)
    for _ in range(12):
        pred = rng.random((13, 11)) < 0.13
        truth = rng.random((13, 11)) < 0.11
        if not truth.any():
            truth[4, 4] = True
        fast = score_binary(pred, truth)
        slow = score_bruteforce(pred, truth)
        for key in ("tp_weighted", "fp_weighted", "fn_weighted", "dti"):
            assert np.isclose(fast[key], slow[key], atol=1e-10), key


def test_known_pixels_are_removed_exactly() -> None:
    pred = np.zeros((9, 9), bool)
    truth = np.zeros((9, 9), bool)
    pred[4, 4] = truth[4, 4] = True
    known = np.zeros_like(pred)
    known[4, 4] = True
    result = score_binary(pred, truth, known=known)
    assert result["n_truth"] == 0
    assert result["n_prediction"] == 0
