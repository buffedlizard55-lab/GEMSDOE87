# Three-Pass Implementation, Restoration & Verification Log — GEMSDOE87

**Review Date:** 2026-10-22 UTC.
**Branch:** `arena/03ae521e-gemsdoe87`.
**Method Lane:** `H87-CMGEP` (Cross-Scale Paired Magnetic–Gravity–Conductivity Edge Persistence with Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300 m Kernel Emission).

---

## Pass 1 — Full Data/Template Restoration, Byte-Level Forensics & Pipeline Implementation

1. **Shared Template & Pinned Data Restoration (`IR-87-03` resolved):**
   - Restored all 23 modules of `vendor/gems57/` (`evaluate_holdout.py` v2, `holdout.py`, `metric.py`, `submission_writer.py`, `uniqueness.py`, `validate.py`, `grid.py`, `gates.py`, etc.) and `registry/data_manifest.json` from `buffedlizard55-lab/57GEMSDOE`.
   - Restored all 23 SHA-256-pinned competition, external, and historical scored files (`training_features.tif`, `existing_faults.tif`, `labels.tif`, `sample_submission.tif`, `lidar_scarp_features_u8.tif`, `geodawn_rad_u8.tif`, `geodawn_extensions_u8.tif`, `derived_sgmc_faults_100m_u8.tif`, GDR CSVs, and historical scored GeoTIFFs) from `buffedlizard55-lab/GEMSDOE24` (`gems-data-v1` release) into `.cache/raw/`, verifying every SHA-256 hash (`data/restore_receipt.json`).
   - Scanned all 87 public `GEMSDOE*` repositories (`999` `.tif` records in `registry/inventory.json`) and curated `202` grid-verified canonical deduplicated GeoTIFFs into `.cache/raw/scored/` (`registry/canonical_scored_index.json`).
2. **Byte-Level Forensic Proof of `GEMSDOE32` (`h33-2-b2-zeros.tif`, `0.2778`):**
   - Inspected `GEMSDOE25__dotted-h19-5-d2-8.tif` (`44,090` dots, `0.2647`), `GEMSDOE28__h27-4-r1-solo-d2-8.tif` (`40,199` dots, `0.2683`), and `GEMSDOE32__h33-2-b2-zeros.tif` (`37,654` dots, `0.2778`) directly against `existing_faults.tif`.
   - Proved via `np.array_equal` that `p28 == p25 & (d_cat > 1.0)` and `p32 == p25 & (d_cat > 2.0)` across all `12,279,160` cells, and derived the exact DTI denominator contraction ($\Delta\text{FP}_w = -6,436$, $\alpha\,\Delta\text{FP}_w = -1,287.2$) and $300\text{ m}$ kernel reach mechanism in [`docs/score-claim-audit.md`](score-claim-audit.md).
3. **Implementation of Lane `H87-CMGEP` (`src/gems87/`):**
   - Implemented the 92-channel streaming feature pipeline (`src/gems87/features.py`): 60 core physical/geothermal/radiometric/1m-LiDAR channels + 8 novel `H87-CMGEP` physical persistence channels + 18 fold-proper visible-catalogue structural-relay channels + 6 H87 physical-structural coupling channels.
   - Implemented the Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300 m Kernel Emitter (`src/gems87/dinkelbach_emitter.py`) and end-to-end 3-experiment driver (`scripts/run_h87_cmgep_pipeline.py`).

---

## Pass 2 — Bug Hunting, Edge Cases, Memory/Runtime Audits & Fixes

During Pass 2, six non-trivial engineering and statistical issues were caught and fixed before finalizing the promotion run:

1. **Container Memory Limit (`3.8 GiB`) During Feature Build (`src/gems87/features.py`):**
   - *Bug caught:* Holding 16 full `(3730, 3292)` `float32` bands (~786 MB) simultaneously with 24 structure-tensor arrays (~1.18 GB) and the output memmap (~703 MB) exceeded the 3.8 GiB container limit (`exit_code: -1`).
   - *Fix:* Rewrote `load_or_build_rowmajor_f16` to stream band-by-band and scale-by-scale directly into `1D` `[footprint]` slices (`max_rss = 1987 MB`).
2. **Non-Grid Test Fixtures in Harvested `.cache/raw/scored/` (`IR-87-04`):**
   - *Bug caught:* Two harvested `.tif` files (`GEMSDOE36__GEMS36_FORMAT_TEST_NOT_SUBMISSION.tif` with shape `32 x 48` and `14GEMSDOE__..._site_e96e942f.tif` with cropped transform) were non-grid fixtures that caused `ValueError` in `vendor/gems57/uniqueness.py`.
   - *Fix:* Audited every `.tif` against `(3730, 3292)`, `EPSG:32611`, and the reference affine transform, unlinking the 2 fixtures and retaining all `202` grid-verified canonical rasters in `registry/canonical_scored_index.json`.
3. **Space-Filling Registry Rasters (`halo_coverage >= 0.70`, `IR-87-05`):**
   - *Bug caught:* Six historical rasters in `.cache/raw/scored/` (`13GEMSDOE` r11/r13, `15GEMSDOE` curv_scarp, etc.) have 3-px dilated halos covering `72.45%` to `100.00%` of the footprint, firing any literal overlap gate on every non-empty submission.
   - *Fix:* Annotated `registry/canonical_scored_index.json` with exact `halo_coverage` and `representation_v2` (`196` `discriminating`, `6` `space_filling`) matching `vendor/gems57/uniqueness.py` (`binding_duplicate_decision`), and replaced slow `cKDTree` queries with 2D `scipy.ndimage.binary_dilation` (`disk` radius 3 px) inside `_build_candidate_halo_matrix` (`8s` vs `>1500s`).
4. **LOQO Inter-Quadrant Tail-Scale Drift (`seed20_NE`, `IR-87-06`):**
   - *Bug caught:* Raw `predict_proba` outputs across the 4 Leave-One-Quadrant-Out models exhibited tail compression in `seed20_NE` (`q=1`), starving `seed20_NE` to `11`–`33` dots under a global threshold.
   - *Fix:* Added label-blind `_quadrant_quantile_match` (`q_blend = 0.70`) inside `emit_dinkelbach_submodular_300m`, restoring `4,931` emitted dots and `HOLDOUT-DTI = 0.145116` in `seed20_NE`.
5. **Truncated 43-Channel Specialist vs. Full 92-Channel Ensemble:**
   - *Bug caught:* An initial 43-channel specialist subset underperformed the 78-channel core model because it omitted 49 physical and relay features.
   - *Fix:* Trained the full 92-channel LightGBM model (`colsample_bytree = 0.88`) and ensembled it with the 78-channel core model (`0.60 * oof_92 + 0.40 * oof_78`), achieving strict monotonic improvement across all 6 ablation arms (`A0 = 0.0040 < A1 = 0.0411 < A2 = 0.0817 < A3 = 0.1641 < A4 = 0.1649 < A5 = 0.1716`).
6. **Sequential Arm Evaluation in `EXP-87-2` (`scripts/run_h87_cmgep_pipeline.py`):**
   - *Bug caught:* Holding all 6 `preds_a0..preds_a5` (`12 x 49.1 MB = 590 MB`) simultaneously alongside `draws_by_seed` (`400 MB`) and `mmap` arrays (`1.38 GB`) hit the container memory limit.
   - *Fix:* Evaluated one arm at a time into its `12 KB` `(380, 4)` `terms` array and freed the 2D prediction rasters immediately (`EXP-87-2` runtime `297.2s`, `exit_code: 0`).

---

## Pass 3 — Final Verification Against All Prompt Requirements & Readiness Gates

- **GeoTIFF Deliverable & Dual Validator Verification:**
  - Primary artifact `downloads/h87-h87-cmgep-20261022T060000Z-8f394f43.tif` (`1,586,840 B`, SHA-256 `1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69`, `NaN` outside footprint) passes `scripts/validate_submission.py` (`ready = true`, `errors = []`).
  - Companion artifact `downloads/h87-h87-cmgep-20261022T060000Z-6e2c741a-zeros.tif` (`131,577 B`, SHA-256 `f6833b831d91618577f73522f4a269f1f878a982cc38ba2bbb27d942396b2403`, `0.0` outside footprint) passes `vendor/gems57/validate.py` (`all_checks_passed = true`).
- **Parallel-Run Protocol Gates:**
  - Single-feature leakage canary (`EXP-87-1`): `max_symmetric_auc = 0.78230 <= 0.90` (`0` flagged channels).
  - Spatially-blocked holdout (`EXP-87-2`): `HOLDOUT-DTI = 0.171555` (`95% CI [0.154922, 0.187832]`, `gems57-pooled-hide-v2`, `22,663` withheld positives), beating all 5 controls with strictly positive 95% paired bootstrap confidence intervals.
  - 202-raster registry uniqueness (`EXP-87-3`): `worst |rho_S| = 0.61814` (surface) / `0.03977` (dots) `<= 0.90`, `worst 3-px overlap across 196 discriminating priors = 0.62000 <= 0.70`, `duplicate = false`, `byte_unique = true`, `pixel_unique = true`.
  - Budget: `3 / 3` experiments used (`26.4 min < 120 min`).
- **GitHub Pages Site & Automated Tests:**
  - Updated `README.md`, `index.html`, `executive-summary.html`, `research.html`, `sources.html`, `data/run-card.json`, `data/submission-status.json`, `data/sources.json`, `data/feed.json`, and `tests/test_site.py`.
  - Verified all unit and integration tests via `pytest`, verified `git status` and `.gitignore` exclusions for `.cache/`, and merged pull request onto `main`.

---

## Unified Multi-Session Audit Summary (2026-10-23)

 Scientific & Engineering Review (Passes 1–3)

- **Pass 1 (Implement & Execute):** Restored SHA-256-verified competition + public USGS/DOE rasters and `34` cross-repo prediction rasters; discovered `IR87-028` (`Band 06 = GeoDAWN TC`, `r = +0.997140`), `IR87-029` (`Bands 10 & 16` swarm/background density), `IR87-030` (Session 1 `B02/B19/B08` swap), and `IR87-031` (`GEMSDOE32` reverse label self-masking); trained all `12/12` out-of-fold workers (`comp:0..7` + `quad:0..3`) and generated `gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.{tif,zip,json}`.
- **Pass 2 (Edge Cases & Calibration Audit):** Replaced single-head `m3` placement with leak-free dual-head `0.55 * logit(m3) + 0.45 * logit(m1)` fusion (`3,058` frontier dots `> 2.5 km`, `LOQO-Comp = 0.138160` vs `H33_2_B2_fold_fair = 0.097493`, `Spatial-4Q = 0.133386` vs `EXP2 = 0.121746`), fixed un-zeroed `bmtd_dots` comparison, and fixed `IR87-033` hardcoded date in `scripts/update_feed.py`.
- **Pass 3 (Full Prompt Reconciliation):** Confirmed both `H87B-STFD` (`1d3f50ffd13f`) and frozen `H87-BMTD-01` (`50041440adba`) are clearly presented at the top of `docs/index.html`, `docs/executive-summary.html`, and `README.md` with unmistakable `DO NOT SUBMIT` badges, complete `HOLDOUT-DTI` CIs, `31/31` real fault-candidate uniqueness + `3` dense witness disclosure, embedded figures, and full `pytest` + Chromium smoke coverage.
