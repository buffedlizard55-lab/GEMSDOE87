from __future__ import annotations

import numpy as np

from gems87.holdout import _training_negative_mask, make_folds, nms_select


def test_component_fold_hides_whole_segments_and_uses_collar() -> None:
    footprint = np.ones((100, 100), dtype=bool)
    labels = np.zeros_like(footprint)
    # One component crosses the NW/NE boundary and must be withheld as a whole
    # in either fold it touches; other components populate all quadrants.
    labels[20, 48:91] = True  # extends well beyond the NW collar into NE
    labels[20, 20:25] = True
    labels[20, 75:80] = True
    labels[75, 20:25] = True
    labels[75, 75:80] = True
    folds = make_folds(labels, footprint, buffer_px=4)
    nw = next(f for f in folds if f.name == "NW")
    assert nw.truth[20, 48]
    # Truth is scored only in the core, but the full cross-boundary component
    # must be removed from the visible set, including its NE half.
    assert not nw.visible_labels[20, 48]
    assert not nw.visible_labels[20, 90]
    assert not np.any(nw.train_domain & nw.core)  # core and collar are not training
    # The same cross-boundary component persists beyond the collar. It must be
    # excluded from the background class even though it is not NW scoring truth.
    assert nw.train_domain[20, 90]
    assert nw.withheld_labels[20, 90]
    assert not _training_negative_mask(nw)[20, 90]


def test_nms_spacing_is_stricter_than_three_pixel_radius() -> None:
    shape = (30, 30)
    flat = np.arange(shape[0] * shape[1])
    # Random continuous values prevent ties and yield many local peaks.
    scores = np.random.default_rng(4).random(flat.size).astype("float32")
    mask = nms_select(flat, scores, shape, count=4)
    points = np.argwhere(mask)
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert max(abs(int(a[0] - b[0])), abs(int(a[1] - b[1]))) > 3
