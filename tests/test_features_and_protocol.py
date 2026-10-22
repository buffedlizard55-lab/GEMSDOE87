"""Synthetic software regression only: these are NOT new GEMS experiments."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from gems87 import features, experiment
from gems57 import uniqueness
from scripts import run_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_hash_pinned_shared_tools_are_unmodified():
    pin = json.loads((ROOT / 'registry/template_pin.json').read_text())
    for filename, row in pin['files'].items():
        assert hashlib.sha256((ROOT / 'vendor/gems57' / filename).read_bytes()).hexdigest() == row['sha256']
    assert hashlib.sha256((ROOT / 'vendor/prepare_data.py').read_bytes()).hexdigest() == pin['cache_builder']['sha256']


def test_original_negative_feature_source_remains_reproducible():
    measured = json.loads((ROOT / 'evidence/feature_build.json').read_text())
    archive = ROOT / measured['algorithm_source_at_run']['file']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == measured['algorithm_sha256']
    assert measured['post_run_review']['scientific_remeasurement_after_stop'] is False
    assert hashlib.sha256((ROOT / 'src/gems87/features.py').read_bytes()).hexdigest() != measured['algorithm_sha256']


def test_fixed_boundary_guard_on_synthetic_texture_only():
    rng = np.random.default_rng(871)
    field = rng.normal(size=(140, 150)).astype('float32')
    fp = np.ones(field.shape, bool)
    channels, metadata = features.bmtd(field, fp)
    output = channels['bmtd']
    edge = np.zeros(field.shape, bool)
    edge[:features.GUARD_PX] = True
    edge[-features.GUARD_PX:] = True
    edge[:, :features.GUARD_PX] = True
    edge[:, -features.GUARD_PX:] = True
    assert not output[edge].any()  # IR87-016 regression: all-four-grid-edge guard
    assert metadata['usable_pixels'] == (140 - 80) * (150 - 80)
    assert np.isfinite(output).all()
    assert output.dtype == np.float32
    assert output.min() >= 0 and output.max() <= 1
    assert len(channels) == 5
    assert metadata['catalogue_inputs_accepted'] is False
    for channel in channels.values():
        assert not channel[edge].any()


def test_internal_missing_region_is_also_guarded():
    rng = np.random.default_rng(872)
    field = rng.normal(size=(160, 160)).astype('float32')
    field[80, 80] = np.nan
    channels, metadata = features.bmtd(field, np.ones(field.shape, bool))
    assert metadata['usable_pixels'] < (160 - 80) ** 2
    for channel in channels.values():
        assert channel[80, 80] == 0
        assert channel[80, 80 + features.GUARD_PX - 1] == 0


@pytest.mark.parametrize('empty', ['missing', 'constant'])
def test_texture_without_physical_variation_is_rejected(empty):
    field = np.full((90, 90), np.nan if empty == 'missing' else 2, dtype='float32')
    with pytest.raises(ValueError):
        features.bmtd(field, np.ones(field.shape, bool))


def test_control_scaling_does_not_fill_invalid_cells():
    p = np.arange(36, dtype='float32').reshape(6, 6)
    p[0, 0] = np.nan
    usable = np.ones(p.shape, bool)
    usable[1, 1] = False
    out = features.bounded_control(p, usable)
    assert out[0, 0] == out[1, 1] == 0
    assert np.isfinite(out).all()
    assert 0 <= out.min() <= out.max() <= 1


def test_auc_canary_exposes_deliberate_label_leakage():
    g = np.zeros((20, 20), bool)
    g[3:7, 3:7] = True
    active = np.ones(g.shape, bool)
    assert experiment.canary(g.astype(float), g, active, seed=87)['two_sided_auc'] == 1
    assert experiment.canary((~g).astype(float), g, active, seed=87)['two_sided_auc'] == 1
    assert experiment.canary(np.ones(g.shape), g, active, seed=87)['two_sided_auc'] == .5


def registry_fixture(tmp_path, reference):
    file = tmp_path / 'registry.tif'
    with rasterio.open(file, 'w', driver='GTiff', count=1, width=reference.shape[1], height=reference.shape[0],
                       dtype='float32', crs='EPSG:32611', transform=Affine(100, 0, 0, 0, -100, 10000)) as dst:
        dst.write(reference.astype('float32'), 1)
    record = dict(repo_first='synthetic/fixture', sources=['synthetic-fixture'], cache_file=str(file),
                  sha256=hashlib.sha256(file.read_bytes()).hexdigest())
    return dict(rasters=[record], complete_accessible_scan=True, errors=[])


@pytest.mark.parametrize('count,duplicate', [(70, False), (71, True), (100, True)])
def test_literal_forward_overlap_threshold(tmp_path, count, duplicate):
    candidate = np.zeros((100, 100), dtype='float32')
    yy, xx = np.meshgrid(np.arange(5, 100, 10), np.arange(5, 100, 10), indexing='ij')
    candidate[yy, xx] = 1
    reference = np.zeros_like(candidate)
    reference[yy.ravel()[:count], xx.ravel()[:count]] = 1
    result = uniqueness.compare_array_to_registry(candidate, registry_fixture(tmp_path, reference), np.ones(candidate.shape, bool))
    row = result['rows'][0]
    assert row['my_dots_within_3px_of_theirs'] == count / 100
    assert row['duplicate_by_overlap'] is duplicate
    assert result['overlap_limit'] == .70
    assert result['rho_limit'] == .90
    if count == 70:
        assert result['unique'] is True  # Jaccard .70 is diagnostic, not a substitute gate


def test_dense_registry_is_not_exempted(tmp_path):
    candidate = np.zeros((20, 20), dtype='float32')
    candidate[10, 10] = .4
    candidate[15, 15] = .8
    index = registry_fixture(tmp_path, np.ones(candidate.shape))
    result = uniqueness.compare_array_to_registry(candidate, index, np.ones(candidate.shape, bool))
    assert result['rows'][0]['my_dots_within_3px_of_theirs'] == 1
    assert result['stop_required'] is True
    assert result['unique'] is False


def test_correlation_uses_positive_rank_not_absolute_value(tmp_path):
    candidate = np.arange(400, dtype='float32').reshape(20, 20) / 400
    index = registry_fixture(tmp_path, 1 - candidate)
    result = uniqueness.compare_array_to_registry(candidate, index, np.ones(candidate.shape, bool))
    assert result['rows'][0]['spearman_full_footprint'] == pytest.approx(-1)
    assert result['rows'][0]['duplicate_by_rho'] is False
    # Dense positive support STILL blocks by overlap, independently of rho.
    assert result['rows'][0]['duplicate_by_overlap'] is True


def test_stopped_runner_does_not_touch_data_or_features(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('A permanently stopped experiment must not invoke this operation')
    monkeypatch.setattr(run_experiment, 'load_grid', forbidden)
    monkeypatch.setattr(run_experiment, 'bmtd', forbidden)
    monkeypatch.setattr(run_experiment.sys, 'argv', ['run_experiment.py', '--features-only'])
    with pytest.raises(RuntimeError, match='duplicate stop'):
        run_experiment.main()


def test_stop_state_and_no_final_dots_are_permanent():
    budget = json.loads((ROOT / 'evidence/budget.json').read_text())
    card = json.loads((ROOT / 'run_card.json').read_text())
    assert budget['status'] == 'stopped-by-duplicate'
    assert budget['scientific_experiments_after_stop'] == 0
    assert budget['final_dot_placement_performed'] is False
    assert budget['experiments_used'] == 1
    assert card['verdict'] == 'negative'
    assert card['safe_to_submit'] is False
    assert card['correlation_overlap_vs_registry']['final_dot_placement_performed'] is False
    assert card['submission_slots_used'] == 0
    assert card['execution_defects'][0]['remeasured_after_duplicate_stop'] is False
    assert len(card['submission_note']) <= 140
