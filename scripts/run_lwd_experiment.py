#!/usr/bin/env python3
"""Run the preregistered H87-LWD experiment. Never uploads or selects a slot.

The frozen H87-BMTD lane (evidence/budget.json) is not modified.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'vendor'), str(ROOT)]

import numpy as np
from gems57.grid import load_grid
from gems57.submission_writer import write_submission
from gems57.uniqueness import (compare_array_to_registry, representation_class,
                               saturation_certificate, two_phase_summary)
from gems57.emit import emit_decimated, emit_prefix
from gems87.experiment import write_json
from gems87.features import load_band, sha256, bounded_control
from gems87.holdout_eval import evaluate_surfaces
from gems87.lwd import tilt_local_wavenumber, session_controls

ARM = 'lwd_dots'
SURFACE_ARM = 'lwd_continuous_diagnostic'
CONTROLS = ('magnetic_hgm_control', 'gravity_hgm_control', 'topographic_slope_control')
BUDGET_DOTS = 37_654
CACHE = ROOT / 'data/derived/h87lwd'
EVIDENCE = ROOT / 'evidence/h87lwd'


def verify_template():
    pin = json.loads((ROOT / 'registry/template_pin.json').read_text())
    for name, metadata in pin['files'].items():
        if sha256(ROOT / 'vendor/gems57' / name) != metadata['sha256']:
            raise ValueError(f'Shared template changed: {name}; do not fork it locally')
    if sha256(ROOT / 'vendor/prepare_data.py') != pin['cache_builder']['sha256']:
        raise ValueError('Shared feature cache builder changed')


def registry_scope(records, errors=None):
    return dict(rasters=records, complete_accessible_scan=False,
                errors=list(errors or []) + [
                    dict(error='Scoped comparison set, not a complete accessible inventory clearance.')])


def comparison_records():
    items = [
        dict(repo_first='GEMSDOE68',
             sources=['GEMSDOE68:registry/rasters/rasters/GEMSDOE32__h33-2-b2-zeros.tif'],
             blob='17a76895f68174cc93f3cb1597d25686f6d6bc67',
             sha256='c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9',
             cache_file='.cache/registry/17a76895f68174cc93f3cb1597d25686f6d6bc67.tif',
             role='sparse-h33-educational'),
        dict(repo_first='GEMSDOE68',
             sources=['GEMSDOE68:registry/rasters/rasters/GEMSDOE28__h27-4-r1-solo-d2-8.tif'],
             blob='7e422e07d5d3aac9ceb187a154bacc0f72a79f5c',
             sha256='2fc94a38d77f74d4f4ed1a97a83e7bb71a1ceea090515ec641e6681cc47c44c8',
             cache_file='.cache/registry/7e422e07d5d3aac9ceb187a154bacc0f72a79f5c.tif',
             role='sparse-h27-4-parent-family'),
        dict(repo_first='GEMSDOE68',
             sources=['GEMSDOE68:registry/rasters/rasters/GEMSDOE30__d28-poisson300m-offcat-44090.tif'],
             blob='a59665a7fad659dcc6a45e5e7e71059586c3247a',
             sha256='8cf893ead5667df21d3288a9968c35fd5385c425b029d82ee71d311715b129fd',
             cache_file='.cache/registry/a59665a7fad659dcc6a45e5e7e71059586c3247a.tif',
             role='sparse-d28-poisson-family'),
        dict(repo_first='57GEMSDOE',
             sources=['57GEMSDOE:docs/downloads/h57-continuous-anatomy-20261009T201252Z-f44b207a70f0.tif'],
             blob='94106cce41eb878e3744818a71d99affde67028d',
             sha256='66e8ea67c86374ed67075812e6ab7c7b17d5eaa714b521dcd35c57f58454a46e',
             cache_file='.cache/registry/94106cce41eb878e3744818a71d99affde67028d.tif',
             role='dense-saturation-witness'),
    ]
    out = []
    for item in items:
        path = ROOT / item['cache_file']
        if not path.is_file():
            raise FileNotFoundError(f'Missing comparison raster: {path}')
        if sha256(path) != item['sha256']:
            raise ValueError(f'Comparison raster hash mismatch: {item["cache_file"]}')
        out.append(item)
    return out


def main():
    verify_template()
    CACHE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (CACHE / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prereg_path = ROOT / 'registry/preregistration_lwd.json'
        prereg = json.loads(prereg_path.read_text())
        prereg_hash = hashlib.sha256(prereg_path.read_bytes()).hexdigest()
        now = datetime.now(timezone.utc)
        budget_path = EVIDENCE / 'budget.json'
        if budget_path.exists():
            budget = json.loads(budget_path.read_text())
            if budget['preregistration_sha256'] != prereg_hash:
                raise ValueError('Preregistration changed during the experiment')
            if budget.get('status') in {'stopped-by-duplicate', 'complete-negative', 'complete'}:
                print(f"Existing LWD budget status={budget['status']}; not rerunning science.", flush=True)
                return 0
        else:
            budget = dict(experiment_id=prereg['experiment_id'], experiments_used=1,
                          experiments_allowed=3, started_utc=now.isoformat(), maximum_hours=2,
                          preregistration_sha256=prereg_hash, status='running',
                          frozen_h87_bmtd_untouched=True)
            write_json(budget_path, budget)
        start = datetime.fromisoformat(budget['started_utc'])
        if (now - start).total_seconds() >= 7200:
            raise RuntimeError('Two-hour scientific budget exhausted')
        frozen = json.loads((ROOT / 'evidence/budget.json').read_text())
        if frozen['status'] != 'stopped-by-duplicate' or frozen['experiment_id'] != 'H87-BMTD-01':
            raise ValueError('Refusing to run a new lane unless the frozen BMTD stop is intact')

        grid = load_grid(ROOT / 'data/raw')
        meta_path = EVIDENCE / 'feature_build.json'
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta['algorithm_sha256'] != sha256(ROOT / 'src/gems87/lwd.py'):
                raise ValueError('Cached LWD features belong to a different implementation')
            features = {}
            for name, item in meta['outputs'].items():
                path = ROOT / item['file']
                if sha256(path) != item['sha256']:
                    raise ValueError(f'Feature pin changed: {name}')
                features[name] = np.load(path, mmap_mode='r')
            print('LWD features restored from pins', flush=True)
        else:
            t0 = time.time()
            hg = load_band(ROOT, 3)
            vg = load_band(ROOT, 9)
            features, meta = tilt_local_wavenumber(hg, vg, grid.footprint,
                                                   log=lambda s: print(s, flush=True))
            raw_hg = np.array(hg)
            raw_hg[~np.isfinite(raw_hg)] = 0
            raw_hg[~grid.footprint] = 0
            raw_vg = np.array(vg)
            raw_vg[~np.isfinite(raw_vg)] = 0
            raw_vg[~grid.footprint] = 0
            features['tmi_hg_input_canary_only'] = raw_hg
            features['tmi_vg_input_canary_only'] = raw_vg
            features.update(session_controls(ROOT, grid.footprint))
            outputs = {}
            for name, values in features.items():
                path = CACHE / (name + '.npy')
                np.save(path, np.asarray(values, np.float32))
                outputs[name] = dict(file=str(path.relative_to(ROOT)), sha256=sha256(path))
            meta.update(outputs=outputs, seconds=time.time() - t0,
                        source='Shared cached competition feature stack; no previous prediction raster used',
                        algorithm_sha256=sha256(ROOT / 'src/gems87/lwd.py'))
            write_json(meta_path, meta)
            print(f'Feature construction {meta["seconds"]:.1f}s', flush=True)

        result_path = EVIDENCE / 'holdout.json'
        if result_path.exists():
            result = json.loads(result_path.read_text())
            print('Existing LWD holdout receipt retained; not refitted.', flush=True)
        else:
            result = evaluate_surfaces(
                {k: np.asarray(v) for k, v in features.items()},
                grid.footprint, grid.catalogue,
                candidate_key='lwd', control_names=CONTROLS,
                arm=ARM, surface_arm=SURFACE_ARM, full_budget=BUDGET_DOTS,
                log=lambda s: print(s, flush=True))
            result['experiment_id'] = budget['experiment_id']
            result['generated_utc'] = datetime.now(timezone.utc).isoformat()
            write_json(result_path, result)
        if not result.get('all_canaries_pass'):
            budget.update(status='blocked-by-leakage-canary',
                          elapsed_seconds=(datetime.now(timezone.utc) - start).total_seconds())
            write_json(budget_path, budget)
            print('LEAKAGE CANARY fired; no uniqueness/packaging of a trusted surface.', flush=True)
            return 2

        surface = np.asarray(features['lwd'], np.float32)
        allowed = grid.footprint & ~grid.catalogue
        continuous = np.where(allowed, surface, 0).astype(np.float32)
        records = comparison_records()
        witness = next(r for r in records if r['role'] == 'dense-saturation-witness')
        cert = saturation_certificate(ROOT / witness['cache_file'], grid.footprint,
                                      grid.catalogue, expected_grid=(grid.shape, grid.crs, grid.transform))
        write_json(EVIDENCE / 'saturation_certificate.json', cert)
        print('Saturation blocker', cert['universal_overlap_blocker'],
              'uncovered', cert['uncovered_allowed_pixels'], flush=True)

        scope = registry_scope(records)
        before = compare_array_to_registry(continuous, scope, grid.footprint,
                                           include_reverse=True,
                                           expected_grid=(grid.shape, grid.crs, grid.transform))
        phase = two_phase_summary(before['rows'], int(grid.footprint.sum()),
                                  expected_rasters=len(records))
        before.update(phase='continuous-surface-before-final-dot-placement', two_phase=phase)
        write_json(EVIDENCE / 'registry_surface.json', before)

        like_dup = bool(phase['like_for_like_reading']['duplicate'])
        rho_dup = bool(phase['literal_reading']['rho_firings'])
        print('Surface like-for-like duplicate', like_dup, 'rho duplicate', rho_dup,
              'literal overlap', phase['literal_reading']['worst_forward_overlap'], flush=True)

        ranking, _ = emit_decimated(continuous, allowed, tile_px=3)
        dots = emit_prefix(ranking, BUDGET_DOTS).astype(np.float32)
        dots = np.where(allowed, dots, 0).astype(np.float32)
        n_dots = int((dots > 0).sum())
        print(f'Emitted {n_dots} off-catalogue spaced dots', flush=True)

        after = compare_array_to_registry(dots, scope, grid.footprint,
                                          include_reverse=True,
                                          expected_grid=(grid.shape, grid.crs, grid.transform))
        after_phase = two_phase_summary(after['rows'], int(grid.footprint.sum()),
                                        expected_rasters=len(records))
        after.update(phase='sparse-dots', two_phase=after_phase)
        write_json(EVIDENCE / 'registry_dots.json', after)
        dots_like_dup = bool(after_phase['like_for_like_reading']['duplicate'])
        dots_rho_dup = bool(after_phase['literal_reading']['rho_firings'])
        print('Dots like-for-like duplicate', dots_like_dup, 'rho duplicate', dots_rho_dup,
              'worst sparse overlap',
              after_phase['like_for_like_reading']['worst_forward_overlap_dot_fields'], flush=True)

        holdout_beats = bool(result.get('paired_lower_ci_beats_all_comparable_controls'))
        lane_unique = (not like_dup and not rho_dup and not dots_like_dup and not dots_rho_dup)
        # Literal dense-field overlap is the known protocol degeneracy; reported, not a lane.
        if like_dup or rho_dup:
            prediction = continuous
            representation = 'continuous-research-surface'
            final_dots = False
            stop_reason = 'Surface failed Spearman or like-for-like overlap vs sparse priors.'
        elif dots_like_dup or dots_rho_dup:
            prediction = continuous
            representation = 'continuous-research-surface'
            final_dots = False
            stop_reason = 'Sparse dots failed Spearman or like-for-like overlap vs sparse priors; no final dots kept.'
        else:
            prediction = dots
            representation = 'sparse-offcatalogue-tile3'
            final_dots = True
            stop_reason = None

        if not holdout_beats:
            # Even unique dots are a negative scientific result.
            if representation == 'sparse-offcatalogue-tile3':
                # Keep the unique sparse field as the research download; still not a slot.
                pass
            verdict = 'negative'
        else:
            verdict = 'negative' if (not lane_unique or stop_reason) else 'negative'
        # Selector is separate and cap is unavailable: never promote.
        safe = False

        sample = ROOT / 'data/raw/sample_submission.tif'
        decoded = hashlib.sha256(np.ascontiguousarray(prediction).tobytes()).hexdigest()[:12]
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        name = f'gems87-lwd-{stamp}-{decoded}-RESEARCH-DO-NOT-SUBMIT.tif'
        dest = ROOT / 'docs/downloads' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        for old in dest.parent.glob('gems87-lwd-*-RESEARCH-DO-NOT-SUBMIT.tif'):
            # Do not delete the frozen BMTD file; only previous LWD attempts in this folder.
            pass
        note = ('H87 LWD tilt local-wavenumber; NEGATIVE research. '
                'No weekly slot. DO NOT SUBMIT.')
        if len(note) > 140:
            raise ValueError('note too long')
        sub_name = 'GEMSDOE87-LWD-01-NEGATIVE'
        write_submission(dest, prediction, sample, grid.footprint,
                         note=note, name=sub_name, catalogue=grid.catalogue,
                         metadata=dict(experiment=budget['experiment_id'],
                                       representation=representation,
                                       final_dot_placement_performed=final_dots))
        print('Wrote', dest, flush=True)

        pooled = result['pooled']
        cand = pooled['scores'][ARM]
        best_name = result['best_comparable_control']
        best = pooled['scores'][best_name]
        delta = pooled['paired_differences'][best_name]
        surf = pooled['scores'][SURFACE_ARM]
        budget.update(
            status='complete-negative',
            elapsed_seconds=(datetime.now(timezone.utc) - start).total_seconds(),
            submission_slots_used=0, selector_invoked=False,
            final_dot_placement_performed=final_dots,
            stop_reason=stop_reason or 'Holdout did not beat controls and/or selector unavailable.',
            stopped_utc=datetime.now(timezone.utc).isoformat(),
            scientific_experiments_after_stop=0)
        write_json(budget_path, budget)

        card = dict(
            schema_version=1,
            generated_utc=datetime.now(timezone.utc).isoformat(),
            hypothesis='H87-LWD: magnetic tilt-angle local wavenumber peaks over concealed 2-D contacts.',
            mechanism=('Miller–Singh tilt from TMI VDR/HGM; Thurston–Smith local wavenumber k=|grad tilt|; '
                       'ranking is k times analytic-signal reliability. No catalogue features.'),
            non_fault_mimic=('Lithologic magnetic contacts, dikes, volcanic flow edges, and GeoDAWN '
                             'flight-line or terrain-clearance artifacts.'),
            holdout_dti=dict(
                evidence_class='HOLDOUT-DTI',
                evaluator_version=result['evaluator_version'],
                withheld_positive_pixels=cand['withheld_positive_pixels'],
                binary_diagnostic=cand,
                downloadable_continuous_artifact=surf if representation.startswith('continuous') else dict(
                    **{k: cand[k] for k in cand}, representation=representation),
                best_comparable_control=dict(name=best_name, **best),
                paired_difference_vs_best=delta,
                gravity_hgm_control=pooled['scores']['gravity_hgm_control'],
                topographic_slope_control=pooled['scores']['topographic_slope_control'],
                bootstrap=pooled['bootstrap'],
                inherited_comparable_best_available=False,
                paired_lower_ci_beats_all_comparable_controls=holdout_beats,
            ),
            leakage_canary=dict(
                passed=True,
                maximum_two_sided_auc=max(
                    c['two_sided_auc'] for fold in result['folds'] for c in fold['canaries'].values()
                    if c.get('two_sided_auc') is not None),
                features_tested=len(result['folds'][0]['canaries']),
                folds=len(result['folds']),
                threshold=0.9,
                qualification='No canary trigger; not proof of leakage absence.',
            ),
            correlation_overlap_vs_registry=dict(
                inventory_repositories=93,
                inventory_valid_unique_rasters=1164,
                inventory_complete=False,
                candidate_rasters_compared=len(records),
                surface_before_placement=before['rows'],
                serialized_artifact=after['rows'] if final_dots else before['rows'],
                two_phase_surface=phase,
                two_phase_dots=after_phase,
                universal_overlap_witness=cert,
                thresholds=dict(spearman=0.9, forward_overlap_3px=0.7),
                protocol_uniqueness_pass=False,  # literal dense witness still fires
                like_for_like_uniqueness_pass=bool(lane_unique),
                full_registry_clearance_claimed=False,
                final_dot_placement_performed=final_dots,
                uniqueness_resolution=(
                    'Protocol names rank-correlation on rasters and 3 px overlap on dots. '
                    'Shared uniqueness.two_phase_summary reports both the inherited literal reading '
                    '(every positive pixel is a dot; dense surfaces fire on every nonempty candidate) '
                    'and a like-for-like reading (overlap only vs dot fields; Spearman vs every raster). '
                    'Lane-drift stop uses like-for-like overlap plus any Spearman >0.90. '
                    'Literal dense-field overlap is recorded, not treated as copying a sparse lane. '
                    'Thresholds are unchanged. Complete inventory clearance is not claimed.'
                ),
            ),
            raster_sha256=sha256(dest),
            decoded_raster_sha256=hashlib.sha256(np.ascontiguousarray(prediction).tobytes()).hexdigest(),
            byte_identical_to_any_accessible_registry_file=False,
            validator_output=None,  # filled by packager/checker
            submission_name=sub_name,
            submission_note=note,
            submission_file=dest.name,
            submission_zip=dest.with_suffix('.zip').name,
            approved_for_weekly_slot=False,
            safe_to_submit=safe,
            organizer_confirmed_score=None,
            current_weekly_cap_from_submission_page=None,
            submission_slots_used=0,
            verdict=verdict,
            reasons=[
                'No authenticated submission-page cap/usage or selector authorization.',
                'Literal dense-support overlap with the saturated registry witness remains 1.0 under the inherited positive-pixel rule.',
            ] + ([] if holdout_beats else [
                'Paired HOLDOUT-DTI lower confidence bound did not beat every comparable control.',
            ]) + ([] if lane_unique else [
                'Like-for-like uniqueness versus sparse priors failed, or Spearman exceeded 0.90.',
            ]),
            budget=budget,
            artifact_policy=('New format-valid research GeoTIFF; download is safe; '
                             'competition submission is NOT approved.'),
            representation=representation,
            n_emitted_positive_pixels=int((prediction > 0).sum()),
            frozen_h87_bmtd_preserved=True,
        )
        write_json(EVIDENCE / 'run_card.json', card)
        print('LWD experiment complete', 'verdict', verdict, 'dots', final_dots,
              'holdout_beats', holdout_beats, 'like_for_like', lane_unique, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
