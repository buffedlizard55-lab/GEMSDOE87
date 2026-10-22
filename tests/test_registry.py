from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.stats import spearmanr

from gems87.registry import _git_blob_sha1_file, compare_final_dots, compare_surface


def _raster(path, values):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:32611",
        transform=from_origin(0, 1000, 100, 100),
    ) as ds:
        ds.write(values.astype("float32"), 1)


def test_git_blob_hash_includes_git_object_header(tmp_path) -> None:
    path = tmp_path / "blob.bin"
    path.write_bytes(b"abc")
    # Git's SHA-1 object identity is not a bare SHA-1 of the file.
    assert _git_blob_sha1_file(path) == "f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f"


def test_final_duplicate_gate_detects_same_dot_mask(tmp_path) -> None:
    mask = np.zeros((40, 40), bool)
    mask[10, 10] = True
    mask[25, 25] = True
    tif = tmp_path / "registry.tif"
    _raster(tif, mask)
    registry = {"complete_discovery": True, "complete_materialization": True, "materialized": [{"cache_path": str(tif), "source_url": "synthetic", "sha256": "synthetic"}]}
    result = compare_final_dots(mask, np.ones_like(mask), registry)
    assert result["verdict"] == "DUPLICATE"
    assert result["offenders"][0]["candidate_dots_within_3px_fraction"] == 1.0


def test_surface_gate_uses_exact_tie_aware_ranks_for_continuous_reference(tmp_path) -> None:
    surface = np.array([[0.1, 0.1, 0.9], [0.2, 0.5, 0.7], [0.4, 0.3, 0.8]], dtype="float32")
    reference = np.array([[9.0, 2.0, 1.0], [4.0, 8.0, 3.0], [7.0, 6.0, 5.0]], dtype="float32")
    tif = tmp_path / "continuous.tif"
    _raster(tif, reference)
    registry = {"complete_discovery": True, "complete_materialization": True, "materialized": [{"cache_path": str(tif), "source_url": "synthetic", "sha256": "synthetic"}]}
    result = compare_surface(surface, np.ones(surface.shape, bool), registry)
    observed = result["comparisons"][0]["exact_spearman_rank_correlation"]
    expected = spearmanr(surface.ravel(), reference.ravel()).statistic
    assert np.isclose(observed, expected)
    assert not result["comparisons"][0]["reference_is_binary"]


def test_surface_gate_allows_unrelated_surface(tmp_path) -> None:
    rng = np.random.default_rng(2)
    surface = rng.random((40, 40)).astype("float32")
    reference = np.zeros((40, 40), dtype="float32")
    reference[::6, ::6] = 1
    tif = tmp_path / "registry.tif"
    _raster(tif, reference)
    registry = {"complete_discovery": True, "complete_materialization": True, "materialized": [{"cache_path": str(tif), "source_url": "synthetic", "sha256": "synthetic"}]}
    result = compare_surface(surface, np.ones(surface.shape, bool), registry)
    assert result["verdict"] == "UNIQUE"
    assert result["comparison_method"].startswith("exact tie-aware Spearman")
    assert result["comparisons"][0]["comparison_pixels"] == surface.size
    assert result["comparisons"][0]["reference_is_binary"]
