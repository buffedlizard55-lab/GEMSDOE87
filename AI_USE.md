# Generative-AI Use Disclosure — GEMSDOE87 (DOE GEMS Prize #306)

Prepared per Section 3 of the [DOE/NLR GEMS Prize Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) and Agent Brief v2 Hard Constraint 6.

## 1. What Generative AI Wrote (2026-10-23 UTC)

- **Session `arena/c677fe69-gemsdoe87` (`AXIS = SNAP`):**
  - `src/gems87/snap.py` & `scripts/build_snap_variants.py`: verifies all 25 SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `37,654` dots) with exact byte-level SHA-256 identity (`c55bafc4…` zeros / `baeae321…` NaN), audits `Band 05` (`iso_grav_anom_slope`, isotropic $|\nabla_H g|$ `r = +0.9619`) vs. `Band 18` (`iso_grav_anom_hg`, directional $\partial g/\partial x$ `r = +0.9482`), builds three fixed-count (`37,654` dots), fixed-exclusion (`d_cat > 2 px`, `0` on catalogue), spacing-preserving (`min_sep >= sqrt(8)`) cross-strike `<= 2.0 px` `AXIS = SNAP` variants (`SNAPrtp2`, `SNAPtg2`, `SNAPscarp2`) strictly from organizer-provided `training_features.tif` bands (`FIXED_SEED = 0`, zero external lidar rasters used), re-reads every written GeoTIFF from disk through both format validators, and computes report-only `PROXY` diagnostics (`releases/snap_manifest.json`, `ledger/snap_mechanism_cards.json`).
  - `tests/test_snap_axis.py`: unit-tests midrank quantile equivalence, planar-ramp Hessian nullity and 1-D ridge centering, `<= 2.0 px` bijective displacement/exclusion/spacing invariants, and re-read GeoTIFF + ledger receipts.
- **Session `arena/82031087-gemsdoe87` (`AXIS = PRUNE`):**
  - `scripts/build_prune_variants.py`, `tests/test_dti_algebra_and_prune.py`, `tests/test_refresh_feed.py`, `releases/manifest.json`.
- **Session `arena/6743515f-gemsdoe87` (`AXIS = CONCENTRATION`):**
  - `src/gems87/concentration.py`, `scripts/generate_concentration_variants.py`, `scripts/restore_r0_inputs.py`, `ledger/mechanism_cards.json`, `tests/test_concentration_axis.py`, `tests/test_ledger_concentration.py`.
- **Shared Ledger & Documentation:** `ledger/submissions.csv`, `ledger/lineage_claims.csv`, `SLOT_PLAN.md`, `docs/SUBMIT.md`, `IRREGULARITIES.md`, `AI_USE.md`, and the `CURRENT STATE` block in `README.md`.

## 2. What AI Did NOT Do

- Did **not** access `drivendata.org` or `dropbox.com`, log in, scrape leaderboard numbers, read/store credentials, or upload/submit any file.
- Did **not** use external lidar-derived rasters in `AXIS = SNAP` (strictly used organizer-provided `training_features.tif` channels per Brief §5).
- Did **not** invent `TOP_PUBLIC`, remaining submission slots, or organizer `RECEIPT` scores (all projections are labeled `MODEL`, all local holdouts and SGMC controls `PROXY`).

## 3. What the Human Competitor (`buffedlizard55-lab`) Decides & Supplies

- Supplies `TOP_PUBLIC` (with observation date), confirms competition deadline (`2026-12-03`) and remaining weekly/total submission quota on DrivenData, and records actual submission-page `RECEIPT` scores and dates in `ledger/submissions.csv`.
- Chooses the session `AXIS` when overriding the default plan, decides which single validated GeoTIFF (`releases/<id>.tif` primary NaN-outside or `<id>-zeros.tif` fallback) to upload per slot from their own single registered account, and selects the single blind final submission.
