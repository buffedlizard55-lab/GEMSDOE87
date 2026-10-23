"""Generic hide-and-recover evaluation for a label-free candidate plus controls."""
from __future__ import annotations

from typing import Callable

import numpy as np

from gems57 import emit, evaluate_holdout, spatial
from gems87.experiment import canary, crop_slices


def evaluate_surfaces(features: dict[str, np.ndarray], footprint: np.ndarray,
                      catalogue: np.ndarray, *, candidate_key: str,
                      control_names: tuple[str, ...], arm: str, surface_arm: str,
                      full_budget: int = 37_654, bootstrap_draws: int = 2000,
                      canary_seed_base: int = 87100, bootstrap_seed: int = 87122,
                      log: Callable[[str], None] = lambda _: None) -> dict:
    fp, cat = np.asarray(footprint, bool), np.asarray(catalogue, bool)
    if candidate_key not in features or any(n not in features for n in control_names):
        raise ValueError('Missing preregistered candidate or controls')
    if any(a.shape != fp.shape for a in features.values()) or cat.shape != fp.shape:
        raise ValueError('Feature grid mismatch')
    names = [arm, *control_names, surface_arm]
    terms = {n: None for n in names}
    folds = []
    all_canaries_pass = True
    for fold in spatial.folds(cat, fp, buffer_px=80):
        f = int(fold['fold'])
        sl = crop_slices(fold['region'])
        local = {k: fold[k][sl] for k in ('region', 'truth', 'visible')}
        valid = fp[sl]
        active = valid & local['region'] & ~local['visible']
        canaries = {name: canary(values[sl], local['truth'], active,
                                 seed=canary_seed_base + f)
                    for name, values in features.items()}
        this_canary = all(c['passed'] for c in canaries.values())
        all_canaries_pass &= this_canary
        if not this_canary:
            return dict(evidence_class='HOLDOUT-DTI', evaluator_version=evaluate_holdout.VERSION,
                        status='blocked-by-leakage-canary', canaries=canaries,
                        failed_fold=f, all_canaries_pass=False)
        budget = int(round(full_budget * int((valid & local['region']).sum()) / int(fp.sum())))
        metrics = {}
        for name in names:
            feature_name = candidate_key if name in (arm, surface_arm) else name
            values = features[feature_name][sl]
            if name == surface_arm:
                prediction = np.where(active, values, 0).astype(np.float32)
            else:
                ranking, _ = emit.emit_decimated(values, active, tile_px=3)
                prediction = emit.emit_prefix(ranking, budget).astype(np.float32)
            result, block_terms = evaluate_holdout.evaluate(
                prediction, local, valid, block_side=200,
                origin=(sl[0].start, sl[1].start), global_shape=fp.shape)
            terms[name] = block_terms if terms[name] is None else terms[name] + block_terms
            metrics[name] = result
            log(f'fold {f} arm {name}: HOLDOUT-DTI={result["dti"]:.6f}, positives={result["n_truth"]}')
        folds.append(dict(fold=f, split=fold['receipt'], canaries=canaries,
                          area_allocated_budget=budget, metrics=metrics,
                          crop_origin=[sl[0].start, sl[1].start]))
    summary = evaluate_holdout.pooled_summary(terms, draws=bootstrap_draws,
                                              seed=bootstrap_seed, candidate=arm)
    comparable = list(control_names)
    best = max(comparable, key=lambda n: summary['scores'][n]['dti'])
    improving = all(summary['paired_differences'][n]['ci95'][0] > 0 for n in comparable)
    return dict(evidence_class='HOLDOUT-DTI', evaluator_version=evaluate_holdout.VERSION,
                status='evaluated', all_canaries_pass=all_canaries_pass,
                full_grid_budget=full_budget, folds=folds, pooled=summary,
                comparable_controls=comparable, best_comparable_control=best,
                paired_lower_ci_beats_all_comparable_controls=bool(improving),
                inherited_comparable_holdout_best=None,
                limitations=[
                    'Labels are the mapped catalogue, not organizer hidden faults or geothermal vents.',
                    'Negatives are unlabelled proxies; intervals condition on labels, folds, and fixed method.',
                    'The continuous research artifact and binary placement diagnostics are separately reported.',
                    'No leaderboard projection or organizer-confirmed submission score is produced.',
                ])
