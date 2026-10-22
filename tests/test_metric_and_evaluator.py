"""Literal mathematical checks of the unchanged shared official-formula tools."""
import numpy as np
import pytest
from gems57 import metric, evaluate_holdout, spatial


@pytest.mark.parametrize('seed', range(12))
def test_exact_metric_matches_literal_bruteforce(seed):
    rng = np.random.default_rng(seed)
    p = rng.random((8, 9))
    p[p < .72] = 0
    truth = rng.random(p.shape) < .1
    truth[3, 4] = True
    exact = metric.dti_exact(p, truth)
    oracle = metric.dti_bruteforce(p, truth)
    for term in ('tp', 'fp', 'fn', 'dti'):
        assert exact[term] == pytest.approx(oracle[term], abs=1e-12)


def test_published_component_example():
    # Organizer worked example rounds its final result; no invented pixel layout.
    value = metric.dti_from_components(3.0, 1.89, 2.0)
    assert value == pytest.approx(3 / (3 + .2 * 1.89 + .8 * 2), abs=1e-12)
    assert round(value, 2) == .60


def test_triangular_support_is_zero_at_three_pixels():
    assert metric.kernel(0) == 1
    assert metric.kernel(1) == pytest.approx(2 / 3)
    assert metric.kernel(2) == pytest.approx(1 / 3)
    assert metric.kernel(3) == 0
    assert metric.kernel(3.01) == 0


def test_cover_uses_maximum_not_sum():
    truth = np.zeros((13, 13), bool)
    truth[6, 6] = True
    p = np.zeros(truth.shape)
    p[6, 6] = .5
    p[6, 7] = .9
    covers, _, _ = metric.max_cover(p, truth)
    assert covers[0] == pytest.approx(.9 * (2 / 3))


def test_exact_known_mask_not_a_neighborhood_mask():
    shape = (15, 15)
    truth, known, p = (np.zeros(shape, dtype=t) for t in (bool, bool, float))
    truth[2, 2] = True
    known[10, 10] = True
    p[10, 10] = 1
    p[10, 11] = 1
    fold = dict(region=np.ones(shape, bool), truth=truth, visible=known)
    result, terms = evaluate_holdout.evaluate(p, fold, np.ones(shape, bool), block_side=5)
    assert result['fpw'] == pytest.approx(1.0)  # neighbor is NOT broadly masked
    assert result['n_emitted'] == 1
    assert terms[:, 3].sum() == 1


@pytest.mark.parametrize('bad', [np.nan, np.inf, -.01, 1.01])
def test_shared_evaluator_rejects_invalid_even_if_masked(bad):
    p = np.zeros((10, 10))
    p[0, 0] = bad
    g = np.zeros((10, 10), bool)
    g[5, 5] = True
    region = np.ones((10, 10), bool)
    region[0, 0] = False
    with pytest.raises(ValueError, match='finite'):
        evaluate_holdout.evaluate(p, dict(region=region, truth=g, visible=np.zeros_like(g)), np.ones_like(g))


def test_whole_component_tails_do_not_leak_to_training():
    fp = np.ones((128, 128), bool)
    cat = np.zeros_like(fp)
    cat[15, 25:105] = True  # one component crosses both upper quadrants
    cat[95:100, 20] = True
    cat[95:100, 100] = True
    folds = list(spatial.folds(cat, fp, buffer_px=8))
    for f in folds:
        assert not np.any(f['visible'] & f['held_all'])
        assert not np.any(f['train'] & (f['region'] | f['held_all']))
        assert f['receipt']['shared_train_truth_components'] == 0
        if f['fold'] in (0, 1):
            assert f['held_all'][15, 25:105].all()
            assert not f['visible'][15, 25:105].any()
    assert sum(int(f['truth'].sum()) for f in folds) == cat.sum()


def test_pooled_score_is_from_summed_terms_and_paired_ci():
    candidate = np.array([[4, 2, 6, 10], [10, 20, 20, 30], [0, 4, 0, 0]], float)
    control = np.array([[3, 2, 7, 10], [9, 20, 21, 30], [0, 4, 0, 0]], float)
    result = evaluate_holdout.pooled_summary({'candidate': candidate, 'control': control}, draws=100, candidate='candidate', seed=87)
    expected = metric.dti_from_components(14, 26, 26)
    assert result['scores']['candidate']['dti'] == pytest.approx(expected)
    assert result['scores']['candidate']['withheld_positive_pixels'] == 40
    assert result['bootstrap']['clusters'] == 3  # FP-only cluster must not be discarded
    assert result['scores']['candidate']['ci95'][0] <= expected <= result['scores']['candidate']['ci95'][1]
    assert result['evidence_class'] == 'HOLDOUT-DTI'


def test_pooled_summary_rejects_different_truth_counts():
    a = np.array([[1, 1, 9, 10], [2, 3, 8, 10]], float)
    b = a.copy()
    b[1, 3] = 11
    with pytest.raises(ValueError, match='same integer truth'):
        evaluate_holdout.pooled_summary({'a': a, 'b': b}, draws=100, candidate='a')


def test_global_crop_terms_align_to_physical_blocks():
    shape = (20, 20)
    p = np.zeros(shape)
    g = np.zeros(shape, bool)
    g[9, 9], g[9, 10] = True, True
    p[g] = 1
    fold = dict(region=np.ones(shape, bool), truth=g, visible=np.zeros(shape, bool))
    _, terms = evaluate_holdout.evaluate(p, fold, np.ones(shape, bool), block_side=10,
                                         origin=(20, 20), global_shape=(50, 50))
    assert terms.shape == (25, 4)
    assert terms[12, 3] == 1
    assert terms[13, 3] == 1
