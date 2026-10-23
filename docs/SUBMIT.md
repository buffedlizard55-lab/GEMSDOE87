# Submission Handoff & Validation Receipts — Agent Brief v2

**Upload Rule:** The human competitor uploads **at most ONE `.tif` per slot** from their own registered DrivenData account (`releases/<id>.tif` = primary `NaN`-outside spec GeoTIFF matching `sample_submission.tif`; `releases/<id>-zeros.tif` = `0.0`-outside fallback twin with identical in-footprint dots). Parent `R0 = 0.2778` is **`CLAIM`** until a receipt is recorded in `ledger/submissions.csv` ([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

---

## Part 0 — `AXIS = SNAP` Variants (built 2026-10-23; reproduce with `python scripts/build_snap_variants.py`)

**Operator:** each R0 dot moves `<= 2 px` (200 m) to the strongest 4-direction crest (strict maximum along at least 2 of the 4 lines through the pixel) of one provided band. The move is refused if it would land within `sqrt(5)` px of another dot, inside the catalogue collar (`d_cat <= 2 px`), or outside the footprint. The count stays `37,654`, and the exclusions are identical to R0's. The parent was rebuilt byte-exact (`baeae3219bba…` NaN / `c55bafc47005…` zeros), and all `25` manifest files were sha256-verified. Git HEAD at build: `d1f1b2d34165`.

**Upload the NaN-outside `.tif`.** The `-zeros.tif` twins pass `gems57.validate`, but they fail the strict spec check ("outside-footprint pixels must be null/NaN"). Use one only if the NaN file is rejected.

### 0.1 `SNAPslope`: b19 det_elev_slope. Recommended SNAP slot (slot 3)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPslope-20261023-81ae160f.tif` (`356,429 B`, sha256 `81ae160fb11c68045bdcf008231e1ca0b23fb4d912c2c2c75c9a571483b73c4e`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPslope-20261023-81ae160f-zeros.tif` (`219,901 B`, sha256 `50328a3a9c0ecefb96baecfbf0d28c642a10b6160bcea40083d0f2f1f0076eae`)
- **Name:** `h33-h33-2-b2-SNAPslope-20261023-81ae160f`
- **Note (93/140):** `h33-h33-2-b2; SNAP<=2px to det_elev_slope crest (89.4% moved, mean 1.33px); pred +0.004 MODEL`
- **Parent diff and format receipt:**
  - Dots: `37,654`, of which `33,648` moved (**89.36% changed**; SNAP is exempt from the 50% cap). Another `1,106` were refused by the spacing rule.
  - Displacement: mean `1.3266 px` over all dots (`132.7 m`); `1.4846 px` over moved dots.
  - Distances: min `d_cat` `2.2361 px`; min spacing `2.2361 px`.
  - Block-density CV: `0.6381 -> 0.6412` at 10 km.
  - Format: `0` pixels on the catalogue. Re-read from disk: `validate_submission` `ready=true`, `errors=[]`; `gems57.validate` all checks pass.
- **Mechanism card (written for a structural geologist):**
  - *Hypothesis:* Fault scarps and faceted range fronts are local maxima of slope on detrended elevation. If the unmapped new faults have topographic expression, slope crests within 200 m locate the trace more precisely than the H19-5 ridge does.
  - *Mechanism:* Same operator on band 19 det_elev_slope: move <= 2 px to the strongest 4-direction maximum, keep the count, the exclusions and the sqrt(5) px spacing.
  - *Non-fault mimic:* Stream-cut valley walls, terrace risers, lake shorelines and resistant bedding all make slope crests. On a range front the steepest 100 m slope is usually uphill of the trace, so the snap can move dots off the piedmont junction where the fault actually sits.
  - *Predicted live change:* +0.004 DTI [MODEL] versus R0; range -0.006 to +0.012. Basis: on the catalogue PROXY, slope-crest movers beat random-crest movers by about +4% of near-truth credit (about +0.011 if new faults behaved like the catalogue). Discounted by more than half because mapped Quaternary faults are scarp-selected and new faults are probably less expressed.
  - *Falsifier:* Live Delta >= +0.01 versus R0 would mean new faults are topographically expressed and the 100 m slope crest is within ~1 px of the trace. Then lidar-scale (3DEP) scarp snapping becomes worth building.

### 0.2 `SNAPtmihg`: b03 tmi_hg. Reserve: only after a positive SNAPslope receipt

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPtmihg-20261023-d0a0c668.tif` (`356,585 B`, sha256 `d0a0c668a92d3bd89c48210a137e731478e497d06047efea7eb1e3533a1334d5`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPtmihg-20261023-d0a0c668-zeros.tif` (`220,117 B`, sha256 `affc2db94b19ce088ad2d944c9a91c94f82ce239ac829046c268410933e053f8`)
- **Name:** `h33-h33-2-b2-SNAPtmihg-20261023-d0a0c668`
- **Note (85/140):** `h33-h33-2-b2; SNAP<=2px to tmi_hg crest (55.5% moved, mean 0.83px); pred -0.003 MODEL`
- **Parent diff and format receipt:**
  - Dots: `37,654`, of which `20,898` moved (**55.5% changed**; SNAP is exempt from the 50% cap). Another `2,753` were refused by the spacing rule.
  - Displacement: mean `0.8313 px` over all dots (`83.1 m`); `1.4979 px` over moved dots.
  - Distances: min `d_cat` `2.2361 px`; min spacing `2.2361 px`.
  - Block-density CV: `0.6381 -> 0.6369` at 10 km.
  - Format: `0` pixels on the catalogue. Re-read from disk: `validate_submission` `ready=true`, `errors=[]`; `gems57.validate` all checks pass.
- **Mechanism card (written for a structural geologist):**
  - *Hypothesis:* R0 dots sit on H19-5 composite ridges, which are blurred by roughly the kernel radius. Steeply dipping faults that juxtapose rocks of contrasting magnetization (basalt or tuff against basin fill) put their sharpest magnetic contrast where the fault reaches the shallowest magnetic source. The crest of the TMI horizontal gradient should therefore sit within 100-200 m of the trace, closer than the composite ridge does.
  - *Mechanism:* Each R0 dot moves to the strongest 4-direction maximum of band 03 tmi_hg within <= 2 px (200 m). The move is refused if it would put the dot within sqrt(5) px of another dot, inside the 2 px catalogue collar, or outside the footprint. The count stays 37,654. A dot on truth gains credit 1/3 per px of approach (triangular kernel, R = 3 px) and loses the same per px of retreat.
  - *Non-fault mimic:* TMI is not reduced to the pole. At the inclination of the Nevada field, the maxima of the TMI horizontal gradient shift down-dip, off the source edge, by a fraction of the source depth. Flat flow margins, dikes, intrusive contacts and the 400 m flight-line gridding (GeoDAWN Area 2) also make crests with no fault behind them.
  - *Predicted live change:* -0.003 DTI [MODEL] versus R0; range -0.010 to +0.003. Basis: on the catalogue PROXY, TMI-HG movers gain less credit per moved dot than random-crest movers (about -0.7% of near-truth credit).
  - *Falsifier:* Live Delta >= +0.01 versus R0's receipt would mean the TMI-HG crests localize new faults better than the H19-5 ridge at the 100-200 m scale. That would be a reason to combine SNAP with PRUNE3/CONCc10.

### 0.3 `SNAPgravhg`: b18 iso_grav_anom_hg. Do not spend a slot: near no-op (5% moved), cannot clear 0.01

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPgravhg-20261023-67fcb1e8.tif` (`355,608 B`, sha256 `67fcb1e8c9dc2208e5380d5475db1b0d77a4b5b4415af86d777731eb4df7474b`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPgravhg-20261023-67fcb1e8-zeros.tif` (`219,047 B`, sha256 `95e3270cd4e9e369b8fef2918b78c740274f458e6109ce9d09cf46ddd1590e32`)
- **Name:** `h33-h33-2-b2-SNAPgravhg-20261023-67fcb1e8`
- **Note (93/140):** `h33-h33-2-b2; SNAP<=2px to iso_grav_anom_hg crest (5.0% moved, mean 0.08px); pred 0.000 MODEL`
- **Parent diff and format receipt:**
  - Dots: `37,654`, of which `1,900` moved (**5.05% changed**; SNAP is exempt from the 50% cap). Another `423` were refused by the spacing rule.
  - Displacement: mean `0.0777 px` over all dots (`7.8 m`); `1.5397 px` over moved dots.
  - Distances: min `d_cat` `2.2361 px`; min spacing `2.2361 px`.
  - Block-density CV: `0.6381 -> 0.6382` at 10 km.
  - Format: `0` pixels on the catalogue. Re-read from disk: `validate_submission` `ready=true`, `errors=[]`; `gems57.validate` all checks pass.
- **Mechanism card (written for a structural geologist):**
  - *Hypothesis:* Basin-bounding normal faults put dense bedrock against low-density basin fill. The crest of the isostatic-gravity horizontal gradient marks the steepest basement step, and steep faults sit near that step.
  - *Mechanism:* Same operator on band 18 iso_grav_anom_hg: move <= 2 px to the strongest 4-direction maximum, keep the count, the exclusions and the sqrt(5) px spacing.
  - *Non-fault mimic:* Gravity stations are spaced at km scale, so crest positions on a 100 m grid are interpolation products. Dipping (45-60 degree) range-front faults shift the gradient maximum basinward, onto the hanging wall. Density contrasts at plutons and buried caldera walls also make crests.
  - *Predicted live change:* 0.000 DTI [MODEL] versus R0; range -0.003 to +0.003. Only ~5% of dots find a gravity crest within 200 m (smooth field), so the variant is close to a no-op and cannot clear the 0.01 evidence bar.
  - *Falsifier:* Live Delta >= +0.01 versus R0 would mean gravity-gradient crests localize new faults to <= 200 m, which contradicts the km-scale resolution argument.

### 0.4 Report-only PROXY diagnostics (never gates)

- **Catalogue snap test (PROXY):**
  - Setup: `10,261` H19-5 d28 dots lie within `0 < d_cat <= 4 px` of a known trace. I applied the same snap to them, with landing on the catalogue allowed. Credit is `k(d_cat)` on the 300 m triangular kernel.
  - Comparator: H19-5 contains no catalogue pixels, so any move can only raise credit. The random-crest null (5 seeds) gains `0.01468`. Read each band's excess over that null, per source dot:
  - `slope`: Δcredit `0.02996`, 95% CI `[0.02321, 0.03631]` (10 km blocks); excess over null `0.01566` (+4.1% of source credit).
  - `tmihg`: Δcredit `0.00571`, 95% CI `[0.00128, 0.01019]` (10 km blocks); excess over null `-0.00248` (-0.6% of source credit).
  - `gravhg`: Δcredit `0.00027`, 95% CI `[-0.001, 0.00148]` (10 km blocks); excess over null `-0.00054` (-0.1% of source credit).
  - Bias: mapped Quaternary faults are scarp-selected, so this test favours `slope`.
- **Static hide-and-recover (PROXY):** `gems57-pooled-hide-v2`, n = `22,663` withheld positives. All arms sit near 0.004, because every arm keeps the full-catalogue 2 px collar: `R0` 0.004006 [0.003424, 0.00469]; `SNAPtmihg` 0.004426 [0.003802, 0.005113]; `SNAPgravhg` 0.003999 [0.003377, 0.004676]; `SNAPslope` 0.003858 [0.003314, 0.004507]. It has no power to separate SNAP variants.
- **SGMC off-catalogue control (PROXY):** `62,122` pixels: `R0` 0.095386; `SNAPtmihg` 0.094639; `SNAPgravhg` 0.095313; `SNAPslope` 0.09557.
- **Leakage canary (PROXY):** catalogue pixels against off-catalogue pixels (d_cat > 3), for 19 provided bands. Max symmetric AUC `0.57406` ≤ 0.90 (`b04_geod_2ndinv`); no channel flagged.

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
