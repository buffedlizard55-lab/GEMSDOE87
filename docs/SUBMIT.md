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

## Part S — `AXIS = SNAP` Variants (Built `2026-10-23`, Human-Assigned Axis; Reproducible via `python3 scripts/build_snap_edge_variants.py`, session `arena/e89a6f6d` edge-argmax operator)

**Parent `R0` Exact Byte-Level Rebuild Receipt (this session):** Identical procedure to Part A — rebuilt from SHA-256-verified `registry/data_manifest.json` inputs via `dot_thin_geodesic_bfs(..., 2.8) & (d_cat > 2.0)` (`37,654` dots), matching both R0 twins **byte-for-byte** (`zeros` `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, `nan` `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd`).

**SNAP operator (identical for all three; only the edge field changes):** each R0 dot may move `<= 2 px` (Euclidean; `13`-pixel window `dy² + dx² <= 4`) to the argmax of a `3x3` footprint-normalised-smoothed edge field; destination must satisfy R0's own exclusions (`footprint & d_cat > 2 px`); count fixed at `37,654`; deterministic row-major processing, own-pixel-wins ties, collisions resolved to the next-best free candidate, `0` overflow moves. Edge fields come only from pinned `training_features.tif` bands (`tmi_hg` band `3`; `iso_grav_anom_hg` band `18`); no lidar-derived rasters were used. Invalid band pixels (`3,061` in footprint, `0.06%`) are filled with the footprint minimum so they never attract a snap.

### S1. `SNAPcomb2` — Best edge-argmax arm (rank-composite TMI ⊕ gravity crest); falsifier, not a slot candidate per the merged `SLOT_PLAN.md`

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPcomb2-20261023-bf0a7e2b.tif` (`355,332 B`, sha256 `bf0a7e2b906a19526a78cc67e175e36e4716975017bbff5a2e1f9a100820deff`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPcomb2-20261023-bf0a7e2b-zeros.tif` (`219,310 B`, sha256 `007f83e0042258362a0f88f688cd55c9b3a0358cb3e46446d3cba43f4a88b38d`)
- **Name:** `h33-h33-2-b2-SNAPcomb2-20261023-bf0a7e2b`
- **Note (124/140):** `h33-h33-2-b2; SNAP<=2px on comb2 edge crest (n=37654, d_cat>2 kept, 98.9% moved, mean 1.80px); pred +0.002 to +0.008 [MODEL]`
- **Parent-diff & format receipt:** `37,654` dots, **`98.90%` moved** (mean displacement `1.80 px` = `180 m`; hist `0 px: 414`, `1 px: 1,825`, `√2 px: 8,075`, `2 px: 27,340`; `87.04%` of moves land off `H19-5` ridges), `min d_cat = 2.2361 px` (exclusion kept), `min NN sep = 1.0 px`, `10 km CV` `0.6381 -> 0.6382`, `0` on catalogue. Re-read verified: `scripts/validate_submission.py` `ready=true`, `errors=[]`; `gems57.validate` `all_checks_passed=true` on zeros.
- **Mechanism (condensed; full card in `ledger/mechanism_cards.json`):** basin-margin normal faults usually step BOTH the magnetic basement and the Bouguer surface; the equal-weight rank composite requires partial two-sensor agreement, filtering single-sensor crest noise (flight-line corrugation for TMI, compilation smoothing for gravity). *Mimic:* caldera resurgent-dome margins and density-contrast lithologic contacts. *Predicted live change:* `+0.002` to `+0.008` [`MODEL`]. *Falsifier:* comb2 lands `>= 0.01` below BOTH `SNAPtmi2` and `R0` live.

### S2. `SNAPtmi2` — Single-Sensor Magnetic Control

- **File:** `releases/h33-h33-2-b2-SNAPtmi2-20261023-b87ddfc5.tif` (`355,066 B`, sha256 `b87ddfc5ae71e761af01c13bc9f6c2ba2f3dee431e43b9537a884fee2eb36ae8`)
- **Fallback:** `releases/h33-h33-2-b2-SNAPtmi2-20261023-b87ddfc5-zeros.tif` (`218,999 B`, sha256 `b7c96cbbef9750e114578e337bb6515024d19f394a9694bb30ba83283c9af12f`)
- **Name:** `h33-h33-2-b2-SNAPtmi2-20261023-b87ddfc5`
- **Note (123/140):** `h33-h33-2-b2; SNAP<=2px on tmi2 edge crest (n=37654, d_cat>2 kept, 98.7% moved, mean 1.78px); pred +0.002 to +0.010 [MODEL]`
- **Parent-diff & format receipt:** `37,654` dots, **`98.75%` moved** (mean `1.78 px`; `86.48%` off-ridge), `min d_cat = 2.2361 px`, `min NN sep = 1.0 px`, `10 km CV` `0.6381 -> 0.6372`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism (condensed):** GeoDAWN Area 2's `400 m` line spacing ([USGS](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) makes ridge-seed positions uncertain by ~the `300 m` kernel radius; re-centering on the `tmi_hg` crest converts partial kernel credit into full credit. *Mimic:* flight-line corrugation, cultural magnetics, dike swarms, caldera ring fractures. *Predicted live change:* `+0.002` to `+0.010` [`MODEL`]. *Falsifier:* live drop `>= 0.01` vs `R0` receipt.

### S3. `SNAPgrav2` — Single-Sensor Gravity Control

- **File:** `releases/h33-h33-2-b2-SNAPgrav2-20261023-ac2bdb06.tif` (`355,504 B`, sha256 `ac2bdb061774b38d0bdfa9e4fb77fb7ad3ae66d671eebe7406e42333c662c348`)
- **Fallback:** `releases/h33-h33-2-b2-SNAPgrav2-20261023-ac2bdb06-zeros.tif` (`219,336 B`, sha256 `31dbcaac0d7f2107cc6ca491ceaba388e948e75411d3d4217de072458e5dbadf`)
- **Name:** `h33-h33-2-b2-SNAPgrav2-20261023-ac2bdb06`
- **Note (124/140):** `h33-h33-2-b2; SNAP<=2px on grav2 edge crest (n=37654, d_cat>2 kept, 99.8% moved, mean 1.95px); pred -0.002 to +0.006 [MODEL]`
- **Parent-diff & format receipt:** `37,654` dots, **`99.78%` moved** (mean `1.95 px`; `88.20%` off-ridge), `min d_cat = 2.2361 px`, `min NN sep = 1.0 px`, `10 km CV` `0.6381 -> 0.6387`, `0` on catalogue. Re-read verified: `ready=true`, `all_checks_passed=true`.
- **Mechanism (condensed):** the Bouguer step tracks basin-fill/range-front density contrast independently of magnetics. *Mimic:* km-smooth compilation crests at paleo-basin edges or buried pluton margins. *Predicted live change:* `-0.002` to `+0.006` [`MODEL`]. *Falsifier:* grav2 beats tmi2 by `>= +0.01`, or falls `>= 0.01` below `R0`.

### S4. Report-Only `PROXY` Diagnostics (`SNAP` Session — Never Used as Gates)

- **Fold-proper hide-and-recover `PROXY`** (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives, Seeds 20 & 30, `1,000` draws): `R0_fp` `0.097493 [0.0854, 0.1096]` (exactly reproduces the prior session's fold-fair `H33_2_B2` value), `SNAPcomb2_fp` `0.090396` (paired `Δ -0.0003 [−0.0027, +0.0023]`), `SNAPgrav2_fp` `0.092401` (`Δ -0.0023 [−0.0073, +0.0035]`), `SNAPtmi2_fp` `0.090115` (`Δ -0.0074 [−0.0116, −0.0029]`) [`PROXY`].
- **Static-raster hide-and-recover `PROXY`** (full-catalogue self-masking caveat): `R0` `0.004006`, `SNAPtmi2` `0.004360`, `SNAPgrav2` `0.004221`, `SNAPcomb2` `0.004138` [`PROXY`].
- **Off-catalogue USGS SGMC control `PROXY`** (`62,122` bedrock fault px at `d_cat > 3 px`): `R0` `0.095386`, `SNAPgrav2` `0.089565`, `SNAPcomb2` `0.086703`, `SNAPtmi2` `0.085701` [`PROXY`].
- **Leakage canary `PROXY`:** `22` channels audited (19 training bands + 3 smoothed SNAP edge fields); max symmetric AUC = **`0.56883 <= 0.90`** (`0` flagged) [`PROXY`].
- **Honest reading:** the local `PROXY` does not support the edge-argmax family (catalogue hide-and-recover has correlated `-0.87…+0.54` with live scores and is never a gate), and the literal operator rewrote `~99%` of dots (`IR-87-V2-09`). The merged `SLOT_PLAN.md` therefore ranks the conservative crest arms (Part D: `SNAPtmi-hg`, `SNAPscarp`) first for Slot 2+ and keeps this family as falsifiers: `SNAPcomb2` is the `PROXY`-neutral arm and `SNAPtmi2` the single-sensor bound.

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

---

## Part D — `AXIS = SNAP` Variants (Session `arena/d76a6a5f` crest operator, Reproducible via `python3 scripts/build_snap_variants.py`)

**Parent `R0` rebuild receipt (re-verified this session):** `dot_thin_geodesic_bfs(H19-5, 2.8) & (d_cat > 2.0)` from the SHA-256-pinned `registry/data_manifest.json` inputs, written with `deflate/predictor=3/zlevel=9/tiled=256`, matches **both** R0 twins byte-for-byte (`zeros` `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, `NaN` `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd`, `37,654` dots). All `25/25` manifest pins verified before building; zero randomness (`FIXED_SEED = 0`, row-major tie-breaks).

**Operator (identical for all three arms):** take a provided potential-field/topographic band, robust-z score it inside the footprint (median/MAD, clipped ±10), subtract its 2 km Gaussian trend (removes the regional gradient that would otherwise drag every window maximum toward the regional high), robust-z the residual, then move each dot that is **not already on a 3x3 edge crest** onto the strongest *unclaimed* crest pixel inside a 5×5 window (Chebyshev radius `2 px = 200 m`). Dots already on a crest never move; a mover can never displace a stayer; destinations are unique, so the dot count is exactly preserved and no destination lands on a catalogue pixel.

### D1. `SNAPtmi-hg` — Recommended Slot 2 (`magnetic horizontal gradient`, `21.60%` of dots moved)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-SNAPtmi-hg-20261023-95057a8a.tif` (`355,602 B`, sha256 `95057a8ae47390891e1692075f0e958089a6518bc1dee33241323a8aae24d4a0`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPtmi-hg-20261023-95057a8a-zeros.tif` (`219,235 B`, sha256 `2f42ec8e4f4883b151a8fb9f584beb3c483a9bfec0dfb191ea65e693d6e6c8e9`)
- **Name:** `h33-h33-2-b2-SNAPtmi-hg-20261023-95057a8a`
- **Note (116/140):** `h33-h33-2-b2; SNAP<=2px off-crest dots to magnetic-HGM crest (bd03 hp2km), 8132 moved; pred -0.006 to +0.008 [MODEL]`
- **Parent-diff & format receipt:** `8,132` dots moved (`21.60%` changed), mean displacement **`1.9482 px` (195 m)**, max `2.8284 px`; `26,886` dots had no free crest in their window and stayed, `1,825` lost their crest to a higher-gain dot; `min d_cat = 2.2361 px` (parent exclusion inherited), `0` on catalogue; `10 km` block-density `CV` `0.6381 -> 0.6376`; nearest-neighbour median `3.0 -> 3.1623 px` but `2,345` dots now sit in a new sub-`2 px` pair (see `IR-87-V2-08`). Re-read from disk: `validate_submission` `ready=true`, `errors=[]`; `gems57.validate` `all_checks_passed=true`.
- **Mechanism card:** see `ledger/mechanism_cards_snap.json` (hypothesis: GeoDAWN 400 m line spacing / 150–200 m terrain clearance leaves H19-5 lineaments 100–200 m off the basement edge; mechanism: crest re-seating raises kernel credit `T` at fixed mass; mimic: reversely magnetised Tertiary basalts, pluton contacts, caldera rings; prediction `-0.006…+0.008` [`MODEL`]; falsifier: `|Δ| < 0.01` retires the whole SNAP axis).

### D2. `SNAPscarp` — Largest-dose arm (`DEM detrended-elevation slope`, `63.37%` moved)

- **File (NaN outside):** `releases/h33-h33-2-b2-SNAPscarp-20261023-8245ad43.tif` (`355,988 B`, sha256 `8245ad430b6aea10b94d580ee66403d68624cd9451bd2add2ec09310bf1f2250`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPscarp-20261023-8245ad43-zeros.tif` (`219,482 B`, sha256 `8d0d343f87061a5df75f62361fb86311e32c86b367776c93fc773e36ced3a915`)
- **Name:** `h33-h33-2-b2-SNAPscarp-20261023-8245ad43`
- **Note (114/140):** `h33-h33-2-b2; SNAP<=2px to DEM scarp crest (bd19 det_elev_slope hp2km), 23861 moved; pred -0.008 to +0.006 [MODEL]`
- **Parent-diff & format receipt:** `23,861` dots moved (`63.37%`), mean `1.9659 px` (197 m), max `2.8284 px`; `9,096` stayed with no free crest, `2,768` lost their crest; `min d_cat = 2.2361 px`; `2,396` dots in new sub-`2 px` pairs; `CV_10km` `0.6381 -> 0.6383`; validators `ready=true` / `all_checks_passed=true`.

### D3. `SNAPgrav-argmax` — Misplacement control, not a slot candidate (`20.71%` moved, mean `2.69 px`)

- **File (NaN outside):** `releases/h33-h33-2-b2-SNAPgrav-argmax-20261023-7b0a8ac9.tif` (`355,606 B`, sha256 `7b0a8ac9327fb3a342d7ef75af96e3e8c8844505e7e0aabbb82692af60c5e07b`)
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-SNAPgrav-argmax-20261023-7b0a8ac9-zeros.tif` (`219,339 B`, sha256 `4e367cf9003ae750ef0868509f4b857cdf019946f2793c2a468bb09177ee7a59`)
- **Name:** `h33-h33-2-b2-SNAPgrav-argmax-20261023-7b0a8ac9`
- **Note (113/140):** `h33-h33-2-b2; SNAP<=2px gravity-HGM window-argmax control (bd18 hp2km), 7799 moved; pred -0.010 to +0.008 [MODEL]`
- **Why the rule differs:** the provided isostatic-gravity horizontal gradient resolves only `3,330` crest px in `5,171,373` footprint px, so the crest operator moves just `363` dots (`0.96%`) — a near-copy of R0 that cannot test the mechanism. The arm therefore uses the literal window maximum with a `0.25` robust-z gain margin; because that residual is nearly flat, the margin is met only at window corners, giving a maximal-misplacement control (mean `2.6932 px = 269 m`). **Do not spend a slot on this file unless Slots 1–3 all fail to separate from R0.**

### D4. Report-Only `PROXY` Diagnostics (SNAP session — never gates, never called scores)

- **Fold-proper hide-and-recover `PROXY`** (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives, seeds 20 & 30, 95% CI): `R0` (fold-fair control) `0.097493 [0.0857, 0.1094]`; `tmi-hg` `0.096323 [0.0850, 0.1081]` (Δ `+0.00117 [-0.00024, +0.00240]`); `scarp` `0.098196 [0.0863, 0.1101]` (Δ `-0.00070 [-0.00333, +0.00208]`); `grav-argmax` `0.092882 [0.0819, 0.1036]` (Δ `+0.00461 [+0.00127, +0.00853]`) [`PROXY`]. The `R0` arm reproduces the `0.097493` value already recorded for `H33-2-B2_fold_fair`, an independent check that the fold-proper harness is unchanged.
- **Off-catalogue USGS SGMC control `PROXY`** (`62,122` bedrock fault px at `d_cat > 3 px`): `R0` `0.095386`; `tmi-hg` `0.094801`; `scarp` `0.093186`; `grav-argmax` `0.091822` [`PROXY`]. All three arms are *below* R0 here while `grav-argmax` is *above* it on the hide-and-recover proxy: the two proxies disagree in sign, which is why no SNAP file is promoted on proxy evidence.
- **Leakage canary `PROXY`:** `23` channels audited (all 19 training bands, the three residual edge fields, and the binary H19-5 parent); max symmetric AUC = **`0.56883 <= 0.90`**, `0` flagged [`PROXY`].
- **Static-raster `PROXY`** (`~0.0039` for every arm) is reported only to document the `IR87-031` self-masking artefact: the literal files carry the full-catalogue `2 px` collar, so they zero their own credit against withheld truth.
