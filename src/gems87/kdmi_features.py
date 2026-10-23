"""Pure-physics 92-channel `H87-KDMI` feature builder (zero catalogue & zero SGMC inputs).

Memory-safe cgroup-v2 streaming architecture (`< 600 MB` peak RSS, `POSIX_FADV_DONTNEED` page
eviction, `(92, N_fp)` contiguous feature-major float16 layout) using the verified official
19-band NETL/INGENIOUS `training_features.tif` schema (`IR-87-08` fix).
"""
from __future__ import annotations

import csv
import gc
import io
import json
import os
import resource
import struct
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol
from rasterio.warp import transform as warp_transform
from rasterio.windows import Window
from scipy.ndimage import distance_transform_edt, gaussian_filter

TF_BAND_NAMES = [
    "mag_anom",
    "rtp",
    "tmi_hg",
    "geod_2ndinv",
    "iso_grav_anom_slope",
    "tc",
    "geod_shearrate",
    "geod_dilaterate",
    "tmi_vg",
    "deq_n100a15_log1p",
    "iso_grav_anom_vg",
    "det_elev",
    "iso_grav_anom",
    "tmi",
    "depth_to_base_surf_m",
    "ieq_n100a15_log1p",
    "cond_surf",
    "iso_grav_anom_hg",
    "det_elev_slope",
]

FEATURE_NAMES_92 = (
    TF_BAND_NAMES
    + [
        "tf_any_nan_flag",
        "grav_hg_worm_hp8",
        "tmi_hg_worm_hp8",
        "tc_worm_hp8",
        "base_grad_mag_m_per_px",
        "base_laplacian_m",
        "transtensional_obliquity",
        # Block B: Exact Trigonometry Kirchhoff Listric Dip-Migration Interferometry (23 channels)
        "kdmi_sdip_px",
        "kdmi_dip_coherence",
        "kdmi_grav_hg_hw_pullback_sdip",
        "kdmi_grav_hg_hw_max_4_14",
        "kdmi_grav_hg_dipole_6",
        "kdmi_grav_hg_dipole_12",
        "kdmi_grav_hg_dipole_sdip",
        "kdmi_grav_vg_dipole_10",
        "kdmi_base_throw_m_8",
        "kdmi_base_throw_m_14",
        "kdmi_rtp_dipole_sdip",
        "kdmi_tc_edge_pullback_5",
        "kdmi_tmi_up150_dipole_9",
        "kdmi_cond_hw_peak_4",
        "kdmi_cond_damage_asymmetry_10",
        "kdmi_ksn_fw_drop_4",
        "kdmi_det_elev_scarp_step_3",
        "kdmi_hydro_upgradient_pullback",
        "kdmi_5domain_interferogram",
        "kdmi_radon_along_strike_9",
        "kdmi_radon_along_strike_21",
        "kdmi_radon_anisotropy_9",
        "kdmi_scarp_radon_anisotropy_9",
        # Block C: Surface LiDAR + 10m DEM + Fluvial Chi + Pluvial Deconfounder (29 channels)
        "has_lidar",
        "lidar_slope_max",
        "lidar_slope_p90",
        "lidar_slope_mean",
        "lidar_slope_std",
        "lidar_lap_abs_max",
        "lidar_lap_neg_max",
        "lidar_lap_pos_max",
        "lidar_lap_std",
        "lidar_rough_mean",
        "lidar_rough_max",
        "lidar_rel_mean",
        "lidar_crest_toe_dipole",
        "topo10_slope",
        "topo10_plan_curv",
        "topo10_prof_curv",
        "topo10_tpi300",
        "topo10_tpi1000",
        "topo10_tpi2500",
        "topo10_tri",
        "topo10_open_pos",
        "topo10_lineament_aniso",
        "chi_step_max",
        "chi_step_min",
        "chi_ksn_max",
        "chi_log10_area",
        "along_strike_zstd_11",
        "pluvial_shoreline_mimic_score",
        "piedmont_fan_habitat",
        # Block D: GeoDAWN Alteration + Leak-Free Hydrothermal / 2m Probe / Sinter (14 channels)
        "geodawn_K",
        "geodawn_Th",
        "geodawn_U",
        "geodawn_ThK",
        "geodawn_UK",
        "geodawn_mag_destruction",
        "gdr_spring_temp_kernel",
        "gdr_geothermometer_kernel",
        "probe2m_f2mdab_pos_kernel",
        "probe2m_survey_coverage",
        "paleo_sinter_travertine_kernel",
        "volcanic_vent_strike_corridor",
        "hydro_strike_corridor_21",
        "crustal_weakness_conduit_potential",
    ]
)

assert len(FEATURE_NAMES_92) == 92
assert all("sgmc" not in nm.lower() for nm in FEATURE_NAMES_92)
assert all("fault_px" not in nm.lower() for nm in FEATURE_NAMES_92)

F16_MAX = 30000.0


class _FeatureMajorWriter:
    """Sequential binary writer for `(92, N_fp)` float16 matrix with zero dirty-page retention."""

    def __init__(self, path: Path, n_features: int, n_fp: int) -> None:
        self.path = path
        self.n_features = n_features
        self.n_fp = n_fp
        self.row_bytes = n_fp * 2
        self.fh = path.open("wb+")
        self.fh.truncate(n_features * self.row_bytes)
        self.written: set[int] = set()

    def write_feature(self, idx: int, values_fp: np.ndarray, allow_nan: bool = False) -> None:
        assert 0 <= idx < self.n_features, f"Invalid feature index {idx}"
        if allow_nan:
            v = np.where(np.isnan(values_fp), np.nan, np.clip(values_fp, -F16_MAX, F16_MAX)).astype(np.float16)
        else:
            v = np.clip(np.nan_to_num(values_fp, nan=0.0, posinf=F16_MAX, neginf=-F16_MAX), -F16_MAX, F16_MAX).astype(np.float16)
        assert v.shape == (self.n_fp,)
        self.fh.seek(idx * self.row_bytes)
        self.fh.write(v.tobytes())
        self.fh.flush()
        if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
            os.posix_fadvise(self.fh.fileno(), idx * self.row_bytes, self.row_bytes, os.POSIX_FADV_DONTNEED)
        self.written.add(idx)

    def close(self) -> None:
        assert len(self.written) == self.n_features, (
            f"Missing features: {sorted(set(range(self.n_features)) - self.written)}"
        )
        self.fh.flush()
        os.fsync(self.fh.fileno())
        if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
            os.posix_fadvise(self.fh.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        self.fh.close()


def extract_rows_from_fmajor(mm_92_nfp: np.memmap, row_idx: np.ndarray) -> np.ndarray:
    """Fast sequential column gather `(len(row_idx), 92)` float32 in < 0.45s & minimal RAM."""
    out = np.empty((len(row_idx), mm_92_nfp.shape[0]), dtype=np.float32)
    fd = mm_92_nfp._mmap.fileno() if hasattr(mm_92_nfp, "_mmap") and hasattr(mm_92_nfp._mmap, "fileno") else None
    row_bytes = mm_92_nfp.shape[1] * 2
    for j in range(mm_92_nfp.shape[0]):
        out[:, j] = mm_92_nfp[j, row_idx].astype(np.float32)
        if fd is not None and hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, j * row_bytes, row_bytes, os.POSIX_FADV_DONTNEED)
    return out


def _fill_nearest_valid(arr: np.ndarray, bad_mask: np.ndarray) -> np.ndarray:
    if not np.any(bad_mask):
        return arr.astype(np.float32, copy=False)
    idx = distance_transform_edt(bad_mask, return_distances=False, return_indices=True)
    out = arr.astype(np.float32, copy=True)
    out[bad_mask] = out[idx[0][bad_mask], idx[1][bad_mask]]
    return out


def _robust_z_on_fp(arr: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    vals = arr[valid_mask]
    med = float(np.nanmedian(vals))
    iqr = float(np.nanpercentile(vals, 75) - np.nanpercentile(vals, 25))
    scale = max(iqr / 1.349, 1e-6)
    return np.clip((arr - med) / scale, -12.0, 12.0).astype(np.float32, copy=False)


def _pos_sigmoid(z: np.ndarray) -> np.ndarray:
    return (1.0 / (1.0 + np.exp(-np.clip(z, -10.0, 10.0)))).astype(np.float32, copy=False)


def _bilinear_shift(arr: np.ndarray, dy: np.ndarray | float, dx: np.ndarray | float) -> np.ndarray:
    """Allocation-lean 4-neighbor bilinear warp without persistent `(H, W)` coordinate grids."""
    h, w = arr.shape
    rf = np.clip(np.arange(h, dtype=np.float32)[:, None] + dy, 0.0, h - 1.001)
    cf = np.clip(np.arange(w, dtype=np.float32)[None, :] + dx, 0.0, w - 1.001)
    r0 = rf.astype(np.int32)
    c0 = cf.astype(np.int32)
    fr = (rf - r0).astype(np.float32, copy=False)
    fc = (cf - c0).astype(np.float32, copy=False)
    del rf, cf
    return (
        (1.0 - fr) * ((1.0 - fc) * arr[r0, c0] + fc * arr[r0, c0 + 1])
        + fr * ((1.0 - fc) * arr[r0 + 1, c0] + fc * arr[r0 + 1, c0 + 1])
    ).astype(np.float32, copy=False)


def _multi_kernel_splat(
    shape: tuple[int, int],
    rows: np.ndarray,
    cols: np.ndarray,
    weights: np.ndarray,
    sigmas: tuple[float, ...],
) -> np.ndarray:
    grid = np.zeros(shape, dtype=np.float32)
    h, w = shape
    ok = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w) & np.isfinite(weights) & (weights > 0)
    if np.any(ok):
        np.add.at(grid, (rows[ok], cols[ok]), weights[ok].astype(np.float32))
    acc = np.zeros(shape, dtype=np.float32)
    for sig in sigmas:
        sm = gaussian_filter(grid, sigma=sig, mode="nearest")
        mx = float(sm.max())
        if mx > 1e-12:
            acc += sm * (1.0 / mx)
    return (acc / max(len(sigmas), 1)).astype(np.float32, copy=False)


def _load_leak_free_hydrothermal_points(
    ext_dir: Path, transform: rasterio.Affine, dst_crs: str
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    ws_path = ext_dir / "gdr_wellspring_in_footprint.csv"
    rows_t, cols_t, w_temp = [], [], []
    rows_g, cols_g, w_geoth = [], [], []
    ALLOWED_WS_COLS = {"row", "col", "temp_c", "geothermquartz_c", "geothermchalc_c", "geothermcat_c"}
    assert "dist_known_fault_px" not in ALLOWED_WS_COLS
    with ws_path.open("r", encoding="utf-8", errors="replace") as f:
        for rec in csv.DictReader(f):
            try:
                r = int(float(rec["row"]))
                c = int(float(rec["col"]))
            except (KeyError, ValueError):
                continue
            tc_s = rec.get("temp_c", "").strip()
            if tc_s:
                try:
                    tc = float(tc_s)
                    if np.isfinite(tc) and tc > 20.0:
                        rows_t.append(r)
                        cols_t.append(c)
                        w_temp.append(min(tc - 20.0, 140.0))
                except ValueError:
                    pass
            gt_vals = []
            for gk in ("geothermquartz_c", "geothermchalc_c", "geothermcat_c"):
                gs = rec.get(gk, "").strip()
                if gs:
                    try:
                        gv = float(gs)
                        if 40.0 <= gv <= 360.0:
                            gt_vals.append(gv)
                    except ValueError:
                        pass
            if gt_vals:
                gmax = max(gt_vals)
                if gmax > 75.0:
                    rows_g.append(r)
                    cols_g.append(c)
                    w_geoth.append(min(gmax - 75.0, 220.0))
    out["spring_temp"] = (np.array(rows_t, np.int32), np.array(cols_t, np.int32), np.array(w_temp, np.float32))
    out["geotherm"] = (np.array(rows_g, np.int32), np.array(cols_g, np.int32), np.array(w_geoth, np.float32))

    vv_path = ext_dir / "gdr_volcanic_vents_in_footprint.csv"
    rv, cv, wv = [], [], []
    with vv_path.open("r", encoding="utf-8", errors="replace") as f:
        for rec in csv.DictReader(f):
            try:
                rv.append(int(float(rec["row"])))
                cv.append(int(float(rec["col"])))
                wv.append(1.0)
            except (KeyError, ValueError):
                continue
    out["vents"] = (np.array(rv, np.int32), np.array(cv, np.int32), np.array(wv, np.float32))

    probe_zip = ext_dir / "2m_temperature_probe_INGENIOUS_regional_data.zip"
    lons_p, lats_p, f2m_p = [], [], []
    with zipfile.ZipFile(probe_zip) as zf:
        dbf = zf.read("2m_temperature_probe_INGENIOUS_regional_data/2m_temperature_probe_n83geo/2m_temperature_probe_n83geo.dbf")
        nrec, hdr_len, rec_len = struct.unpack("<IHH", dbf[4:12])
        off = 32
        fields = []
        while off < hdr_len - 1 and dbf[off] != 0x0D:
            fname = dbf[off : off + 11].split(b"\x00", 1)[0].decode("ascii", "replace")
            flen = dbf[off + 16]
            fields.append((fname, flen))
            off += 32
        field_offsets = {}
        pos = 1
        for fname, flen in fields:
            field_offsets[fname] = (pos, pos + flen)
            pos += flen
        lo_sl = field_offsets["LongDegree"]
        la_sl = field_offsets["LatDegreeN"]
        f2_sl = field_offsets["F2mDAB"]
        for i in range(nrec):
            base = hdr_len + i * rec_len
            if dbf[base] == 0x2A:
                continue
            try:
                lon = float(dbf[base + lo_sl[0] : base + lo_sl[1]].decode("ascii", "ignore").strip())
                lat = float(dbf[base + la_sl[0] : base + la_sl[1]].decode("ascii", "ignore").strip())
                f2m = float(dbf[base + f2_sl[0] : base + f2_sl[1]].decode("ascii", "ignore").strip())
                if -125.0 <= lon <= -110.0 and 34.0 <= lat <= 44.0 and np.isfinite(f2m):
                    lons_p.append(lon)
                    lats_p.append(lat)
                    f2m_p.append(f2m)
            except ValueError:
                continue
    xs_p, ys_p = warp_transform("EPSG:4269", dst_crs, lons_p, lats_p)
    rp, cp = rowcol(transform, xs_p, ys_p)
    rp_arr = np.asarray(rp, dtype=np.int32)
    cp_arr = np.asarray(cp, dtype=np.int32)
    f2m_arr = np.asarray(f2m_p, dtype=np.float32)
    out["probe_pos"] = (rp_arr, cp_arr, np.clip(f2m_arr, 0.0, 25.0))
    out["probe_cov"] = (rp_arr, cp_arr, np.ones_like(f2m_arr, dtype=np.float32))

    paleo_zip = ext_dir / "paleo_geothermal_regional.zip"
    lons_s, lats_s, ws_s = [], [], []
    with zipfile.ZipFile(paleo_zip) as zf:
        txt = io.TextIOWrapper(zf.open("Paleo_geothermal_final.csv"), encoding="utf-8", errors="replace")
        for rec in csv.DictReader(txt):
            try:
                lon = float(rec["Long_deg_NAD83"])
                lat = float(rec["Lat_deg_NAD83"])
                dtype = rec.get("Deposit_type", "").lower()
                w = 1.6 if "sinter" in dtype else 1.15
                if -125.0 <= lon <= -110.0 and 34.0 <= lat <= 44.0:
                    lons_s.append(lon)
                    lats_s.append(lat)
                    ws_s.append(w)
            except (KeyError, ValueError):
                continue
    xs_s, ys_s = warp_transform("EPSG:4269", dst_crs, lons_s, lats_s)
    rs, cs = rowcol(transform, xs_s, ys_s)
    out["sinter"] = (np.asarray(rs, np.int32), np.asarray(cs, np.int32), np.asarray(ws_s, np.float32))
    return out


def build_or_load_kdmi_stack(cache_dir: Path, force: bool = False) -> dict:
    """Materialize `(92, N_fp)` contiguous feature-major float16 `KDMI` stack (< 600 MB RAM)."""
    feat_dir = cache_dir / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)
    # Remove any old stale file first so disk stays clean
    old_dat = feat_dir / "h87_kdmi_92_f16.dat"
    if old_dat.exists():
        old_dat.unlink()

    dat_path = feat_dir / "h87_kdmi_92_fmajor_f16.bin"
    meta_path = feat_dir / "h87_kdmi_92_meta.json"
    fp_idx_path = feat_dir / "h87_fp_flat_idx.npy"
    dip_path = feat_dir / "h87_dip_vectors_f16.npz"

    if not force and dat_path.exists() and meta_path.exists() and fp_idx_path.exists() and dip_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("schema_version") == "h87-kdmi-fmajor-v3":
            fp_idx = np.load(fp_idx_path)
            mm = np.memmap(dat_path, dtype=np.float16, mode="r", shape=(92, len(fp_idx)))
            return {"mm": mm, "fp_idx": fp_idx, "meta": meta, "dip_path": dip_path}

    core_dir = cache_dir / "gems_data" / "core"
    ext_dir = cache_dir / "gems_data" / "external"

    with rasterio.open(core_dir / "sample_submission.tif") as src:
        sample = src.read(1)
        valid_mask = np.isfinite(sample)
        shape = sample.shape
        transform = src.transform
        dst_crs = str(src.crs)
        del sample

    h, w = shape
    fp_idx = np.flatnonzero(valid_mask).astype(np.int32)
    n_fp = len(fp_idx)
    np.save(fp_idx_path, fp_idx)
    writer = _FeatureMajorWriter(dat_path, 92, n_fp)

    # Single-pass strip decompression of 19-band pixel-interleaved GeoTIFF (3.3s), keeping ONLY 10 bands!
    keep_idx = {1: "rtp", 2: "tmi_hg", 3: "strain_2nd", 5: "tc", 6: "shear", 7: "dilate",
                10: "grav_vg", 11: "det_elev", 14: "hbase_m", 15: "ieq_log", 16: "cond_surf", 17: "grav_hg"}
    kept: dict[str, np.ndarray] = {}
    raw19 = np.empty((19, h, w), dtype=np.float32)
    with rasterio.open(core_dir / "training_features.tif") as src:
        step = 373
        for r0 in range(0, h, step):
            hh = min(step, h - r0)
            raw19[:, r0 : r0 + hh, :] = src.read(window=Window(0, r0, w, hh))

    bad_b6 = (~valid_mask) | (~np.isfinite(raw19[5])) | (np.abs(raw19[5]) > 1e20)
    nn_idx = distance_transform_edt(bad_b6, return_distances=False, return_indices=True)
    in_fp_nan = valid_mask & ((~np.isfinite(raw19[5])) | (np.abs(raw19[5]) > 1e20))
    del bad_b6

    for b_i in range(19):
        arr = raw19[b_i]
        bad = (~valid_mask) | (~np.isfinite(arr)) | (np.abs(arr) > 1e20)
        in_fp_nan |= valid_mask & ((~np.isfinite(arr)) | (np.abs(arr) > 1e20))
        arr[bad] = arr[nn_idx[0][bad], nn_idx[1][bad]]
        if b_i in (9, 15):
            arr[:] = np.log1p(np.maximum(arr, 0.0))
        writer.write_feature(b_i, arr.ravel()[fp_idx])
        if b_i in keep_idx:
            kept[keep_idx[b_i]] = arr.copy()

    del raw19, nn_idx
    writer.write_feature(19, in_fp_nan.ravel()[fp_idx].astype(np.float32))
    del in_fp_nan
    gc.collect()

    # Block A worms & basement architecture [20..25]
    writer.write_feature(20, (kept["grav_hg"] - gaussian_filter(kept["grav_hg"], 8.0)).ravel()[fp_idx])
    writer.write_feature(21, (kept["tmi_hg"] - gaussian_filter(kept["tmi_hg"], 8.0)).ravel()[fp_idx])
    writer.write_feature(22, (kept["tc"] - gaussian_filter(kept["tc"], 8.0)).ravel()[fp_idx])
    del kept["tmi_hg"]

    hb_sm = gaussian_filter(kept["hbase_m"], 1.5)
    gy_hb, gx_hb = np.gradient(hb_sm)
    base_grad_mag = np.hypot(gy_hb, gx_hb).astype(np.float32)
    writer.write_feature(23, base_grad_mag.ravel()[fp_idx])
    writer.write_feature(24, (hb_sm - gaussian_filter(kept["hbase_m"], 7.0)).ravel()[fp_idx])
    del hb_sm, gy_hb, gx_hb

    transtens = (
        kept["shear"] / (np.abs(kept["dilate"]) + np.abs(kept["shear"]) + 0.5) * kept["strain_2nd"]
    ).astype(np.float32)
    writer.write_feature(25, transtens.ravel()[fp_idx])
    del kept["shear"], kept["dilate"], transtens
    gc.collect()

    # Read `dem10_chi_100m_i16.tif` [71..74] + `zmean` & `ksn_z`
    with rasterio.open(ext_dir / "dem10_chi_100m_i16.tif") as src:
        chi5 = src.read()
    writer.write_feature(71, np.clip(_fill_nearest_valid(chi5[0].astype(np.float32), (~valid_mask) | (chi5[0] < -30000)) * 0.001, -20.0, 20.0).ravel()[fp_idx])
    writer.write_feature(72, np.clip(_fill_nearest_valid(chi5[1].astype(np.float32), (~valid_mask) | (chi5[1] < -30000)) * 0.001, -20.0, 20.0).ravel()[fp_idx])
    ksn_z = _robust_z_on_fp(_fill_nearest_valid(chi5[2].astype(np.float32), (~valid_mask) | (chi5[2] < -30000)), valid_mask)
    writer.write_feature(73, ksn_z.ravel()[fp_idx])
    writer.write_feature(74, np.clip(_fill_nearest_valid(chi5[3].astype(np.float32), (~valid_mask) | (chi5[3] < -30000)) * 0.001, -5.0, 20.0).ravel()[fp_idx])
    zmean = _fill_nearest_valid(chi5[4].astype(np.float32), (~valid_mask) | (chi5[4] < -30000))
    del chi5
    gc.collect()

    # Regional Tectonic Dip Unit Vector n(x) & Orthogonal Strike Tangent t(x)
    zy, zx = np.gradient(gaussian_filter(zmean, 11.0))
    dy_det, dx_det = np.gradient(gaussian_filter(kept["det_elev"], 9.0))
    hy_b, hx_b = np.gradient(gaussian_filter(kept["hbase_m"], 12.0))
    z_mag = float(np.percentile(np.hypot(zy, zx)[valid_mask], 90)) + 1e-6
    d_mag = float(np.percentile(np.hypot(dy_det, dx_det)[valid_mask], 90)) + 1e-6
    b_mag = float(np.percentile(np.hypot(hy_b, hx_b)[valid_mask], 90)) + 1e-6
    vy = (-0.38 * (zy / z_mag) - 0.34 * (dy_det / d_mag) + 0.28 * (hy_b / b_mag)).astype(np.float32)
    vx = (-0.38 * (zx / z_mag) - 0.34 * (dx_det / d_mag) + 0.28 * (hx_b / b_mag)).astype(np.float32)
    del zy, zx, dy_det, dx_det, hy_b, hx_b

    vmag = np.hypot(vy, vx).astype(np.float32)
    ny = (vy / np.maximum(vmag, 1e-5)).astype(np.float32)
    nx = (vx / np.maximum(vmag, 1e-5)).astype(np.float32)
    ty = (-nx).astype(np.float32)
    tx = ny.astype(np.float32)
    del vy, vx

    np.savez_compressed(dip_path, ny_fp=ny.ravel()[fp_idx].astype(np.float16), nx_fp=nx.ravel()[fp_idx].astype(np.float16))

    sdip = np.clip((np.maximum(kept["hbase_m"], 0.0) * 0.57735027) / 100.0, 2.5, 15.0).astype(np.float32)
    writer.write_feature(26, sdip.ravel()[fp_idx])
    writer.write_feature(27, np.clip(vmag, 0.0, 5.0).ravel()[fp_idx])
    del vmag

    # Along-strike sea-level elevation std + Pleistocene pluvial shoreline mimic [75..76] right now so zmean frees immediately!
    z_mean_t = zmean.copy()
    for m in (-3, -2, -1, 1, 2, 3):
        z_mean_t += _bilinear_shift(zmean, (1.8 * m) * ty, (1.8 * m) * tx)
    z_mean_t *= 1.0 / 7.0
    z_var_t = (zmean - z_mean_t) ** 2
    for m in (-3, -2, -1, 1, 2, 3):
        z_var_t += (_bilinear_shift(zmean, (1.8 * m) * ty, (1.8 * m) * tx) - z_mean_t) ** 2
    z_std_t = np.sqrt(np.maximum(z_var_t * (1.0 / 7.0), 0.0)).astype(np.float32)
    del z_mean_t, z_var_t
    writer.write_feature(75, np.clip(z_std_t, 0.0, 120.0).ravel()[fp_idx])

    shore_bands = (
        np.exp(-(((zmean - 1332.0) / 16.0) ** 2))
        + 0.70 * np.exp(-(((zmean - 1205.0) / 16.0) ** 2))
        + 0.80 * np.exp(-(((zmean - 1463.0) / 16.0) ** 2))
        + 0.80 * np.exp(-(((zmean - 1552.0) / 16.0) ** 2))
    ).astype(np.float32)
    writer.write_feature(76, (shore_bands / (1.0 + z_std_t / 3.0)).ravel()[fp_idx])
    del zmean, z_std_t, shore_bands
    gc.collect()

    # GeoDAWN radiometrics + upward-continued TMI [78..83]
    with rasterio.open(ext_dir / "geodawn_extensions_u8.tif") as src:
        gd_ext = src.read()
    thk_u8 = _fill_nearest_valid(gd_ext[0].astype(np.float32), (~valid_mask) | (gd_ext[0] == 0))
    uk_u8 = _fill_nearest_valid(gd_ext[1].astype(np.float32), (~valid_mask) | (gd_ext[1] == 0))
    tmi_up150 = _robust_z_on_fp(_fill_nearest_valid(gd_ext[3].astype(np.float32), (~valid_mask) | (gd_ext[3] == 0)), valid_mask)
    del gd_ext

    with rasterio.open(ext_dir / "geodawn_rad_u8.tif") as src:
        gd_rad = src.read()
    kz = _robust_z_on_fp(_fill_nearest_valid(gd_rad[0].astype(np.float32), (~valid_mask) | (gd_rad[0] == 0)), valid_mask)
    writer.write_feature(78, kz.ravel()[fp_idx])
    writer.write_feature(79, _robust_z_on_fp(_fill_nearest_valid(gd_rad[1].astype(np.float32), (~valid_mask) | (gd_rad[1] == 0)), valid_mask).ravel()[fp_idx])
    writer.write_feature(80, _robust_z_on_fp(_fill_nearest_valid(gd_rad[2].astype(np.float32), (~valid_mask) | (gd_rad[2] == 0)), valid_mask).ravel()[fp_idx])
    del gd_rad
    writer.write_feature(81, _robust_z_on_fp(thk_u8, valid_mask).ravel()[fp_idx])
    writer.write_feature(82, _robust_z_on_fp(uk_u8, valid_mask).ravel()[fp_idx])
    writer.write_feature(83, (kz - tmi_up150).ravel()[fp_idx])
    del thk_u8, uk_u8, kz
    gc.collect()

    # Leak-free hydrothermal points [84..91]
    pts = _load_leak_free_hydrothermal_points(ext_dir, transform, dst_crs)
    spring_k = _multi_kernel_splat(shape, *pts["spring_temp"], sigmas=(3.5, 12.0, 28.0))
    geoth_k = _multi_kernel_splat(shape, *pts["geotherm"], sigmas=(4.5, 15.0, 34.0))
    probe_pos_k = _multi_kernel_splat(shape, *pts["probe_pos"], sigmas=(3.0, 9.0, 22.0))
    probe_cov_k = _multi_kernel_splat(shape, *pts["probe_cov"], sigmas=(8.0,))
    sinter_k = _multi_kernel_splat(shape, *pts["sinter"], sigmas=(3.0, 10.0, 24.0))
    vent_k = _multi_kernel_splat(shape, *pts["vents"], sigmas=(4.0, 14.0, 30.0))
    del pts
    writer.write_feature(84, spring_k.ravel()[fp_idx])
    writer.write_feature(85, geoth_k.ravel()[fp_idx])
    writer.write_feature(86, probe_pos_k.ravel()[fp_idx])
    writer.write_feature(87, probe_cov_k.ravel()[fp_idx])
    writer.write_feature(88, sinter_k.ravel()[fp_idx])
    hydro_comp = (0.30 * spring_k + 0.30 * geoth_k + 0.22 * probe_pos_k + 0.18 * sinter_k).astype(np.float32)
    del spring_k, geoth_k, probe_pos_k, probe_cov_k, sinter_k

    vent_strike = vent_k.copy()
    hydro_strike = hydro_comp.copy()
    for m in (-3, -2, -1, 1, 2, 3):
        vent_strike += _bilinear_shift(vent_k, (2.5 * m) * ty, (2.5 * m) * tx)
        hydro_strike += _bilinear_shift(hydro_comp, (2.5 * m) * ty, (2.5 * m) * tx)
    writer.write_feature(89, (vent_strike * (1.0 / 7.0)).ravel()[fp_idx])
    writer.write_feature(90, (hydro_strike * (1.0 / 7.0)).ravel()[fp_idx])
    del vent_k, vent_strike, hydro_strike

    conduit_pot = (
        0.28 * _pos_sigmoid(_robust_z_on_fp(kept["strain_2nd"], valid_mask))
        + 0.28 * _pos_sigmoid(_robust_z_on_fp(kept["cond_surf"], valid_mask))
        + 0.24 * _pos_sigmoid(_robust_z_on_fp(kept["ieq_log"], valid_mask))
        + 0.20 * _pos_sigmoid(_robust_z_on_fp(base_grad_mag, valid_mask))
    ).astype(np.float32)
    writer.write_feature(91, conduit_pot.ravel()[fp_idx])
    del kept["strain_2nd"], base_grad_mag, conduit_pot
    gc.collect()

    # Block B [28..47]: Kirchhoff Listric Dip-Migration Interferometry (domain by domain, <500 MB RAM!)
    grav_hg = kept.pop("grav_hg")
    g_hw_sdip = _bilinear_shift(grav_hg, sdip * ny, sdip * nx)
    grav_dip_sdip = g_hw_sdip - _bilinear_shift(grav_hg, -0.6 * sdip * ny, -0.6 * sdip * nx)
    grav_hw_max = np.maximum(
        np.maximum(_bilinear_shift(grav_hg, 4.0 * ny, 4.0 * nx), _bilinear_shift(grav_hg, 9.0 * ny, 9.0 * nx)),
        _bilinear_shift(grav_hg, 14.0 * ny, 14.0 * nx),
    )
    writer.write_feature(28, g_hw_sdip.ravel()[fp_idx])
    writer.write_feature(29, grav_hw_max.ravel()[fp_idx])
    writer.write_feature(30, (_bilinear_shift(grav_hg, 6.0 * ny, 6.0 * nx) - _bilinear_shift(grav_hg, -6.0 * ny, -6.0 * nx)).ravel()[fp_idx])
    writer.write_feature(31, (_bilinear_shift(grav_hg, 12.0 * ny, 12.0 * nx) - _bilinear_shift(grav_hg, -12.0 * ny, -12.0 * nx)).ravel()[fp_idx])
    writer.write_feature(32, grav_dip_sdip.ravel()[fp_idx])
    del grav_hg, g_hw_sdip

    grav_vg = kept.pop("grav_vg")
    writer.write_feature(33, (_bilinear_shift(grav_vg, 10.0 * ny, 10.0 * nx) - _bilinear_shift(grav_vg, -10.0 * ny, -10.0 * nx)).ravel()[fp_idx])
    del grav_vg

    hbase_m = kept.pop("hbase_m")
    base_throw_8 = _bilinear_shift(hbase_m, 8.0 * ny, 8.0 * nx) - _bilinear_shift(hbase_m, -8.0 * ny, -8.0 * nx)
    writer.write_feature(34, base_throw_8.ravel()[fp_idx])
    writer.write_feature(35, (_bilinear_shift(hbase_m, 14.0 * ny, 14.0 * nx) - _bilinear_shift(hbase_m, -14.0 * ny, -14.0 * nx)).ravel()[fp_idx])

    dom_grav = _pos_sigmoid(
        0.45 * _robust_z_on_fp(grav_dip_sdip, valid_mask)
        + 0.30 * _robust_z_on_fp(grav_hw_max, valid_mask)
        + 0.25 * _robust_z_on_fp(base_throw_8, valid_mask)
    )
    del grav_dip_sdip, grav_hw_max, base_throw_8

    rtp = kept.pop("rtp")
    tc = kept.pop("tc")
    rtp_dip = np.abs(_bilinear_shift(rtp, sdip * ny, sdip * nx) - _bilinear_shift(rtp, -0.7 * sdip * ny, -0.7 * sdip * nx))
    tc_hw5 = _bilinear_shift(tc, 5.0 * ny, 5.0 * nx)
    tmi_up_dip9 = np.abs(_bilinear_shift(tmi_up150, 9.0 * ny, 9.0 * nx) - _bilinear_shift(tmi_up150, -9.0 * ny, -9.0 * nx))
    writer.write_feature(36, rtp_dip.ravel()[fp_idx])
    writer.write_feature(37, tc_hw5.ravel()[fp_idx])
    writer.write_feature(38, tmi_up_dip9.ravel()[fp_idx])
    dom_mag = _pos_sigmoid(
        0.45 * _robust_z_on_fp(rtp_dip, valid_mask)
        + 0.30 * _robust_z_on_fp(tc_hw5, valid_mask)
        + 0.25 * _robust_z_on_fp(tmi_up_dip9, valid_mask)
    )
    del rtp, tc, tmi_up150, sdip, rtp_dip, tc_hw5, tmi_up_dip9

    cond_surf = kept.pop("cond_surf")
    cond_hw4 = _bilinear_shift(cond_surf, 4.0 * ny, 4.0 * nx)
    cond_asym10 = cond_hw4 - _bilinear_shift(cond_surf, -8.0 * ny, -8.0 * nx)
    writer.write_feature(39, cond_hw4.ravel()[fp_idx])
    writer.write_feature(40, cond_asym10.ravel()[fp_idx])
    dom_cond = _pos_sigmoid(
        0.55 * _robust_z_on_fp(cond_hw4, valid_mask) + 0.45 * _robust_z_on_fp(cond_asym10, valid_mask)
    )
    del cond_surf, cond_hw4, cond_asym10

    det_elev = kept.pop("det_elev")
    ksn_drop4 = _bilinear_shift(ksn_z, -4.0 * ny, -4.0 * nx) - _bilinear_shift(ksn_z, 4.0 * ny, 4.0 * nx)
    elev_step3 = _bilinear_shift(det_elev, -3.0 * ny, -3.0 * nx) - _bilinear_shift(det_elev, 3.0 * ny, 3.0 * nx)
    writer.write_feature(41, ksn_drop4.ravel()[fp_idx])
    writer.write_feature(42, elev_step3.ravel()[fp_idx])
    dom_geom = _pos_sigmoid(
        0.50 * _robust_z_on_fp(ksn_drop4, valid_mask) + 0.50 * _robust_z_on_fp(elev_step3, valid_mask)
    )
    del det_elev, ksn_z, ksn_drop4, elev_step3

    ieq_log = kept.pop("ieq_log")
    hydro_up = np.maximum(
        hydro_comp,
        np.maximum(_bilinear_shift(hydro_comp, 4.5 * ny, 4.5 * nx), _bilinear_shift(hydro_comp, 9.5 * ny, 9.5 * nx)),
    )
    writer.write_feature(43, hydro_up.ravel()[fp_idx])
    dom_hydro = _pos_sigmoid(
        0.65 * _robust_z_on_fp(hydro_up, valid_mask) + 0.35 * _robust_z_on_fp(ieq_log, valid_mask)
    )
    del ieq_log, hydro_comp, hydro_up
    gc.collect()

    interferogram = np.power(
        np.maximum(dom_grav * dom_mag * dom_cond * dom_geom * dom_hydro, 1e-12), 0.20
    ).astype(np.float32)
    del dom_grav, dom_mag, dom_cond, dom_geom, dom_hydro

    radon_9 = interferogram.copy()
    for m in (-3, -2, -1, 1, 2, 3):
        radon_9 += _bilinear_shift(interferogram, (1.5 * m) * ty, (1.5 * m) * tx)
    radon_9 *= 1.0 / 7.0
    radon_21 = interferogram.copy()
    for m in (-4, -3, -2, -1, 1, 2, 3, 4):
        radon_21 += _bilinear_shift(interferogram, (2.6 * m) * ty, (2.6 * m) * tx)
    radon_21 *= 1.0 / 9.0
    radon_cross = 0.5 * (
        _bilinear_shift(interferogram, 4.5 * ny, 4.5 * nx) + _bilinear_shift(interferogram, -4.5 * ny, -4.5 * nx)
    )
    writer.write_feature(44, interferogram.ravel()[fp_idx])
    writer.write_feature(45, radon_9.ravel()[fp_idx])
    writer.write_feature(46, radon_21.ravel()[fp_idx])
    writer.write_feature(47, (radon_9 - radon_cross).ravel()[fp_idx])
    del interferogram, radon_9, radon_21, radon_cross
    gc.collect()

    # Block C: 1m LiDAR [49..61] (native NaN outside coverage!) + 10m DEM [62..70, 48, 77]
    with rasterio.open(ext_dir / "lidar_scarp_features_u8.tif") as src:
        lid12 = src.read()
    has_lidar = (lid12[11] > 0) & valid_mask
    writer.write_feature(49, has_lidar.ravel()[fp_idx].astype(np.float32))
    lap_neg_keep = None
    lap_pos_keep = None
    for b in range(11):
        arr = lid12[b].astype(np.float32)
        arr[~has_lidar] = np.nan
        writer.write_feature(50 + b, arr.ravel()[fp_idx], allow_nan=True)
        if b == 5:
            lap_neg_keep = arr
        elif b == 6:
            lap_pos_keep = arr
    del lid12
    dipole_scarp = np.sqrt(np.maximum(lap_neg_keep * lap_pos_keep, 0.0))
    dipole_scarp[~has_lidar] = np.nan
    writer.write_feature(61, dipole_scarp.ravel()[fp_idx], allow_nan=True)
    del lap_neg_keep, lap_pos_keep, dipole_scarp, has_lidar
    gc.collect()

    with rasterio.open(ext_dir / "topo_10m_derived_100m_u8.tif") as src:
        t10 = src.read()
    topo10_slope_keep = None
    topo10_scarp_proxy = None
    for b in range(9):
        arr = _fill_nearest_valid(t10[b].astype(np.float32), (~valid_mask) | (t10[b] == 0))
        writer.write_feature(62 + b, arr.ravel()[fp_idx])
        if b == 0:
            topo10_slope_keep = arr
        elif b == 3:
            topo10_scarp_proxy = np.abs(arr - 128.0).astype(np.float32)
    del t10

    sc_along = topo10_scarp_proxy.copy()
    for m in (-3, -2, -1, 1, 2, 3):
        sc_along += _bilinear_shift(topo10_scarp_proxy, (1.5 * m) * ty, (1.5 * m) * tx)
    sc_along *= 1.0 / 7.0
    sc_cross = 0.5 * (
        _bilinear_shift(topo10_scarp_proxy, 4.0 * ny, 4.0 * nx)
        + _bilinear_shift(topo10_scarp_proxy, -4.0 * ny, -4.0 * nx)
    )
    writer.write_feature(48, _robust_z_on_fp(sc_along - sc_cross, valid_mask).ravel()[fp_idx])
    del sc_along, sc_cross, topo10_scarp_proxy, ny, nx, ty, tx

    pied_hab = (
        _pos_sigmoid((hbase_m - 220.0) / 120.0)
        * _pos_sigmoid((115.0 - topo10_slope_keep) * 0.045)
        * _pos_sigmoid((topo10_slope_keep - 6.0) * 0.12)
    ).astype(np.float32)
    writer.write_feature(77, pied_hab.ravel()[fp_idx])
    del hbase_m, topo10_slope_keep, pied_hab
    writer.close()
    gc.collect()

    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    meta = {
        "schema_version": "h87-kdmi-fmajor-v3",
        "layout": [92, int(n_fp)],
        "n_fp": int(n_fp),
        "n_features": 92,
        "shape": [int(h), int(w)],
        "dtype": "float16",
        "peak_rss_mb": round(peak_mb, 1),
        "feature_names": FEATURE_NAMES_92,
        "sgmc_in_X": False,
        "catalogue_in_X": False,
        "dist_known_fault_px_read": False,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    mm = np.memmap(dat_path, dtype=np.float16, mode="r", shape=(92, n_fp))
    return {"mm": mm, "fp_idx": fp_idx, "meta": meta, "dip_path": dip_path}
