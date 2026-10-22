from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from gems87.submission import validate_submission_geotiff, write_submission


def _inputs(tmp_path):
    transform = from_origin(243350, 4508550, 100, 100)
    profile = dict(driver="GTiff", height=9, width=11, count=1, dtype="float32", crs="EPSG:32611", transform=transform, nodata=np.nan)
    template = tmp_path / "template.tif"
    footprint = np.ones((9, 11), dtype=bool)
    footprint[:2, :3] = False
    with rasterio.open(template, "w", **profile) as ds:
        ds.write(np.where(footprint, 0.0, np.nan).astype("float32"), 1)
    labels = tmp_path / "labels.tif"
    label_profile = profile | {"dtype": "int8", "nodata": -1}
    label_values = np.where(footprint, 0, -1).astype("int8")
    label_values[4, 4] = 1
    with rasterio.open(labels, "w", **label_profile) as ds:
        ds.write(label_values, 1)
    return template, labels, footprint


def test_writer_rejects_mismatched_label_grid(tmp_path) -> None:
    template, _, footprint = _inputs(tmp_path)
    bad_labels = tmp_path / "bad-labels.tif"
    profile = dict(
        driver="GTiff", height=8, width=11, count=1, dtype="int8",
        crs="EPSG:32611", transform=from_origin(243350, 4508550, 100, 100), nodata=-1,
    )
    with rasterio.open(bad_labels, "w", **profile) as ds:
        ds.write(np.zeros((8, 11), dtype="int8"), 1)
    with pytest.raises(ValueError, match="labels grid"):
        write_submission(np.zeros_like(footprint), out_dir=tmp_path / "out", slug="unit", timestamp_tag="20261022T000000Z", template_path=template, labels_path=bad_labels)


def test_writer_reopens_and_portal_validates_all_finite_file(tmp_path) -> None:
    template, labels, footprint = _inputs(tmp_path)
    mask = np.zeros(footprint.shape, bool)
    mask[4, 4] = True  # known label: writer must clear it
    mask[6, 7] = True
    receipt = write_submission(mask, out_dir=tmp_path / "out", slug="unit", timestamp_tag="20261022T000000Z", template_path=template, labels_path=labels)
    assert receipt["passed"]
    assert receipt["full_grid"]["nan_or_inf_pixels"] == 0
    assert receipt["footprint"]["visible_catalogue_positive_pixels"] == 0
    repeated = validate_submission_geotiff(tmp_path / "out" / receipt["submission_name"], template_path=template, labels_path=labels)
    assert repeated["passed"]
    assert repeated["footprint"]["positive_pixels"] == 1
    # The same path may be re-attested without altering the bytes, but a new
    # timestamp for identical dot content is a prohibited local reissue.
    again = write_submission(mask, out_dir=tmp_path / "out", slug="unit", timestamp_tag="20261022T000000Z", template_path=template, labels_path=labels)
    assert again["sha256"] == receipt["sha256"]
    with pytest.raises(FileExistsError, match="duplicate prediction content"):
        write_submission(mask, out_dir=tmp_path / "out", slug="unit", timestamp_tag="20261022T000001Z", template_path=template, labels_path=labels)
