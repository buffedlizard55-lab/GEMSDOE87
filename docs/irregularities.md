# Irregularities, Failure Modes & Methodological Audit (`GEMSDOE87`)

Every irregularity encountered in the official data, sibling `GEMSDOE*` repositories, shared `vendor/gems57` tooling, and competition submission format is explicitly logged below with measured quantitative evidence. Nothing is silently patched or hidden.

---

## `IR-87-01` — Unverified Owner-Ledger Live Leaderboard Numbers (`0.2778`, `0.2708`, `0.2600`, `0.3195`, `0.4413`)
- **Finding:** Neither `GEMSDOE87` nor any sibling repository contains cryptographic organizer receipts or portal API exports verifying reported live scores (`0.2778` for `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`, `0.2708` for `H27-4`, `0.2600` for `D2.8`, `0.4413` public top).
- **Resolution:** Strict adherence to Parallel-Run Protocol Rule 3: every score produced here is labeled **`HOLDOUT-DTI`** (`evaluator_version = "gems57-pooled-hide-v2"`, `n = 22,663`, 2,000-draw 95% block-bootstrap CI). Organizer scores for prior sibling runs are labeled strictly as *User-Reported / Unverified Owner-Ledger Claims*, and `organizer_confirmed_scores.candidate_gems87_csct_dink300 = null` (`UNSCORED`). Zero projections are reported as scores.

---

## `IR-87-02` — Root Cause of Prior `"Predicted values must be in range [0, 1]"` Upload Failure & Dual GeoTIFF Packaging
- **Finding:** `data/sample_submission.tif` contains `5,167,373` valid study-area cells and `7,111,787` exterior cells encoded as `NaN` (`nodata = NaN`), whereas downstream portal/NumPy validators checking `np.all((arr >= 0.0) & (arr <= 1.0))` without `np.isnan` masking evaluate to `False` whenever any `NaN` or out-of-range sentinel (`-9999.0`, `-3.4e38`) is present. Conversely, setting `nodata = 0.0` causes `rasterio.read(1, masked=True)` to mask legitimate `0.0` background predictions *inside* the study footprint.
- **Resolution:**
  1. **Primary Submission (`downloads/gems87-csct-dink300-37654dots-20261022-zeros.tif` + `.zip`):** Written via unmodified `vendor/gems57/submission_writer.py` with `nodata = None`, exact `0.0` on all `7,111,787` exterior cells, and `{0.0, 1.0}` `float32` on all `5,167,373` interior cells (`n_nan = 0`, `n_inf = 0`, `min = 0.0`, `max = 1.0`, matching the exact GeoTIFF header of `h33-h33-2-b2-...-zeros.tif`). Passes `14 / 14` checks in `vendor/gems57/validate.py` AND `scripts/validate_submission.py --allow-zero-exterior`.
  2. **Companion Reference-Mask Artifact (`downloads/gems87-csct-dink300-37654dots-20261022-nan.tif`):** Identical `37,654` binary interior dots with exact `NaN` exterior (`nodata = NaN`) matching `data/sample_submission.tif` cell-for-cell. Passes `scripts/validate_submission.py` in strict default mode (`ready = True, errors = []`).

---

## `IR-87-03` — Pigeonhole Proof on Sparse Space-Covering Lattices in `vendor/gems57/uniqueness.py` (`calib_r13lattice_00904.tif`)
- **Finding:** Upstream `vendor/gems57/uniqueness.py:representation_class` classifies any raster with `support_fraction <= 0.20` (`<= 1,033,474` positive cells) as `"dot_field"`. However, scanning all `858` files (`476` unique SHA-256 digests) uncovered **`60GEMSDOE__registry__rasters__calib_r13lattice_00904.tif`**, a synthetic regular $5 \times 5$ lattice with only `206,895` positive pixels (`support_fraction = 0.040039 <= 0.20`). Because every integer grid cell $(y, x) \in \mathbb{Z}^2$ lies within $\sqrt{2^2 + 2^2} = \sqrt{8} = 2.828427 < 3.0\text{ px}$ of $(5i, 5j)$, its `3.0 px` Euclidean halo covers **`5,099,871 / 5,106,385` (`99.8724%`)** of the entire allowed study area of Nevada, leaving only **`6,514` boundary cells** uncovered.
- **Mathematical Proof (Pigeonhole Principle):** For **every** candidate binary subset $S \subseteq \text{allowed}$ of size $|S| = 37{,}654$:
  $$\text{overlap}_{3\text{px}}(S, R_{5\times 5}) \ge \frac{37{,}654 - 6{,}514}{37{,}654} = \frac{31{,}140}{37{,}654} = \mathbf{0.827004 > 0.70}.$$
  Likewise, `gems61-...-k400k-b2zeros.tif` (`311,617` pixels, `cov = 0.969626`), `r14_union_tips10_lat6.tif` (`cov = 0.762115`), `r11_greedy_mp.tif` (`cov = 0.736623`), and raw feature raster `geodawn_dem_a2_100m.tif` (`cov = 0.999974`) cover `>= 73.7%` of all Nevada allowed terrain for uniform random pixels.
- **Resolution:** Zero lines of `vendor/gems57/uniqueness.py` were forked (`13 / 13` template SHA-256 hashes verified intact). `evidence/uniqueness_audit_full.json` reports both the unmodified `vendor_two_phase_summary` AND explicit `pigeonhole_space_covering_certificates` for all `12` space-covering priors (`cov_allowed >= 0.70`), while strictly enforcing **`my_dots_within_3px_of_theirs <= 0.650 < 0.70` across ALL `464 / 464` non-space-covering rasters (`0` overlap violations; `max_forward_3px_overlap = 0.649997`)**.

---

## `IR-87-04` — Incomplete Registry Scans in Recent Sibling Repositories (`GEMSDOE81` & `GEMSDOE83`)
- **Finding:** Direct inspection of sibling Run Cards revealed that `GEMSDOE81` (`CONT`) audited overlap against only **5 local rasters** (missing `GEMSDOE67`'s `167,597`-dot collar raster where `CONT`'s `100%` near-catalogue ring has **`> 0.96` forward overlap**), and `GEMSDOE83` (`H83-GVCD`) packed halos for only the **29 files in `data/scored/`** rather than all `858` sibling files across `buffedlizard55-lab`. Furthermore, `CONT` placed **`0` dots at `d_cat > 10 px`** (`0%` blind fault coverage), exploiting buffered component holdout geometry where withheld segments connect to visible segments.
- **Resolution:** `GEMSDOE87` built a full bit-packed 3-px halo index across **all `476` unique SHA-256 rasters on disk (`858` files across 93 repositories)**, achieving **`0 / 464` discriminating overlap firings (`max = 0.649997 <= 0.70`)** AND allocating `12,732` dots (`33.8%` of budget) outside `1 km` (`10,474` in `1–3 km` piedmont step-overs + `2,258` in `> 3 km` detached blind basins).

---

## `IR-87-05` — Exact 25-Pixel Support of the 300 m Triangular Evaluation Kernel
- **Finding:** On a `100 m` grid, diagonal offsets $(\pm 2, \pm 2)$ have Euclidean distance $\sqrt{8}\times 100\text{ m} = 282.84\text{ m} < 300\text{ m}$, giving positive kernel weight $1 - \sqrt{8}/3 = 0.057191 > 0$. Approximations truncating $B_{300\text{m}}$ to a 21-pixel cross omit `4` corner cells per dot.
- **Resolution:** `src/gems87/model.py:KERNEL_300M` uses all **25 exact cells** of $\{-2,-1,0,1,2\}^2$, identical to `vendor/gems57/metric.py`.

---

## `IR-87-06` — Non-Uniform USGS 3DEP 1 m LiDAR Coverage & Relief Bias
- **Finding:** High-resolution `1 m` LiDAR covers only a subset of Nevada ranges/basins and raw slope saliency concentrates `>75%` of rankings on steep pre-Quaternary bedrock cliffs rather than low-relief Quaternary basin-margin scarps.
- **Resolution:** Divisive 2.5 km relief normalization (`f03..f10`), explicit LiDAR coverage indicator + cross-physics fallback to 100 m DEM/gravity/GeoDAWN/MT where LiDAR is absent, and exact per-quadrant log-odds Bayes calibration (`NW: 8,870`, `NE: 11,491`, `SW: 9,824`, `SE: 7,469`).

---

## `IR-87-07` — Original Static Site Deployment Omitted `downloads/` & `evidence/`
- **Finding:** `.github/workflows/pages.yml` previously assembled `_site/` without copying `downloads/` or `evidence/`, which would have caused HTTP `404` on deployed download links once a validated submission was promoted.
- **Resolution:** Fixed `.github/workflows/pages.yml` to copy both `downloads/` and `evidence/` into `_site/`, updated `.gitignore` to allow validated `downloads/*.zip` alongside `downloads/*.tif`, and added automated link-target existence checks in `tests/test_site.py`.
