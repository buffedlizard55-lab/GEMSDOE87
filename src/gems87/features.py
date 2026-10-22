"""Label-free cached feature stack for hypothesis H87-FRB.

No channel in this module reads the visible fault catalogue.  That separation is
intentional: labels are used only by the holdout/training harness, and a catalogue
distance field would be a leakage hazard rather than a geological observation.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy import ndimage

from .data import read_band_clean, read_template, sha256_file
from .paths import RAW, WORK

FEATURE_VERSION = "H87-FRB-feature-stack-v1"
FEATURE_NAMES = (
    "fabric_rotation_boundary",
    "fabric_anisotropy_support",
    "magnetic_edge",
    "gravity_edge",
    "topography_edge",
    "strain_boundary",
    "conductivity_edge",
    "strain_energy",
    "dilation_positive",
    "cover_suppression",
    "h87_frb_surface",
)

# One-indexed source bands from the source GeoTIFF.
BAND = {
    "geod_shear": 7,
    "geod_dilate": 8,
    "elevation": 12,
    "gravity": 13,
    "tmi": 14,
    "conductivity": 17,
}


def _normalise_01(values: np.ndarray, footprint: np.ndarray, *, lo: float = 5.0, hi: float = 95.0) -> np.ndarray:
    """Robust monotone normalisation, fitted only to non-label raster values."""
    selected = values[footprint]
    lower, upper = np.percentile(selected, [lo, hi])
    if not np.isfinite(lower) or not np.isfinite(upper) or upper <= lower:
        out = np.zeros(values.shape, dtype=np.float32)
    else:
        out = np.clip((values - lower) / (upper - lower), 0.0, 1.0).astype(np.float32)
    out[~footprint] = 0.0
    return out


def _gradient_magnitude(values: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    smoothed = ndimage.gaussian_filter(values, sigma=sigma, mode="nearest") if sigma else values
    gy, gx = np.gradient(smoothed)
    result = np.hypot(gx, gy).astype(np.float32)
    del smoothed, gx, gy
    return result


def _orientation_components(values: np.ndarray, scale: float = 2.0, window: float = 5.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return orientation cos/sin(2θ), anisotropy coherence, and orientation-rotation magnitude.

    Structure-tensor orientation is axial, hence the double-angle representation.
    `rotation` is the spatial change in that axial direction.  It is not a
    catalogue-derived signal and does not encode a fault distance.
    """
    gx = ndimage.gaussian_filter(values, sigma=scale, order=(0, 1), mode="nearest")
    gy = ndimage.gaussian_filter(values, sigma=scale, order=(1, 0), mode="nearest")
    jxx = ndimage.gaussian_filter(gx * gx, sigma=scale, mode="nearest")
    jyy = ndimage.gaussian_filter(gy * gy, sigma=scale, mode="nearest")
    jxy = ndimage.gaussian_filter(gx * gy, sigma=scale, mode="nearest")
    trace = jxx + jyy
    anis = np.sqrt(np.maximum(((jxx - jyy) * 0.5) ** 2 + jxy**2, 0.0)) / (trace + np.float32(1e-8))
    theta2 = np.arctan2(2.0 * jxy, jxx - jyy + np.float32(1e-8))
    c = np.cos(theta2).astype(np.float32)
    s = np.sin(theta2).astype(np.float32)
    # Smoothed axial vector prevents pixel-scale derivative noise dominating.
    c_local = ndimage.gaussian_filter(c, sigma=window, mode="nearest")
    s_local = ndimage.gaussian_filter(s, sigma=window, mode="nearest")
    cgy, cgx = np.gradient(c_local)
    sgy, sgx = np.gradient(s_local)
    rotation = np.sqrt(cgx * cgx + cgy * cgy + sgx * sgx + sgy * sgy).astype(np.float32)
    coherence = np.clip(anis, 0.0, 1.0).astype(np.float32)
    del gx, gy, jxx, jyy, jxy, trace, anis, theta2, c_local, s_local, cgy, cgx, sgy, sgx
    return c, s, coherence, rotation


def _write_channel(stack: np.memmap, index: int, values: np.ndarray, footprint: np.ndarray) -> None:
    stack[index, :, :] = np.where(footprint, values, 0.0).astype(np.float32, copy=False)
    stack.flush()


def build_feature_stack(
    *,
    features_path: Path | None = None,
    template_path: Path | None = None,
    output_path: Path | None = None,
    force: bool = False,
) -> dict:
    """Build a disk-backed stack of H87-FRB fields and a reproducible receipt.

    The cache is only a deterministic transform of six numerical source bands.
    It contains neither labels nor any distance-to-label/cross-validation feature.
    """
    features_path = features_path or (RAW / "training_features.tif")
    template_path = template_path or (RAW / "sample_submission.tif")
    output_path = output_path or (WORK / "h87_frb_feature_stack.npy")
    receipt_path = output_path.with_suffix(".receipt.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256_file(features_path)
    if output_path.exists() and receipt_path.exists() and not force:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("version") == FEATURE_VERSION and receipt.get("source_sha256") == source_hash:
            receipt["cache_reused"] = True
            return receipt

    started = time.monotonic()
    footprint, grid, _ = read_template(template_path)
    h, w = footprint.shape
    stack = np.lib.format.open_memmap(output_path, mode="w+", dtype=np.float32, shape=(len(FEATURE_NAMES), h, w))

    raw = {name: read_band_clean(features_path, index, footprint) for name, index in BAND.items()}
    # Structure orientation from independent physical fields.  We combine their
    # directional *discordance* (not agreement) to locate rotation boundaries.
    sum_c = np.zeros((h, w), dtype=np.float32)
    sum_s = np.zeros((h, w), dtype=np.float32)
    sum_coh = np.zeros((h, w), dtype=np.float32)
    sum_rotation = np.zeros((h, w), dtype=np.float32)
    for name in ("tmi", "gravity", "elevation"):
        c, s, coherence, rotation = _orientation_components(raw[name])
        sum_c += coherence * c
        sum_s += coherence * s
        sum_coh += coherence
        sum_rotation += rotation
        del c, s, coherence, rotation
    mean_coh = sum_coh / np.float32(3.0)
    directional_resultant = np.hypot(sum_c, sum_s) / (sum_coh + np.float32(1e-8))
    discordance = np.clip(1.0 - directional_resultant, 0.0, 1.0).astype(np.float32)
    rotation_mean = sum_rotation / np.float32(3.0)
    fabric = (
        _normalise_01(rotation_mean, footprint)
        * _normalise_01(discordance, footprint)
        * _normalise_01(mean_coh, footprint)
    ).astype(np.float32)
    support = _normalise_01(mean_coh, footprint)

    mag_edge = _normalise_01(_gradient_magnitude(raw["tmi"], 1.5), footprint)
    gravity_edge = _normalise_01(_gradient_magnitude(raw["gravity"], 1.5), footprint)
    topo_edge = _normalise_01(_gradient_magnitude(raw["elevation"], 1.0), footprint)
    conductivity_edge = _normalise_01(_gradient_magnitude(raw["conductivity"], 2.0), footprint)
    strain_energy_raw = np.hypot(raw["geod_shear"], raw["geod_dilate"]).astype(np.float32)
    strain_energy = _normalise_01(strain_energy_raw, footprint)
    strain_boundary = _normalise_01(_gradient_magnitude(strain_energy_raw, 2.0), footprint)
    dilation_positive = _normalise_01(np.maximum(raw["geod_dilate"], 0.0), footprint)
    cover_suppression = (1.0 - topo_edge).astype(np.float32)

    # The fixed, label-free hypothesis surface is a conservative product.  The
    # spatial holdout separately compares this and a pre-registered HGB
    # calibration against the same visible-fault proxy.
    h87_surface = np.sqrt(np.maximum(fabric * strain_boundary * conductivity_edge, 0.0)).astype(np.float32)
    h87_surface *= (0.5 + 0.5 * cover_suppression)
    h87_surface = _normalise_01(h87_surface, footprint)

    channels: Iterable[np.ndarray] = (
        fabric,
        support,
        mag_edge,
        gravity_edge,
        topo_edge,
        strain_boundary,
        conductivity_edge,
        strain_energy,
        dilation_positive,
        cover_suppression,
        h87_surface,
    )
    for i, values in enumerate(channels):
        _write_channel(stack, i, values, footprint)
    del stack

    receipt = {
        "version": FEATURE_VERSION,
        "cache_reused": False,
        "path": str(output_path),
        "source_features_path": str(features_path),
        "source_sha256": source_hash,
        "template_path": str(template_path),
        "grid": grid.as_dict(),
        "shape": [len(FEATURE_NAMES), h, w],
        "feature_names": list(FEATURE_NAMES),
        "source_bands": BAND,
        "labels_used": False,
        "catalogue_distance_feature_used": False,
        "footprint_pixels": int(footprint.sum()),
        "seconds": round(time.monotonic() - started, 3),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def open_feature_stack(path: Path | None = None) -> tuple[np.memmap, tuple[str, ...]]:
    path = path or (WORK / "h87_frb_feature_stack.npy")
    arr = np.load(path, mmap_mode="r")
    if arr.ndim != 3 or arr.shape[0] != len(FEATURE_NAMES):
        raise ValueError(f"unexpected H87-FRB feature stack shape {arr.shape} at {path}")
    return arr, FEATURE_NAMES
