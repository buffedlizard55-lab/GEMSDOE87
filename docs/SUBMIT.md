# Submission Handoff & Validation Receipts — Agent Brief v2

**Upload Rule:** The human competitor uploads **at most ONE `.tif` per slot** from their own registered DrivenData account (`releases/<id>.tif` = primary `NaN`-outside spec GeoTIFF matching `sample_submission.tif`; `releases/<id>-zeros.tif` = `0.0`-outside fallback twin with identical in-footprint dots). Parent `R0 = 0.2778` is **`CLAIM`** until a receipt is recorded in `ledger/submissions.csv` ([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

---

## Part A — `AXIS = PRUNE` Variants (Built `2026-10-23`, Reproducible via `python3 scripts/build_prune_variants.py`)

**Parent `R0` Exact Byte-Level Rebuild Receipt:** Rebuilt from SHA-256-verified `registry/data_manifest.json` (`scored_h19_5` `ec1f9b56…` + `existing_faults.tif` `7ba308cc…` + `sample_submission.tif` `2176d08e…`) via `dot_thin_geodesic_bfs(..., 2.8) & (d_cat > 2.0)` (`37,654` dots) with `deflate/predictor=3/zlevel=9/tiled=256`, matching `R0` **byte-for-byte** (`zeros` SHA-256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, `nan` SHA-256 `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd`).

### A1. `PRUNE3` — Recommended Slot 1 (`d_cat > 3.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c.tif` (`354,515 B`, sha256 `bc00a06c51ddabce568401702b8b8446919665979b17555e859f66e1fed13e82`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c-zeros.tif` (`218,052 B`, sha256 `482e21662dd99b9b33ca16b4627d6dadb81dc0892323ba85fbecf0332cf01876`)
- **Name:** `h33-h33-2-b2-PRUNE3-20261023-bc00a06c`
- **Note (122/140):** `h33-h33-2-b2; PRUNE<=3px (2171 collar dots refilled on H19-5 by DTI dT, n=37654, 5.77% chg); pred +0.005 to +0.012 [MODEL]`
- **Parent-diff & Format receipt:** `37,654` dots (`shared = 35,483`, `removed = 2,171`, `added = 2,171`, **`5.77%` changed**), `min d_cat = 3.1623 px` (`>= 3 px`), `min sep = 2.2361 px` (`sqrt(5)`), `10 km CV` `0.6381 -> 0.6571` (`15 km CV` `0.5162 -> 0.5332`), `0` on catalogue. Re-read verified: `scripts/validate_submission.py` `ready=true`, `errors=[]`; `gems57.validate` `all_checks_passed=true` on zeros.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* Dots in `200–300 m` (`2 < d <= 3 px`) around mapped USGS/INGENIOUS Quaternary faults sit inside the known-fault potential-field/scarp halo where new-fault density is low, while dots at `d >= 3.16 px` (`316 m`) still project `300 m` kernel credit inward onto splay junctions ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)).
  - *Mechanism:* Delete `2,171` R0 dots in `2 < d_cat <= 3 px` (eliminating up to `0.2 * 2,171 = 434.2` denominator FP units) and refill `2,171` dots onto uncovered `H19-5` ridge gaps (`d_cat > 3 px`) ranked by exact sequential DTI marginal gain `dT` (`2.86` down to `0.88` kernel units).
  - *Non-fault mimic:* Off-collar `H19-5` lineaments along Tertiary volcanic dike margins, caldera ring fractures, or fluvial terrace risers.
  - *Predicted live change:* `+0.005` to `+0.012` [`MODEL`] vs. `R0` (`|Δ| < 0.01` = no evidence).
  - *Falsifier:* Live `RECEIPT` drops `>= 0.01` below `R0`, proving re-mapped strands of existing systems ([forum #11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) concentrate inside `200–300 m`.

### A2. `PRUNE1` — Conditional Inward Collar Control (`d_cat > 1.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c.tif` (`355,668 B`, sha256 `4679d91c5426a46ed813d680095175805851d158075304118fa2ff90c8485049`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c-zeros.tif` (`219,324 B`, sha256 `b3b1e75b82f1ac418902aa3ac4fecbe517ca429b4eac0794cb43e487761b7b2a`)
- **Name:** `h33-h33-2-b2-PRUNE1-20261023-4679d91c`
- **Note (125/140):** `h33-h33-2-b2; PRUNE<=1px (restore 2545 1-2px dots, drop 2545 weak R0 dots, n=37654, 6.76% chg); pred -0.012 to -0.005 [MODEL]`
- **Parent-diff & Format receipt:** `37,654` dots (`shared = 35,109`, `removed = 2,545`, `added = 2,545`, **`6.76%` changed**), `min d_cat = 1.4142 px`, `min sep = 2.8284 px`, `10 km CV` `0.6381 -> 0.6286`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* Separates `solo-d28 -> R0`'s `-2,545` dot mass reduction from its `1–2 px` collar deletion at fixed `37,654` count.
  - *Mechanism:* Restore all `2,545` `d28` parent dots in `1 < d_cat <= 2 px` and remove the `2,545` lowest exact LOO DTI marginal-loss dots of `R0` (`dT_loss <= 1.0`, isolated 1-px speckles).
  - *Non-fault mimic:* `1:24k`/`1:100k` fault-line digitization offset relative to the `100 m` DEM/TMI scarp crest (`100–200 m` lateral offset beside a single known strand).
  - *Predicted live change:* `-0.012` to `-0.005` [`MODEL`] vs. `R0`.
  - *Falsifier:* Live `RECEIPT` rises `>= +0.01` over `R0`, showing `100–200 m` flanks host dense newly mapped fault geometry.

### A3. `PRUNE4` — Conditional GeoDAWN 400 m Halo Probe (`d_cat > 4.0 px`, Fixed `37,654` Dots)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782.tif` (`353,609 B`, sha256 `f5c5378214120a58ae3bd04cf74d75fe7722b19bd6a47d0b463e909d964a9895`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782-zeros.tif` (`217,405 B`, sha256 `16539fac84c71b8c0e8d7769b8bb7be9a74128febc44e870c9c82ac0ad7d48d3`)
- **Name:** `h33-h33-2-b2-PRUNE4-20261023-f5c53782`
- **Note (123/140):** `h33-h33-2-b2; PRUNE<=4px (3825 collar dots refilled on H19-5 by DTI dT, n=37654, 10.16% chg); pred -0.004 to +0.006 [MODEL]`
- **Parent-diff & Format receipt:** `37,654` dots (`shared = 33,829`, `removed = 3,825`, `added = 3,825`, **`10.16%` changed**), `min d_cat = 4.1231 px`, `min sep = 2.2361 px`, `10 km CV` `0.6381 -> 0.6752`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism Card (Structural Geologist):**
  - *Hypothesis:* Tests whether GeoDAWN Area 2's `400 m` flight-line spacing ([USGS GeoDAWN](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) smears known-fault potential-field halos to `4 px`, or whether pruning past `R = 300 m` cuts into hanging-wall synthetic splays and relay ramps.
  - *Mechanism:* Delete `3,825` R0 dots in `2 < d_cat <= 4 px` and refill `3,825` dots onto uncovered `H19-5` ridge gaps (`d_cat > 4 px`) by exact DTI marginal gain `dT` (`3.45` down to `0.75`).
  - *Non-fault mimic:* Airborne minimum-curvature gridding shoulders (`300–400 m`) beside a single steep range-front fault.
  - *Predicted live change:* `-0.004` to `+0.006` [`MODEL`] vs. `R0` (diminishing return past `R = 300 m`).
  - *Falsifier:* `PRUNE4` beats `PRUNE3` by `>= +0.01` (`RECEIPT`).

### A4. Report-Only `PROXY` Diagnostics (`PRUNE` Session — Never Used as Gates)

- **Fold-proper hide-and-recover `PROXY`** (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives, Seeds 20 & 30, 95% CI): `PRUNE1` `0.091880 [0.0811, 0.1031]`, `R0 (PRUNE2)` `0.095962 [0.0843, 0.1076]`, `PRUNE3` `0.095412 [0.0835, 0.1076]`, `PRUNE4` `0.094483 [0.0822, 0.1065]` [`PROXY`].
- **Off-catalogue USGS SGMC control `PROXY`** (`62,122` bedrock fault px at `d_cat > 3 px`): `PRUNE1` `0.091757`, `R0` `0.095386`, **`PRUNE3` `0.096085`**, `PRUNE4` `0.094560` [`PROXY`].
- **Leakage canary `PROXY`:** `40` raw/external/parent channels audited; max symmetric AUC = **`0.60217 <= 0.90`** (`0` flagged) [`PROXY`].

---

## Part B — `AXIS = CONCENTRATION` Variants (Prior Session in `ledger/submissions.csv`)

### B1. `CONCc10` (`10.00%` relocated across 1 km blocks, `2 px` collar inherited)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab.tif` (sha256 `a9e67bab4ab3ddc01027383ba47f8febc6232e0c8bd42ba62cc4e782737c84ec`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab-zeros.tif` (sha256 `c79400032488ed92002f897a078b8143272f35787e843f179073aab686dae6f0`)
- **Name:** `h33-h33-2-b2-CONCc10-20261023-a9e67bab`
- **Note (81/140):** `h33-2-b2 CONCc10 37654 move10% lo->hi 1km; pred +0.004 MODEL; parent 0.2778 CLAIM`
- **Format receipt:** `37,654` dots, `10.00%` changed, `CV_occ` `0.619 -> 0.748`, `min sep` `sqrt(8)`, `min d_cat` `2.236`, `0` on catalogue (`ready=true`, `all_checks_passed=true`).

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
