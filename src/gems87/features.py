"""Memory-disciplined feature engineering for Lane H87-CMGEP (GEMSDOE87).

Streams all 68 physical/geothermal/H87-CMGEP channels and 24 fold-proper structural/coupling
channels directly into `(n_fp, C)` `float16` matrices on `[footprint]`, keeping peak RSS < 450 MB
on a 3.8 GiB container.
"""
from __future__ import annotations

import csv
import gc
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.signal import oaconvolve

TRAINING_BAND_NAMES: Tuple[str, ...] = (
    "mag_anomaly_deviation",
    "mag_reduced_to_pole",
    "tmi_horizontal_gradient",
    "geodetic_second_invariant",
    "iso_gravity_slope",
    "tilt_angle_total_curvature",
    "geodetic_shear_rate",
    "geodetic_dilatation_rate",
    "tmi_vertical_gradient",
    "distance_to_earthquake",
    "iso_gravity_vertical_gradient",
    "detrended_elevation",
    "iso_gravity_anomaly",
    "total_magnetic_intensity",
    "depth_to_basement",
    "earthquake_density",
    "conductivity_surface",
    "iso_gravity_horizontal_gradient",
    "detrended_elevation_slope",
)

CORE_PHYSICAL_CHANNEL_NAMES: Tuple[str, ...] = (
    "z_mag_anomaly_deviation",
    "z_mag_reduced_to_pole",
    "z_tmi_horizontal_gradient",
    "z_geodetic_second_invariant",
    "z_iso_gravity_slope",
    "z_tilt_angle_total_curvature",
    "z_geodetic_shear_rate",
    "z_geodetic_dilatation_rate",
    "z_tmi_vertical_gradient",
    "z_distance_to_earthquake",
    "z_iso_gravity_vertical_gradient",
    "z_detrended_elevation",
    "z_iso_gravity_anomaly",
    "z_total_magnetic_intensity",
    "z_depth_to_basement",
    "z_earthquake_density",
    "z_conductivity_surface",
    "z_iso_gravity_horizontal_gradient",
    "z_detrended_elevation_slope",
    "grad_mag_reduced_to_pole",
    "grad_tilt_angle_total_curvature",
    "grad_detrended_elevation",
    "grad_iso_gravity_anomaly",
    "grad_total_magnetic_intensity",
    "grad_depth_to_basement",
    "grad_conductivity_surface",
    "grad_detrended_elevation_slope",
    "lap_tilt_angle_total_curvature",
    "lap_detrended_elevation",
    "lap_iso_gravity_anomaly",
    "lap_total_magnetic_intensity",
    "lap_depth_to_basement",
    "lap_conductivity_surface",
    "ridge_mag_reduced_to_pole",
    "ridge_tilt_angle_total_curvature",
    "ridge_detrended_elevation",
    "ridge_iso_gravity_anomaly",
    "ridge_total_magnetic_intensity",
    "ridge_depth_to_basement",
    "ridge_conductivity_surface",
    "ridge_detrended_elevation_slope",
    "std5_tilt_angle_total_curvature",
    "std5_detrended_elevation",
    "std5_total_magnetic_intensity",
    "std5_conductivity_surface",
    "x_couple_tmi_dem",
    "x_couple_tmi_grav",
    "x_ridge_dem_slope",
    "x_strain_transtension",
    "geotherm_vent_plume_s6",
    "geotherm_vent_plume_s18",
    "geotherm_reservoir_enthalpy",
    "geotherm_claycap_conduit",
    "rad_k_metasomatism",
    "rad_u_redox_halo",
    "rad_tc_grad",
    "mag_shallow_residual",
    "mag_shallow_ridge",
    "lidar_relief_norm_scarp",
    "lidar_scarp_coherence",
)

H87_NOVEL_PHYSICAL_NAMES: Tuple[str, ...] = (
    "cmgep_edge_persist",
    "cmgep_orient_cos2",
    "strain_curv_coinc",
    "transtension_scarp_lock",
    "cond_base_pot_corrob",
    "basement_flexure_step",
    "seismic_strain_aniso",
    "vent_enthalpy_alteration_conduit",
)

PHYSICAL_CHANNEL_NAMES: Tuple[str, ...] = CORE_PHYSICAL_CHANNEL_NAMES + H87_NOVEL_PHYSICAL_NAMES

STRUCTURAL_NETWORK_NAMES: Tuple[str, ...] = (
    "ns_logdist",
    "ns_den4",
    "ns_den12",
    "ns_den32",
    "ns_cont",
    "ns_gap",
    "ns_sib",
    "ns_cont_max",
    "ns_sib_max",
    "ns_coh",
    "net_beam_short",
    "net_beam_med",
    "net_beam_long",
    "net_bridge_med",
    "net_bridge_long",
    "net_tip_ray",
    "net_ann_near",
    "net_ann_far",
)

COUPLING_INTERACTION_NAMES: Tuple[str, ...] = (
    "coup_cmgep_cont",
    "coup_vent_tip",
    "coup_condbase_gap",
    "coup_straincurv_sib",
    "coup_lidar_bridge",
    "coup_seism_tip",
)

STRUCT8 = np.ones((3, 3), dtype=bool)
N_STRIKE_BINS = 12
R_KERNEL = 25
FORBIDDEN_POINT_COLUMNS = frozenset({"dist_known_fault_px", "known_fault", "label"})


def physical_channel_names() -> List[str]:
    return list(PHYSICAL_CHANNEL_NAMES)


def all_channel_names() -> List[str]:
    return physical_channel_names() + list(STRUCTURAL_NETWORK_NAMES) + list(COUPLING_INTERACTION_NAMES)


def _robust_z_flat(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float32)
    fin = np.isfinite(v)
    if not fin.any():
        return np.zeros_like(v, dtype=np.float32)
    med = float(np.median(v[fin]))
    mad = float(np.median(np.abs(v[fin] - med)))
    scale = max(1.4826 * mad, float(np.std(v[fin])), 1e-6)
    out = np.where(fin, (v - med) / scale, 0.0)
    return np.clip(out, -8.0, 8.0).astype(np.float32)


def _fill_band(arr: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    out = arr.astype(np.float32, copy=True)
    bad = ~np.isfinite(out) | (np.abs(out) > 1e20)
    valid_fp = footprint & ~bad
    med = float(np.median(out[valid_fp])) if valid_fp.any() else 0.0
    out[bad] = med
    out[~footprint] = med
    return out


def _grad_mag(arr: np.ndarray) -> np.ndarray:
    gy = ndi.sobel(arr, axis=0) * 0.125
    gx = ndi.sobel(arr, axis=1) * 0.125
    out = np.hypot(gx, gy).astype(np.float32)
    del gy, gx
    return out


def _hessian_ridge(arr: np.ndarray, sigma: float = 1.8) -> np.ndarray:
    s = ndi.gaussian_filter(arr.astype(np.float32), sigma=sigma)
    gy = ndi.sobel(s, axis=0) * 0.125
    gx = ndi.sobel(s, axis=1) * 0.125
    del s
    gyy = ndi.sobel(gy, axis=0) * 0.125
    gyx = ndi.sobel(gy, axis=1) * 0.125
    del gy
    gxy = ndi.sobel(gx, axis=0) * 0.125
    gxx = ndi.sobel(gx, axis=1) * 0.125
    del gx
    b = 0.5 * (gxy + gyx)
    del gxy, gyx
    tr = gxx + gyy
    det = np.hypot(0.5 * (gxx - gyy), b)
    del gxx, gyy, b
    lam_min = 0.5 * tr - det
    del tr, det
    return np.maximum(-lam_min * (sigma * sigma), 0.0).astype(np.float32)


def _local_std5(arr: np.ndarray) -> np.ndarray:
    a = arr.astype(np.float32)
    m1 = ndi.uniform_filter(a, size=5)
    m2 = ndi.uniform_filter(a * a, size=5)
    out = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)).astype(np.float32)
    del m1, m2
    return out


def _structure_tensor_fp(
    arr: np.ndarray, footprint: np.ndarray, sigma_grad: float, sigma_int: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return `(gmag_fp, cos2_fp, sin2_fp, coh_fp)` strictly on `footprint` (`1D float32` vectors)
    so 2D temporaries are immediately freed.
    """
    sm = ndi.gaussian_filter(arr.astype(np.float32), sigma=sigma_grad)
    gy = ndi.sobel(sm, axis=0) * 0.125
    gx = ndi.sobel(sm, axis=1) * 0.125
    del sm
    gmag_fp = np.hypot(gx[footprint], gy[footprint]).astype(np.float32)
    jxx = ndi.gaussian_filter(gx * gx, sigma=sigma_int)[footprint]
    jyy = ndi.gaussian_filter(gy * gy, sigma=sigma_int)[footprint]
    jxy = ndi.gaussian_filter(gx * gy, sigma=sigma_int)[footprint]
    del gx, gy
    tr = jxx + jyy + 1e-12
    dx = jxx - jyy
    del jxx, jyy
    dy = 2.0 * jxy
    del jxy
    aniso = np.hypot(dx, dy)
    coh_fp = np.clip(aniso / tr, 0.0, 1.0).astype(np.float32)
    cos2_fp = (dx / (aniso + 1e-12)).astype(np.float32)
    sin2_fp = (dy / (aniso + 1e-12)).astype(np.float32)
    del tr, dx, dy, aniso
    return gmag_fp, cos2_fp, sin2_fp, coh_fp


def _rasterize_geothermal_and_vents(
    raw_dir: Path, shape: Tuple[int, int], transform, footprint: np.ndarray
) -> Dict[str, np.ndarray]:
    H, W = shape
    x0 = float(transform.c)
    dx = float(transform.a)
    y0 = float(transform.f)
    dy = float(transform.e)

    temp_grid = np.zeros((H, W), dtype=np.float32)
    diseq_grid = np.zeros((H, W), dtype=np.float32)
    enthalpy_grid = np.zeros((H, W), dtype=np.float32)

    ws_path = raw_dir / "external" / "gdr_wellspring_in_footprint.csv"
    with ws_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ux = float(row["utm_e"])
                uy = float(row["utm_n"])
                col = int((ux - x0) / dx)
                r = int((uy - y0) / dy)
            except (KeyError, ValueError):
                try:
                    r = int(float(row["row"]))
                    col = int(float(row["col"]))
                except (KeyError, ValueError):
                    continue
            if not (0 <= r < H and 0 <= col < W):
                continue

            tsurf = 15.0
            for tk in ("temp_c", "Temp_C"):
                if row.get(tk, "").strip():
                    try:
                        v = float(row[tk])
                        if np.isfinite(v) and 10.0 < v < 400.0:
                            tsurf = v
                            ex = max(0.0, v - 15.0)
                            if ex > temp_grid[r, col]:
                                temp_grid[r, col] = ex
                    except ValueError:
                        pass

            qmax = 0.0
            for gk in (
                "gt_quartz_c",
                "gt_chalcedony_c",
                "gt_na_k_ca_c",
                "geothermquartz_c",
                "geothermchalc_c",
                "geothermcat_c",
            ):
                if row.get(gk, "").strip():
                    try:
                        gv = float(row[gk])
                        if np.isfinite(gv) and 20.0 < gv < 450.0:
                            qmax = max(qmax, gv)
                    except ValueError:
                        pass
            if qmax > 25.0:
                ent = qmax - 25.0
                if ent > enthalpy_grid[r, col]:
                    enthalpy_grid[r, col] = ent
                dq = max(0.0, qmax - max(tsurf, 15.0)) + 0.6 * max(0.0, tsurf - 20.0)
                if dq > diseq_grid[r, col]:
                    diseq_grid[r, col] = dq

    vent_grid = np.zeros((H, W), dtype=np.float32)
    vv_path = raw_dir / "external" / "gdr_volcanic_vents_in_footprint.csv"
    if vv_path.exists():
        with vv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ux = float(row["utm_e"])
                    uy = float(row["utm_n"])
                    col = int((ux - x0) / dx)
                    r = int((uy - y0) / dy)
                except (KeyError, ValueError):
                    try:
                        r = int(float(row["row"]))
                        col = int(float(row["col"]))
                    except (KeyError, ValueError):
                        continue
                if 0 <= r < H and 0 <= col < W:
                    vent_grid[r, col] += 1.0

    p_s6 = _robust_z_flat(np.log1p(ndi.gaussian_filter(temp_grid + 0.3 * diseq_grid, sigma=6.0)[footprint]))
    p_s18 = _robust_z_flat(np.log1p(ndi.gaussian_filter(temp_grid + 0.5 * diseq_grid, sigma=18.0)[footprint]))
    ent_s12 = _robust_z_flat(
        np.log1p(
            (
                ndi.gaussian_filter(enthalpy_grid, sigma=12.0)
                + 0.4 * ndi.gaussian_filter(diseq_grid, sigma=10.0)
                + 2.0 * ndi.gaussian_filter(vent_grid, sigma=20.0)
            )[footprint]
        )
    )
    diseq_s10 = _robust_z_flat(np.log1p(ndi.gaussian_filter(diseq_grid, sigma=10.0)[footprint]))
    del temp_grid, enthalpy_grid, diseq_grid, vent_grid
    gc.collect()
    return {
        "geotherm_vent_plume_s6": p_s6,
        "geotherm_vent_plume_s18": p_s18,
        "geotherm_reservoir_enthalpy": ent_s12,
        "geotherm_diseq_s10": diseq_s10,
    }


def load_or_build_rowmajor_f16(
    raw_dir: Path, footprint: np.ndarray, proc_dir: Path
) -> Tuple[List[str], np.ndarray]:
    """Return `(names, X_rm_f16)` of shape `(n_fp, 68)` built directly from `raw_dir` with <400 MB peak RAM."""
    names = physical_channel_names()
    n_fp = int(footprint.sum())
    n_ch = len(names)
    proc_dir.mkdir(parents=True, exist_ok=True)
    rm_path = proc_dir / "h87_phys_rm.f16.npy"
    meta_path = proc_dir / "h87_phys_rm.names.txt"

    if rm_path.exists() and meta_path.exists():
        cached_names = [line.strip() for line in meta_path.read_text().splitlines() if line.strip()]
        if cached_names == names:
            mm = np.load(rm_path, mmap_mode="r")
            if mm.shape == (n_fp, n_ch):
                return names, mm

    mm_rm = np.lib.format.open_memmap(rm_path, mode="w+", dtype=np.float16, shape=(n_fp, n_ch))
    col_idx = {nm: i for i, nm in enumerate(names)}
    band_idx_map = {nm: i for i, nm in enumerate(TRAINING_BAND_NAMES, start=1)}

    def write_col(name: str, vec_fp: np.ndarray) -> None:
        mm_rm[:, col_idx[name]] = _robust_z_flat(vec_fp).astype(np.float16)

    grad_set = {
        "mag_reduced_to_pole",
        "tilt_angle_total_curvature",
        "detrended_elevation",
        "iso_gravity_anomaly",
        "total_magnetic_intensity",
        "depth_to_basement",
        "conductivity_surface",
        "detrended_elevation_slope",
    }
    lap_set = {
        "tilt_angle_total_curvature",
        "detrended_elevation",
        "iso_gravity_anomaly",
        "total_magnetic_intensity",
        "depth_to_basement",
        "conductivity_surface",
    }
    ridge_set = grad_set
    std5_set = {
        "tilt_angle_total_curvature",
        "detrended_elevation",
        "total_magnetic_intensity",
        "conductivity_surface",
    }

    tf_path = raw_dir / "training_features.tif"
    with rasterio.open(tf_path) as src:
        transform = src.transform
        shape = (src.height, src.width)

        # Pass 1: single-band z, grad, lap, ridge, std5 one band at a time
        for b_idx, b_name in enumerate(TRAINING_BAND_NAMES, start=1):
            arr = _fill_band(src.read(b_idx), footprint)
            write_col(f"z_{b_name}", arr[footprint])

            if b_name in grad_set:
                g = _grad_mag(arr)
                write_col(f"grad_{b_name}", np.log1p(g[footprint]))
                del g

            if b_name in lap_set:
                lap = ndi.laplace(ndi.gaussian_filter(arr, sigma=1.2)).astype(np.float32)
                write_col(f"lap_{b_name}", lap[footprint])
                del lap

            if b_name in ridge_set:
                rdg = _hessian_ridge(arr, sigma=1.8)
                write_col(f"ridge_{b_name}", np.log1p(rdg[footprint]))
                del rdg

            if b_name in std5_set:
                s5 = _local_std5(arr)
                write_col(f"std5_{b_name}", np.log1p(s5[footprint]))
                del s5

            del arr
            gc.collect()

        mm_rm.flush()

        # Pass 2: cross-physics couplings (read from already-computed columns in mm_rm where possible!)
        z_tmi_hg = mm_rm[:, col_idx["z_tmi_horizontal_gradient"]].astype(np.float32)
        z_dem_sl = mm_rm[:, col_idx["z_detrended_elevation_slope"]].astype(np.float32)
        z_grav_hg = mm_rm[:, col_idx["z_iso_gravity_horizontal_gradient"]].astype(np.float32)
        z_rdg_sl = mm_rm[:, col_idx["ridge_detrended_elevation_slope"]].astype(np.float32)
        write_col("x_couple_tmi_dem", z_tmi_hg * z_dem_sl)
        write_col("x_couple_tmi_grav", z_tmi_hg * z_grav_hg)
        write_col("x_ridge_dem_slope", z_rdg_sl * z_dem_sl)
        del z_tmi_hg, z_dem_sl

        z_sh = mm_rm[:, col_idx["z_geodetic_shear_rate"]].astype(np.float32)
        z_dil = mm_rm[:, col_idx["z_geodetic_dilatation_rate"]].astype(np.float32)
        z_inv = mm_rm[:, col_idx["z_geodetic_second_invariant"]].astype(np.float32)
        x_transt = 0.45 * z_sh + 0.35 * np.maximum(z_dil, 0.0) + 0.20 * z_inv
        write_col("x_strain_transtension", x_transt)
        del z_dil, z_inv

        # External Geothermal & Volcanic Vents
        gt = _rasterize_geothermal_and_vents(raw_dir, shape, transform, footprint)
        write_col("geotherm_vent_plume_s6", gt["geotherm_vent_plume_s6"])
        write_col("geotherm_vent_plume_s18", gt["geotherm_vent_plume_s18"])
        write_col("geotherm_reservoir_enthalpy", gt["geotherm_reservoir_enthalpy"])
        z_cond = mm_rm[:, col_idx["z_conductivity_surface"]].astype(np.float32)
        z_base_g = mm_rm[:, col_idx["grad_depth_to_basement"]].astype(np.float32)
        write_col("geotherm_claycap_conduit", 0.45 * z_cond + 0.35 * gt["geotherm_vent_plume_s6"] + 0.20 * z_base_g)
        del z_base_g

        # External GeoDAWN Radiometric & Upward-Continued Magnetic Extensions
        with rasterio.open(raw_dir / "external" / "geodawn_rad_u8.tif") as src_rad:
            rad_k_fp = _robust_z_flat(_fill_band(src_rad.read(1), footprint)[footprint])
            rad_th_fp = _robust_z_flat(_fill_band(src_rad.read(2), footprint)[footprint])
            rad_u_fp = _robust_z_flat(_fill_band(src_rad.read(3), footprint)[footprint])
            rad_tc = _fill_band(src_rad.read(4), footprint)
            tc_grad_fp = np.log1p(_grad_mag(rad_tc)[footprint])
            del rad_tc
        with rasterio.open(raw_dir / "external" / "geodawn_extensions_u8.tif") as src_ext:
            ext_thk_fp = _robust_z_flat(_fill_band(src_ext.read(1), footprint)[footprint])
            ext_uk_fp = _robust_z_flat(_fill_band(src_ext.read(2), footprint)[footprint])
            ext_uth_fp = _robust_z_flat(_fill_band(src_ext.read(3), footprint)[footprint])
            ext_up150_fp = _robust_z_flat(_fill_band(src_ext.read(4), footprint)[footprint])

        k_meta = rad_k_fp - 0.65 * rad_th_fp - 0.35 * ext_thk_fp
        u_redox = 0.5 * rad_u_fp + 0.25 * ext_uk_fp + 0.25 * ext_uth_fp
        write_col("rad_k_metasomatism", k_meta)
        write_col("rad_u_redox_halo", u_redox)
        write_col("rad_tc_grad", tc_grad_fp)
        del rad_k_fp, rad_th_fp, rad_u_fp, ext_thk_fp, ext_uk_fp, ext_uth_fp, tc_grad_fp, u_redox

        # Shallow magnetic residual (TMI - TMI_up150)
        z_tmi_fp = mm_rm[:, col_idx["z_total_magnetic_intensity"]].astype(np.float32)
        mag_res_fp = z_tmi_fp - ext_up150_fp
        write_col("mag_shallow_residual", mag_res_fp)
        del z_tmi_fp, ext_up150_fp
        mag_res_2d = np.zeros(shape, dtype=np.float32)
        mag_res_2d[footprint] = mag_res_fp
        mag_res_rdg = _hessian_ridge(mag_res_2d, sigma=1.6)
        write_col("mag_shallow_ridge", np.log1p(mag_res_rdg[footprint]))
        del mag_res_2d, mag_res_rdg
        gc.collect()

        # External USGS 3DEP 1 m LiDAR Scarp features
        with rasterio.open(raw_dir / "external" / "lidar_scarp_features_u8.tif") as src_lid:
            lid_scarp = src_lid.read(1).astype(np.float32)
            lid_step = src_lid.read(3).astype(np.float32)
            lid_relief = src_lid.read(9).astype(np.float32)
            lid_coh = src_lid.read(10).astype(np.float32)
            lid_cov = (src_lid.read(12) > 0) & footprint

        cov_fp = lid_cov[footprint]
        scarp_raw_cov = (0.6 * lid_scarp[lid_cov] + 0.4 * lid_step[lid_cov]) / (lid_relief[lid_cov] + 18.0)
        z_scarp_cov = _robust_z_flat(scarp_raw_cov)
        scarp_fp = _robust_z_flat(z_rdg_sl).copy()
        scarp_fp[cov_fp] = 0.75 * z_scarp_cov + 0.25 * scarp_fp[cov_fp]
        write_col("lidar_relief_norm_scarp", scarp_fp)

        coh_fp = np.zeros(n_fp, dtype=np.float32)
        coh_fp[cov_fp] = _robust_z_flat(lid_coh[lid_cov])
        write_col("lidar_scarp_coherence", coh_fp)
        del lid_scarp, lid_step, lid_relief, lid_coh, lid_cov, cov_fp, scarp_raw_cov, z_scarp_cov, coh_fp, z_rdg_sl
        gc.collect()

        # =====================================================================
        # 8 NOVEL H87-CMGEP HYPOTHESIS CHANNELS (streamed scale-by-scale)
        # =====================================================================
        # H87-1: Cross-Scale Paired Magnetic-Gravity Edge Persistence (cmgep_edge_persist, cmgep_orient_cos2)
        mag_rtp = _fill_band(src.read(band_idx_map["mag_reduced_to_pole"]), footprint)
        tmi = _fill_band(src.read(band_idx_map["total_magnetic_intensity"]), footprint)
        mag_comp = 0.6 * mag_rtp + 0.4 * tmi
        del mag_rtp, tmi
        grav_comp = _fill_band(src.read(band_idx_map["iso_gravity_anomaly"]), footprint)

        gm1, mc2_1, ms2_1, mcoh1 = _structure_tensor_fp(mag_comp, footprint, 1.5, 2.5)
        gg1, gc2_1, gs2_1, gcoh1 = _structure_tensor_fp(grav_comp, footprint, 1.5, 2.5)
        cross_align_1 = (mc2_1 * gc2_1 + ms2_1 * gs2_1) * np.sqrt(mcoh1 * gcoh1)
        del mcoh1, gcoh1

        gm4, mc2_4, ms2_4, mcoh4 = _structure_tensor_fp(mag_comp, footprint, 4.0, 6.0)
        gg4, gc2_4, gs2_4, gcoh4 = _structure_tensor_fp(grav_comp, footprint, 4.0, 6.0)
        cross_align_4 = (mc2_4 * gc2_4 + ms2_4 * gs2_4) * np.sqrt(mcoh4 * gcoh4)
        orient_cos2_fp = 0.55 * cross_align_1 + 0.45 * cross_align_4
        write_col("cmgep_orient_cos2", orient_cos2_fp)
        del cross_align_1, cross_align_4, mcoh4, gcoh4, orient_cos2_fp

        gm8, mc2_8, ms2_8, _ = _structure_tensor_fp(mag_comp, footprint, 8.0, 11.0)
        gg8, gc2_8, gs2_8, _ = _structure_tensor_fp(grav_comp, footprint, 8.0, 11.0)
        del mag_comp, grav_comp

        mag_scale_align = np.maximum(0.0, mc2_1 * mc2_8 + ms2_1 * ms2_8)
        grav_scale_align = np.maximum(0.0, gc2_1 * gc2_8 + gs2_1 * gs2_8)
        del mc2_1, ms2_1, mc2_8, ms2_8, gc2_1, gs2_1, gc2_8, gs2_8

        mag_persist = np.cbrt(np.log1p(gm1) * np.log1p(gm4) * np.log1p(gm8)) * (0.3 + 0.7 * mag_scale_align)
        grav_persist = np.cbrt(np.log1p(gg1) * np.log1p(gg4) * np.log1p(gg8)) * (0.3 + 0.7 * grav_scale_align)
        del gm1, gm4, gm8, gg1, gg4, gg8, mag_scale_align, grav_scale_align

        paired_persist_fp = np.sqrt(
            np.maximum(_robust_z_flat(mag_persist) + 2.5, 0.0)
            * np.maximum(_robust_z_flat(grav_persist) + 2.5, 0.0)
        )
        write_col("cmgep_edge_persist", paired_persist_fp)
        del mag_persist, grav_persist, paired_persist_fp
        gc.collect()

        # H87-2: Geodetic Strain-Curvature Coincidence (strain_curv_coinc, transtension_scarp_lock)
        dem = _fill_band(src.read(band_idx_map["detrended_elevation"]), footprint)
        lap_z_fine = np.abs(mm_rm[:, col_idx["lap_detrended_elevation"]].astype(np.float32))
        lap_z_med = np.abs(ndi.laplace(ndi.gaussian_filter(dem, sigma=4.0))[footprint])
        del dem
        curv_multiscale = 0.6 * _robust_z_flat(np.log1p(lap_z_fine)) + 0.4 * _robust_z_flat(np.log1p(lap_z_med))
        del lap_z_fine, lap_z_med
        strain_pos = np.maximum(x_transt + 1.5, 0.0)
        write_col("strain_curv_coinc", curv_multiscale * strain_pos)
        write_col("transtension_scarp_lock", np.maximum(x_transt, 0.0) * np.maximum(scarp_fp, 0.0))
        del curv_multiscale, strain_pos, x_transt, scarp_fp
        gc.collect()

        # H87-3: Conductive-Base Boundary with Potential-Field Corroboration (cond_base_pot_corrob, basement_flexure_step)
        base_2d = _fill_band(src.read(band_idx_map["depth_to_basement"]), footprint)
        cond_2d = _fill_band(src.read(band_idx_map["conductivity_surface"]), footprint)
        gb, bc2, bs2, bcoh = _structure_tensor_fp(base_2d, footprint, 2.0, 4.0)
        gc_m, _, _, _ = _structure_tensor_fp(cond_2d, footprint, 2.0, 4.0)
        del cond_2d
        pot_align = np.maximum(0.0, 0.5 * (bc2 * mc2_4 + bs2 * ms2_4) + 0.5 * (bc2 * gc2_4 + bs2 * gs2_4))
        cond_base_edge = (0.6 * _robust_z_flat(np.log1p(gb)) + 0.4 * _robust_z_flat(np.log1p(gc_m))) * (
            0.35 + 0.65 * pot_align * bcoh
        )
        write_col("cond_base_pot_corrob", cond_base_edge)
        del gb, bc2, bs2, bcoh, gc_m, pot_align, cond_base_edge, mc2_4, ms2_4, gc2_4, gs2_4

        lap_base = ndi.laplace(ndi.gaussian_filter(base_2d, sigma=1.2)).astype(np.float32)
        del base_2d
        biharm_base = np.abs(ndi.laplace(lap_base))[footprint]
        del lap_base
        write_col("basement_flexure_step", np.log1p(biharm_base) * (0.5 + 0.5 * np.maximum(z_grav_hg, 0.0)))
        del biharm_base, z_grav_hg
        gc.collect()

        # H87-4: Anisotropic Seismic-Density / Strain Fabric (seismic_strain_aniso)
        dist_eq = _fill_band(src.read(band_idx_map["distance_to_earthquake"]), footprint)
        dens_eq = _fill_band(src.read(band_idx_map["earthquake_density"]), footprint)
        eq_comp = np.log1p(np.maximum(dist_eq, 0.0)) + 0.7 * np.log1p(np.maximum(dens_eq, 0.0))
        del dist_eq, dens_eq
        _, _, _, eqcoh = _structure_tensor_fp(eq_comp, footprint, 2.5, 5.5)
        seism_aniso_fp = (_robust_z_flat(eq_comp[footprint]) + 2.0) * eqcoh * np.maximum(z_sh + 1.5, 0.0)
        write_col("seismic_strain_aniso", seism_aniso_fp)
        del eq_comp, eqcoh, seism_aniso_fp, z_sh
        gc.collect()

        # H87-5: Hydrothermal Vent K-Metasomatism & Silica Geothermometer Plume along Demagnetized Conduits
        demag_pos = np.maximum(-_robust_z_flat(mag_res_fp), 0.0)
        k_meta_pos = np.maximum(k_meta + 1.0, 0.0)
        enthalpy_pos = np.maximum(gt["geotherm_reservoir_enthalpy"] + 0.6 * gt["geotherm_diseq_s10"] + 1.2, 0.0)
        vent_conduit_fp = enthalpy_pos * (0.45 * k_meta_pos + 0.35 * demag_pos + 0.20 * np.maximum(z_cond + 1.0, 0.0))
        write_col("vent_enthalpy_alteration_conduit", vent_conduit_fp)
        del demag_pos, k_meta_pos, enthalpy_pos, vent_conduit_fp, mag_res_fp, k_meta, gt, z_cond

    mm_rm.flush()
    meta_path.write_text("\n".join(names) + "\n", encoding="utf-8")
    del mm_rm
    gc.collect()
    return names, np.load(rm_path, mmap_mode="r")


def build_cmgep_unsupervised_surface(
    X_phys_rm: np.ndarray, phys_names: List[str], footprint: np.ndarray
) -> np.ndarray:
    idx = {n: i for i, n in enumerate(phys_names)}
    score_fp = (
        0.26 * X_phys_rm[:, idx["cmgep_edge_persist"]].astype(np.float32)
        + 0.10 * X_phys_rm[:, idx["cmgep_orient_cos2"]].astype(np.float32)
        + 0.16 * X_phys_rm[:, idx["strain_curv_coinc"]].astype(np.float32)
        + 0.14 * X_phys_rm[:, idx["cond_base_pot_corrob"]].astype(np.float32)
        + 0.12 * X_phys_rm[:, idx["vent_enthalpy_alteration_conduit"]].astype(np.float32)
        + 0.14 * X_phys_rm[:, idx["lidar_relief_norm_scarp"]].astype(np.float32)
        + 0.08 * X_phys_rm[:, idx["x_ridge_dem_slope"]].astype(np.float32)
    )
    z = _robust_z_flat(score_fp)
    p_fp = (1.0 / (1.0 + np.exp(-0.85 * z))).astype(np.float32)
    out = np.zeros(footprint.shape, dtype=np.float32)
    out[footprint] = p_fp
    return out


def _strike_field(mask: np.ndarray) -> np.ndarray:
    i = ndi.gaussian_filter(mask.astype(np.float32), 1.0)
    gy = ndi.sobel(i, axis=0)
    gx = ndi.sobel(i, axis=1)
    del i
    jxx = ndi.gaussian_filter(gx * gx, 3.0)
    jyy = ndi.gaussian_filter(gy * gy, 3.0)
    jxy = ndi.gaussian_filter(gx * gy, 3.0)
    del gx, gy
    phi = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    del jxx, jyy, jxy
    theta = np.mod(phi + np.pi / 2.0, np.pi)
    del phi
    return theta.astype(np.float32)


def _oriented_kernels(theta: float, r: int = R_KERNEL) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    dy, dx = np.mgrid[-r : r + 1, -r : r + 1].astype(np.float32)
    ux, uy = np.cos(theta), np.sin(theta)
    along = dx * ux + dy * uy
    across = -dx * uy + dy * ux
    lat = np.exp(-0.5 * (across / 1.5) ** 2) * np.exp(-np.abs(along) / 12.0) * (np.abs(along) <= 25)
    kf = (lat * (along > 0.5)).astype(np.float32)
    kb = (lat * (along < -0.5)).astype(np.float32)
    ks = ((np.abs(across) >= 4) & (np.abs(across) <= 20) & (np.abs(along) <= 15)).astype(np.float32)
    ks *= np.exp(-0.5 * (along / 8.0) ** 2).astype(np.float32)
    kf /= kf.sum()
    kb /= kb.sum()
    ks /= ks.sum()
    return kf, kb, ks


def compute_structural_and_coupling_fp(
    visible_mask: np.ndarray,
    footprint: np.ndarray,
    X_phys_rm: np.ndarray,
    phys_names: List[str],
    cache_path: Path | None = None,
) -> np.ndarray:
    """Stream all 18 structural-relay and 6 H87 physics-coupling channels directly into a `(n_fp, 24)`
    `float16` matrix so 2D `float32` temporaries are freed immediately after each step.
    """
    n_fp = int(footprint.sum())
    n_cols = len(STRUCTURAL_NETWORK_NAMES) + len(COUPLING_INTERACTION_NAMES)
    if cache_path is not None and cache_path.exists():
        mm = np.load(cache_path, mmap_mode="r")
        if mm.shape == (n_fp, n_cols):
            return mm

    m = np.asarray(visible_mask, dtype=bool) & np.asarray(footprint, dtype=bool)
    fp = np.asarray(footprint, dtype=bool)
    mat = np.empty((n_fp, n_cols), dtype=np.float16)
    s_idx = {nm: i for i, nm in enumerate(STRUCTURAL_NETWORK_NAMES)}

    # 1. Distance and densities
    d_vis = ndi.distance_transform_edt(~m)
    mat[:, s_idx["ns_logdist"]] = np.log1p(d_vis[fp]).astype(np.float16)
    del d_vis
    mf = m.astype(np.float32)
    for s in (4, 12, 32):
        den_s = ndi.gaussian_filter(mf, float(s))
        mat[:, s_idx[f"ns_den{s}"]] = den_s[fp].astype(np.float16)
        del den_s

    # 2. Strike-binned continuation, gap, sibling, coherence
    theta = _strike_field(m)
    bins = np.minimum((theta / np.pi * N_STRIKE_BINS).astype(np.int16), N_STRIKE_BINS - 1)
    cont = np.zeros(m.shape, np.float32)
    gap = np.zeros(m.shape, np.float32)
    sib = np.zeros(m.shape, np.float32)
    cont_max = np.zeros(m.shape, np.float32)
    sib_max = np.zeros(m.shape, np.float32)
    for k in range(N_STRIKE_BINS):
        mk = (m & (bins == k)).astype(np.float32)
        if not mk.any():
            continue
        kf, kb, ks = _oriented_kernels((k + 0.5) * np.pi / N_STRIKE_BINS)
        f = np.maximum(oaconvolve(mk, kf, mode="same"), 0.0).astype(np.float32)
        b = np.maximum(oaconvolve(mk, kb, mode="same"), 0.0).astype(np.float32)
        s = np.maximum(oaconvolve(mk, ks, mode="same"), 0.0).astype(np.float32)
        c = f + b
        cont += c
        gap += np.sqrt(f * b)
        sib += s
        np.maximum(cont_max, c, out=cont_max)
        np.maximum(sib_max, s, out=sib_max)
        del f, b, s, c, mk

    mat[:, s_idx["ns_cont"]] = cont[fp].astype(np.float16)
    mat[:, s_idx["ns_gap"]] = gap[fp].astype(np.float16)
    mat[:, s_idx["ns_sib"]] = sib[fp].astype(np.float16)
    mat[:, s_idx["ns_cont_max"]] = cont_max[fp].astype(np.float16)
    mat[:, s_idx["ns_sib_max"]] = sib_max[fp].astype(np.float16)
    del cont, gap, sib, cont_max, sib_max, bins

    c2 = ndi.gaussian_filter(mf * np.cos(2 * theta), 20.0)
    s2 = ndi.gaussian_filter(mf * np.sin(2 * theta), 20.0)
    del theta
    den = ndi.gaussian_filter(mf, 20.0)
    coh = np.hypot(c2, s2) / (den + 1e-6) * (den > 1e-4)
    mat[:, s_idx["ns_coh"]] = coh[fp].astype(np.float16)
    del c2, s2, den, coh
    gc.collect()

    # 3. Oriented hollow relay beams, bridges, tip rays, and annuli
    gy = ndi.sobel(mf, axis=0)
    gx = ndi.sobel(mf, axis=1)
    strike = np.arctan2(-gx, gy)
    del gy, gx
    nb_count = ndi.convolve(mf, np.ones((3, 3), dtype=np.float32), mode="constant", cval=0.0)
    tips = m & (nb_count >= 1.5) & (nb_count <= 3.5)
    del nb_count

    beam_short = np.zeros(m.shape, dtype=np.float32)
    beam_med = np.zeros(m.shape, dtype=np.float32)
    beam_long = np.zeros(m.shape, dtype=np.float32)
    bridge_med = np.zeros(m.shape, dtype=np.float32)
    bridge_long = np.zeros(m.shape, dtype=np.float32)
    tip_ray = np.zeros(m.shape, dtype=np.float32)

    for k in range(8):
        ang = k * (np.pi / 8.0)
        align = np.abs(np.cos(strike - ang))
        oriented = np.where(m & (align > 0.78), mf, 0.0).astype(np.float32)
        oriented_tips = np.where(tips & (align > 0.72), 1.0, 0.0).astype(np.float32)
        del align
        dy, dx = np.sin(ang), np.cos(ang)

        f_s = np.zeros(m.shape, dtype=np.float32)
        b_s = np.zeros(m.shape, dtype=np.float32)
        f_m = np.zeros(m.shape, dtype=np.float32)
        b_m = np.zeros(m.shape, dtype=np.float32)
        f_l = np.zeros(m.shape, dtype=np.float32)
        b_l = np.zeros(m.shape, dtype=np.float32)
        t_r = np.zeros(m.shape, dtype=np.float32)

        for s in (4, 6, 8, 10, 12, 16, 20, 26, 32, 40):
            r_off = int(round(s * dy))
            c_off = int(round(s * dx))
            sh_f = np.roll(oriented, (r_off, c_off), axis=(0, 1))
            sh_b = np.roll(oriented, (-r_off, -c_off), axis=(0, 1))
            if s <= 12:
                ws = float(np.exp(-s / 8.0))
                f_s += ws * sh_f
                b_s += ws * sh_b
            if s <= 26:
                wm = float(np.exp(-s / 16.0))
                f_m += wm * sh_f
                b_m += wm * sh_b
            wl = float(np.exp(-s / 28.0))
            f_l += wl * sh_f
            b_l += wl * sh_b
            if s <= 26:
                wt = float(np.exp(-s / 14.0))
                t_r += wt * (
                    np.roll(oriented_tips, (r_off, c_off), axis=(0, 1))
                    + np.roll(oriented_tips, (-r_off, -c_off), axis=(0, 1))
                )
            del sh_f, sh_b

        del oriented, oriented_tips
        f_s = ndi.gaussian_filter(f_s, sigma=1.2)
        b_s = ndi.gaussian_filter(b_s, sigma=1.2)
        f_m = ndi.gaussian_filter(f_m, sigma=1.8)
        b_m = ndi.gaussian_filter(b_m, sigma=1.8)
        f_l = ndi.gaussian_filter(f_l, sigma=2.5)
        b_l = ndi.gaussian_filter(b_l, sigma=2.5)
        t_r = ndi.gaussian_filter(t_r, sigma=1.8)

        np.maximum(beam_short, f_s + b_s, out=beam_short)
        np.maximum(beam_med, f_m + b_m, out=beam_med)
        np.maximum(beam_long, f_l + b_l, out=beam_long)
        np.maximum(bridge_med, np.sqrt(f_m * b_m), out=bridge_med)
        np.maximum(bridge_long, np.sqrt(f_l * b_l), out=bridge_long)
        np.maximum(tip_ray, t_r, out=tip_ray)
        del f_s, b_s, f_m, b_m, f_l, b_l, t_r

    del strike, tips
    mat[:, s_idx["net_beam_short"]] = _robust_z_flat(beam_short[fp]).astype(np.float16)
    mat[:, s_idx["net_beam_med"]] = _robust_z_flat(beam_med[fp]).astype(np.float16)
    mat[:, s_idx["net_beam_long"]] = _robust_z_flat(beam_long[fp]).astype(np.float16)
    mat[:, s_idx["net_bridge_med"]] = _robust_z_flat(bridge_med[fp]).astype(np.float16)
    mat[:, s_idx["net_bridge_long"]] = _robust_z_flat(bridge_long[fp]).astype(np.float16)
    mat[:, s_idx["net_tip_ray"]] = _robust_z_flat(tip_ray[fp]).astype(np.float16)
    del beam_short, beam_med, beam_long, bridge_med, bridge_long, tip_ray

    ann_near = np.maximum(
        0.0, ndi.gaussian_filter(mf, sigma=7.0) - 0.85 * ndi.gaussian_filter(mf, sigma=2.0)
    )
    mat[:, s_idx["net_ann_near"]] = _robust_z_flat(ann_near[fp]).astype(np.float16)
    del ann_near
    ann_far = np.maximum(
        0.0, ndi.gaussian_filter(mf, sigma=18.0) - 0.85 * ndi.gaussian_filter(mf, sigma=4.0)
    )
    mat[:, s_idx["net_ann_far"]] = _robust_z_flat(ann_far[fp]).astype(np.float16)
    del ann_far, mf, m
    gc.collect()

    # 4. 6 H87 physics-coupling channels
    cont_fp = _robust_z_flat(mat[:, s_idx["ns_cont"]].astype(np.float32))
    tip_fp = mat[:, s_idx["net_tip_ray"]].astype(np.float32)
    gap_fp = _robust_z_flat(mat[:, s_idx["ns_gap"]].astype(np.float32))
    sib_fp = _robust_z_flat(mat[:, s_idx["ns_sib"]].astype(np.float32))
    brg_fp = mat[:, s_idx["net_bridge_med"]].astype(np.float32)

    base_j = len(STRUCTURAL_NETWORK_NAMES)
    mat[:, base_j + 0] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("cmgep_edge_persist")].astype(np.float32), 0.0)
        * np.maximum(cont_fp, 0.0)
    ).astype(np.float16)
    mat[:, base_j + 1] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("vent_enthalpy_alteration_conduit")].astype(np.float32), 0.0)
        * np.maximum(tip_fp, 0.0)
    ).astype(np.float16)
    mat[:, base_j + 2] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("cond_base_pot_corrob")].astype(np.float32), 0.0)
        * np.maximum(gap_fp, 0.0)
    ).astype(np.float16)
    mat[:, base_j + 3] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("strain_curv_coinc")].astype(np.float32), 0.0)
        * np.maximum(sib_fp, 0.0)
    ).astype(np.float16)
    mat[:, base_j + 4] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("lidar_relief_norm_scarp")].astype(np.float32), 0.0)
        * np.maximum(brg_fp, 0.0)
    ).astype(np.float16)
    mat[:, base_j + 5] = _robust_z_flat(
        np.maximum(X_phys_rm[:, phys_names.index("seismic_strain_aniso")].astype(np.float32), 0.0)
        * np.maximum(tip_fp, 0.0)
    ).astype(np.float16)

    del cont_fp, tip_fp, gap_fp, sib_fp, brg_fp
    gc.collect()

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, mat)
        del mat
        gc.collect()
        return np.load(cache_path, mmap_mode="r")
    return mat


def synthetic_withhold(
    mask: np.ndarray,
    footprint: np.ndarray,
    quad: np.ndarray,
    seed: int,
    frac: float = 0.20,
    collar_px: int = 3,
) -> Tuple[np.ndarray, np.ndarray]:
    m = np.asarray(mask, dtype=bool) & np.asarray(footprint, dtype=bool)
    comp, n = ndi.label(m, STRUCT8)
    sizes = np.bincount(comp.ravel(), minlength=n + 1)
    hidden = np.zeros(m.shape, dtype=bool)
    for q in range(4):
        inq = quad == q
        cand = np.unique(comp[m & inq])
        clipped = np.unique(comp[m & ~inq])
        elig = np.setdiff1d(cand[cand > 0], clipped)
        if elig.size == 0:
            continue
        rng = np.random.default_rng(870_000 + 97 * seed + q)
        perm = rng.permutation(elig)
        cum = np.cumsum(sizes[perm])
        k = int(np.searchsorted(cum, frac * float((m & inq).sum()))) + 1
        hidden |= np.isin(comp, perm[: min(k, perm.size)]) & m
    collar = ndi.distance_transform_edt(~hidden) <= collar_px
    state = m & ~collar
    assert not (state & hidden).any()
    return hidden, state
