"""Comprehensive automated regression suite for Session 2 H87B-STFD (zero human intervention)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import numpy as np
import rasterio

from gems57 import gates
from gems57.validate import validate
from gems87 import stfd_features, stfd_model
from scripts import check_submission

ROOT = Path(__file__).resolve().parents[1]
H87B_CARD = ROOT / "docs/evidence/h87b_run_card.json"
H87B_REG34 = ROOT / "docs/evidence/h87b_registry_34.json"
BAND_AUDIT = ROOT / "docs/evidence/band_identity_audit.json"
H87B_ABLATION = ROOT / "evidence/h87b_ablation.json"
H87B_TIF = ROOT / "docs/downloads/gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.tif"
H87B_ZIP = ROOT / "docs/downloads/gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.zip"
H87B_JSON = ROOT / "docs/downloads/gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.json"


def test_h87b_geotiff_and_zip_pass_all_automated_checks_without_human_intervention():
    assert H87B_TIF.is_file() and H87B_ZIP.is_file() and H87B_JSON.is_file()
    card = json.loads(H87B_CARD.read_text(encoding="utf-8"))
    bundle = check_submission.check_h87b_bundle(card)
    assert bundle["local_format_valid"] is True
    assert bundle["safe_to_submit"] is False
    assert bundle["decision"] == "DO NOT SUBMIT"
    assert bundle["no_nan_inside_footprint"] is True
    assert bundle["range_0_1"] is True
    assert bundle["crs_shape_transform_match"] is True
    assert bundle["zip_contains_exactly_one_matching_tiff"] is True

    sample = ROOT / "data/raw/sample_submission.tif"
    existing = ROOT / "data/raw/existing_faults.tif"

    tif_bytes = H87B_TIF.read_bytes()
    expected_sha = "1d3f50ffd13f9c7ec0258579717810be3bd4d1fc039b80a0f6e2e4c523ba394f"
    assert hashlib.sha256(tif_bytes).hexdigest() == expected_sha

    with rasterio.open(H87B_TIF) as src, rasterio.open(existing) as cat_src:
        arr = src.read(1)
        cat_raw = cat_src.read(1)
        fp = cat_raw != -1
        cat = cat_raw == 1
        assert gates.format_report(H87B_TIF, sample, footprint=fp)["ok"] is True
        assert validate(H87B_TIF, fp, cat)["all_checks_passed"] is True
        assert src.count == 1
        assert src.dtypes == ("float32",)
        assert str(src.crs) == "EPSG:32611"
        assert src.shape == (3730, 3292)
        assert not np.isnan(arr).any() and not np.isinf(arr).any()
        assert arr.min() == 0.0 and arr.max() == 1.0
        assert set(np.unique(arr).tolist()) == {0.0, 1.0}
        assert int((arr > 0).sum()) == 37654
        assert int((arr[~fp] > 0).sum()) == 0
        assert int((arr[cat] > 0).sum()) == 0

    with zipfile.ZipFile(H87B_ZIP) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert names == [H87B_TIF.name]
        assert zf.read(names[0]) == tif_bytes


def test_h87b_run_card_ablation_and_34_raster_audit_invariants():
    card = json.loads(H87B_CARD.read_text(encoding="utf-8"))
    reg34 = json.loads(H87B_REG34.read_text(encoding="utf-8"))
    audit = json.loads(BAND_AUDIT.read_text(encoding="utf-8"))
    ablation = json.loads(H87B_ABLATION.read_text(encoding="utf-8"))

    assert card["verdict"] == "negative"
    assert card["safe_to_submit"] is False
    assert len(card["submission_note"]) <= 140
    assert card["budget"]["experiments_used"] == 3 <= card["budget"]["experiments_allowed"]
    assert card["budget"]["weekly_slots_used"] == 0

    assert card["leakage_canary"]["passed"] is True
    assert card["leakage_canary"]["features_tested"] == 64
    assert card["leakage_canary"]["max_two_sided_auc"] <= 0.90
    assert card["leakage_canary"]["tripped_features"] == []
    assert len(ablation["leakage_canary_rows"]) == 64

    comp = card["holdout_dti"]["dual_seed_buffered_component_holdout"]
    quad = card["holdout_dti"]["four_quadrant_whole_component_holdout"]
    assert comp["withheld_positive_pixels"] == 22663
    assert quad["withheld_positive_pixels"] == 60988

    exp3_comp = comp["all_scores"]["EXP3_stfd_heterogeneous_dink300"]["dti"]
    exp2_comp = comp["all_scores"]["EXP2_counterfactual_single_hgb"]["dti"]
    h33_fair = comp["all_scores"]["H33_2_B2_fold_fair"]["dti"]
    d28_comp = comp["all_scores"]["GEMSDOE24_d2_8"]["dti"]
    h33_static = comp["all_scores"]["GEMSDOE32_H33_2_B2"]["dti"]
    assert exp2_comp > exp3_comp > h33_fair > d28_comp > h33_static
    assert comp["paired_differences"]["H33_2_B2_fold_fair"]["ci95"][0] > 0.02

    assert (
        quad["all_scores"]["true_slope_b08_control"]["dti"]
        > 2.0 * quad["all_scores"]["topographic_slope_control"]["dti"]
    )
    assert quad["paired_differences"]["EXP2_counterfactual_single_hgb"]["ci95"][0] > 0.0

    b6 = audit["band_06_tc_audit"]
    assert b6["fraction_negative"] == 0.0
    assert b6["pearson_r_with_geodawn_TC"] > 0.995
    assert abs(b6["pearson_r_with_true_miller_singh_magnetic_tilt"]) < 0.05

    assert reg34["total_rasters_audited"] == 34
    assert reg34["real_fault_candidates_count"] == 31
    assert reg34["space_filling_witnesses_count"] == 3
    assert reg34["discriminating_real_candidate_gate"]["passed"] is True
    assert reg34["discriminating_real_candidate_gate"]["duplicates_count"] == 0
    assert reg34["discriminating_real_candidate_gate"]["max_dot_overlap_3px"] <= 0.70
    assert reg34["discriminating_real_candidate_gate"]["max_abs_spearman_rho"] <= 0.90
    assert reg34["literal_unstratified_gate"]["stop_required"] is True
    assert reg34["literal_unstratified_gate"]["duplicates_count"] == 3


def test_readme_preserves_original_user_brief_core_values_and_downloads():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "<!-- USER_BRIEF_START -->" in readme
    assert "Maximize P(Win)" in readme
    assert "Own the Outcome" in readme
    assert "DO NOT SUBMIT" in readme
    assert H87B_TIF.name in readme
    assert "gems87-bmtd-20261022-50041440adba-RESEARCH-DO-NOT-SUBMIT.tif" in readme


def test_visible_structural_features_and_expected_credit_emitter_synthetic():
    shape = (48, 52)
    fp = np.ones(shape, dtype=bool)
    fp[:2, :] = False
    vis = np.zeros(shape, dtype=bool)
    vis[12:36, 20] = True
    vis[20:40, 34] = True
    n_fp = int(fp.sum())

    rng = np.random.default_rng(87023)
    aux = {
        "cover_regime_fp": rng.uniform(0.0, 1.0, size=n_fp).astype(np.float32),
        "mag_sin2_fp": rng.normal(size=n_fp).astype(np.float32),
        "mag_cos2_fp": rng.normal(size=n_fp).astype(np.float32),
        "scarp_sin2_fp": rng.normal(size=n_fp).astype(np.float32),
        "scarp_cos2_fp": rng.normal(size=n_fp).astype(np.float32),
        "b18_fp": rng.normal(size=n_fp).astype(np.float32),
        "blind_hydro_fp": rng.uniform(0.0, 1.0, size=n_fp).astype(np.float32),
        "scarp_bridge_fp": rng.uniform(0.0, 1.0, size=n_fp).astype(np.float32),
    }
    mock_grid = SimpleNamespace(footprint=fp)
    feats, d_fp = stfd_features.compute_visible_structural_features(mock_grid, vis, aux)
    assert feats.shape == (n_fp, 16)
    assert d_fp.shape == (n_fp,)
    assert feats.dtype == np.float32
    assert np.isfinite(feats).all()

    prob = rng.uniform(0.01, 0.95, size=shape).astype(np.float32)
    dots = stfd_model.emit_expected_credit_dots(prob, fp & (~vis), n_dots=25, min_dist_px=2.83)
    assert dots.dtype == np.float32
    assert set(np.unique(dots).tolist()) <= {0.0, 1.0}
    assert 1 <= int(dots.sum()) <= 25
    assert int(dots[vis].sum()) == 0
    assert int(dots[~fp].sum()) == 0

    ys, xs = np.nonzero(dots > 0)
    if len(ys) >= 2:
        dy = ys[:, None] - ys[None, :]
        dx = xs[:, None] - xs[None, :]
        d2 = dy * dy + dx * dx + np.eye(len(ys)) * 1e6
        assert float(np.sqrt(d2.min())) >= 2.829
