"""One fixed experiment; shared whole-component folds and pooled DTI only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
from sklearn.metrics import roc_auc_score

from gems57 import evaluate_holdout, spatial, emit

ARM = 'bmtd_dots'
SURFACE_ARM = 'bmtd_continuous_diagnostic'
CONTROL_NAMES = ('magnetic_hgm_control', 'topographic_slope_control')


def canary(feature: np.ndarray, truth: np.ndarray, active: np.ndarray,
           *, seed: int, max_negatives: int = 50_000) -> dict:
    values = np.asarray(feature)
    truth = np.asarray(truth, bool)
    active = np.asarray(active, bool)
    if values.shape != truth.shape or values.shape != active.shape:
        raise ValueError('Canary grids differ')
    if not np.isfinite(values[active]).all():
        raise ValueError('Canary feature contains unsupported nonfinite values')
    positives = values[truth & active]
    negative_ids = np.flatnonzero(active & ~truth)
    rng = np.random.default_rng(seed)
    if negative_ids.size > max_negatives:
        negative_ids = rng.choice(negative_ids, max_negatives, replace=False)
    negatives = values.ravel()[negative_ids]
    if not len(positives) or not len(negatives):
        return dict(passed=False, auc=None, two_sided_auc=None,
                    reason='No held positives or catalogue-zero proxy negatives')
    auc = float(roc_auc_score(np.r_[np.ones(len(positives)), np.zeros(len(negatives))],
                              np.r_[positives, negatives]))
    two_sided = max(auc, 1 - auc)
    return dict(auc=auc, two_sided_auc=two_sided, passed=bool(two_sided <= 0.90),
                threshold=0.90, withheld_positive_pixels=len(positives),
                sampled_proxy_negative_pixels=len(negatives), seed=seed,
                evidence_class='HOLDOUT-AUC-CANARY',
                interpretation='A pass does not prove no leakage; catalogue-zero is not verified fault absence.')


def crop_slices(region: np.ndarray, *, tile: int = 3, halo: int = 6):
    y, x = np.nonzero(region)
    if not y.size:
        raise ValueError('Empty evaluation region')
    # Global tile alignment must not depend on the withheld trace.
    y0 = max(0, (int(y.min()) - halo) // tile * tile)
    x0 = max(0, (int(x.min()) - halo) // tile * tile)
    y1 = min(region.shape[0], int(y.max()) + halo + 1)
    x1 = min(region.shape[1], int(x.max()) + halo + 1)
    return slice(y0, y1), slice(x0, x1)


def evaluate_features(features: dict[str, np.ndarray], footprint: np.ndarray,
                      catalogue: np.ndarray, *, full_budget: int = 37_654,
                      bootstrap_draws: int = 2000,
                      log: Callable[[str], None] = lambda _: None) -> dict:
    fp, cat = np.asarray(footprint, bool), np.asarray(catalogue, bool)
    if 'bmtd' not in features or any(n not in features for n in CONTROL_NAMES):
        raise ValueError('Missing preregistered candidate or controls')
    if any(a.shape != fp.shape for a in features.values()) or cat.shape != fp.shape:
        raise ValueError('Feature grid mismatch')
    names = [ARM, *CONTROL_NAMES, SURFACE_ARM]
    terms = {n: None for n in names}
    folds = []
    all_canaries_pass = True
    # Shared fixed spatial quadrants, whole intersecting 8-connected components,
    # buffer of both quadrant and complete held-component tails. No private split.
    for fold in spatial.folds(cat, fp, buffer_px=80):
        f = int(fold['fold'])
        sl = crop_slices(fold['region'])
        local = {k: fold[k][sl] for k in ('region', 'truth', 'visible')}
        valid = fp[sl]
        active = valid & local['region'] & ~local['visible']
        canaries = {name: canary(values[sl], local['truth'], active,
                                 seed=87000 + f) for name, values in features.items()}
        this_canary = all(c['passed'] for c in canaries.values())
        all_canaries_pass &= this_canary
        if not this_canary:
            return dict(evidence_class='HOLDOUT-DTI', evaluator_version=evaluate_holdout.VERSION,
                        status='blocked-by-leakage-canary', canaries=canaries,
                        failed_fold=f, all_canaries_pass=False)
        # Budget is determined from region/footprint area, NEVER hidden labels.
        # Visible exact pixels only are removed; there is no broad known-fault
        # exclusion that would also erase the held-out target neighborhood.
        budget = int(round(full_budget * int((valid & local['region']).sum()) / int(fp.sum())))
        metrics = {}
        for arm in names:
            feature_name = 'bmtd' if arm in (ARM, SURFACE_ARM) else arm
            values = features[feature_name][sl]
            if arm == SURFACE_ARM:
                prediction = np.where(active, values, 0).astype(np.float32)
            else:
                ranking, _ = emit.emit_decimated(values, active, tile_px=3)
                prediction = emit.emit_prefix(ranking, budget).astype(np.float32)
            result, block_terms = evaluate_holdout.evaluate(
                prediction, local, valid, block_side=200,
                origin=(sl[0].start, sl[1].start), global_shape=fp.shape)
            terms[arm] = block_terms if terms[arm] is None else terms[arm] + block_terms
            metrics[arm] = result
            log(f'fold {f} arm {arm}: HOLDOUT-DTI={result["dti"]:.6f}, positives={result["n_truth"]}')
        folds.append(dict(fold=f, split=fold['receipt'], canaries=canaries,
                          area_allocated_budget=budget, metrics=metrics,
                          crop_origin=[sl[0].start, sl[1].start]))
    summary = evaluate_holdout.pooled_summary(terms, draws=bootstrap_draws, seed=87022, candidate=ARM)
    # The continuous artifact is a diagnostic, not a competing control whose
    # deliberately larger mass could make a binary emission look better.
    comparable = list(CONTROL_NAMES)
    best = max(comparable, key=lambda n: summary['scores'][n]['dti'])
    improving = all(summary['paired_differences'][n]['ci95'][0] > 0 for n in comparable)
    return dict(evidence_class='HOLDOUT-DTI', evaluator_version=evaluate_holdout.VERSION,
                status='evaluated', all_canaries_pass=all_canaries_pass,
                full_grid_budget=full_budget, folds=folds, pooled=summary,
                comparable_controls=comparable, best_comparable_control=best,
                paired_lower_ci_beats_all_comparable_controls=bool(improving),
                inherited_comparable_holdout_best=None,
                limitations=[
                    'No pre-existing comparable holdout best in the initially empty repository.',
                    'Labels are the mapped catalogue, not organizer hidden faults or geothermal vents.',
                    'Negatives are unlabelled proxies; intervals condition on labels, folds, and fixed method.',
                    'The continuous research artifact and binary placement diagnostics are separately reported.',
                    'No leaderboard projection or organizer-confirmed submission score is produced.'])


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)
