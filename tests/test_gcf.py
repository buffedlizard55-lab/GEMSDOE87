"""Synthetic software regression for H87-GCF. Not a GEMS experiment."""
import numpy as np
import pytest

from gems87 import gcf


def test_gcf_step_and_guard():
    h, w = 140, 150
    x = np.arange(w, dtype=np.float32)
    field = np.broadcast_to((x > w / 2).astype(np.float32) * 10, (h, w)).copy()
    fp = np.ones((h, w), bool)
    channels, meta = gcf.gravity_curvature_flanks(field, fp)
    edge = np.zeros((h, w), bool)
    edge[:gcf.GUARD_PX] = True
    edge[-gcf.GUARD_PX:] = True
    edge[:, :gcf.GUARD_PX] = True
    edge[:, -gcf.GUARD_PX:] = True
    for values in channels.values():
        assert values.dtype == np.float32
        assert np.isfinite(values).all()
        assert 0 <= values.min() <= values.max() <= 1
        assert not values[edge].any()
    assert meta['catalogue_inputs_accepted'] is False
    assert channels['gcf'][:, 70:80].mean() > channels['gcf'][:, 20:30].mean()


def test_gcf_rejects_empty():
    with pytest.raises(ValueError):
        gcf.gravity_curvature_flanks(np.full((40, 40), np.nan, np.float32),
                                     np.ones((40, 40), bool))
