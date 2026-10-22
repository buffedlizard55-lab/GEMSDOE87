"""Spatial-component holdout for GEMS fault-placement hypotheses.

This evaluator is deliberately a *proxy* evaluation: it hides whole visible fault
segments, learns only from the remaining catalogue, masks visible-fault pixels
exactly at scoring time, and applies the local 300-m triangular-kernel DTI.  It
cannot certify a leaderboard score on the organizer's hidden expert labels.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.ndimage import binary_dilation, label, maximum_filter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from .data import read_labels, read_template
from .features import FEATURE_NAMES, open_feature_stack
from .metric import ALPHA, BETA, EPS, score_binary
from .paths import EVIDENCE, RAW, WORK

EVALUATOR_VERSION = "gems87.spatial_component_holdout.v3"
RNG_SEED = 87022026
BUFFER_PX = 30
MIN_SEPARATION_PX = 3
EMISSION_FRACTION = 0.0070
BOOTSTRAP_REPS = 20_000

# Defined before seeing H87-FRB results.  The baseline intentionally omits every
# fabric-rotation channel; the candidate uses the fixed H87-FRB stack.
BASELINE_FEATURES = ("magnetic_edge", "gravity_edge", "topography_edge", "strain_boundary", "conductivity_edge", "strain_energy", "dilation_positive", "cover_suppression")
CANDIDATE_FEATURES = FEATURE_NAMES


@dataclass(frozen=True)
class FoldDefinition:
    name: str
    core: np.ndarray
    withheld_components: np.ndarray
    # Full pixel support of the components selected by this fold. This is
    # separate from `truth`, which is intentionally scored only in the core.
    withheld_labels: np.ndarray
    visible_labels: np.ndarray
    train_domain: np.ndarray
    truth: np.ndarray
    active: np.ndarray


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sample_indices(mask: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.flatnonzero(mask.ravel())
    if idx.size == 0:
        raise ValueError("cannot sample from an empty mask")
    if idx.size <= n:
        return idx
    return rng.choice(idx, size=n, replace=False)


def _quadrant_masks(footprint: np.ndarray) -> dict[str, np.ndarray]:
    rows = np.flatnonzero(footprint.any(axis=1))
    cols = np.flatnonzero(footprint.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        raise ValueError("empty footprint")
    rmid = (int(rows[0]) + int(rows[-1]) + 1) // 2
    cmid = (int(cols[0]) + int(cols[-1]) + 1) // 2
    yy, xx = np.indices(footprint.shape)
    return {
        "NW": footprint & (yy < rmid) & (xx < cmid),
        "NE": footprint & (yy < rmid) & (xx >= cmid),
        "SW": footprint & (yy >= rmid) & (xx < cmid),
        "SE": footprint & (yy >= rmid) & (xx >= cmid),
    }


def make_folds(labels: np.ndarray, footprint: np.ndarray, buffer_px: int = BUFFER_PX) -> list[FoldDefinition]:
    """Withhold every connected segment touching one spatial block.

    A 30-pixel collar is removed from model fitting.  Scoring uses the core block
    and masks all remaining visible catalogue pixels exactly, rather than relying
    on an approximate distance buffer.
    """
    components, n_components = label(labels, structure=np.ones((3, 3), dtype=np.uint8))
    folds: list[FoldDefinition] = []
    for name, core in _quadrant_masks(footprint).items():
        component_ids = np.unique(components[core & labels])
        component_ids = component_ids[component_ids > 0]
        withheld = np.isin(components, component_ids)
        visible = labels & ~withheld
        collar = binary_dilation(core, iterations=buffer_px) & footprint
        train_domain = footprint & ~collar
        truth = withheld & core
        active = core & footprint & ~visible
        if not truth.any():
            raise ValueError(f"{name} contains no withheld fault pixels")
        if not (visible & train_domain).any():
            raise ValueError(f"{name} leaves no visible training positives after collar")
        folds.append(
            FoldDefinition(
                name=name,
                core=core,
                withheld_components=component_ids,
                withheld_labels=withheld,
                visible_labels=visible,
                train_domain=train_domain,
                truth=truth,
                active=active,
            )
        )
    return folds


def _feature_indices(names: Iterable[str]) -> list[int]:
    index = {name: i for i, name in enumerate(FEATURE_NAMES)}
    return [index[name] for name in names]


def _rows_from_flat(stack: np.ndarray, feature_indices: list[int], flat: np.ndarray, width: int) -> np.ndarray:
    rows = flat // width
    cols = flat % width
    # Broadcast the channel axis explicitly: (features, 1) × (1, rows).
    # This avoids materialising an entire C×H×W copy of the memory-mapped stack.
    channels = np.asarray(feature_indices, dtype=np.intp)[:, None]
    return np.asarray(stack[channels, rows[None, :], cols[None, :]].T, dtype=np.float32)


def _training_negative_mask(fold: FoldDefinition) -> np.ndarray:
    """Return eligible background without any visible or withheld fault pixels.

    A withheld component can extend beyond a fold's core and its 30-pixel collar.
    It is still held out as a whole, so it must not quietly re-enter training as a
    negative just because `truth` is scored only inside the core.
    """
    return fold.train_domain & ~fold.visible_labels & ~fold.withheld_labels


def _fit_model(
    stack: np.ndarray,
    fold: FoldDefinition,
    feature_names: tuple[str, ...],
    *,
    rng: np.random.Generator,
) -> HistGradientBoostingClassifier:
    h, w = fold.active.shape
    indices = _feature_indices(feature_names)
    positives = fold.visible_labels & fold.train_domain
    # Exclude the full support of every held-out segment—not only the portion
    # inside the scoring core—from the background class.
    negatives = _training_negative_mask(fold)
    p = _sample_indices(positives, min(40_000, int(positives.sum())), rng)
    n = _sample_indices(negatives, min(max(4 * len(p), 20_000), 180_000, int(negatives.sum())), rng)
    flat = np.concatenate([p, n])
    y = np.concatenate([np.ones(len(p), dtype=np.uint8), np.zeros(len(n), dtype=np.uint8)])
    order = rng.permutation(flat.size)
    x = _rows_from_flat(stack, indices, flat[order], w)
    y = y[order]
    model = HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_iter=120,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=int(rng.integers(0, np.iinfo(np.int32).max)),
    )
    model.fit(x, y)
    return model


def _predict_at_active(
    model: HistGradientBoostingClassifier,
    stack: np.ndarray,
    feature_names: tuple[str, ...],
    active: np.ndarray,
    chunk_size: int = 250_000,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = active.shape
    indices = _feature_indices(feature_names)
    flat = np.flatnonzero(active.ravel())
    result = np.empty(flat.size, dtype=np.float32)
    for start in range(0, flat.size, chunk_size):
        part = flat[start : start + chunk_size]
        x = _rows_from_flat(stack, indices, part, w)
        result[start : start + part.size] = model.predict_proba(x)[:, 1].astype(np.float32)
    return flat, result


def nms_select(
    flat: np.ndarray,
    scores: np.ndarray,
    shape: tuple[int, int],
    count: int,
    *,
    min_separation_px: int = MIN_SEPARATION_PX,
) -> np.ndarray:
    """Select high-scoring local maxima separated beyond the 300-m kernel support.

    `maximum_filter` enforces a 7×7 exclusion square, which is stricter than a
    Euclidean 3-pixel radius and therefore avoids self-competition under the DTI.
    A deterministic coordinate dither makes plateau selection reproducible.
    """
    if count <= 0:
        return np.zeros(shape, dtype=bool)
    if flat.size != scores.size:
        raise ValueError("flat/scores length mismatch")
    grid = np.full(shape[0] * shape[1], -np.inf, dtype=np.float32)
    # Dither is far below probability precision and only resolves exact ties.
    dither = ((flat.astype(np.int64) * 2_654_435_761) % 104_729).astype(np.float32) / np.float32(104_729 * 10_000_000)
    grid[flat] = scores + dither
    grid = grid.reshape(shape)
    size = 2 * int(min_separation_px) + 1
    local_max = grid == maximum_filter(grid, size=size, mode="constant", cval=-np.inf)
    candidates = np.flatnonzero(local_max.ravel() & np.isfinite(grid.ravel()))
    if candidates.size < count:
        raise ValueError(
            f"NMS provides only {candidates.size} candidates for requested {count}; refusing to weaken 300-m spacing"
        )
    vals = grid.ravel()[candidates]
    chosen = candidates[np.argpartition(vals, -count)[-count:]]
    mask = np.zeros(shape[0] * shape[1], dtype=bool)
    mask[chosen] = True
    return mask.reshape(shape)


def _feature_canary(
    stack: np.ndarray,
    fold: FoldDefinition,
    *,
    rng: np.random.Generator,
) -> dict[str, dict[str, float | int]]:
    """A feature-alone AUC screen; >0.90 is treated as leakage until explained."""
    h, w = fold.active.shape
    truth_flat = np.flatnonzero(fold.truth.ravel())
    negative_mask = fold.active & ~fold.truth
    neg_flat = _sample_indices(negative_mask, min(80_000, int(negative_mask.sum())), rng)
    flat = np.concatenate([truth_flat, neg_flat])
    y = np.concatenate([np.ones(truth_flat.size, dtype=np.uint8), np.zeros(neg_flat.size, dtype=np.uint8)])
    rows, cols = flat // w, flat % w
    result: dict[str, dict[str, float | int]] = {}
    for i, name in enumerate(FEATURE_NAMES):
        values = np.asarray(stack[i, rows, cols], dtype=np.float32)
        raw_auc = float(roc_auc_score(y, values))
        oriented_auc = max(raw_auc, 1.0 - raw_auc)
        result[name] = {
            "evidence_label": "HOLDOUT-DTI",
            "raw_auc": raw_auc,
            "oriented_auc": oriented_auc,
            "n_withheld_positive_pixels": int(truth_flat.size),
            "n_negative_pixels": int(neg_flat.size),
            "leakage_flag": bool(oriented_auc > 0.90),
        }
    return result


def _dti_from_components(tp: np.ndarray | float, fp: np.ndarray | float, fn: np.ndarray | float) -> np.ndarray:
    tp_arr = np.asarray(tp, dtype=np.float64)
    return tp_arr / (tp_arr + ALPHA * np.asarray(fp, dtype=np.float64) + BETA * np.asarray(fn, dtype=np.float64) + EPS)


def _pooled_summary(fold_scores: list[dict[str, Any]], arm: str, rng: np.random.Generator, reps: int = BOOTSTRAP_REPS) -> dict[str, Any]:
    """Pooled DTI primary estimate plus a block-bootstrap confidence interval.

    A mean of per-block ratios is not the requested pooled DTI.  This routine
    aggregates TP/FP/FN across blocks before applying the Tversky ratio, and
    applies the same aggregation inside each bootstrap draw.
    """
    components = np.asarray(
        [[f["arms"][arm]["tp_weighted"], f["arms"][arm]["fp_weighted"], f["arms"][arm]["fn_weighted"]] for f in fold_scores],
        dtype=np.float64,
    )
    pooled = _dti_from_components(*components.sum(axis=0))
    draw_idx = rng.integers(0, components.shape[0], size=(reps, components.shape[0]))
    draws = components[draw_idx].sum(axis=1)
    boot = _dti_from_components(draws[:, 0], draws[:, 1], draws[:, 2])
    lo, hi = np.quantile(boot, [0.025, 0.975])
    values = [float(f["arms"][arm]["dti"]) for f in fold_scores]
    return {
        "evidence_label": "HOLDOUT-DTI",
        # `mean` is retained for simple consumers but is explicitly the pooled
        # metric, not an unweighted average of fold ratios.
        "mean": float(pooled),
        "pooled_dti": float(pooled),
        "ci95_low": float(lo),
        "ci95_high": float(hi),
        "n_folds": int(components.shape[0]),
        "unweighted_fold_mean_dti": float(np.mean(values)),
        "n_withheld_positive_pixels": int(sum(f["n_withheld_positive_pixels"] for f in fold_scores)),
        "n_emitted_pixels": int(sum(f["arms"][arm]["n_prediction"] for f in fold_scores)),
        "pooled_components": {"tp_weighted": float(components[:, 0].sum()), "fp_weighted": float(components[:, 1].sum()), "fn_weighted": float(components[:, 2].sum())},
        "per_fold_dti": {f["fold"]: float(f["arms"][arm]["dti"]) for f in fold_scores},
    }


def _paired_pooled_contrast(fold_scores: list[dict[str, Any]], candidate_arm: str, baseline_arm: str, rng: np.random.Generator, reps: int = BOOTSTRAP_REPS) -> dict[str, Any]:
    candidate = np.asarray([[f["arms"][candidate_arm]["tp_weighted"], f["arms"][candidate_arm]["fp_weighted"], f["arms"][candidate_arm]["fn_weighted"]] for f in fold_scores], dtype=np.float64)
    baseline = np.asarray([[f["arms"][baseline_arm]["tp_weighted"], f["arms"][baseline_arm]["fp_weighted"], f["arms"][baseline_arm]["fn_weighted"]] for f in fold_scores], dtype=np.float64)
    estimate = _dti_from_components(*candidate.sum(axis=0)) - _dti_from_components(*baseline.sum(axis=0))
    draw_idx = rng.integers(0, candidate.shape[0], size=(reps, candidate.shape[0]))
    c = candidate[draw_idx].sum(axis=1)
    b = baseline[draw_idx].sum(axis=1)
    draws = _dti_from_components(c[:, 0], c[:, 1], c[:, 2]) - _dti_from_components(b[:, 0], b[:, 1], b[:, 2])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "evidence_label": "HOLDOUT-DTI",
        "contrast": f"{candidate_arm} - {baseline_arm}",
        "mean": float(estimate),
        "pooled_dti_difference": float(estimate),
        "ci95_low": float(lo),
        "ci95_high": float(hi),
        "n_folds": int(candidate.shape[0]),
    }


def run_h87_frb_experiment(
    *,
    stack_path: Path | None = None,
    template_path: Path | None = None,
    labels_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run pre-registered Experiment 1: H87-FRB vs matched baseline.

    The method runs three arms in each of four spatial folds:
    * `baseline_hgb`: the shared non-rotation structural channels;
    * `h87_frb_surface`: the fixed, label-free hypothesis surface;
    * `h87_frb_hgb`: same HGB specification plus the full pre-registered FRB stack.
    """
    stack_path = stack_path or (WORK / "h87_frb_feature_stack.npy")
    template_path = template_path or (RAW / "sample_submission.tif")
    labels_path = labels_path or (RAW / "labels.tif")
    output_path = output_path or (EVIDENCE / "experiment_h87_frb.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stack, names = open_feature_stack(stack_path)
    footprint, grid, _ = read_template(template_path)
    labels = read_labels(labels_path, footprint, grid)
    if stack.shape[1:] != footprint.shape:
        raise ValueError(f"feature stack {stack.shape} does not match template {footprint.shape}")
    folds = make_folds(labels, footprint)
    rng = np.random.default_rng(RNG_SEED)
    all_canaries: dict[str, Any] = {}
    fold_results: list[dict[str, Any]] = []
    leakage = False
    surface_index = names.index("h87_frb_surface")

    for ordinal, fold in enumerate(folds):
        canary = _feature_canary(stack, fold, rng=rng)
        all_canaries[fold.name] = canary
        leakage = leakage or any(bool(v["leakage_flag"]) for v in canary.values())
        target_count = int(round(EMISSION_FRACTION * int(fold.active.sum())))
        result: dict[str, Any] = {
            "evidence_label": "HOLDOUT-DTI",
            "fold": fold.name,
            "n_withheld_components": int(fold.withheld_components.size),
            "n_withheld_positive_pixels": int(fold.truth.sum()),
            "n_visible_positive_pixels": int(fold.visible_labels.sum()),
            "n_train_positive_pixels": int((fold.visible_labels & fold.train_domain).sum()),
            "n_test_active_pixels": int(fold.active.sum()),
            "emission_target_pixels": target_count,
            "arms": {},
        }
        # Surface is label-free; it still receives the same exact spacing/budget.
        active_flat = np.flatnonzero(fold.active.ravel())
        surface_scores = np.asarray(stack[surface_index].ravel()[active_flat], dtype=np.float32)
        surface_pred = nms_select(active_flat, surface_scores, footprint.shape, target_count)
        result["arms"]["h87_frb_surface"] = score_binary(
            surface_pred, fold.truth, valid=fold.core & footprint, known=fold.visible_labels
        )

        if not leakage:
            for arm, feature_names in (("baseline_hgb", BASELINE_FEATURES), ("h87_frb_hgb", CANDIDATE_FEATURES)):
                model = _fit_model(stack, fold, feature_names, rng=rng)
                flat, scores = _predict_at_active(model, stack, feature_names, fold.active)
                pred = nms_select(flat, scores, footprint.shape, target_count)
                result["arms"][arm] = score_binary(pred, fold.truth, valid=fold.core & footprint, known=fold.visible_labels)
        fold_results.append(result)

    # If a canary flags leakage, no supervised arm is trusted.  Retain the raw
    # surface measurements as a negative/review artifact rather than concealing it.
    arm_names = ["h87_frb_surface"] if leakage else ["baseline_hgb", "h87_frb_surface", "h87_frb_hgb"]
    summary_rng = np.random.default_rng(RNG_SEED + 1)
    summaries = {arm: _pooled_summary(fold_results, arm, summary_rng) for arm in arm_names}
    baseline = summaries.get("baseline_hgb")
    candidate = summaries.get("h87_frb_hgb")
    paired = (
        _paired_pooled_contrast(fold_results, "h87_frb_hgb", "baseline_hgb", summary_rng)
        if baseline and candidate
        else None
    )

    # Conservative no-slot promotion gate.  A mean is insufficient; the lower
    # bootstrap bound of the paired contrast must be positive and every feature
    # canary must be below the stated 0.90 threshold.
    promoted = bool(
        not leakage
        and paired is not None
        and paired["mean"] > 0.0
        and paired["ci95_low"] > 0.0
        and candidate is not None
        and candidate["mean"] > baseline["mean"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_utc": _utc_now(),
        "experiment": "H87-FRB-1",
        "evaluator_version": EVALUATOR_VERSION,
        "evidence_label": "HOLDOUT-DTI",
        "protocol": {
            "unit": "HOLDOUT-DTI",
            "folds": "four spatial quadrants; whole connected label components touching each core are withheld",
            "train_buffer_pixels": BUFFER_PX,
            "visible_fault_masking": "pixel-exact at metric time",
            "catalogue_derived_features": [],
            "kernel": "triangular, radius 3 pixels (300 m at the source grid)",
            "alpha": 0.2,
            "beta": 0.8,
            "emission_fraction": EMISSION_FRACTION,
            "minimum_separation_pixels": MIN_SEPARATION_PX,
            "confidence_interval": f"nonparametric spatial-block bootstrap of pooled TP/FP/FN, {BOOTSTRAP_REPS} draws",
            "organizer_score": {"evidence_label": "ORGANIZER-CONFIRMED", "value": None, "receipt": None},
        },
        "grid": grid.as_dict(),
        "feature_stack": {"path": str(stack_path), "feature_names": list(names), "labels_used_to_build_features": False},
        "leakage_canary": {"threshold_auc": 0.90, "passed": not leakage, "per_fold": all_canaries},
        "folds": fold_results,
        "summary": summaries,
        "paired_contrast": paired,
        "promotion_gate": {
            "criterion": "candidate beats matched baseline with paired HOLDOUT-DTI 95% CI entirely above zero; no canary AUC > 0.90",
            "verdict": "PROMOTE" if promoted else "NEGATIVE",
            "weekly_submission_slot_used": False,
            "reason": (
                "All local proxy gates passed; this is not an organizer score or a submission receipt."
                if promoted
                else "No submission artifact may be promoted from this experiment."
            ),
        },
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
