"""Distance-weighted Tversky metric used by the local holdout.

The implementation follows the public competition description: triangular distance
credit to 300 m (three 100-m pixels), alpha=0.2, beta=0.8.  It is a local
reimplementation with brute-force tests; it is not an organizer scoring service.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
EPS = 1e-12


def triangular_kernel(distance: np.ndarray | float, radius_px: float = RADIUS_PX) -> np.ndarray:
    return np.maximum(1.0 - np.asarray(distance, dtype=np.float64) / radius_px, 0.0)


def score_binary(
    prediction: np.ndarray,
    truth: np.ndarray,
    *,
    valid: np.ndarray | None = None,
    known: np.ndarray | None = None,
) -> dict[str, Any]:
    """Exact local DTI for binary points, including known-pixel masking.

    `known` removes both prediction and truth pixels before the metric, which
    matches the stated test protocol's pixel-exact visible-fault mask.
    """
    pred = np.asarray(prediction, dtype=bool)
    target = np.asarray(truth, dtype=bool)
    if pred.shape != target.shape or pred.ndim != 2:
        raise ValueError("prediction and truth must be equal-shaped 2-D arrays")
    domain = np.ones(pred.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    excluded = np.zeros(pred.shape, dtype=bool) if known is None else np.asarray(known, dtype=bool)
    if domain.shape != pred.shape or excluded.shape != pred.shape:
        raise ValueError("valid/known masks must match prediction shape")
    active = domain & ~excluded
    pred = pred & active
    target = target & active
    n_truth = int(target.sum())
    n_pred = int(pred.sum())
    if n_truth == 0:
        return {
            "tp_weighted": 0.0,
            "fp_weighted": float(n_pred),
            "fn_weighted": 0.0,
            "n_truth": 0,
            "n_prediction": n_pred,
            "coverage": 0.0,
            "dti": 0.0,
        }
    if n_pred == 0:
        return {
            "tp_weighted": 0.0,
            "fp_weighted": 0.0,
            "fn_weighted": float(n_truth),
            "n_truth": n_truth,
            "n_prediction": 0,
            "coverage": 0.0,
            "dti": 0.0,
        }
    dist_to_prediction = distance_transform_edt(~pred)
    tp = float(triangular_kernel(dist_to_prediction[target]).sum())
    fn = float(n_truth) - tp
    dist_to_truth = distance_transform_edt(~target)
    fp = float((1.0 - triangular_kernel(dist_to_truth[pred])).sum())
    dti = tp / (tp + ALPHA * fp + BETA * fn + EPS)
    return {
        "tp_weighted": tp,
        "fp_weighted": fp,
        "fn_weighted": fn,
        "n_truth": n_truth,
        "n_prediction": n_pred,
        "coverage": tp / n_truth,
        "dti": float(dti),
    }


def score_bruteforce(prediction: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    """Small-grid direct calculation retained only to test `score_binary`."""
    pred = np.asarray(prediction, dtype=bool)
    target = np.asarray(truth, dtype=bool)
    p = np.argwhere(pred)
    g = np.argwhere(target)
    tp = 0.0
    for y, x in g:
        best = 0.0
        for py, px in p:
            best = max(best, float(triangular_kernel(np.hypot(py - y, px - x))))
        tp += best
    fp = 0.0
    for y, x in p:
        best = 0.0
        for gy, gx in g:
            best = max(best, float(triangular_kernel(np.hypot(gy - y, gx - x))))
        fp += 1.0 - best
    fn = float(len(g)) - tp
    return {"tp_weighted": tp, "fp_weighted": fp, "fn_weighted": fn, "dti": tp / (tp + ALPHA * fp + BETA * fn + EPS)}


def dti_improvement_credit_threshold(current_dti: float) -> float:
    """Kernel credit required for one additional unit of prediction mass to help DTI."""
    return ALPHA * float(current_dti)
