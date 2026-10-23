"""H87-CROSSGRAD: archived-artifact and run-card integrity.

These are software/publication checks. They do not re-run the geophysical
experiment and they cannot prove absence of leakage or organizer acceptance.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / 'evidence/h87crossgrad/run_card.json'
DOWNLOADS = ROOT / 'docs/downloads'


def card():
    return json.loads(CARD.read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_run_card_is_negative_and_never_self_authorises():
    c = card()
    assert c['verdict'] == 'negative'
    assert c['approved_for_weekly_slot'] is False
    assert c['safe_to_submit'] is False
    assert c['organizer_confirmed_score'] is None
    assert c['submission_slots_used'] == 0
    assert len(c['submission_note']) <= 140
    assert c['holdout_dti']['evidence_class'] == 'HOLDOUT-DTI'
    assert c['holdout_dti']['evaluator_version'] == 'gems57-pooled-hide-v2'
    assert c['holdout_dti']['withheld_positive_pixels'] > 0
    # A failed promotion must be recorded as such, not only implied.
    assert c['holdout_dti']['paired_difference_vs_best']['ci95'][0] <= 0
    assert c['reasons']


@pytest.mark.parametrize('key', ['submission_file', 'submission_zip'])
def test_primary_artifact_bytes_match_the_recorded_hash(key):
    c = card()
    path = DOWNLOADS / c[key]
    assert path.is_file(), f'missing archived artifact: {path}'
    if key == 'submission_file':
        assert sha256(path) == c['raster_sha256']


def test_primary_zip_contains_exactly_the_recorded_tiff():
    c = card()
    with zipfile.ZipFile(DOWNLOADS / c['submission_zip']) as z:
        assert z.namelist() == [c['submission_file']]
        assert z.testzip() is None
        member = z.read(c['submission_file'])
    assert hashlib.sha256(member).hexdigest() == c['raster_sha256']


def test_primary_artifact_is_format_valid_in_range_and_off_catalogue():
    rasterio = pytest.importorskip('rasterio')
    c = card()
    with rasterio.open(DOWNLOADS / c['submission_file']) as src:
        data = src.read(1)
        assert src.count == 1
        assert src.dtypes[0] == 'float32'
        assert src.shape == (3730, 3292)
        assert src.crs is not None and src.crs.to_epsg() == 32611
        assert tuple(src.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
    assert np.isfinite(data).all()
    assert float(data.min()) >= 0.0 and float(data.max()) <= 1.0
    # Binary-dot representation: exactly the recorded budget, all-positive pixels == 1.0.
    positives = data > 0
    assert int(positives.sum()) == 37654
    assert set(np.unique(data[positives]).tolist()) == {1.0}


def test_secondary_continuous_artifact_matches_its_recorded_hash():
    c = card()
    secondary = c['archived_secondary_artifact']
    path = DOWNLOADS / secondary['submission_file']
    assert path.is_file()
    assert sha256(path) == secondary['raster_sha256']
    assert secondary['validator_output']['all_checks_passed'] is True


def test_archived_artifacts_are_not_byte_identical_to_each_other():
    c = card()
    dots = sha256(DOWNLOADS / c['submission_file'])
    cont = sha256(DOWNLOADS / c['archived_secondary_artifact']['submission_file'])
    assert dots != cont


def test_experiment_budget_and_feature_pin_are_recorded():
    budget = json.loads((ROOT / 'evidence/h87crossgrad/budget.json').read_text())
    assert budget['experiment_id'] == 'H87-CROSSGRAD-01'
    assert budget['submission_slots_used'] == 0
    assert budget['selector_invoked'] is False
    assert budget['experiments_used'] <= budget['experiments_allowed']

    build = json.loads((ROOT / 'evidence/h87crossgrad/feature_build.json').read_text())
    assert build['catalogue_inputs_accepted'] is False
    assert build['catalogue_derived_features'] == []
    assert build['algorithm_sha256'] == sha256(ROOT / 'src/gems87/features_crossgrad.py')


def test_holdout_receipt_records_the_canary_and_pooled_interval():
    result = json.loads((ROOT / 'evidence/h87crossgrad/holdout.json').read_text())
    assert result['all_canaries_pass'] is True
    pooled = result['pooled']
    assert pooled['evidence_class'] == 'HOLDOUT-DTI'
    scores = pooled['scores']
    # The shipped representation's own pooled score must match the card.
    assert scores['crossgrad_dots']['dti'] == pytest.approx(
        card()['holdout_dti']['binary_diagnostic']['dti'], rel=0, abs=1e-12)
    assert scores['crossgrad_dots']['withheld_positive_pixels'] == 60988
    assert pooled['bootstrap']['confidence'] == 0.95
    # The promotion gate must be recorded as failed, not merely omitted.
    assert result['paired_lower_ci_beats_all_comparable_controls'] is False


def test_generator_refuses_to_overwrite_archived_artifacts():
    """Re-running must fail loudly rather than mint a second dated candidate."""
    script = (ROOT / 'scripts/generate_crossgrad_tif.py').read_text()
    assert 'Refusing to overwrite archived artifact' in script
    assert 'p.unlink()' not in script.split('def main()')[1]


def test_registry_check_receipt_is_internally_consistent():
    """The lane-drift claim must match the numbers it cites."""
    receipt = json.loads((ROOT / 'evidence/h87crossgrad/registry_check.json').read_text())
    rows = receipt['rows']
    assert receipt['priors_compared'] == len(rows)
    assert receipt['priors_errored'] == len(receipt['errors'])
    assert receipt['full_registry_clearance_claimed'] is False
    assert receipt['candidate_dots_sha256'] == card()['raster_sha256']
    sparse = [r for r in rows if 'h57-continuous-anatomy' not in r['submission']]
    # No sparse prior may trip either protocol threshold.
    assert all((r['spearman_full_footprint'] or 0.0) <= 0.90 for r in sparse)
    assert all(r['my_dots_within_3px_of_theirs'] <= 0.70 for r in sparse)
    # The one literal firing must be the saturated dense surface, and nothing else.
    firing = [r for r in rows if r['duplicate_by_overlap'] or r['duplicate_by_rho']]
    assert len(firing) == 1
    assert 'h57-continuous-anatomy' in firing[0]['submission']
    assert firing[0]['support_fraction'] > 0.9


def test_run_card_discloses_prior_art_instead_of_claiming_novelty():
    disclosure = card()['prior_art_disclosure']
    assert disclosure['novel_family'] is False
    text = disclosure['note']
    for prior in ('GEMSDOE54', 'GEMSDOE77', 'GEMSDOE88'):
        assert prior in text
