#!/usr/bin/env python3
"""Serialize the completed negative result, without placing any final dots.

Not an experiment or a selector. The literal registry stop is permanent for
this run. A newly computed, continuous confidence GeoTIFF is retained for
reproducible research and file-format testing; it is NEVER cleared to submit.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src'), str(ROOT / 'vendor')]

import numpy as np
from gems57.grid import load_grid
from gems57.submission_writer import write_submission
from gems57.uniqueness import compare_array_to_registry
from gems87.experiment import ARM, SURFACE_ARM, write_json
from gems87.features import sha256


def scoped_registry(inventory, records):
    return dict(rasters=records, complete_accessible_scan=False,
                errors=[*inventory['errors'], dict(error='Deliberate stop-on-witness subset; cannot certify complete candidate comparisons.')])


def main():
    card_path = ROOT / 'docs/evidence/run_card.json'
    if card_path.exists():
        from scripts.check_submission import check_bundle
        existing = json.loads(card_path.read_text())
        report = check_bundle(existing)
        if not report['local_format_valid']:
            raise ValueError('Existing bundle failed on-disk validation; do not overwrite or silently repair it')
        if existing.get('verdict') == 'promote' and report.get('safe_to_submit') is not True:
            raise ValueError('The frozen serializer cannot accept edited promotion flags')
        print('Retaining the verified existing bundle; no overwrite or scientific recomputation.')
        return 0
    holdout = json.loads((ROOT / 'evidence/holdout.json').read_text())
    budget = json.loads((ROOT / 'evidence/budget.json').read_text())
    if budget['status'] != 'stopped-by-duplicate':
        raise ValueError('This serializer is only for the completed protocol-negative run')
    if not holdout.get('all_canaries_pass'):
        raise ValueError('Do not package an unexplained leakage-canary failure')
    grid = load_grid(ROOT / 'data/raw')
    metadata = json.loads((ROOT / 'evidence/feature_build.json').read_text())
    feature_record = metadata['outputs']['bmtd']
    source = ROOT / feature_record['file']
    if sha256(source) != feature_record['sha256']:
        raise ValueError('Completed experimental surface changed')
    surface = np.array(np.load(source, mmap_mode='r'), dtype=np.float32)
    inventory = json.loads((ROOT / 'evidence/registry_refreshed.json').read_text())
    witness = json.loads((ROOT / 'evidence/registry_saturation_witness.json').read_text())
    if not witness['certificate']['universal_overlap_blocker']:
        raise ValueError('No universal overlap blocker proved; this is not a shortcut to approval')
    h33 = next(r for r in inventory['rasters'] if any(
        s.endswith('gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif') for s in r['sources']))
    # A negative decision requires only one valid counterexample. H33 is measured
    # first for the requested educational comparison, then the blocking witness.
    records = [h33, witness['record']]
    scope = scoped_registry(inventory, records)
    before = compare_array_to_registry(surface, scope, grid.footprint,
                                      include_reverse=False,
                                      expected_grid=(grid.shape, grid.crs, grid.transform))
    before.update(phase='continuous-surface-before-final-dot-placement',
                  inventory_unique_grid_rasters=inventory['n_unique_grid_rasters'],
                  final_dot_placement_performed=False,
                  decision='negative: literal overlap duplicate; stop, no final dot placement')
    write_json(ROOT / 'evidence/registry_surface.json', before)
    write_json(ROOT / 'docs/evidence/registry_surface.json', before)
    # No new scientific computation or dot placement after the duplicate stop:
    # serialize the already evaluated continuous diagnostic with exact known
    # fault masking. This is not the binary holdout arm and is named accordingly.
    prediction = np.where(grid.footprint & ~grid.catalogue, surface, 0).astype(np.float32)
    decoded = hashlib.sha256(prediction.tobytes()).hexdigest()
    name = 'GEMSDOE87-BMTD-01-NEGATIVE'
    note = 'H87 magnetic texture dislocation; NEGATIVE: no control gain; literal registry-overlap duplicate. Research only; DO NOT SUBMIT.'
    filename = f'gems87-bmtd-{datetime.now(timezone.utc):%Y%m%d}-{decoded[:12]}-RESEARCH-DO-NOT-SUBMIT.tif'
    receipt = write_submission(ROOT / 'docs/downloads' / filename, prediction,
                               ROOT / 'data/raw/sample_submission.tif', grid.footprint,
                               note=note, name=name, catalogue=grid.catalogue,
                               metadata=dict(experiment_id=budget['experiment_id'],
                                   result='negative', representation='continuous confidence diagnostic, not final dots',
                                   byte_freshness='newly computed from cached RTP only; not an imported prior',
                                   protocol_uniqueness_pass=False, safe_to_submit=False,
                                   literal_duplicate_stop=True))
    final = compare_array_to_registry(prediction, scope, grid.footprint,
                                     file_sha256=receipt['sha256'], include_reverse=False,
                                     expected_grid=(grid.shape, grid.crs, grid.transform))
    final.update(phase='serialized-continuous-research-artifact-support',
                 inventory_unique_grid_rasters=inventory['n_unique_grid_rasters'],
                 note='No final dots placed: pre-placement stop. Positive support checked literally on the diagnostic artifact.')
    write_json(ROOT / 'evidence/registry_final.json', final)
    write_json(ROOT / 'docs/evidence/registry_final.json', final)
    inventory_hashes = {r['sha256'] for r in inventory['rasters']}
    freshness = receipt['sha256'] not in inventory_hashes
    if not freshness:
        raise AssertionError('New diagnostic bytes unexpectedly match a registry file')
    best = holdout['best_comparable_control']
    card = dict(
        schema_version=1,
        generated_utc=datetime.now(timezone.utc).isoformat(),
        hypothesis='H87-BMTD: a tangential shift restores bilateral magnetic texture similarity across a concealed fault.',
        mechanism='NCC gain for opposite-side RTP texture panels under fixed tangential shifts; texture energy and balance suppress unstable matches.',
        non_fault_mimic='Curved volcanic flow contacts and paleochannels; flight-line leveling artifacts can also mimic shifted texture.',
        holdout_dti=dict(
            evidence_class='HOLDOUT-DTI', evaluator_version=holdout['evaluator_version'],
            withheld_positive_pixels=holdout['pooled']['scores'][ARM]['withheld_positive_pixels'],
            binary_diagnostic=holdout['pooled']['scores'][ARM],
            downloadable_continuous_artifact=holdout['pooled']['scores'][SURFACE_ARM],
            best_comparable_control=dict(name=best, **holdout['pooled']['scores'][best]),
            paired_difference_vs_best=holdout['pooled']['paired_differences'][best],
            bootstrap=holdout['pooled']['bootstrap'],
            inherited_comparable_best_available=False),
        leakage_canary=dict(passed=True, maximum_two_sided_auc=max(
            c['two_sided_auc'] for f in holdout['folds'] for c in f['canaries'].values()),
            features_tested=len(holdout['folds'][0]['canaries']),
            folds=len(holdout['folds']), threshold=0.90,
            qualification='No canary trigger; not proof of leakage absence.'),
        correlation_overlap_vs_registry=dict(
            inventory_repositories=len(inventory['repos_scanned']),
            inventory_valid_unique_rasters=inventory['n_unique_grid_rasters'],
            inventory_complete=False, inventory_errors=inventory['errors'],
            candidate_rasters_compared=len(records),
            surface_before_placement=before['rows'], serialized_artifact=final['rows'],
            universal_overlap_witness=witness['certificate'],
            thresholds=dict(spearman=0.90, forward_overlap_3px=0.70),
            protocol_uniqueness_pass=False,
            full_registry_clearance_claimed=False,
            final_dot_placement_performed=False,
            final_dot_check='not applicable: stopped before final dot placement; diagnostic positive support was checked'),
        raster_sha256=receipt['sha256'],
        decoded_raster_sha256=decoded,
        byte_identical_to_any_accessible_registry_file=not freshness,
        validator_output=receipt['validator'],
        template_validator=receipt['template_report'],
        submission_name=name, submission_note=note,
        submission_file=filename, submission_zip=receipt['zip_file'],
        approved_for_weekly_slot=False, safe_to_submit=False,
        organizer_confirmed_score=None,
        current_weekly_cap_from_submission_page=None,
        submission_slots_used=0,
        verdict='negative',
        reasons=[
            'No positive paired lower confidence bound versus the strongest comparable control.',
            'Literal >70% overlap with a saturated registry raster: protocol duplicate stop.',
            'Registry contains a malformed TIFF; global clearance cannot be asserted.',
            'No organizer submission receipt or authenticated current cap/usage is available.'],
        budget=budget,
        artifact_policy='New format-valid research GeoTIFF; download is safe, competition submission is NOT approved. No final dots after the stop.')
    write_json(card_path, card)
    write_json(ROOT / 'run_card.json', card)
    write_json(ROOT / 'docs/evidence/registry_inventory_summary.json', dict(
        generated_utc=inventory['generated_utc'], repositories=len(inventory['repos_scanned']),
        valid_unique_rasters=inventory['n_unique_grid_rasters'], errors=inventory['errors'],
        complete_accessible_scan=False, candidate_comparisons=len(records),
        scope=inventory['scope']))
    print(json.dumps(dict(file=filename, sha256=receipt['sha256'],
                         format_valid=receipt['validator']['all_checks_passed'],
                         fresh_bytes=freshness, safe_to_submit=False,
                         verdict='negative'), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
