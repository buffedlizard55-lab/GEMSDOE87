# Submission Handoff & Validation Receipts — Agent Brief v2

**Upload Rule:** The human competitor uploads **at most ONE `.tif` per slot** from their own registered DrivenData account (`releases/<id>.tif` = primary `NaN`-outside spec GeoTIFF matching `sample_submission.tif`; `releases/<id>-zeros.tif` = `0.0`-outside fallback twin with identical in-footprint dots). Parent `R0 = 0.2778` is **`CLAIM`** until a receipt is recorded in `ledger/submissions.csv` ([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

---

## Part S — `AXIS = SNAP` Variants (Built `2026-10-23`, Reproducible via `python3 scripts/build_snap_variants.py`)

**Parent `R0` Exact Byte-Level Rebuild & Input Receipt:** All `25` SHA-256 pins in `registry/data_manifest.json` verified on disk; `R0` rebuilt from `scored_h19_5` (`ec1f9b56…`) + `existing_faults.tif` (`7ba308cc…`) + `sample_submission.tif` (`2176d08e…`) via `dot_thin_geodesic_bfs(..., 2.8) & (d_cat > 2.0)` (`37,654` dots) with `deflate/predictor=3/zlevel=9/tiled=256`, matching `R0` **byte-for-byte** (`zeros` SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, `nan` SHA-256 `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd`). Zero external lidar rasters used (`training_features.tif` Bands `02`, `03`, `05`, `19` only; `IR-87-V2-07` verified `Band 05` is isotropic $|\nabla_H g|$ `r = +0.9619` whereas `Band 18` is directional $\partial g/\partial x$ `r = +0.9482`).

### S1. `SNAPscarp2` — Recommended `SNAP` Candidate (`<= 2 px` Cross-Strike RTP + Gravity + Scarp Crest, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPscarp2-20261023-065e17a9.tif` (`355,512 B`, sha256 `065e17a96674d997ed98e25fa93433c15e79e7bb06ccedd2e4a4868018c00cb9`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPscarp2-20261023-065e17a9-zeros.tif` (`219,348 B`, sha256 `b2098fa58fbabeb6ebc1e766c7c2138eba776cfc0337d5cdedab5ee5c47aeb2a`)
- **Name:** `h33-h33-2-b2-SNAPscarp2-20261023-065e17a9`
- **Note (121/140):** `h33-h33-2-b2; SNAP<=2px x-strike RTP+grav+scarp crest (n=37654, 36.03% chg, mean d=0.54px); pred +0.005 to +0.012 [MODEL]`
- **Displacement, Parent-diff & Format receipt:** `37,654` dots (`shared = 24,089`, `moved = 13,565`, **`36.03%` changed**), **mean displacement = `0.5390 px` (`53.9 m`) across all `37,654` dots** (`1.4961 px` / `149.6 m` across moved dots; `24,089` at `0 px`, `3,814` at `1 px`, `5,158` at `sqrt(2) px`, `4,593` at `2 px`; `max = 2.0000 px`), `min d_cat = 2.2361 px` (`> 2 px`, `0` on catalogue, identical exclusions to `R0`), `min sep = 2.8284 px` (`sqrt(8)`), `10 km CV` `0.6381 -> 0.6376`. Re-read verified: `scripts/validate_submission.py` `ready=true`, `errors=[]`; `gems57.validate` `all_checks_passed=true` on zeros.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* Range-front and piedmont normal faults dip `45°–60°` basinward, shifting subsurface magnetic/gravity gradients into the hanging wall while the mapped surface fault trace sits on the `100 m` topographic break-in-slope (`Band 19 det_elev_slope`); conversely, concealed basin faults lack relief and express only in RTP/gravity crests (`Bands 02 & 05`). Combining both aligns surface scarps and blind basin structures across [GeoDAWN's `400 m` line spacing](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7).
  - *Mechanism:* Compute `max(q_rtp_crest, q_grav_crest, q_scarp_crest)` via 1-D Blakely-Simpson Hessian ridge curvature $-\lambda_{\min}(\nabla^2 \log(1+G))$ strictly on organizer-provided `Bands 02, 05, 19` and snap each R0 dot `<= 2.0 px` cross-strike (`|\mathbf{u}\cdot\mathbf{n}_\perp| \ge 0.80`) when `q >= 0.80` and `Δq >= +0.10`, holding `n_dots = 37,654`, `d_cat > 2 px`, and `sqrt(8)` spacing fixed.
  - *Non-fault mimic:* Pleistocene Lake Lahontan wave-cut shorelines, incised fan-head trench walls, and erosional range-front facet spurs retreated `100–200 m` footwall-ward from the active piedmont fault trace.
  - *Predicted live change:* `+0.005` to `+0.012` [`MODEL`] vs. `R0` (`|Δ| < 0.01` = no evidence).
  - *Falsifier:* Live `RECEIPT` underperforms `SNAPrtp2` or `R0` by `>= 0.01`, proving footwall scarp retreat and pluvial shoreline terraces pull dots off true fault traces.

### S2. `SNAPrtp2` — Pure Subsurface Potential-Field Crest (`<= 2 px` Cross-Strike RTP + Gravity Crest, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPrtp2-20261023-3d8bcc8a.tif` (`355,217 B`, sha256 `3d8bcc8a47481ac2d2a7e7549d8c837ce2961bee1057ebbb0cb2206ba4048727`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPrtp2-20261023-3d8bcc8a-zeros.tif` (`218,983 B`, sha256 `58539675dcafc069d9b43f16232cbd17d8eb941c0beafec10c175e967031b79a`)
- **Name:** `h33-h33-2-b2-SNAPrtp2-20261023-3d8bcc8a`
- **Note (115/140):** `h33-h33-2-b2; SNAP<=2px x-strike RTP+grav crest (n=37654, 30.95% chg, mean d=0.48px); pred +0.004 to +0.011 [MODEL]`
- **Displacement, Parent-diff & Format receipt:** `37,654` dots (`shared = 26,001`, `moved = 11,653`, **`30.95%` changed**), **mean displacement = `0.4833 px` (`48.3 m`) across all `37,654` dots** (`1.5617 px` / `156.2 m` across moved dots; `26,001` at `0 px`, `2,288` at `1 px`, `4,814` at `sqrt(2) px`, `4,551` at `2 px`; `max = 2.0000 px`), `min d_cat = 2.2361 px`, `min sep = 2.8284 px`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* GeoDAWN's `400 m` flight-line gridding, unweighted BFS `dot_thin(2.8)` placement on the northern/western margin of `2–4 px` wide `H19-5` ribbons, and Nevada's `~64°` geomagnetic inclination leave `R0` dots `100–200 m` off steep subsurface contacts; snapping onto Reduced-to-Pole (`Band 02`) and isotropic gravity (`Band 05`) 1-D crests centers the `300 m` DTI kernel.
  - *Mechanism:* Snap each `R0` dot `<= 2.0 px` cross-strike onto `max(q_rtp_crest, q_grav_crest)` when `q >= 0.75` and `Δq >= +0.10` (`n = 37,654`, `d_cat > 2 px`, `min sep = sqrt(8)`).
  - *Non-fault mimic:* Unfaulted Tertiary volcanic flow margins, shallow dikes, and Miocene caldera ring contacts.
  - *Predicted live change:* `+0.004` to `+0.011` [`MODEL`] vs. `R0`.
  - *Falsifier:* Live `RECEIPT` drops `>= 0.01` below `R0`, showing `H19-5`'s smoothed multi-layer centerline sits closer to fault traces than subsurface RTP/gravity steps.

### S3. `SNAPtg2` — Raw `tmi_hg` + Gravity Crest Control (`<= 2 px` Cross-Strike `Band 03` + `Band 05`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPtg2-20261023-712c9309.tif` (`355,500 B`, sha256 `712c9309ed55dfc2229ab49d6c5864867fe59d1f03926ae6741ec3b2dac906c2`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPtg2-20261023-712c9309-zeros.tif` (`219,410 B`, sha256 `3294eb1e30fc008e8a8347509be50fb178dc2ec8793e426855fdfd14f28eaf1b`)
- **Name:** `h33-h33-2-b2-SNAPtg2-20261023-712c9309`
- **Note (118/140):** `h33-h33-2-b2; SNAP<=2px x-strike tmi_hg+grav crest (n=37654, 31.51% chg, mean d=0.49px); pred +0.002 to +0.008 [MODEL]`
- **Displacement, Parent-diff & Format receipt:** `37,654` dots (`shared = 25,791`, `moved = 11,863`, **`31.51%` changed**), **mean displacement = `0.4908 px` (`49.1 m`) across all `37,654` dots** (`1.5578 px` / `155.8 m` across moved dots; `25,791` at `0 px`, `2,350` at `1 px`, `4,943` at `sqrt(2) px`, `4,570` at `2 px`; `max = 2.0000 px`), `min d_cat = 2.2361 px`, `min sep = 2.8284 px`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* Direct control against `SNAPrtp2`: tests whether raw provided `tmi_hg` (`Band 03`) + `iso_grav_anom_slope` (`Band 05`) crests capture airborne gridding offsets without RTP transformation, or lose kernel credit due to `~100–250 m` southward dipolar TMI shift.
  - *Mechanism:* Identical operator, thresholds (`q >= 0.75`, `Δq >= +0.10`), `d_cat > 2 px`, and `sqrt(8)` spacing as `SNAPrtp2`, substituting `Band 03 (tmi_hg)` for `|\nabla_H(Band 02 rtp)|`.
  - *Non-fault mimic:* Oblique-inclination dipolar shift and remanently magnetized volcanic contacts plus E–W `400 m` flight-line corrugation.
  - *Predicted live change:* `+0.002` to `+0.008` [`MODEL`] vs. `R0`.
  - *Falsifier:* `SNAPtg2` beats `SNAPrtp2` by `>= +0.01` (`RECEIPT`), showing remanent magnetization invalidates constant-inclination RTP centering.

### S4. Report-Only `PROXY` Diagnostics (`SNAP` Session — Never Used as Gates)

- **Fold-proper hide-and-recover `PROXY`** (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives, Seeds 20 & 30, 95% CI): `R0` `0.097493 [0.0854, 0.1096]`, `SNAPtg2` `0.097543 [0.0860, 0.1092]`, `SNAPrtp2` `0.098233 [0.0863, 0.1099]`, **`SNAPscarp2` `0.100124 [0.0879, 0.1124]`** [`PROXY`].
- **Off-catalogue USGS SGMC control `PROXY`** (`62,122` bedrock fault px at `d_cat > 3 px`): `R0` `0.095386`, `SNAPtg2` `0.095416`, `SNAPrtp2` `0.096457`, **`SNAPscarp2` `0.096814`** [`PROXY`].
- **Leakage canary `PROXY`:** `23` provided + crest channels audited; max symmetric AUC = **`0.56883 <= 0.90`** (`0` flagged) [`PROXY`].

---

## Part A — `AXIS = PRUNE` Variants (Prior Session in `ledger/submissions.csv`)

### A1. `PRUNE3` — Recommended Slot 1 (`d_cat > 3.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c.tif` (`354,515 B`, sha256 `bc00a06c51ddabce568401702b8b8446919665979b17555e859f66e1fed13e82`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c-zeros.tif` (`218,052 B`, sha256 `482e21662dd99b9b33ca16b4627d6dadb81dc0892323ba85fbecf0332cf01876`)
- **Name:** `h33-h33-2-b2-PRUNE3-20261023-bc00a06c`
- **Note (122/140):** `h33-h33-2-b2; PRUNE<=3px (2171 collar dots refilled on H19-5 by DTI dT, n=37654, 5.77% chg); pred +0.005 to +0.012 [MODEL]`
- **Parent-diff & Format receipt:** `37,654` dots (`shared = 35,483`, `removed = 2,171`, `added = 2,171`, **`5.77%` changed**), `min d_cat = 3.1623 px` (`>= 3 px`), `min sep = 2.2361 px` (`sqrt(5)`), `0` on catalogue (`ready=true`, `all_checks_passed=true`).

### A2. `PRUNE1` — Conditional Inward Collar Control (`d_cat > 1.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c.tif` (`355,668 B`, sha256 `4679d91c5426a46ed813d680095175805851d158075304118fa2ff90c8485049`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c-zeros.tif` (`219,324 B`, sha256 `b3b1e75b82f1ac418902aa3ac4fecbe517ca429b4eac0794cb43e487761b7b2a`)
- **Name:** `h33-h33-2-b2-PRUNE1-20261023-4679d91c`
- **Note (125/140):** `h33-h33-2-b2; PRUNE<=1px (restore 2545 1-2px dots, drop 2545 weak R0 dots, n=37654, 6.76% chg); pred -0.012 to -0.005 [MODEL]`

### A3. `PRUNE4` — Conditional GeoDAWN 400 m Halo Probe (`d_cat > 4.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782.tif` (`353,609 B`, sha256 `f5c5378214120a58ae3bd04cf74d75fe7722b19bd6a47d0b463e909d964a9895`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782-zeros.tif` (`217,405 B`, sha256 `16539fac84c71b8c0e8d7769b8bb7be9a74128febc44e870c9c82ac0ad7d48d3`)
- **Name:** `h33-h33-2-b2-PRUNE4-20261023-f5c53782`
- **Note (123/140):** `h33-h33-2-b2; PRUNE<=4px (3825 collar dots refilled on H19-5 by DTI dT, n=37654, 10.16% chg); pred -0.004 to +0.006 [MODEL]`

---

## Part B — `AXIS = CONCENTRATION` Variants (Prior Session in `ledger/submissions.csv`)

### B1. `CONCc10` (`10.00%` relocated across 1 km blocks, `2 px` collar inherited)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab.tif` (sha256 `a9e67bab4ab3ddc01027383ba47f8febc6232e0c8bd42ba62cc4e782737c84ec`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab-zeros.tif` (sha256 `c79400032488ed92002f897a078b8143272f35787e843f179073aab686dae6f0`)
- **Name:** `h33-h33-2-b2-CONCc10-20261023-a9e67bab`
- **Note (81/140):** `h33-2-b2 CONCc10 37654 move10% lo->hi 1km; pred +0.004 MODEL; parent 0.2778 CLAIM`

### B2. `CONCc15` (`15.00%` relocated)

- **File:** `releases/h33-h33-2-b2-CONCc15-20261023-25e403d0.tif` (sha256 `25e403d041015ff95789a07187df47b18c7e2d33f4011833612597699324b6d5`)
- **Fallback:** `releases/h33-h33-2-b2-CONCc15-20261023-25e403d0-zeros.tif` (sha256 `d632f28b50b0fec93392ce2849cb3e8003a40499ca4d7f3ea33f2fa752d81ddc`)
- **Name:** `h33-h33-2-b2-CONCc15-20261023-25e403d0`
- **Note (81/140):** `h33-2-b2 CONCc15 37654 move15% lo->hi 1km; pred +0.002 MODEL; parent 0.2778 CLAIM`

### B3. `CONCc20` (`20.00%` relocated)

- **File:** `releases/h33-h33-2-b2-CONCc20-20261023-03244051.tif` (sha256 `03244051b856f952a24919c5e9af050a6d33495c2bbfd853c695ea1dd3330c1f`)
- **Fallback:** `releases/h33-h33-2-b2-CONCc20-20261023-03244051-zeros.tif` (sha256 `a9b0a226404ca91f34f91026313a68a0b168728481bf0eb9b8f7b3bb7ad6fb2f`)
- **Name:** `h33-h33-2-b2-CONCc20-20261023-03244051`
- **Note (81/140):** `h33-2-b2 CONCc20 37654 move20% lo->hi 1km; pred -0.006 MODEL; parent 0.2778 CLAIM`
