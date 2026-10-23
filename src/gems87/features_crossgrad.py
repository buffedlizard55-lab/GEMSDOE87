"""H87-CROSSGRAD: Gravity-Magnetic Cross-Gradient Structural Detection.

A novel detector targeting concealed faults where gravity and magnetic
gradients are orthogonal (cross-gradient magnitude is high), indicating
a structural boundary not strongly expressed in either field alone.

Physical inputs: iso_grav_anom (band 13), rtp (band 2), tmi_hg (band 3),
tmi_vg (band 9), iso_grav_anom_hg (band 18), iso_grav_anom_vg (band 11).

No catalogue, labels, or prior predictions enter the candidate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
from scipy import ndimage as ndi


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_band(root: Path, number: int) -> np.ndarray:
    receipt = json.loads((root / 'evidence/feature_cache.json').read_text())
    entry = next(e for e in receipt['bands'] if e['band'] == number)
    path = root / entry['cache_file']
    if sha256(path) != entry['sha256']:
        raise ValueError(f'Cached physical band {number} failed its hash pin')
    return np.load(path, mmap_mode='r')


def crossgrad_magnitude(gx: np.ndarray, gy: np.ndarray,
                        mx: np.ndarray, my: np.ndarray) -> np.ndarray:
    """Compute cross-gradient magnitude |∇g × ∇m| = |gx*my - gy*mx|."""
    return np.abs(gx * my - gy * mx)


def gradient_components(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Central difference gradients with NaN handling."""
    a_filled = np.where(np.isfinite(a), a, 0)
    gy, gx = np.gradient(a_filled)
    return gx, gy


def structure_tensor_eigenvalues(gx: np.ndarray, gy: np.ndarray,
                                  window: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """Eigenvalues of structure tensor for coherence/orientation."""
    j11 = ndi.uniform_filter(gx * gx, window, mode='nearest')
    j22 = ndi.uniform_filter(gy * gy, window, mode='nearest')
    j12 = ndi.uniform_filter(gx * gy, window, mode='nearest')
    trace = j11 + j22
    det = j11 * j22 - j12 * j12
    disc = np.sqrt(np.maximum(trace * trace - 4 * det, 0))
    lambda1 = (trace + disc) * 0.5
    lambda2 = (trace - disc) * 0.5
    return lambda1, lambda2


def crossgrad(grav: np.ndarray, mag: np.ndarray, footprint: np.ndarray,
              log: Callable[[str], None] = lambda _: None) -> tuple[dict[str, np.ndarray], dict]:
    """Cross-gradient detector with coherence and magnitude gates.

    Returns bounded confidence features and metadata.
    """
    a = np.asarray(grav, np.float32)
    m = np.asarray(mag, np.float32)
    fp = np.asarray(footprint, bool)
    if a.ndim != 2 or a.shape != fp.shape or m.shape != fp.shape or not fp.any():
        raise ValueError('Gravity, magnetic, and footprint must share a 2D grid')

    good = fp & np.isfinite(a) & np.isfinite(m) & (np.abs(a) < 1e30) & (np.abs(m) < 1e30)
    if good.sum() < 100:
        raise ValueError('Insufficient physical support')

    # Robust normalization per field (work on copies since inputs may be read-only)
    a_work = a.copy()
    m_work = m.copy()
    for arr, name in [(a_work, 'grav'), (m_work, 'mag')]:
        med = float(np.median(arr[good]))
        scale = max(float(np.median(np.abs(arr[good] - med))) * 1.4826, 1e-6)
        arr[good] = (arr[good] - med) / scale
        arr[~good] = 0
        log(f'{name} normalized: median={med:.3f}, scale={scale:.3f}')
    a, m = a_work, m_work

    # Gradient components
    gx, gy = gradient_components(a)
    mx, my = gradient_components(m)
    log('gradients computed')

    # Cross-gradient magnitude
    cg = crossgrad_magnitude(gx, gy, mx, my)
    log('cross-gradient magnitude computed')

    # Coherence from structure tensors (high coherence = linear feature)
    g_l1, g_l2 = structure_tensor_eigenvalues(gx, gy)
    m_l1, m_l2 = structure_tensor_eigenvalues(mx, my)
    g_coherence = (g_l1 - g_l2) / (g_l1 + g_l2 + 1e-8)
    m_coherence = (m_l1 - m_l2) / (m_l1 + m_l2 + 1e-8)
    joint_coherence = np.sqrt(np.maximum(g_coherence, 0) * np.maximum(m_coherence, 0))
    log('coherence computed')

    # Gradient magnitude gates (suppress noise in flat areas)
    g_mag = np.sqrt(gx * gx + gy * gy)
    m_mag = np.sqrt(mx * mx + my * my)
    g_mag_gate = np.clip(g_mag / (np.percentile(g_mag[good], 95) + 1e-8), 0, 1)
    m_mag_gate = np.clip(m_mag / (np.percentile(m_mag[good], 95) + 1e-8), 0, 1)
    mag_gate = g_mag_gate * m_mag_gate
    log('magnitude gates computed')

    # Cross-gradient normalized
    cg_scale = max(float(np.percentile(cg[good], 99)), 1e-8)
    cg_norm = np.clip(cg / cg_scale, 0, 1)

    # Final score: cross-gradient * coherence * magnitude_gate
    score = cg_norm * joint_coherence * mag_gate

    # Mask to footprint and ensure finite
    score[~fp] = 0
    score = np.where(np.isfinite(score), score, 0)
    score = np.clip(score, 0, 1)

    # Individual feature channels for canaries
    features = {
        'crossgrad_mag': np.clip(cg_norm, 0, 1),
        'joint_coherence': np.clip(joint_coherence, 0, 1),
        'mag_gate': mag_gate,
        'crossgrad': score,
    }
    for k in features:
        features[k][~fp] = 0
        features[k] = np.where(np.isfinite(features[k]), features[k], 0)

    meta = dict(
        hypothesis='H87-CROSSGRAD',
        physical_input_bands=[13, 2],
        control_bands=[3, 9, 11, 18, 19],
        catalogue_derived_features=[],
        catalogue_inputs_accepted=False,
        normalization='robust percentile + joint coherence + magnitude gate',
        crossgrad_scale=cg_scale,
        usable_pixels=int(good.sum()),
    )
    log('H87-CROSSGRAD feature construction complete')
    return features, meta


def bounded_control(a: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Monotone physical control scaling; no labels or sample predictions."""
    a = np.asarray(a, np.float32)
    good = np.asarray(footprint, bool) & np.isfinite(a) & (np.abs(a) < 1e30)
    if not good.any():
        raise ValueError('Control has no physical measurements')
    v = np.maximum(a[good], 0)
    scale = max(float(np.quantile(v, 0.99)), 1e-8)
    out = np.zeros_like(a)
    out[good] = np.clip(v / scale, 0, 1)
    return out