"""Zero-leakage physical tomogram stack & fold-visible crack-tip/relay mechanics for G87-CSCT.

Strict provenance & leakage invariants:
1. ``build_or_load_static_stack`` reads ONLY sensor grids (19-band official GeoDAWN
   ``training_features.tif``, USGS 3DEP 1 m LiDAR scarp summary, USGS GeoDAWN radiometric &
   upward-continued magnetic grids, and DOE GDR-1391 spring/well temperatures & volcanic vents
   with ``dist_known_fault_px`` explicitly forbidden). It NEVER touches ``labels.tif``,
   ``existing_faults.tif``, ``derived_sgmc_faults_100m_u8.tif``, or any registry raster.
2. ``compute_visible_transfer_features`` derives crack-tip beams, horsetail splays, en-echelon
   relay-ramp overlap, and strike-lock features strictly from the supplied ``visible_mask``
   (i.e. ``fold['visible']`` inside each holdout fold). Held-out segments are never seen.
"""

from __future__ import annotations

import csv
import gc
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

FORBIDDEN_GDR_COLUMNS = frozenset({"dist_known_fault_px"})

# 8 undirected strike azimuths in image coordinates (row=y down, col=x right):
# theta in [0, pi), unit tangent (dy, dx) = (sin(theta), cos(theta))
STRIKE_ANGLES = tuple(float(k * np.pi / 8.0) for k in range(8))

# 16 directed propagation rays in [0, 2*pi): (dy, dx) = (sin(phi), cos(phi))
RAY_ANGLES = tuple(float(k * np.pi / 8.0) for k in range(16))


def _clean_band(arr: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Clean sentinel (-3.4e38) and non-finite pixels using footprint median."""
    x = arr.astype(np.float32, copy=False)
    good = footprint & np.isfinite(x) & (np.abs(x) < 1e30)
    med = float(np.median(x[good])) if good.any() else 0.0
    out = np.where(good, x, med).astype(np.float32)
    return out


def divisive_contrast(arr: np.ndarray, sigma_bg: float = 15.0, eps: float = 1e-5) -> np.ndarray:
    """Normalize local signal amplitude by surrounding meso-scale RMS envelope.

    Suppresses rugged mountain canyon variance so subtle 0.5 m alluvial-fan piedmont scarps
    attain equal contrast with high-relief bedrock scarps.
    """
    rms = np.sqrt(np.maximum(ndi.gaussian_filter(arr * arr, sigma=sigma_bg, mode="nearest"), 0.0))
    floor = float(np.percentile(rms, 15.0)) * 0.25 + eps
    return (arr / np.maximum(rms, floor)).astype(np.float32)


def directional_radon_ridge(
    field: np.ndarray,
    sigma_cross: float = 1.2,
    length_along: float = 4.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Steerable 8-azimuth elongated Gaussian line-integral detector.

    Computes max along-strike elongated response minus cross-strike background across 8 strikes,
    returning:
      - ``max_resp``: peak oriented curvilinear response (float32)
      - ``aniso``: ratio (max_resp - mean_resp) / (std + eps) rejecting circular blobs (float32)
      - ``best_theta``: winning strike orientation in [0, pi) (float32)
    """
    best = np.full(field.shape, -1e30, dtype=np.float32)
    sum_r = np.zeros(field.shape, dtype=np.float32)
    sum_r2 = np.zeros(field.shape, dtype=np.float32)
    best_theta = np.zeros(field.shape, dtype=np.float32)

    # Smooth isotropically at fine scale once, then shift-accumulate along each strike tangent
    base = ndi.gaussian_filter(field, sigma=sigma_cross, mode="nearest").astype(np.float32)
    bg = ndi.gaussian_filter(field, sigma=max(sigma_cross * 3.0, 3.5), mode="nearest").astype(np.float32)
    hp = (base - bg).astype(np.float32)

    steps = (-4, -3, -2, -1, 0, 1, 2, 3, 4) if length_along >= 4.0 else (-2, -1, 0, 1, 2)
    weights = np.array([np.exp(-0.5 * (s / max(length_along * 0.5, 1.0)) ** 2) for s in steps], dtype=np.float32)
    weights /= weights.sum()

    h, w = field.shape
    for theta in STRIKE_ANGLES:
        dy = np.sin(theta)
        dx = np.cos(theta)
        acc = np.zeros((h, w), dtype=np.float32)
        for s, wt in zip(steps, weights):
            sy = int(round(s * dy))
            sx = int(round(s * dx))
            acc += wt * np.roll(hp, shift=(sy, sx), axis=(0, 1))
        take = acc > best
        best = np.where(take, acc, best)
        best_theta = np.where(take, np.float32(theta), best_theta)
        sum_r += acc
        sum_r2 += acc * acc

    mean_r = sum_r * np.float32(1.0 / 8.0)
    std_r = np.sqrt(np.maximum(sum_r2 * np.float32(1.0 / 8.0) - mean_r * mean_r, 1e-10))
    aniso = ((best - mean_r) / (std_r + 1e-5)).astype(np.float32)
    return best, aniso, best_theta


def structure_tensor_coherence(
    field: np.ndarray, sigma_grad: float = 1.5, sigma_win: float = 3.5
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gradient magnitude, axial coherence in [0, 1], and local strike angle in [0, pi)."""
    sm = ndi.gaussian_filter(field, sigma=sigma_grad, mode="nearest").astype(np.float32)
    gy, gx = np.gradient(sm)
    mag = np.hypot(gy, gx).astype(np.float32)
    jxx = ndi.gaussian_filter(gx * gx, sigma=sigma_win, mode="nearest")
    jyy = ndi.gaussian_filter(gy * gy, sigma=sigma_win, mode="nearest")
    jxy = ndi.gaussian_filter(gx * gy, sigma=sigma_win, mode="nearest")
    coh = (np.sqrt(np.maximum((jxx - jyy) ** 2 + 4.0 * jxy * jxy, 0.0)) / (jxx + jyy + 1e-10)).astype(np.float32)
    # Normal direction is 0.5 * atan2(2*jxy, jxx - jyy); strike tangent is normal + pi/2 mod pi
    normal_theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    strike_theta = np.mod(normal_theta + 0.5 * np.pi, np.pi).astype(np.float32)
    return mag, coh, strike_theta


def cross_gradient_operators(
    f1: np.ndarray, f2: np.ndarray, sigma: float = 2.0
) -> tuple[np.ndarray, np.ndarray]:
    """Parallel structural alignment and orthogonal confounder flag between two fields."""
    g1y, g1x = np.gradient(ndi.gaussian_filter(f1, sigma=sigma, mode="nearest"))
    g2y, g2x = np.gradient(ndi.gaussian_filter(f2, sigma=sigma, mode="nearest"))
    m1 = np.hypot(g1x, g1y) + 1e-9
    m2 = np.hypot(g2x, g2y) + 1e-9
    cos_a = (g1x * g2x + g1y * g2y) / (m1 * m2)
    sin2 = np.clip(1.0 - cos_a * cos_a, 0.0, 1.0)
    prod = np.sqrt(divisive_contrast(m1.astype(np.float32), 20.0) * divisive_contrast(m2.astype(np.float32), 20.0))
    align = (prod * (cos_a * cos_a)).astype(np.float32)
    ortho = (prod * sin2).astype(np.float32)
    return align, ortho


def _build_gdr_thermal_grids(data_dir: Path, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build strictly label-free thermal upflow grids from DOE GDR-1391 CSVs."""
    ws_csv = data_dir / "external" / "gdr_wellspring_in_footprint.csv"
    vv_csv = data_dir / "external" / "gdr_volcanic_vents_in_footprint.csv"
    h, w = shape
    hot_spring = np.zeros((h, w), dtype=np.float32)
    geotherm_res = np.zeros((h, w), dtype=np.float32)
    vents = np.zeros((h, w), dtype=np.float32)

    with ws_csv.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        allowed_cols = set(reader.fieldnames or ()) - FORBIDDEN_GDR_COLUMNS
        assert "dist_known_fault_px" not in allowed_cols
        for row in reader:
            r = int(float(row["row"]))
            c = int(float(row["col"]))
            if not (0 <= r < h and 0 <= c < w):
                continue
            tc = 0.0
            if row.get("temp_c"):
                try:
                    tc = float(row["temp_c"])
                except ValueError:
                    tc = 0.0
            gt_vals = []
            for gk in ("geothermquartz_c", "geothermchalc_c", "geothermcat_c"):
                val = row.get(gk, "")
                if val:
                    try:
                        fv = float(val)
                        if np.isfinite(fv) and 0.0 < fv < 400.0:
                            gt_vals.append(fv)
                    except ValueError:
                        pass
            if tc > 22.0:
                hot_spring[r, c] = max(hot_spring[r, c], min((tc - 22.0) / 60.0, 2.5))
            if gt_vals:
                gmax = max(gt_vals)
                if gmax > 70.0:
                    geotherm_res[r, c] = max(geotherm_res[r, c], min((gmax - 70.0) / 140.0, 2.5))

    with vv_csv.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        allowed_cols = set(reader.fieldnames or ()) - FORBIDDEN_GDR_COLUMNS
        assert "dist_known_fault_px" not in allowed_cols
        for row in reader:
            r = int(float(row["row"]))
            c = int(float(row["col"]))
            if 0 <= r < h and 0 <= c < w:
                vents[r, c] = 1.0

    # Multi-scale upflow plume diffusion: 500 m near-conduit + 2.2 km lateral outflow apron
    thermal_near = (
        0.65 * ndi.gaussian_filter(hot_spring, sigma=5.0, mode="constant")
        + 0.35 * ndi.gaussian_filter(geotherm_res, sigma=6.0, mode="constant")
    ).astype(np.float32)
    thermal_meso = (
        0.55 * ndi.gaussian_filter(hot_spring, sigma=18.0, mode="constant")
        + 0.45 * ndi.gaussian_filter(geotherm_res, sigma=20.0, mode="constant")
    ).astype(np.float32)
    vent_halo = ndi.gaussian_filter(vents, sigma=14.0, mode="constant").astype(np.float32)
    return thermal_near, thermal_meso, vent_halo


STATIC_FEATURE_NAMES: tuple[str, ...] = (
    # Family 1: Divisive Local-Regime Geomorphic Scarp & Piedmont Breakline Tomography (12)
    "f00_det_elev_hp4",
    "f01_det_elev_hp12",
    "f02_slope_raw",
    "f03_slope_div15",
    "f04_slope_edge_ms_div",
    "f05_slope_radon_ridge",
    "f06_slope_radon_aniso",
    "f07_valley_radon_ridge",
    "f08_slope_coherence",
    "f09_lidar_scarp_comp",
    "f10_lidar_div_radon",
    "f11_lidar_step_coh",
    # Family 2: Cover-Stratified Half-Graben Basement Step & Gravity Crest Tomography (9)
    "f12_cover_log_depth",
    "f13_base_grad_div",
    "f14_base_radon_ridge",
    "f15_grav_hp8",
    "f16_grav_slope_div",
    "f17_grav_hg_div",
    "f18_grav_vg_abs",
    "f19_grav_radon_ridge",
    "f20_cover_x_grav_crest",
    # Family 3: Shallow Hydrothermal Demagnetization Trough & Magnetic Contact Tomography (8)
    "f21_rtp_hp8",
    "f22_tmi_hg_div",
    "f23_tmi_vg_pos_crest",
    "f24_tmi_vg_neg_trough",
    "f25_tilt_edge",
    "f26_demag_radon_trough",
    "f27_mag_shallow_res",
    "f28_mag_radon_crest",
    # Family 4: MT Conductive Conduit + GeoDAWN Radiometric Alteration + GDR Thermal Upflow (8)
    "f29_cond_raw",
    "f30_cond_grad_div",
    "f31_rad_k_th_ratio",
    "f32_rad_alteration_grad",
    "f33_gdr_thermal_near",
    "f34_gdr_thermal_meso",
    "f35_gdr_vent_halo",
    "f36_lidar_valid",
    # Family 5: Cross-Physics Coupling + Andersonian Strain & Microseismic Corridors (7)
    "f37_topo_grav_align",
    "f38_grav_mag_ortho_flag",
    "f39_strain_2ndinv",
    "f40_strain_shear",
    "f41_strain_dilate",
    "f42_seismic_corridor",
    "f43_anderson_strike_fav",
)


def build_or_load_static_stack(
    data_dir: Path, footprint: np.ndarray, cache_dir: Path
) -> tuple[np.memmap, np.ndarray, list[str]]:
    """Build or reload memory-mapped float32 physical feature matrix on footprint pixels."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    mmap_path = cache_dir / "g87_static_v1.mmap"
    theta_path = cache_dir / "g87_phys_theta_v1.npy"
    meta_path = cache_dir / "g87_static_meta.json"
    n_fp = int(footprint.sum())
    n_feat = len(STATIC_FEATURE_NAMES)

    if mmap_path.exists() and theta_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("shape") == [n_fp, n_feat] and meta.get("features") == list(STATIC_FEATURE_NAMES):
            mm = np.memmap(mmap_path, dtype=np.float32, mode="r", shape=(n_fp, n_feat))
            phys_theta = np.load(theta_path)
            return mm, phys_theta, list(STATIC_FEATURE_NAMES)

    mm = np.memmap(mmap_path, dtype=np.float32, mode="w+", shape=(n_fp, n_feat))
    fp_idx = np.flatnonzero(footprint)

    def put(col: int, grid_arr: np.ndarray) -> None:
        mm[:, col] = grid_arr.ravel()[fp_idx].astype(np.float32, copy=False)

    with rasterio.open(data_dir / "training_features.tif") as ds:
        b = {i: _clean_band(ds.read(i), footprint) for i in range(1, 20)}

    # --- Family 1: Geomorphic scarp, divisive piedmont relief, & Radon ridges ---
    det_elev = b[12]
    slope = np.maximum(b[19], 0.0)
    put(0, det_elev - ndi.gaussian_filter(det_elev, sigma=4.0, mode="nearest"))
    put(1, det_elev - ndi.gaussian_filter(det_elev, sigma=12.0, mode="nearest"))
    put(2, np.log1p(slope))
    slope_div = divisive_contrast(slope, sigma_bg=15.0)
    put(3, slope_div)

    ms_edge = np.zeros_like(slope, dtype=np.float32)
    for sig in (1.0, 2.0, 3.8):
        gy, gx = np.gradient(ndi.gaussian_filter(slope, sigma=sig, mode="nearest"))
        ms_edge += divisive_contrast(np.hypot(gy, gx).astype(np.float32), sigma_bg=16.0)
    ms_edge *= np.float32(1.0 / 3.0)
    put(4, ms_edge)

    sl_ridge, sl_aniso, theta_topo = directional_radon_ridge(slope_div, sigma_cross=1.1, length_along=4.5)
    put(5, sl_ridge)
    put(6, sl_aniso)

    val_ridge, _, _ = directional_radon_ridge(-divisive_contrast(det_elev - ndi.gaussian_filter(det_elev, 8.0), 18.0), 1.3, 4.5)
    put(7, val_ridge)

    _, sl_coh, theta_st = structure_tensor_coherence(slope, sigma_grad=1.6, sigma_win=3.5)
    put(8, sl_coh)

    # 1 m USGS 3DEP LiDAR scarps
    with rasterio.open(data_dir / "external" / "lidar_scarp_features_u8.tif") as lds:
        ex_max = lds.read(1).astype(np.float32) * np.float32(1.0 / 255.0)
        step_max = lds.read(3).astype(np.float32) * np.float32(1.0 / 255.0)
        lapneg = lds.read(4).astype(np.float32) * np.float32(1.0 / 255.0)
        downf = lds.read(6).astype(np.float32) * np.float32(1.0 / 255.0)
        coh100 = lds.read(10).astype(np.float32) * np.float32(1.0 / 255.0)
        lid_valid = (lds.read(12) > 0) & footprint

    lid_comp = (0.35 * ex_max + 0.30 * step_max + 0.20 * downf + 0.15 * lapneg).astype(np.float32)
    # Fill outside LiDAR tiles with smooth median before spatial filtering, restore NaN outside coverage where needed
    lid_med = float(np.median(lid_comp[lid_valid])) if lid_valid.any() else 0.0
    lid_fill = np.where(lid_valid, lid_comp, lid_med).astype(np.float32)
    lid_div = divisive_contrast(lid_fill, sigma_bg=14.0)
    lid_rad, _, theta_lid = directional_radon_ridge(lid_div, sigma_cross=1.0, length_along=4.5)
    put(9, np.where(lid_valid, lid_comp, np.nan))
    put(10, np.where(lid_valid, lid_rad, np.nan))
    put(11, np.where(lid_valid, step_max * coh100, np.nan))
    put(36, lid_valid.astype(np.float32))
    del ex_max, step_max, lapneg, downf, coh100, lid_comp, lid_fill, lid_div, lid_rad
    gc.collect()

    # --- Family 2: Cover-Stratified Half-Graben Basement & Gravity Crest Tomography ---
    cover_depth = np.log1p(np.maximum(b[15], 0.0)).astype(np.float32)
    put(12, cover_depth)
    bgy, bgx = np.gradient(ndi.gaussian_filter(b[15], sigma=2.0, mode="nearest"))
    base_grad_div = divisive_contrast(np.hypot(bgx, bgy).astype(np.float32), sigma_bg=20.0)
    put(13, base_grad_div)
    base_rad, _, _ = directional_radon_ridge(base_grad_div, sigma_cross=1.5, length_along=5.0)
    put(14, base_rad)

    grav = b[13]
    put(15, grav - ndi.gaussian_filter(grav, sigma=8.0, mode="nearest"))
    grav_sl_div = divisive_contrast(np.maximum(b[5], 0.0), sigma_bg=18.0)
    put(16, grav_sl_div)
    grav_hg_div = divisive_contrast(np.abs(b[18]), sigma_bg=18.0)
    put(17, grav_hg_div)
    put(18, divisive_contrast(np.abs(b[11]), sigma_bg=18.0))
    grav_rad, _, theta_grav = directional_radon_ridge(grav_sl_div + 0.5 * grav_hg_div, sigma_cross=1.5, length_along=5.0)
    put(19, grav_rad)
    put(20, (cover_depth * np.maximum(grav_rad, 0.0)).astype(np.float32))

    # --- Family 3: Shallow Hydrothermal Demagnetization Trough & Magnetic Contact ---
    rtp = b[2]
    put(21, rtp - ndi.gaussian_filter(rtp, sigma=8.0, mode="nearest"))
    put(22, divisive_contrast(np.maximum(b[3], 0.0), sigma_bg=16.0))
    tmi_vg = b[9]
    vg_pos = divisive_contrast(np.maximum(tmi_vg, 0.0), sigma_bg=16.0)
    vg_neg = divisive_contrast(np.maximum(-tmi_vg, 0.0), sigma_bg=16.0)
    put(23, vg_pos)
    put(24, vg_neg)
    # Tilt derivative zero-crossing sharpness: high gradient where tc passes low angle
    tc_edge = np.exp(-np.abs(b[6] - np.median(b[6][footprint])) / 15.0).astype(np.float32)
    put(25, tc_edge)
    demag_rad, _, _ = directional_radon_ridge(vg_neg, sigma_cross=1.2, length_along=4.5)
    put(26, demag_rad)

    with rasterio.open(data_dir / "external" / "geodawn_extensions_u8.tif") as eds:
        thk = eds.read(1).astype(np.float32) * np.float32(1.0 / 255.0)
        uth = eds.read(3).astype(np.float32) * np.float32(1.0 / 255.0)
        tmi_up = eds.read(4).astype(np.float32) * np.float32(1.0 / 255.0)
    tmi_norm = (b[14] - np.percentile(b[14][footprint], 1.0)) / max(
        float(np.percentile(b[14][footprint], 99.0) - np.percentile(b[14][footprint], 1.0)), 1.0
    )
    shallow_res = (np.clip(tmi_norm, 0.0, 1.0) - tmi_up).astype(np.float32)
    put(27, shallow_res)
    mag_rad, _, _ = directional_radon_ridge(vg_pos + 0.5 * np.abs(shallow_res), sigma_cross=1.2, length_along=4.5)
    put(28, mag_rad)

    # --- Family 4: MT Conductive Boundary + GeoDAWN Radiometric Alteration + GDR Thermal ---
    cond = b[17]
    put(29, cond)
    cgy, cgx = np.gradient(ndi.gaussian_filter(cond, sigma=1.8, mode="nearest"))
    put(30, divisive_contrast(np.hypot(cgx, cgy).astype(np.float32), sigma_bg=18.0))

    with rasterio.open(data_dir / "external" / "geodawn_rad_u8.tif") as rds:
        rad_k = rds.read(1).astype(np.float32) * np.float32(1.0 / 255.0)
        rad_th = rds.read(2).astype(np.float32) * np.float32(1.0 / 255.0)
        rad_tc = rds.read(4).astype(np.float32) * np.float32(1.0 / 255.0)
    k_th = (rad_k / (rad_th + 0.08)).astype(np.float32)
    put(31, k_th - ndi.gaussian_filter(k_th, sigma=10.0, mode="nearest"))
    rgy, rgx = np.gradient(ndi.gaussian_filter(0.5 * k_th + 0.3 * thk + 0.2 * uth + 0.2 * rad_tc, sigma=1.8, mode="nearest"))
    put(32, divisive_contrast(np.hypot(rgx, rgy).astype(np.float32), sigma_bg=16.0))

    th_near, th_meso, vent_halo = _build_gdr_thermal_grids(data_dir, footprint.shape)
    put(33, th_near)
    put(34, th_meso)
    put(35, vent_halo)
    del rad_k, rad_th, rad_tc, thk, uth, tmi_up, th_near, th_meso, vent_halo
    gc.collect()

    # --- Family 5: Cross-Physics Coupling + Andersonian Strain & Microseismicity ---
    tg_align, _ = cross_gradient_operators(slope, grav, sigma=2.2)
    _, gm_ortho = cross_gradient_operators(grav, rtp, sigma=2.5)
    put(37, tg_align)
    put(38, gm_ortho)
    put(39, b[4])
    put(40, b[7])
    put(41, b[8])
    put(42, np.log1p(np.maximum(b[16], 0.0)) - 0.15 * np.log1p(np.maximum(b[10], 0.0)))

    # Dominant physical strike azimuth (blend topographic structure tensor & potential-field strike by cover depth)
    w_deep = np.clip(cover_depth / 6.0, 0.15, 0.85)
    vx = (1.0 - w_deep) * np.cos(2.0 * theta_st) + w_deep * np.cos(2.0 * theta_grav)
    vy = (1.0 - w_deep) * np.sin(2.0 * theta_st) + w_deep * np.sin(2.0 * theta_grav)
    phys_theta = np.mod(0.5 * np.arctan2(vy, vx), np.pi).astype(np.float32)

    # Convert math angle (dy=sin, dx=cos) to geographic clockwise-from-North azimuth for Anderson prior:
    # north is dy = -1, east is dx = +1 => az_deg = atan2(dx, -dy) mod 180
    az_deg = np.mod(np.rad2deg(np.arctan2(np.cos(phys_theta), -np.sin(phys_theta))), 180.0)
    d_norm = np.minimum(np.abs(az_deg - 18.0), 180.0 - np.abs(az_deg - 18.0))
    d_walk = np.minimum(np.abs(az_deg - 145.0), 180.0 - np.abs(az_deg - 145.0))
    and_fav = (sl_coh * np.maximum(np.cos(np.deg2rad(2.0 * d_norm)), 0.75 * np.cos(np.deg2rad(2.0 * d_walk)))).astype(np.float32)
    put(43, and_fav)

    mm.flush()
    np.save(theta_path, phys_theta)
    meta_path.write_text(
        json.dumps({"shape": [n_fp, n_feat], "features": list(STATIC_FEATURE_NAMES)}, indent=2) + "\n",
        encoding="utf-8",
    )
    del b
    gc.collect()
    mm_ro = np.memmap(mmap_path, dtype=np.float32, mode="r", shape=(n_fp, n_feat))
    return mm_ro, phys_theta, list(STATIC_FEATURE_NAMES)


TRANSFER_FEATURE_NAMES: tuple[str, ...] = (
    "t00_tip_beam_near",
    "t01_tip_beam_far",
    "t02_tip_horsetail_splay",
    "t03_relay_breach_overlap",
    "t04_strand_aniso_cont",
    "t05_tip_phys_strike_lock",
    "t06_host_len_halo",
    "t07_meso_tectonic_prox",
)


def compute_visible_transfer_features(
    visible_mask: np.ndarray,
    footprint: np.ndarray,
    phys_theta: np.ndarray,
    cache_path: Path | None = None,
) -> np.ndarray:
    """Compute strictly fold-visible crack-tip, splay, relay-ramp & strike-lock features.

    CRITICAL INVARIANT: ``visible_mask`` MUST contain ONLY the visible fault trace for the
    active fold (never held-out truth). Uses exact sparse tip coordinate indexing over
    ``np.nonzero(vis)`` for O(|K_vis|) speed (~0.4s/fold). Returns shape ``(n_footprint, 8)`` float32.
    """
    fp_idx = np.flatnonzero(footprint)
    if cache_path is not None and cache_path.exists():
        mm = np.memmap(cache_path, dtype=np.float32, mode="r", shape=(fp_idx.size, len(TRANSFER_FEATURE_NAMES)))
        return mm

    vis = np.asarray(visible_mask, dtype=bool) & footprint
    vis_f = vis.astype(np.float32)
    vis_dil1 = ndi.binary_dilation(vis, iterations=1)

    # Connected component trace sizes -> sqrt(L) elastic stress intensity scaling (Pollard & Segall, 1987)
    comp_lbl, n_comp = ndi.label(vis, structure=np.ones((3, 3), dtype=int))
    comp_sizes = np.bincount(comp_lbl.ravel(), minlength=n_comp + 1).astype(np.float32)
    comp_sizes[0] = 0.0
    len_weight = np.where(vis, np.minimum(2.5, 0.40 + 0.22 * np.sqrt(comp_sizes[comp_lbl])), 0.0).astype(np.float32)

    h, w = footprint.shape
    vy, vx = np.nonzero(vis)
    lw_v = len_weight[vy, vx]

    raw_near = np.zeros((h, w), dtype=np.float32)
    raw_far = np.zeros((h, w), dtype=np.float32)
    best_tip_theta = np.zeros((h, w), dtype=np.float32)
    half_beams = [np.zeros((h, w), dtype=np.float32) for _ in range(16)]

    for m, phi in enumerate(RAY_ANGLES):
        uy = np.sin(phi)
        ux = np.cos(phi)
        # 1. Backward strand support at sparse fault coordinates (vy, vx)
        back = np.zeros(vy.size, dtype=np.int16)
        for s in (1, 2, 3, 4, 5, 6):
            ry = np.clip(vy + int(round(-s * uy)), 0, h - 1)
            rx = np.clip(vx + int(round(-s * ux)), 0, w - 1)
            back += vis[ry, rx]
        # 2. Forward termination gap at steps 2..5 (true termination tip!)
        gap = np.ones(vy.size, dtype=bool)
        for s in (2, 3, 4, 5):
            ry = np.clip(vy + int(round(s * uy)), 0, h - 1)
            rx = np.clip(vx + int(round(s * ux)), 0, w - 1)
            gap &= ~vis_dil1[ry, rx]

        is_tip = (back >= 3) & gap
        if not np.any(is_tip):
            continue
        ty = vy[is_tip]
        tx = vx[is_tip]
        tw = lw_v[is_tip]

        # Scatter forward crack-tip rays along +u
        b_m = half_beams[m]
        for r in range(1, 27):
            sy = ty + int(round(r * uy))
            sx = tx + int(round(r * ux))
            inb = (sy >= 0) & (sy < h) & (sx >= 0) & (sx < w)
            if not np.any(inb):
                continue
            sy_i, sx_i, tw_i = sy[inb], sx[inb], tw[inb]
            if r <= 9:
                wn = tw_i * np.float32(np.exp(-r / 5.0))
                np.maximum.at(raw_near, (sy_i, sx_i), wn)
            wf = tw_i * np.float32(np.exp(-r / 12.0))
            prev = raw_far[sy_i, sx_i]
            np.maximum.at(raw_far, (sy_i, sx_i), wf)
            improved = raw_far[sy_i, sx_i] > prev
            if np.any(improved):
                best_tip_theta[sy_i[improved], sx_i[improved]] = np.float32(phi % np.pi)
            np.maximum.at(b_m, (sy_i, sx_i), wf)

    beam_near_max = ndi.gaussian_filter(raw_near, sigma=1.2, mode="constant").astype(np.float32)
    beam_far_max = ndi.gaussian_filter(raw_far, sigma=2.4, mode="constant").astype(np.float32)

    # Opposing en-echelon relay-ramp overlap: facing beams m and m+8 across stepover width
    relay = np.zeros((h, w), dtype=np.float32)
    for m in range(8):
        if half_beams[m].any() and half_beams[m + 8].any():
            f_a = ndi.gaussian_filter(half_beams[m], sigma=3.5, mode="constant")
            f_b = ndi.gaussian_filter(half_beams[m + 8], sigma=3.5, mode="constant")
            relay = np.maximum(relay, np.sqrt(np.maximum(f_a * f_b, 0.0)))
    del half_beams, raw_near, raw_far

    # Horsetail splay cone
    splay = ndi.gaussian_filter(beam_near_max, sigma=3.2, mode="constant").astype(np.float32)

    # Anisotropic strand continuation
    strand_cont = (
        0.55 * ndi.gaussian_filter(vis_f, sigma=2.5, mode="constant")
        + 0.45 * ndi.gaussian_filter(vis_f, sigma=6.5, mode="constant")
    ).astype(np.float32)

    # Tip-to-physics azimuthal strike lock
    strike_lock = (beam_far_max * np.square(np.cos(best_tip_theta - phys_theta))).astype(np.float32)

    # Host fault length influence & capped mesoscale tectonic proximity
    d_vis, nearest_idx = ndi.distance_transform_edt(~vis, return_indices=True)
    host_len = (len_weight[nearest_idx[0], nearest_idx[1]] * np.exp(-d_vis / 18.0)).astype(np.float32)
    meso_prox = np.exp(-np.maximum(d_vis, 3.0) / 14.0).astype(np.float32)

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        out = np.memmap(cache_path, dtype=np.float32, mode="w+", shape=(fp_idx.size, len(TRANSFER_FEATURE_NAMES)))
    else:
        out = np.empty((fp_idx.size, len(TRANSFER_FEATURE_NAMES)), dtype=np.float32)
    for j, arr in enumerate(
        (beam_near_max, beam_far_max, splay, relay, strand_cont, strike_lock, host_len, meso_prox)
    ):
        out[:, j] = arr.ravel()[fp_idx]
    if cache_path is not None:
        out.flush()
        return np.memmap(cache_path, dtype=np.float32, mode="r", shape=(fp_idx.size, len(TRANSFER_FEATURE_NAMES)))
    return out
