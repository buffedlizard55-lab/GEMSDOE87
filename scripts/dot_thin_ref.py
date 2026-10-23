"""Vendored reference: deterministic geodesic dot thinning (parent recipe).

Copied unchanged in behaviour from GEMSDOE24 ``src/gems/thinning.py``
(owner's shared template lineage; used here only to *reproduce* the
parent emission ``dot_thin(H19-5 & footprint & ~catalogue, d=2.8)`` and
verify it byte-exactly before building MASS variants). Nothing is added
by this transform: the output is a subset of the input mask, visited in
breadth-first order from the lowest raster index of each 8-connected
component. Kept so the MASS build is reproducible from this repo alone.
"""
from __future__ import annotations

from collections import deque

import numpy as np
from scipy.ndimage import label


def _disc_offsets(min_dist: float, width: int) -> list[int]:
    r = int(np.ceil(min_dist))
    limit = min_dist * min_dist
    return [
        dy * width + dx
        for dy in range(-r, r + 1)
        for dx in range(-r, r + 1)
        if dy * dy + dx * dx < limit
    ]


def dot_thin(mask: np.ndarray, min_dist: float) -> np.ndarray:
    """Deterministic geodesic Poisson-disk subset of ``mask`` (see module doc)."""
    mask = np.asarray(mask, bool)
    if mask.ndim != 2:
        raise ValueError("2D mask required")
    if min_dist <= 1.0 or not mask.any():
        return mask.copy()
    H, W = mask.shape
    pad = int(np.ceil(min_dist)) + 1
    Wp, Hp = W + 2 * pad, H + 2 * pad
    padded = np.zeros((Hp, Wp), bool)
    padded[pad: pad + H, pad: pad + W] = mask
    flat_mask = bytearray(padded.tobytes())
    visited = bytearray(Hp * Wp)
    blocked = bytearray(Hp * Wp)
    kept = bytearray(Hp * Wp)
    disc = _disc_offsets(min_dist, Wp)
    nbr = (-Wp - 1, -Wp, -Wp + 1, -1, 1, Wp - 1, Wp, Wp + 1)

    comp, _n = label(padded, structure=np.ones((3, 3), int))
    flat_comp = comp.ravel()
    order = np.flatnonzero(flat_comp)
    _, first = np.unique(flat_comp[order], return_index=True)
    seeds = order[np.sort(first)]
    for seed in seeds.tolist():
        if visited[seed]:
            continue
        visited[seed] = 1
        queue = deque((seed,))
        while queue:
            q = queue.popleft()
            if not blocked[q]:
                kept[q] = 1
                for o in disc:
                    blocked[q + o] = 1
            for o in nbr:
                nb = q + o
                if flat_mask[nb] and not visited[nb]:
                    visited[nb] = 1
                    queue.append(nb)
    out = np.frombuffer(bytes(kept), dtype=np.uint8).reshape(Hp, Wp).astype(bool)
    return out[pad: pad + H, pad: pad + W]
