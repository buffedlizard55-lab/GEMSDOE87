import numpy as np
from gems87.features_pgf import pgf

def test_pgf_bounds_and_step_response():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.01, (240, 240)).astype(np.float32)
    a[:, 120:] += 5.0  # vertical basement step at x=120
    fp = np.ones((240, 240), bool)
    out, meta = pgf(a, fp)
    assert meta['physical_input_band'] == 13 and meta['catalogue_derived_features'] == []
    for v in out.values():
        assert np.isfinite(v).all() and v.min() >= 0 and v.max() <= 1
    # flank-pair score near the step exceeds a far-field column
    assert out['pgf'][:, 118:123].max() > out['pgf'][:, 20:25].max()
