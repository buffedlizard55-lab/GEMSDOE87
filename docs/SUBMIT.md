# Submission Handoff & Validation Receipts — Agent Brief v2 (`AXIS = PRUNE` on `R0`)

**Generated:** 2026-10-23 UTC · **Reproducible Builder:** `python3 scripts/build_prune_variants.py` (`FIXED_SEED = 0`, deterministic row-major tie-break).
**Upload Rule:** The human competitor uploads **at most ONE `.tif` per slot** from their own registered DrivenData account (`releases/<id>.tif` is the primary `NaN`-outside spec GeoTIFF matching `sample_submission.tif`; `releases/<id>-zeros.tif` is the `0.0`-outside fallback twin with identical in-footprint dots). Never upload both twins — they score identically ([official problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

---

## 0. Parent `R0` (`h33-h33-2-b2`, `GEMSDOE32`) Exact Byte-Level Rebuild Receipt

Rebuilt strictly from SHA-256-verified `registry/data_manifest.json` pins (`23/23` verified in `.cache/raw/`):
- `scored_h19_5`: `ec1f9b56b83ce33cad781ceb9f104b18fb4f2ff785263a4e89616af4aabdee8d` (`121,131` ridge px)
- `existing_faults.tif` / `labels.tif`: `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` (`60,988` fault px)
- `sample_submission.tif`: `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` (`5,167,373` footprint px)
- Deterministic recipe: `dot_thin_geodesic_bfs((h19_5 > 0) & foot & ~catalogue, 2.8) & (d_cat > 2.0)` → **`37,654` unit-mass dots**.
- Rebuilt `R0` `-zeros.tif` SHA-256: `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` (**EXACT MATCH**)
- Rebuilt `R0` `-nan.tif` SHA-256: `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd` (**EXACT MATCH**)
- Historical score status: **`0.2778` [`CLAIM`]** (remains `CLAIM` until a DrivenData submission-page receipt is recorded in `ledger/submissions.csv`).

---

## 1. Variant 1 (Recommended Slot 1) — `PRUNE3` (`d_cat > 3.0 px`, Fixed `37,654` Dots)

- **Primary Spec GeoTIFF (`NaN` outside footprint):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c.tif` (`354,515 B`, SHA-256 `bc00a06c51ddabce568401702b8b8446919665979b17555e859f66e1fed13e82`)
- **Fallback GeoTIFF (`0.0` outside footprint):** `releases/h33-h33-2-b2-PRUNE3-20261023-bc00a06c-zeros.tif` (`218,052 B`, SHA-256 `482e21662dd99b9b33ca16b4627d6dadb81dc0892323ba85fbecf0332cf01876`)
- **Submission Name:** `h33-h33-2-b2-PRUNE3-20261023-bc00a06c`
- **Form Note (`122 / 140` chars):**
  `h33-h33-2-b2; PRUNE<=3px (2171 collar dots refilled on H19-5 by DTI dT, n=37654, 5.77% chg); pred +0.005 to +0.012 [MODEL]`
- **Parent-Diff Statistics vs. `R0`:**
  - `n_dots`: `37,654` (`shared = 35,483`, `removed = 2,171`, `added = 2,171`, **`5.77%` (`5.7657%`) of R0 dots changed**, symmetric diff `4,342` dots)
  - `d(catalogue)` px: `min = 3.1623` (`sqrt(10)` — strictly `>= 3 px`), `p10 = 5.00`, `median = 21.00`, `p90 = 68.88`
  - Nearest-neighbor spacing px: `min = 2.2361` (`sqrt(5)`), `p05 = 2.2361`, `median = 3.00`
  - Block-density CV: `10 km` `0.6381 -> 0.6571`; `15 km` `0.5162 -> 0.5332`
- **Mechanism Card (for Structural Geologist):**
  - *Hypothesis:* Dots within `200–300 m` (`2 < d <= 3 px`) of mapped USGS/INGENIOUS Quaternary faults sit inside the known-fault potential-field/topographic gradient halo where new-fault density is low, while a dot placed just outside at `d >= 3.16 px` (`316 m`) still reaches inward across the `300 m` (`3 px`) triangular kernel to score on splay junctions ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)).
  - *Mechanism:* Remove all `2,171` R0 dots in `2 < d_cat <= 3 px` (saving up to `0.2 * 2,171 = 434.2` denominator FP units where `q_new = 0`) and refill `2,171` dots onto uncovered gaps of R0's own `H19-5` off-collar fault ridges (`d_cat > 3 px`, spacing `>= sqrt(5)` px) ranked by exact sequential DTI marginal coverage gain `dT` (`first = 2.862`, `median = 1.000`, `last = 0.883` kernel units).
  - *Non-fault mimic:* Off-collar `H19-5` ridges can follow untectonized Tertiary volcanic dike margins, caldera ring fractures, or fluvial terrace risers rather than active/geothermal faults.
  - *Predicted live change:* **`+0.005` to `+0.012` [`MODEL`]** vs. `R0` (`|Δ| < 0.01` = no evidence on public chunks).
  - *Falsifier:* Live public score drops by `>= 0.01` (`RECEIPT`) relative to `R0`, proving newly mapped geometry of existing fault systems ([forum #11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) concentrates inside `200–300 m`.
- **Format Receipt (Re-Read from Disk):**
  - `scripts/validate_submission.py` (`NaN` primary): `ready = true`, `errors = []`, `CRS = EPSG:32611`, `shape = [3730, 3292]`, `transform = [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]`, `dtype = float32`, `count = 1`, `finite_values_in_0_1 = [0.0, 1.0]`, `in_footprint_nan = 0`, `outside_footprint_nonnull = 0`, `catalogue_mass = 0`.
  - `vendor/gems57/validate.py` (`zeros` fallback): `all_checks_passed = true`, `n_nan = 0`, `outside_footprint_zero = true`, `on_catalogue_positive_pixels = 0`.

---

## 2. Variant 2 (Conditional Inward Control) — `PRUNE1` (`d_cat > 1.0 px`, Fixed `37,654` Dots)

- **Primary Spec GeoTIFF (`NaN` outside footprint):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c.tif` (`355,668 B`, SHA-256 `4679d91c5426a46ed813d680095175805851d158075304118fa2ff90c8485049`)
- **Fallback GeoTIFF (`0.0` outside footprint):** `releases/h33-h33-2-b2-PRUNE1-20261023-4679d91c-zeros.tif` (`219,324 B`, SHA-256 `b3b1e75b82f1ac418902aa3ac4fecbe517ca429b4eac0794cb43e487761b7b2a`)
- **Submission Name:** `h33-h33-2-b2-PRUNE1-20261023-4679d91c`
- **Form Note (`125 / 140` chars):**
  `h33-h33-2-b2; PRUNE<=1px (restore 2545 1-2px dots, drop 2545 weak R0 dots, n=37654, 6.76% chg); pred -0.012 to -0.005 [MODEL]`
- **Parent-Diff Statistics vs. `R0`:**
  - `n_dots`: `37,654` (`shared = 35,109`, `removed = 2,545`, `added = 2,545`, **`6.76%` (`6.7589%`) of R0 dots changed**, symmetric diff `5,090` dots)
  - `d(catalogue)` px: `min = 1.4142` (`sqrt(2)`), `p10 = 2.83`, `median = 17.20`, `p90 = 66.41`
  - Nearest-neighbor spacing px: `min = 2.8284` (`sqrt(8)`), `p05 = 2.8284`, `median = 3.1623`
  - Block-density CV: `10 km` `0.6381 -> 0.6286`; `15 km` `0.5162 -> 0.5095`
- **Mechanism Card (for Structural Geologist):**
  - *Hypothesis:* Historical `solo-d28` (`40,199` dots) → `R0` (`37,654` dots) confounded `1–2 px` pruning with a `-2,545` dot mass cut. Holding `n_dots = 37,654` tests whether `100–200 m` flanks host re-mapped strands of known systems ([forum #11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) or legacy scarp-offset false positives.
  - *Mechanism:* Restore all `2,545` `d28` parent dots in `1 < d_cat <= 2 px` and remove the `2,545` lowest exact LOO DTI marginal-loss dots of `R0` (`dT_loss <= 1.0`, isolated 1-px speckles) so total mass `S = 37,654` is invariant.
  - *Non-fault mimic:* `1:24k`/`1:100k` fault-trace digitization offset relative to the `100 m` DEM/TMI scarp crest creates parallel ridge maxima `100–200 m` beside a single mapped strand.
  - *Predicted live change:* **`-0.012` to `-0.005` [`MODEL`]** vs. `R0` (degrades if `1–2 px` is known-scarp halo).
  - *Falsifier:* Live score rises by `>= +0.01` (`RECEIPT`) over `R0`, proving R0's earlier gain came solely from lower mass while `100–200 m` flanks carry dense new-fault truth.
- **Format Receipt (Re-Read from Disk):**
  - `scripts/validate_submission.py` (`NaN` primary): `ready = true`, `errors = []`, `CRS = EPSG:32611`, `shape = [3730, 3292]`, `dtype = float32`, `finite_values_in_0_1 = [0.0, 1.0]`, `catalogue_mass = 0`.
  - `vendor/gems57/validate.py` (`zeros` fallback): `all_checks_passed = true`, `n_nan = 0`, `on_catalogue_positive_pixels = 0`.

---

## 3. Variant 3 (Conditional Outward GeoDAWN-Halo Probe) — `PRUNE4` (`d_cat > 4.0 px`, Fixed `37,654` Dots)

- **Primary Spec GeoTIFF (`NaN` outside footprint):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782.tif` (`353,609 B`, SHA-256 `f5c5378214120a58ae3bd04cf74d75fe7722b19bd6a47d0b463e909d964a9895`)
- **Fallback GeoTIFF (`0.0` outside footprint):** `releases/h33-h33-2-b2-PRUNE4-20261023-f5c53782-zeros.tif` (`217,405 B`, SHA-256 `16539fac84c71b8c0e8d7769b8bb7be9a74128febc44e870c9c82ac0ad7d48d3`)
- **Submission Name:** `h33-h33-2-b2-PRUNE4-20261023-f5c53782`
- **Form Note (`123 / 140` chars):**
  `h33-h33-2-b2; PRUNE<=4px (3825 collar dots refilled on H19-5 by DTI dT, n=37654, 10.16% chg); pred -0.004 to +0.006 [MODEL]`
- **Parent-Diff Statistics vs. `R0`:**
  - `n_dots`: `37,654` (`shared = 33,829`, `removed = 3,825`, `added = 3,825`, **`10.16%` (`10.1583%`) of R0 dots changed**, symmetric diff `7,650` dots)
  - `d(catalogue)` px: `min = 4.1231` (`sqrt(17)`), `p10 = 6.00`, `median = 22.20`, `p90 = 69.84`
  - Nearest-neighbor spacing px: `min = 2.2361` (`sqrt(5)`), `p05 = 2.2361`, `median = 3.00`
  - Block-density CV: `10 km` `0.6381 -> 0.6752`; `15 km` `0.5162 -> 0.5491`
- **Mechanism Card (for Structural Geologist):**
  - *Hypothesis:* GeoDAWN Area 2's `400 m` flight-line spacing and `150–200 m` clearance ([USGS GeoDAWN](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) smear known-fault magnetic/radiometric gradients out to `~400 m` (`4 px`); however, pruning beyond `R = 300 m` loses kernel reach to near-trace branch junctions and begins excising real hanging-wall synthetic splays and narrow step-overs.
  - *Mechanism:* Remove all `3,825` R0 dots in `2 < d_cat <= 4 px` and refill `3,825` dots onto uncovered `H19-5` ridge gaps at `d_cat > 4 px` (`spacing >= sqrt(5)` px) ranked by exact sequential DTI marginal gain `dT` (`first = 3.448`, `median = 0.883`, `last = 0.745`).
  - *Non-fault mimic:* Minimum-curvature gridding across `400 m`-spaced flight lines over steep range fronts produces `300–400 m` lateral potential-field shoulders beside a single fault plane.
  - *Predicted live change:* **`-0.004` to `+0.006` [`MODEL`]** vs. `R0` (diminishing return / turnover past `R = 300 m`).
  - *Falsifier:* `PRUNE4` beats `PRUNE3` by `>= +0.01` (`RECEIPT`), showing airborne halo smearing to `400 m` outweighs synthetic-splay recall loss.
- **Format Receipt (Re-Read from Disk):**
  - `scripts/validate_submission.py` (`NaN` primary): `ready = true`, `errors = []`, `CRS = EPSG:32611`, `shape = [3730, 3292]`, `dtype = float32`, `finite_values_in_0_1 = [0.0, 1.0]`, `catalogue_mass = 0`.
  - `vendor/gems57/validate.py` (`zeros` fallback): `all_checks_passed = true`, `n_nan = 0`, `on_catalogue_positive_pixels = 0`.

---

## 4. Report-Only Local Diagnostics (Never Gates; All Values Are `PROXY`)

| Diagnostic (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives, Seeds 20 & 30) | `PRUNE1` (`>1 px`) | `R0` (`>2 px`) | `PRUNE3` (`>3 px`) | `PRUNE4` (`>4 px`) | Evidence Label |
|---|---|---|---|---|---|
| Fold-proper hide-and-recover (`d_vis > r` on 80% visible catalogue, `n_dots = 37,654`) | `0.091880` (`[0.0811, 0.1031]`) | `0.095962` (`[0.0843, 0.1076]`) | `0.095412` (`[0.0835, 0.1076]`) | `0.094483` (`[0.0822, 0.1065]`) | **`PROXY`** |
| Static-file hide-and-recover (caveat: full-catalogue `d_cat > r` zeroes `G_fold ⊂ C`) | `0.030042` (`[0.0267, 0.0333]`) | `0.004006` (`[0.0034, 0.0047]`) | `0.000000` (`[0.0000, 0.0000]`) | `0.000000` (`[0.0000, 0.0000]`) | **`PROXY`** |
| Off-catalogue USGS SGMC bedrock-fault control (`62,122` truth px at `d_cat > 3 px`) | `0.091757` | `0.095386` | **`0.096085`** | `0.094560` | **`PROXY`** |

- **Leakage Canary (`40` raw/external/parent channels audited on `22,663` withheld positives):** max single-feature symmetric ROC AUC = **`0.60217 <= 0.90`** (`0` channels flagged) [`PROXY`].
