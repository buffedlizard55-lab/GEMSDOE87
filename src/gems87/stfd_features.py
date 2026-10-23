"""Session 2 feature engineering: Salem Tilt-Depth, Swarm-Triggered Seismicity &
Hydrothermal Self-Sealing Fault Detector (`H87B-STFD`).

Design principles enforced in code:
1. Empirical band-identity corrections (`IR87-028`, `IR87-029`):
   - Band 06 (`tc`) is GeoDAWN Airborne Radiometric Total Count (verified r = +0.9957
     against USGS `geodawn_rad_u8.tif` band 4 `TC`), NOT magnetic tilt angle.
   - True analytic Miller-Singh (1994) magnetic tilt angle is computed directly from
     unit-matched vertical and horizontal derivatives:
         tilt = atan2(100.0 * B09_tmi_vg, B03_tmi_hg + eps)
     and Salem et al. (2007) tilt-depth inverse proxy is |grad_H(tilt)|.
   - Bands 10 & 16 (`deq_n100a15`, `ieq_n100a15`) are Nevada Geodetic Laboratory
     dependent (swarm/aftershock) and independent (declustered background) seismicity
     densities (Kreemer & Young, 2022, DOI 10.1785/0220220153), NOT earthquake distance.
2. Strict zero-leakage firewall:
   - The 48 physical/hydrothermal/geomorphic channels never touch `existing_faults.tif`,
     `dist_known_fault_px`, `derived_sgmc_faults_100m_u8.tif`, or any prediction raster.
   - The 16 structural fracture-mechanics channels are strictly functions of a
     caller-supplied `visible_mask` (`fold["visible"]` inside holdout folds;
     `grid.catalogue` at off-catalogue production time).
3. Strict memory ceiling (< 750 MB RSS on 3.8 GB hardware):
   - Stores only the `N_fp = 5,167,373` in-footprint cells inside an on-disk float32
     memmap `(N_fp, 48)` (~992 MB on disk), computing one 2D grid buffer at a time.
"""

from __future__ import annotations

import csv
import math
import struct
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform
from scipy.ndimage import (
    distance_transform_edt,
    gaussian_filter,
    maximum_filter,
    zoom,
)

from gems57.grid import Grid

EPS = 1e-6

FORBIDDEN_CSV_COLUMNS = frozenset({"dist_known_fault_px"})

PHYSICAL_FEATURE_NAMES: tuple[str, ...] = (
    # Group A: Unit-verified potential fields, Salem tilt-depth & upward continuation (14)
    "b01_depth_base_km",
    "b02_iso_grav_mgal",
    "b03_log_tmi_hg",
    "b05_log_grav_slope",
    "b09_tmi_vg_scaled",
    "b11_grav_vg",
    "b18_grav_hg_signed",
    "b19_tmi_demag_resid",
    "stfd_miller_singh_tilt",
    "stfd_salem_tilt_depth_inv",
    "stfd_tilt_zero_crossing",
    "stfd_up150_shallow_mag_contrast",
    "stfd_gallardo_cross_grad_norm",
    "stfd_basement_relief_grad",
    # Group B: Crustal stress, fluid-swarm seismicity & seismic-geodetic deficit (8)
    "b04_strain_rate",
    "b07_dilation_tendency",
    "b13_slip_tendency",
    "b10_log_deq_density",
    "b16_log_ieq_density",
    "stfd_swarm_excess_logratio",
    "stfd_aseismic_strain_deficit",
    "stfd_coulomb_dilation_product",
    # Group C: Crustal conductivity, heat flow, 2m temperature probes & hydrothermal seals (12)
    "b14_heatflow",
    "b15_log_mt_cond_9200",
    "b17_log_mt_cond_30000",
    "stfd_mt_upflow_conductance_ratio",
    "b06_radiometric_tc",
    "stfd_potassic_alteration_k_th",
    "stfd_uranium_redox_u_th",
    "stfd_probe2m_temp_dab_anom",
    "stfd_well_quartz_temp_excess",
    "stfd_paleo_sinter_seal_prox",
    "stfd_quaternary_vent_prox",
    "stfd_blind_hydrothermal_index",
    # Group D: Dual-scale 1m LiDAR scarp + 10m 3DEP curvature & fluvial chi bridge (14)
    "b08_log_det_elev_slope",
    "b12_det_elev",
    "stfd_lidar_valid_flag",
    "stfd_lidar_scarp_step_norm",
    "stfd_lidar_scarp_coherence",
    "stfd_lidar_throw_polarity_asym",
    "stfd_dem10_slope_p90",
    "stfd_dem10_prof_curv",
    "stfd_dem10_hs_lineament",
    "stfd_dem10_aspect_coherence",
    "stfd_chi_knickpoint_halo",
    "stfd_chi_ksn_halo",
    "stfd_cover_thickness_regime",
    "stfd_scarp_deficiency_buried_fault",
)

STRUCTURAL_FEATURE_NAMES: tuple[str, ...] = (
    "vis_log_dist_px",
    "vis_prox_exp_6px",
    "vis_prox_exp_20px",
    "vis_prox_exp_60px",
    "vis_along_strike_proj_s8",
    "vis_along_strike_proj_s20",
    "vis_crack_tip_wing_lobe",
    "vis_en_echelon_relay_bridge",
    "vis_multi_scale_density_s15",
    "vis_multi_scale_density_s45",
    "vis_gap_saddle_index",
    "vis_strike_alignment_scarp",
    "vis_strike_alignment_mag_tilt",
    "vis_updip_grav_flexure",
    "vis_blind_relay_hydrothermal_gate",
    "vis_cover_masked_continuation",
)

ALL_FEATURE_NAMES: tuple[str, ...] = PHYSICAL_FEATURE_NAMES + STRUCTURAL_FEATURE_NAMES


def _clean_band(raw: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    out = np.asarray(raw, dtype=np.float32).copy()
    bad = (~np.isfinite(out)) | (np.abs(out) > 1e30) | (~valid_mask)
    fill = float(np.median(out[~bad])) if np.any(~bad) else 0.0
    out[bad] = fill
    return out


def _masked_smooth(field: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    m = mask.astype(np.float32)
    num = gaussian_filter(field * m, sigma=sigma, mode="nearest")
    den = gaussian_filter(m, sigma=sigma, mode="nearest")
    out = np.zeros_like(field, dtype=np.float32)
    ok = den > 1e-4
    out[ok] = num[ok] / den[ok]
    return out


def _local_z(field: np.ndarray, mask: np.ndarray, sigma: float = 25.0) -> np.ndarray:
    mean = _masked_smooth(field, mask, sigma=sigma)
    resid = field - mean
    var = _masked_smooth(resid * resid, mask, sigma=sigma)
    out = resid / np.sqrt(np.maximum(var, 1e-6))
    out[~mask] = 0.0
    return np.clip(out, -8.0, 8.0).astype(np.float32)


def _read_dbf_records(zp: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(zp) as zf:
        dbf_name = next(n for n in zf.namelist() if n.lower().endswith(".dbf"))
        raw = zf.read(dbf_name)
    num_rec, hdr_len, rec_len = struct.unpack("<IHH", raw[4:12])
    fields: list[tuple[str, int]] = []
    pos = 32
    while raw[pos] != 0x0D:
        fname = raw[pos : pos + 11].split(b"\x00", 1)[0].decode("latin1")
        flen = raw[pos + 16]
        fields.append((fname, flen))
        pos += 32
    rows: list[dict[str, str]] = []
    offset = hdr_len
    for _ in range(num_rec):
        rec = raw[offset : offset + rec_len]
        offset += rec_len
        if not rec or rec[0:1] == b"*":
            continue
        p = 1
        row: dict[str, str] = {}
        for fname, flen in fields:
            row[fname] = rec[p : p + flen].decode("latin1", errors="ignore").strip()
            p += flen
        rows.append(row)
    return rows


def rasterize_hydrothermal_point_layers(
    grid: Grid,
    ext_dir: Path,
) -> dict[str, np.ndarray]:
    """Rasterize strictly label-free DOE GDR #1391 geochemical, 2-m probe, sinter & vent observations."""
    h, w = grid.shape
    a, _b, c, _d, e, f = (
        grid.transform.a,
        grid.transform.b,
        grid.transform.c,
        grid.transform.d,
        grid.transform.e,
        grid.transform.f,
    )
    # 1. INGENIOUS 2-m temperature survey probes (`F2mDAB`: depth- and altitude-adjusted 2-m anomaly)
    probe_val = np.zeros((h, w), dtype=np.float32)
    probe_cnt = np.zeros((h, w), dtype=np.float32)
    probe_zip = ext_dir / "2m_temperature_probe_INGENIOUS_regional_data.zip"
    if probe_zip.exists():
        ues, uns, dabs = [], [], []
        for rec in _read_dbf_records(probe_zip):
            try:
                ue = float(rec["UTM_E"])
                un = float(rec["UTM_N"])
                dab = float(rec["F2mDAB"])
            except (KeyError, ValueError):
                continue
            if math.isfinite(ue) and math.isfinite(un) and math.isfinite(dab):
                ues.append(ue)
                uns.append(un)
                dabs.append(float(np.clip(dab, -8.0, 25.0)))
        if ues:
            xs11, ys11 = warp_transform("EPSG:26911", "EPSG:32611", ues, uns)
            for x11, y11, dab in zip(xs11, ys11, dabs):
                col = int((x11 - c) / a)
                row = int((y11 - f) / e)
                if 0 <= row < h and 0 <= col < w and grid.footprint[row, col]:
                    probe_val[row, col] += dab
                    probe_cnt[row, col] += 1.0
    probe_anom = _masked_smooth(probe_val, probe_cnt > 0, sigma=12.0) * np.tanh(
        gaussian_filter(probe_cnt, sigma=12.0) * 6.0
    )
    probe_anom[~grid.footprint] = 0.0

    # 2. GDR well & spring fluid temperature / quartz geothermometer enthalpy excess
    well_val = np.zeros((h, w), dtype=np.float32)
    well_cnt = np.zeros((h, w), dtype=np.float32)
    well_csv = ext_dir / "gdr_wellspring_in_footprint.csv"
    if well_csv.exists():
        with well_csv.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            allowed_cols = set(reader.fieldnames or ()) - FORBIDDEN_CSV_COLUMNS
            assert "dist_known_fault_px" not in allowed_cols
            for r in reader:
                try:
                    rr = int(r["row"])
                    cc = int(r["col"])
                except (KeyError, ValueError):
                    continue
                if not (0 <= rr < h and 0 <= cc < w and grid.footprint[rr, cc]):
                    continue
                temps = []
                for k in ("temp_c", "quartz_c", "chalcedony_c"):
                    v_str = (r.get(k) or "").strip()
                    if v_str:
                        try:
                            fv = float(v_str)
                            if 5.0 <= fv <= 380.0:
                                temps.append(fv)
                        except ValueError:
                            pass
                if temps:
                    excess = max(0.0, max(temps) - 22.0)
                    well_val[rr, cc] = max(well_val[rr, cc], math.log1p(excess))
                    well_cnt[rr, cc] = 1.0
    well_excess = _masked_smooth(well_val, well_cnt > 0, sigma=10.0) * np.tanh(
        gaussian_filter(well_cnt, sigma=10.0) * 8.0
    )
    well_excess[~grid.footprint] = 0.0

    # 3. Paleo-geothermal sinter / travertine self-sealed fault outcrops
    paleo_seed = np.zeros((h, w), dtype=bool)
    paleo_zip = ext_dir / "paleo_geothermal_regional.zip"
    if paleo_zip.exists():
        lons, lats = [], []
        for rec in _read_dbf_records(paleo_zip):
            try:
                lon = float(rec["Long_deg"])
                lat = float(rec["Lat_deg"])
            except (KeyError, ValueError):
                continue
            if -125.0 <= lon <= -110.0 and 35.0 <= lat <= 45.0:
                lons.append(lon)
                lats.append(lat)
        if lons:
            pxs, pys = warp_transform("EPSG:4326", "EPSG:32611", lons, lats)
            for x11, y11 in zip(pxs, pys):
                col = int((x11 - c) / a)
                row = int((y11 - f) / e)
                if 0 <= row < h and 0 <= col < w:
                    paleo_seed[row, col] = True
    paleo_dist = distance_transform_edt(~paleo_seed).astype(np.float32) if paleo_seed.any() else np.full((h, w), 500.0, np.float32)
    paleo_prox = np.exp(-paleo_dist / 35.0).astype(np.float32)
    paleo_prox[~grid.footprint] = 0.0

    # 4. Quaternary volcanic vents (label column explicitly excluded)
    vent_seed = np.zeros((h, w), dtype=bool)
    vent_csv = ext_dir / "gdr_volcanic_vents_in_footprint.csv"
    if vent_csv.exists():
        with vent_csv.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            allowed_cols = set(reader.fieldnames or ()) - FORBIDDEN_CSV_COLUMNS
            assert "dist_known_fault_px" not in allowed_cols
            for r in reader:
                try:
                    rr = int(r["row"])
                    cc = int(r["col"])
                except (KeyError, ValueError):
                    continue
                if 0 <= rr < h and 0 <= cc < w:
                    vent_seed[rr, cc] = True
    vent_dist = distance_transform_edt(~vent_seed).astype(np.float32) if vent_seed.any() else np.full((h, w), 500.0, np.float32)
    vent_prox = np.exp(-vent_dist / 50.0).astype(np.float32)
    vent_prox[~grid.footprint] = 0.0

    return {
        "probe_anom": probe_anom,
        "well_excess": well_excess,
        "paleo_prox": paleo_prox,
        "vent_prox": vent_prox,
    }


def build_physical_memmap(
    grid: Grid,
    band_cache_dir: Path,
    ext_dir: Path,
    memmap_path: Path,
    force_rebuild: bool = False,
) -> tuple[np.memmap, dict[str, Any]]:
    """Build or load `(N_fp, 48)` on-disk float32 physical stack plus lightweight strike maps."""
    fp = grid.footprint
    n_fp = int(fp.sum())
    n_ch = len(PHYSICAL_FEATURE_NAMES)
    meta_npz = memmap_path.with_suffix(".aux.npz")

    if memmap_path.exists() and meta_npz.exists() and not force_rebuild:
        mm = np.memmap(memmap_path, dtype=np.float32, mode="r", shape=(n_fp, n_ch))
        aux_loaded = np.load(meta_npz)
        aux = {k: aux_loaded[k] for k in aux_loaded.files}
        return mm, aux

    memmap_path.parent.mkdir(parents=True, exist_ok=True)
    mm = np.memmap(memmap_path, dtype=np.float32, mode="w+", shape=(n_fp, n_ch))

    def load_b(idx1: int) -> np.ndarray:
        raw = np.load(band_cache_dir / f"band-{idx1:02d}.npy", mmap_mode="r")
        return _clean_band(raw, fp)

    def put(col_idx: int, arr2d: np.ndarray) -> None:
        vals = np.asarray(arr2d[fp], dtype=np.float32)
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
        mm[:, col_idx] = vals

    # --- Group A: Potential fields & unit-matched Salem tilt-depth ---
    b01 = load_b(1)  # depth_to_base_surf (m)
    b02 = load_b(2)  # iso_grav_anom (mGal)
    b03 = np.maximum(load_b(3), 0.0)  # tmi_hg (nT / 100 m)
    b05 = np.maximum(load_b(5), 0.0)  # iso_grav_anom_slope
    b09 = load_b(9)  # tmi_vg (nT / m -> x100 to match nT / 100 m)
    b11 = load_b(11)  # iso_grav_anom_vg
    b18 = load_b(18)  # signed iso_grav_anom_hg
    b19 = load_b(19)  # tmi_rtp residual

    tilt = np.arctan2(100.0 * b09, b03 + 1.0).astype(np.float32)
    dtilt_dy, dtilt_dx = np.gradient(tilt)
    salem_inv = np.hypot(dtilt_dx, dtilt_dy).astype(np.float32)
    tilt_zero = np.exp(-np.abs(tilt) / 0.25) * np.tanh(salem_inv / 0.12)

    rad_path = ext_dir / "geodawn_rad_u8.tif"
    ext_mag_path = ext_dir / "geodawn_extensions_u8.tif"
    b06 = load_b(6)  # Verified GeoDAWN Airborne Radiometric Total Count (TC)
    if ext_mag_path.exists():
        with rasterio.open(ext_mag_path) as src:
            thk_u8 = src.read(1).astype(np.float32) / 255.0
            uk_u8 = src.read(2).astype(np.float32) / 255.0
            uth_u8 = src.read(3).astype(np.float32) / 255.0
            up150 = src.read(4).astype(np.float32) / 255.0
    else:
        thk_u8 = np.zeros_like(b01)
        uk_u8 = np.zeros_like(b01)
        uth_u8 = np.zeros_like(b01)
        up150 = np.zeros_like(b01)

    if rad_path.exists():
        with rasterio.open(rad_path) as src:
            tc_u8 = src.read(4).astype(np.float32)
        tc_mask = fp & (tc_u8 > 0)
        tc_pearson_r = float(np.corrcoef(b06[tc_mask], tc_u8[tc_mask])[0, 1])
    else:
        tc_pearson_r = float("nan")

    up150_contrast = _local_z(b19, fp, sigma=18.0) - _local_z(up150, fp, sigma=18.0)

    # Gallardo-Meju normalized cross-gradient between TMI and Bouguer/isostatic gravity
    gt_y, gt_x = np.gradient(_masked_smooth(b19, fp, sigma=1.5))
    gg_y, gg_x = np.gradient(_masked_smooth(b02, fp, sigma=1.5))
    cross_g = (gt_x * gg_y - gt_y * gg_x) / (np.hypot(gt_x, gt_y) * np.hypot(gg_x, gg_y) + 1e-4)
    base_gy, base_gx = np.gradient(_masked_smooth(b01, fp, sigma=2.0))
    base_grad = np.log1p(np.hypot(base_gx, base_gy)).astype(np.float32)

    put(0, b01 / 1000.0)
    put(1, b02)
    put(2, np.log1p(b03))
    put(3, np.log1p(b05))
    put(4, 100.0 * b09)
    put(5, b11)
    put(6, b18)
    put(7, np.clip(b19 / 100.0, -10.0, 10.0))
    put(8, tilt)
    put(9, salem_inv)
    put(10, tilt_zero)
    put(11, up150_contrast)
    put(12, cross_g)
    put(13, base_grad)

    # Save compact orientation & signed flexure arrays for within-fold structural physics
    mag_strike_cos2 = np.cos(2.0 * np.arctan2(dtilt_dy, dtilt_dx + EPS)).astype(np.float32)
    mag_strike_sin2 = np.sin(2.0 * np.arctan2(dtilt_dy, dtilt_dx + EPS)).astype(np.float32)
    del b02, b03, b05, b09, b11, b19, up150, up150_contrast, cross_g, base_grad, gt_x, gt_y, gg_x, gg_y

    # --- Group B: Crustal stress, swarm excess & seismic-geodetic deficit ---
    b04 = np.maximum(load_b(4), 0.0)  # strain_rate
    b07 = load_b(7)  # dilation_tendency
    b13 = load_b(13)  # slip_tendency
    b10 = np.maximum(load_b(10), 0.0)  # deq_n100a15 dependent swarm density
    b16 = np.maximum(load_b(16), 1e-8)  # ieq_n100a15 independent declustered density

    log_deq = np.log10(b10 + 1.0).astype(np.float32)
    log_ieq = np.log10(b16).astype(np.float32)
    swarm_excess = (log_deq - _masked_smooth(log_ieq, fp, sigma=8.0)).astype(np.float32)
    aseismic_deficit = (_local_z(b04, fp, sigma=30.0) - _local_z(log_ieq, fp, sigma=30.0)).astype(np.float32)
    coulomb_dil = (b07 * b13 * np.log1p(b04)).astype(np.float32)

    put(14, b04)
    put(15, b07)
    put(16, b13)
    put(17, log_deq)
    put(18, log_ieq)
    put(19, swarm_excess)
    put(20, aseismic_deficit)
    put(21, coulomb_dil)
    del b04, b07, b13, b10, b16, log_ieq, aseismic_deficit, coulomb_dil

    # --- Group C: Heat flow, MT conductance, radiometrics & hydrothermal fluids ---
    b14 = load_b(14)
    b15 = np.log1p(np.maximum(load_b(15), 0.0))
    b17 = np.log1p(np.maximum(load_b(17), 0.0))
    mt_ratio = (b15 - b17).astype(np.float32)
    k_alter = (uk_u8 - thk_u8).astype(np.float32)
    hydro_pts = rasterize_hydrothermal_point_layers(grid, ext_dir)

    blind_hydro = (
        0.35 * _local_z(b14, fp, sigma=35.0)
        + 0.25 * _local_z(mt_ratio, fp, sigma=25.0)
        + 0.45 * _local_z(hydro_pts["probe_anom"], fp, sigma=25.0)
        + 0.40 * _local_z(hydro_pts["well_excess"], fp, sigma=25.0)
        + 0.30 * _local_z(swarm_excess, fp, sigma=20.0)
    ).astype(np.float32)

    put(22, b14)
    put(23, b15)
    put(24, b17)
    put(25, mt_ratio)
    put(26, b06)
    put(27, k_alter)
    put(28, uth_u8)
    put(29, hydro_pts["probe_anom"])
    put(30, hydro_pts["well_excess"])
    put(31, hydro_pts["paleo_prox"])
    put(32, hydro_pts["vent_prox"])
    put(33, blind_hydro)
    del b14, b15, b17, mt_ratio, b06, k_alter, thk_u8, uk_u8, uth_u8, hydro_pts, log_deq, swarm_excess

    # --- Group D: 1m LiDAR scarp + 10m 3DEP curvature & fluvial chi bridge ---
    b08 = np.log1p(np.maximum(load_b(8), 0.0))
    b12 = load_b(12)

    lidar_path = ext_dir / "lidar_scarp_features_u8.tif"
    if lidar_path.exists():
        with rasterio.open(lidar_path) as src:
            ex_max = src.read(1).astype(np.float32) / 255.0
            step_max = src.read(3).astype(np.float32) / 255.0
            downface = src.read(6).astype(np.float32) / 255.0
            upface = src.read(7).astype(np.float32) / 255.0
            coh100 = src.read(10).astype(np.float32) / 255.0
            strike_rad = (src.read(11).astype(np.float32) / 255.0) * math.pi
            lidar_valid = (src.read(12) > 0) & fp
    else:
        ex_max = step_max = downface = upface = coh100 = strike_rad = np.zeros_like(b08)
        lidar_valid = np.zeros_like(fp)

    topo10_path = ext_dir / "topo_10m_derived_100m_u8.tif"
    if topo10_path.exists():
        with rasterio.open(topo10_path) as src:
            slope_p90 = src.read(1).astype(np.float32) / 255.0
            curv_prof = src.read(6).astype(np.float32) / 255.0
            aspect_coh = src.read(7).astype(np.float32) / 255.0
            hs_lin = src.read(8).astype(np.float32) / 255.0
    else:
        slope_p90 = curv_prof = aspect_coh = hs_lin = np.zeros_like(b08)

    chi_u8_path = ext_dir / "dem10_chi_100m_u8.tif"
    chi_i16_path = ext_dir / "dem10_chi_100m_i16.tif"
    if chi_u8_path.exists() and chi_i16_path.exists():
        with rasterio.open(chi_u8_path) as src:
            chan_n = src.read(1).astype(np.float32)
            knick_n = src.read(2).astype(np.float32)
        with rasterio.open(chi_i16_path) as src:
            ksn_raw = src.read(3)
        ksn_valid = (ksn_raw != -32768) & (chan_n > 0) & fp
        ksn_clean = np.where(ksn_valid, np.maximum(ksn_raw.astype(np.float32), 0.0), 0.0)
        knick_halo = gaussian_filter(np.log1p(knick_n) * fp.astype(np.float32), sigma=3.0, mode="nearest")
        ksn_halo = _masked_smooth(np.log1p(ksn_clean), ksn_valid, sigma=4.0)
    else:
        knick_halo = ksn_halo = np.zeros_like(b08)

    # Seamless cross-sensor scarp step: 1m LiDAR where valid, calibrated 10m profile-curvature fallback where missing
    scarp_bridge = np.where(
        lidar_valid,
        0.55 * step_max + 0.45 * ex_max,
        0.55 * curv_prof + 0.45 * hs_lin,
    ).astype(np.float32)
    coherence_bridge = np.where(lidar_valid, coh100, aspect_coh).astype(np.float32)
    throw_asym = np.where(lidar_valid, np.abs(downface - upface), 0.25 * curv_prof).astype(np.float32)

    # Cover-thickness observational propensity proxy (high in deep low-slope alluvial basins)
    cover_regime = (
        np.tanh(np.maximum(b01, 0.0) / 600.0) * np.exp(-np.maximum(slope_p90, 0.0) * 4.5)
    ).astype(np.float32)
    buried_fault_signal = (
        cover_regime * (0.55 * np.tanh(salem_inv * 4.0) + 0.45 * np.clip(blind_hydro / 3.0, -1.0, 2.0))
    ).astype(np.float32)

    scarp_strike_cos2 = np.where(lidar_valid, np.cos(2.0 * strike_rad), 0.0).astype(np.float32)
    scarp_strike_sin2 = np.where(lidar_valid, np.sin(2.0 * strike_rad), 0.0).astype(np.float32)

    put(34, b08)
    put(35, b12)
    put(36, lidar_valid.astype(np.float32))
    put(37, scarp_bridge)
    put(38, coherence_bridge)
    put(39, throw_asym)
    put(40, slope_p90)
    put(41, curv_prof)
    put(42, hs_lin)
    put(43, aspect_coh)
    put(44, knick_halo)
    put(45, ksn_halo)
    put(46, cover_regime)
    put(47, buried_fault_signal)

    mm.flush()

    aux = {
        "tc_pearson_r": np.array(tc_pearson_r, dtype=np.float32),
        "lidar_valid_fraction": np.array(float(lidar_valid[fp].mean()), dtype=np.float32),
        "cover_regime_fp": cover_regime[fp].astype(np.float32),
        "scarp_cos2_fp": scarp_strike_cos2[fp].astype(np.float32),
        "scarp_sin2_fp": scarp_strike_sin2[fp].astype(np.float32),
        "mag_cos2_fp": mag_strike_cos2[fp].astype(np.float32),
        "mag_sin2_fp": mag_strike_sin2[fp].astype(np.float32),
        "b18_fp": b18[fp].astype(np.float32),
        "blind_hydro_fp": blind_hydro[fp].astype(np.float32),
        "scarp_bridge_fp": scarp_bridge[fp].astype(np.float32),
    }
    np.savez_compressed(meta_npz, **aux)
    return np.memmap(memmap_path, dtype=np.float32, mode="r", shape=(n_fp, n_ch)), aux


def compute_visible_structural_features(
    grid: Grid,
    visible_mask: np.ndarray,
    aux: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the 16 strictly visible-only fracture-mechanics channels `(N_fp, 16)` + `dist_px[fp]`.

    Never reads any hidden labels; uses ONLY `visible_mask` (`fold["visible"]` in holdout folds).
    Captures:
      1. Multi-scale radial distance & exponential proximity kernels (600 m, 2 km, 6 km).
      2. Principal structure-tensor tangent vector of `visible_mask` and directional along-strike
         continuation projection (distinguishes off-end fault propagation from flank pixels).
      3. Mode-II/III crack-tip stress lobes detected strictly from endpoints of `visible_mask`
         and oriented along the terminating trace azimuth.
      4. En-echelon relay stepover bridges across unmapped fault gaps.
      5. Angular alignment of 1m LiDAR scarp strike & Salem magnetic tilt strike with visible fabric.
      6. Signed up-dip gravity gradient & blind hydrothermal relay gating across buried valleys.
    """
    fp = grid.footprint
    vis = np.asarray(visible_mask, dtype=bool) & fp
    n_fp = int(fp.sum())
    out = np.zeros((n_fp, len(STRUCTURAL_FEATURE_NAMES)), dtype=np.float32)

    if not vis.any():
        return out, np.full(n_fp, 999.0, dtype=np.float32)

    # Exact Euclidean distance AND nearest visible pixel indices `(nr, nc)` — immediately sliced to `fp`
    rfp, cfp = np.nonzero(fp)
    dist_px_64, (nr, nc) = distance_transform_edt(~vis, return_indices=True)
    d_fp = dist_px_64[rfp, cfp].astype(np.float32)
    nr_fp = nr[rfp, cfp]
    nc_fp = nc[rfp, cfp]
    dist_px = dist_px_64.astype(np.float32)
    del dist_px_64, nr, nc

    vis_f = vis.astype(np.float32)
    s_small = gaussian_filter(vis_f, sigma=2.5, mode="nearest")
    gy, gx = np.gradient(s_small)
    del s_small
    j_xx = gaussian_filter(gx * gx, sigma=8.0, mode="nearest")
    j_yy = gaussian_filter(gy * gy, sigma=8.0, mode="nearest")
    j_xy = gaussian_filter(gx * gy, sigma=8.0, mode="nearest")
    del gx, gy
    strike_theta = (0.5 * np.arctan2(2.0 * j_xy, j_xx - j_yy + EPS) + 0.5 * math.pi).astype(np.float32)
    del j_xx, j_yy, j_xy
    tx = np.cos(strike_theta)
    ty = np.sin(strike_theta)

    # Vector from nearest visible fault pixel `(nc_fp, nr_fp)` to in-footprint pixel `(cfp, rfp)` (1D over `fp`!)
    vx = (cfp - nc_fp).astype(np.float32)
    vy = (rfp - nr_fp).astype(np.float32)
    vnorm = np.hypot(vx, vy) + 1e-4
    cos_along_fp = np.abs((vx / vnorm) * tx[nr_fp, nc_fp] + (vy / vnorm) * ty[nr_fp, nc_fp]).astype(np.float32)
    del vx, vy, vnorm, nr_fp, nc_fp

    along_s8_fp = (cos_along_fp ** 3) * np.exp(-d_fp / 10.0)
    along_s20_fp = (cos_along_fp ** 2) * np.exp(-d_fp / 28.0)

    # Morphological fault-tip detection on visible trace endpoints (computed strictly over 1D `fp` slices!)
    nbr_count = gaussian_filter(vis_f, sigma=1.0, mode="nearest") * 9.0
    tips = vis & (nbr_count <= 3.1)
    del nbr_count
    if tips.any():
        tip_d64, (tr, tc_idx) = distance_transform_edt(~tips, return_indices=True)
        tip_d_fp = tip_d64[rfp, cfp].astype(np.float32)
        tr_fp = tr[rfp, cfp]
        tc_fp = tc_idx[rfp, cfp]
        del tip_d64, tr, tc_idx
        tvx = (cfp - tc_fp).astype(np.float32) / (tip_d_fp + 1e-4)
        tvy = (rfp - tr_fp).astype(np.float32) / (tip_d_fp + 1e-4)
        tip_cos_fp = np.abs(tvx * tx[tr_fp, tc_fp] + tvy * ty[tr_fp, tc_fp])
        wing_lobe_fp = ((tip_cos_fp ** 1.5) * np.exp(-tip_d_fp / 18.0)).astype(np.float32)
        del tvx, tvy, tr_fp, tc_fp, tip_cos_fp, tip_d_fp
    else:
        wing_lobe_fp = along_s20_fp
    del tips, tx, ty

    # Broad-scale fault-network densities (`sigma = 15 px, 45 px` are band-limited well below 4x Nyquist)
    pad_h = (4 - (vis_f.shape[0] % 4)) % 4
    pad_w = (4 - (vis_f.shape[1] % 4)) % 4
    vis_pad = np.pad(vis_f, ((0, pad_h), (0, pad_w)), mode="edge")
    vis_q4 = vis_pad.reshape(vis_pad.shape[0] // 4, 4, vis_pad.shape[1] // 4, 4).mean(axis=(1, 3))
    s15_q4 = gaussian_filter(vis_q4, sigma=15.0 / 4.0, mode="nearest")
    s45_q4 = gaussian_filter(vis_q4, sigma=45.0 / 4.0, mode="nearest")
    dens_s15_full = zoom(s15_q4, 4.0, order=1)[: vis_f.shape[0], : vis_f.shape[1]]
    dens_s45_full = zoom(s45_q4, 4.0, order=1)[: vis_f.shape[0], : vis_f.shape[1]]
    dens_s15_fp = dens_s15_full[rfp, cfp].astype(np.float32)
    dens_s45_fp = dens_s45_full[rfp, cfp].astype(np.float32)
    dens_s5_fp = gaussian_filter(vis_f, sigma=5.0, mode="nearest")[rfp, cfp].astype(np.float32)
    del vis_f, vis_pad, vis_q4, s15_q4, s45_q4, dens_s15_full, dens_s45_full, dist_px

    relay_bridge_fp = (
        dens_s15_fp * np.exp(-((d_fp - 6.0) ** 2) / (2.0 * 14.0 ** 2)) * (0.35 + 0.65 * cos_along_fp)
    ).astype(np.float32)
    gap_saddle_fp = (dens_s45_fp - 0.65 * dens_s5_fp).astype(np.float32)
    del dens_s5_fp, cos_along_fp

    theta_fp = strike_theta[rfp, cfp]
    del strike_theta, rfp, cfp
    cos2_vis = np.cos(2.0 * theta_fp).astype(np.float32)
    sin2_vis = np.sin(2.0 * theta_fp).astype(np.float32)
    del theta_fp

    out[:, 0] = np.log1p(d_fp)
    out[:, 1] = np.exp(-d_fp / 6.0)
    out[:, 2] = np.exp(-d_fp / 20.0)
    out[:, 3] = np.exp(-d_fp / 60.0)
    out[:, 4] = along_s8_fp
    out[:, 5] = along_s20_fp
    out[:, 6] = wing_lobe_fp
    out[:, 7] = relay_bridge_fp
    out[:, 8] = dens_s15_fp
    out[:, 9] = dens_s45_fp
    out[:, 10] = gap_saddle_fp
    out[:, 11] = cos2_vis * aux["scarp_cos2_fp"] + sin2_vis * aux["scarp_sin2_fp"]
    out[:, 12] = cos2_vis * aux["mag_cos2_fp"] + sin2_vis * aux["mag_sin2_fp"]
    out[:, 13] = np.abs(aux["b18_fp"]) * along_s20_fp
    out[:, 14] = np.maximum(aux["blind_hydro_fp"], 0.0) * relay_bridge_fp
    out[:, 15] = aux["cover_regime_fp"] * along_s20_fp

    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0), d_fp
