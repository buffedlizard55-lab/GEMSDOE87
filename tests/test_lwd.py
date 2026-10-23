"""Synthetic software regression for H87-LWD. Not a GEMS experiment."""
import numpy as np
import pytest

from gems87 import lwd


def _contact_field(h=120, w=130):
    """Vertical magnetic contact: HGM peaks on the contact; VDR changes sign."""
    x = np.arange(w, dtype=np.float32)
    step = (x[None, :] > (w / 2)).astype(np.float32)
    hg = np.exp(-((x[None, :] - w / 2) / 3.0) ** 2) * 5.0 + 0.2
    hg = np.broadcast_to(hg, (h, w)).copy()
    vg = (step - 0.5) * hg
    fp = np.ones((h, w), bool)
    return hg, vg, fp


def test_lwd_guard_and_range():
    hg, vg, fp = _contact_field()
    channels, meta = lwd.tilt_local_wavenumber(hg, vg, fp)
    edge = np.zeros(fp.shape, bool)
    edge[:lwd.GUARD_PX] = True
    edge[-lwd.GUARD_PX:] = True
    edge[:, :lwd.GUARD_PX] = True
    edge[:, -lwd.GUARD_PX:] = True
    for name, values in channels.items():
        assert values.dtype == np.float32
        assert np.isfinite(values).all()
        assert values.min() >= 0 and values.max() <= 1
        assert not values[edge].any()
    assert meta['catalogue_inputs_accepted'] is False
    assert meta['physical_input_bands'] == [3, 9]
    assert channels['lwd'].max() == pytest.approx(1.0)


def test_lwd_rejects_missing_or_constant():
    fp = np.ones((40, 40), bool)
    with pytest.raises(ValueError):
        lwd.tilt_local_wavenumber(np.full((40, 40), np.nan, np.float32),
                                  np.zeros((40, 40), np.float32), fp)
    with pytest.raises(ValueError):
        lwd.tilt_local_wavenumber(np.zeros((40, 40), np.float32),
                                  np.zeros((40, 40), np.float32), fp)


def test_lwd_contact_is_stronger_on_the_step_than_far_field():
    hg, vg, fp = _contact_field()
    channels, _ = lwd.tilt_local_wavenumber(hg, vg, fp)
    score = channels['lwd']
    mid = score[:, 60:70].mean()
    far = score[:, 10:20].mean()
    assert mid > 3 * far
