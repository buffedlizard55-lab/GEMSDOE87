#!/usr/bin/env python3
"""Run preregistered H87-GCF (session experiment 2). Never uploads or selects a slot."""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'vendor'), str(ROOT), str(ROOT / 'scripts')]

import numpy as np
from gems57.grid import load_grid
from gems57.submission_writer import write_submission
from gems57.uniqueness import compare_array_to_registry, saturation_certificate, two_phase_summary
from gems57.emit import emit_decimated, emit_prefix
from gems87.experiment import write_json
from gems87.features import load_band, sha256
from gems87.holdout_eval import evaluate_surfaces
from gems87.lwd import session_controls
from gems87.gcf import gravity_curvature_flanks
from run_lwd_experiment import comparison_records, registry_scope, verify_template, CONTROLS, BUDGET_DOTS

ARM = 'gcf_dots'
SURFACE_ARM = 'gcf_continuous_diagnostic'
CACHE = ROOT / 'data/derived/h87gcf'
EVIDENCE = ROOT / 'evidence/h87gcf'


def main():
    verify_template()
    CACHE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lwd_budget = json.loads((ROOT / 'evidence/h87lwd/budget.json').read_text())
    if lwd_budget.get('status') not in {'complete-negative', 'complete'}:
        raise ValueError('GCF is experiment 2; LWD must already be complete')
    with (CACHE / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prereg_path = ROOT / 'registry/preregistration_gcf.json'
        prereg_hash = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
        now = datetime.now(timezone.utc)
        budget_path = EVIDENCE / 'budget.json'
        if budget_path.exists():
            budget = json.loads(budget_path.read_text())
            if budget.get('status', '').startswith('complete'):
                print('GCF already complete; not rerunning.', flush=True)
                return 0
        else:
            start_lwd = datetime.fromisoformat(lwd_budget['started_utc'])
            budget = dict(experiment_id='H87-GCF-01', experiments_used=2, experiments_allowed=3,
                          started_utc=lwd_budget['started_utc'], maximum_hours=2,
                          preregistration_sha256=prereg_hash, status='running',
                          session_started_utc=lwd_budget['started_utc'])
            write_json(budget_path, budget)
        start = datetime.fromisoformat(budget['started_utc'])
        if (now - start).total_seconds() >= 7200:
            raise RuntimeError('Two-hour scientific budget exhausted')

        grid = load_grid(ROOT / 'data/raw')
        meta_path = EVIDENCE / 'feature_build.json'
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            features = {name: np.load(ROOT / item['file'], mmap_mode='r')
                        for name, item in meta['outputs'].items()}
        else:
            t0 = time.time()
            grav = load_band(ROOT, 13)
            features, meta = gravity_curvature_flanks(grav, grid.footprint,
                                                      log=lambda s: print(s, flush=True))
            raw = np.array(grav)
            raw[~np.isfinite(raw)] = 0
            raw[~grid.footprint] = 0
            features['iso_grav_anom_input_canary_only'] = raw
            features.update(session_controls(ROOT, grid.footprint))
            outputs = {}
            for name, values in features.items():
                path = CACHE / (name + '.npy')
                np.save(path, np.asarray(values, np.float32))
                outputs[name] = dict(file=str(path.relative_to(ROOT)), sha256=sha256(path))
            meta.update(outputs=outputs, seconds=time.time() - t0,
                        algorithm_sha256=sha256(ROOT / 'src/gems87/gcf.py'))
            write_json(meta_path, meta)
            print(f'GCF features {meta["seconds"]:.1f}s', flush=True)

        result_path = EVIDENCE / 'holdout.json'
        if result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            result = evaluate_surfaces(
                {k: np.asarray(v) for k, v in features.items()},
                grid.footprint, grid.catalogue,
                candidate_key='gcf', control_names=CONTROLS,
                arm=ARM, surface_arm=SURFACE_ARM, full_budget=BUDGET_DOTS,
                canary_seed_base=87200, bootstrap_seed=87222,
                log=lambda s: print(s, flush=True))
            result['experiment_id'] = 'H87-GCF-01'
            result['generated_utc'] = datetime.now(timezone.utc).isoformat()
            write_json(result_path, result)
        if not result.get('all_canaries_pass'):
            budget.update(status='blocked-by-leakage-canary',
                          elapsed_seconds=(datetime.now(timezone.utc) - start).total_seconds())
            write_json(budget_path, budget)
            return 2

        surface = np.asarray(features['gcf'], np.float32)
        allowed = grid.footprint & ~grid.catalogue
        continuous = np.where(allowed, surface, 0).astype(np.float32)
        records = comparison_records()
        scope = registry_scope(records)
        before = compare_array_to_registry(continuous, scope, grid.footprint, include_reverse=True,
                                           expected_grid=(grid.shape, grid.crs, grid.transform))
        phase = two_phase_summary(before['rows'], int(grid.footprint.sum()), expected_rasters=len(records))
        before.update(phase='continuous-surface-before-final-dot-placement', two_phase=phase)
        write_json(EVIDENCE / 'registry_surface.json', before)
        ranking, _ = emit_decimated(continuous, allowed, tile_px=3)
        dots = np.where(allowed, emit_prefix(ranking, BUDGET_DOTS), 0).astype(np.float32)
        after = compare_array_to_registry(dots, scope, grid.footprint, include_reverse=True,
                                          expected_grid=(grid.shape, grid.crs, grid.transform))
        after_phase = two_phase_summary(after['rows'], int(grid.footprint.sum()), expected_rasters=len(records))
        after.update(phase='sparse-dots', two_phase=after_phase)
        write_json(EVIDENCE / 'registry_dots.json', after)
        like_dup = bool(phase['like_for_like_reading']['duplicate'] or after_phase['like_for_like_reading']['duplicate'])
        rho_dup = bool(phase['literal_reading']['rho_firings'] or after_phase['literal_reading']['rho_firings'])
        holdout_beats = bool(result.get('paired_lower_ci_beats_all_comparable_controls'))
        print('GCF like-for-like dup', like_dup, 'rho', rho_dup, 'beats', holdout_beats,
              'worst sparse overlap', after_phase['like_for_like_reading']['worst_forward_overlap_dot_fields'],
              flush=True)
        final_dots = not like_dup and not rho_dup
        prediction = dots if final_dots else continuous
        pooled = result['pooled']
        cand = pooled['scores'][ARM]
        best_name = result['best_comparable_control']
        note = 'H87 GCF gravity curvature flanks; NEGATIVE research. No weekly slot. DO NOT SUBMIT.'
        sub_name = 'GEMSDOE87-GCF-01-NEGATIVE'
        decoded = hashlib.sha256(np.ascontiguousarray(prediction).tobytes()).hexdigest()[:12]
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        dest = ROOT / 'docs/downloads' / f'gems87-gcf-{stamp}-{decoded}-RESEARCH-DO-NOT-SUBMIT.tif'
        write_submission(dest, prediction, ROOT / 'data/raw/sample_submission.tif', grid.footprint,
                         note=note, name=sub_name, catalogue=grid.catalogue,
                         metadata=dict(experiment='H87-GCF-01', final_dot_placement_performed=final_dots))
        budget.update(status='complete-negative',
                      elapsed_seconds=(datetime.now(timezone.utc) - start).total_seconds(),
                      submission_slots_used=0, selector_invoked=False,
                      final_dot_placement_performed=final_dots,
                      stopped_utc=datetime.now(timezone.utc).isoformat())
        write_json(budget_path, budget)
        card = dict(
            schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
            hypothesis='H87-GCF: opposite-sign gravity-curvature flanks mark a basement step.',
            mechanism='Laplacian couplet of smoothed isostatic gravity; score between opposite-sign flanks.',
            non_fault_mimic='Sedimentary pinch-outs, buried intrusive margins, smooth basin edges.',
            holdout_dti=dict(
                evidence_class='HOLDOUT-DTI', evaluator_version=result['evaluator_version'],
                withheld_positive_pixels=cand['withheld_positive_pixels'],
                binary_diagnostic=cand,
                downloadable_continuous_artifact=pooled['scores'][SURFACE_ARM],
                best_comparable_control=dict(name=best_name, **pooled['scores'][best_name]),
                paired_difference_vs_best=pooled['paired_differences'][best_name],
                gravity_hgm_control=pooled['scores']['gravity_hgm_control'],
                bootstrap=pooled['bootstrap'],
                paired_lower_ci_beats_all_comparable_controls=holdout_beats,
            ),
            leakage_canary=dict(
                passed=True,
                maximum_two_sided_auc=max(c['two_sided_auc'] for fold in result['folds'] for c in fold['canaries'].values() if c.get('two_sided_auc') is not None),
                features_tested=len(result['folds'][0]['canaries']), folds=len(result['folds']),
                threshold=0.9, qualification='No canary trigger; not proof of leakage absence.'),
            correlation_overlap_vs_registry=dict(
                candidate_rasters_compared=len(records),
                surface_before_placement=before['rows'], serialized_artifact=after['rows'] if final_dots else before['rows'],
                two_phase_surface=phase, two_phase_dots=after_phase,
                protocol_uniqueness_pass=False,
                like_for_like_uniqueness_pass=bool(final_dots),
                full_registry_clearance_claimed=False,
                final_dot_placement_performed=final_dots,
            ),
            raster_sha256=sha256(dest),
            decoded_raster_sha256=hashlib.sha256(np.ascontiguousarray(prediction).tobytes()).hexdigest(),
            submission_name=sub_name, submission_note=note,
            submission_file=dest.name, submission_zip=dest.with_suffix('.zip').name,
            approved_for_weekly_slot=False, safe_to_submit=False,
            organizer_confirmed_score=None, submission_slots_used=0, verdict='negative',
            reasons=['No selector/cap authorization.',
                     'Literal dense-support overlap remains 1.0 under the inherited positive-pixel rule.']
                    + ([] if holdout_beats else ['Paired HOLDOUT-DTI lower CI did not beat every comparable control.'])
                    + ([] if final_dots else ['Like-for-like uniqueness failed.']),
            budget=budget, artifact_policy='Research GeoTIFF only; DO NOT SUBMIT.',
            n_emitted_positive_pixels=int((prediction > 0).sum()),
        )
        write_json(EVIDENCE / 'run_card.json', card)
        print('GCF complete', dest.name, 'DTI', cand['dti'], 'best', best_name,
              pooled['scores'][best_name]['dti'], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
