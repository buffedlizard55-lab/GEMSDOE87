# Generative-AI Use Disclosure — GEMSDOE87 (DOE GEMS Prize #306)

Prepared per Section 3 of the [DOE/NLR GEMS Prize Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) and Agent Brief v2 Hard Constraint 6.

## 1. What Generative AI Wrote (2026-10-23 UTC)

- **Session `arena/82031087-gemsdoe87` (`AXIS = PRUNE`):**
  - `scripts/build_prune_variants.py`: verifies all SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `37,654` dots) with exact byte-level SHA-256 identity (`c55bafc4…` zeros / `baeae321…` NaN), builds three fixed-count (`37,654` dots) `AXIS = PRUNE` variants (`PRUNE3`, `PRUNE1`, `PRUNE4`) on `R0`'s own `H19-5` parent ridges ranked by exact sequential DTI marginal gain (`vendor/gems57/metric.py`, `R = 300 m` kernel, `FIXED_SEED = 0`, deterministic row-major tie-break), runs re-read GeoTIFF format/catalogue/hash gates, and computes report-only `PROXY` diagnostics (`releases/manifest.json`).
  - `tests/test_dti_algebra_and_prune.py` & `tests/test_refresh_feed.py`: unit-tests derived DTI algebra (`DTI = T / (0.2T + 0.2(S-M) + 0.8|G|)`), isolated vs. line-like truth marginal-gain behavior, `drivendata.org`/`dropbox.com` fetch blocking in `scripts/refresh_feed.py`, and re-read GeoTIFF receipts.
- **Session `arena/c677fe69-gemsdoe87` (`AXIS = RELIEF`, this session):**
  - `src/gems87/relief.py` & `scripts/build_relief_variants.py`: re-verifies all `25` SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `37,654` dots) with exact byte-level SHA-256 identity (`c55bafc4…` zeros / `baeae321…` NaN), audits `Band 18` (`dg/dx`) vs. `Band 05` (`|grad_H g|`), partitions the footprint into Basin (`T0`), Piedmont (`T1`), and Range-Front (`T2`) terciles from organizer-provided `Band 12 det_elev` + `Band 19 det_elev_slope`, builds three fixed-count (`37,654`), fixed-spacing (`sqrt(8) px`), fixed-collar (`d_cat > 2 px`) `RELIEF` variants (`RELIEFr2p12`, `RELIEFr2b10`, `RELIEFb2r15`, `FIXED_SEED = 0`), runs re-read GeoTIFF format/catalogue/hash gates, and computes report-only `PROXY` diagnostics (`releases/manifest_RELIEF.json`).
  - `tests/test_relief_axis.py`: unit-tests DTI binary algebra & exact marginal gain (`DTI = T / (0.2T + 0.2(S-M) + 0.8|G|)`), synthetic `RELIEF` operator invariants (count, `sqrt(8)` spacing, untouched third tercile, catalogue exclusion, determinism, 1-D Hessian crest ramp rejection), and release/ledger invariants.
  - `ledger/mechanism_cards_relief.json`, `SLOT_PLAN.md`, `docs/SUBMIT.md` Part E, `IRREGULARITIES.md` `IR-87-V2-09/10`, `ledger/README.md`, and the `CURRENT STATE` block of `README.md`.
- **Session `arena/d76a6a5f-gemsdoe87` (`AXIS = SNAP`):**
  - `scripts/build_snap_variants.py`: re-verifies all `25` SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` with exact byte identity, constructs 2 km high-passed robust-z residual edge fields from the provided `tmi_hg` (band 03), `iso_grav_anom_hg` (band 18) and `det_elev_slope` (band 19) bands, and builds three fixed-count `SNAP` arms (`tmi-hg`, `scarp`, `grav-argmax`) with a deterministic, zero-randomness window operator (unique destinations, no mover/stayer collision, `<= 2 px` Chebyshev cap), the re-read format/catalogue/hash gates, and report-only `PROXY` diagnostics (`releases/manifest_SNAP.json`).
  - `tests/test_snap_axis.py`: synthetic operator tests (count preservation, displacement cap, destination uniqueness, catalogue exclusion, reproducibility, gain margin, crest definition, trend removal) plus release invariants (hashes re-read from disk, `EPSG:32611`/`float32`/`1` band/`37,654` dots, zero catalogue mass, ledger and card completeness).
  - `ledger/mechanism_cards_snap.json`, `SLOT_PLAN.md`, `docs/SUBMIT.md` Part D, `IRREGULARITIES.md` `IR-87-V2-07/08`, `ledger/README.md`, the `CURRENT STATE` block of `README.md`.
- **Session `arena/6743515f-gemsdoe87` (`AXIS = CONCENTRATION`):**
  - `src/gems87/concentration.py`, `scripts/generate_concentration_variants.py`, `scripts/restore_r0_inputs.py`, `ledger/mechanism_cards.json`, `tests/test_concentration_axis.py`, `tests/test_ledger_concentration.py`.
- **Shared Ledger & Documentation:** `ledger/submissions.csv`, `ledger/lineage_claims.csv`, `SLOT_PLAN.md`, `docs/SUBMIT.md`, `IRREGULARITIES.md`, `AI_USE.md`, and the `CURRENT STATE` block in `README.md`.

## 2. What AI Did NOT Do

- Did **not** access `drivendata.org` or `dropbox.com`, log in, scrape leaderboard numbers, read/store credentials, or upload/submit any file.
- Did **not** invent `TOP_PUBLIC`, remaining submission slots, or organizer `RECEIPT` scores (all projections are labeled `MODEL`, all local holdouts `PROXY`).
- Did **not** promote any file on `PROXY` evidence: the SNAP arms' two report-only proxies disagree in sign, so all three are handed to the human as `BUILT` only.

## 3. What the Human Competitor (`buffedlizard55-lab`) Decides & Supplies

- Supplies `TOP_PUBLIC` (with observation date), confirms competition deadline (`2026-12-03`) and remaining weekly/total submission quota on DrivenData, and records actual submission-page `RECEIPT` scores and dates in `ledger/submissions.csv`.
- Chooses the session `AXIS` when overriding the default plan, decides which single validated GeoTIFF (`releases/<id>.tif` primary NaN-outside or `<id>-zeros.tif` fallback) to upload per slot from their own single registered account, and selects the single blind final submission.
