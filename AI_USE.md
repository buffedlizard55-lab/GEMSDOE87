# Generative-AI Use Disclosure — GEMSDOE87 (DOE GEMS Prize #306)

Prepared per Section 3 of the [DOE/NLR GEMS Prize Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) and Agent Brief v2 Hard Constraint 6.

## 1. What Generative AI Wrote (2026-10-23 UTC)

- **Session `arena/e89a6f6d-gemsdoe87` (`AXIS = SNAP`, human-assigned in-session):**
  - `scripts/build_snap_variants.py`: verifies all SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `37,654` dots) with exact byte-level SHA-256 identity (`c55bafc4…` zeros / `baeae321…` NaN), builds three fixed-count (`37,654` dots) `AXIS = SNAP` variants (`tmi2`, `grav2`, `comb2`) — each R0 dot may move `<= 2 px` to the argmax of a `3x3`-smoothed pinned edge field (`tmi_hg` band 3, `iso_grav_anom_hg` band 18, or their equal-weight footprint-rank composite) keeping R0's `d_cat > 2 px` exclusion, fully deterministic (`FIXED_SEED = 0`, row-major processing, own-pixel-wins ties, zero randomness, `0` overflow moves) — runs re-read GeoTIFF format/catalogue/hash/count gates, and computes report-only `PROXY` diagnostics (`evidence/snap_build.json`, `releases/manifest-snap.json`).
  - `tests/test_snap_axis.py`: synthetic unit tests of the SNAP operator (count preservation, `<= 2 px` displacement bound, footprint/collar exclusions, determinism, stay-on-tie, collision fallback, rotation-tolerant moved-count identity) and of the smoothing/rank-normalisation helpers.
  - Doc updates: `ledger/submissions.csv` (3 SNAP rows appended by the script), `ledger/mechanism_cards.json`, `SLOT_PLAN.md`, `docs/SUBMIT.md` Part S, `IRREGULARITIES.md` (`IR-87-V2-07`), and the `CURRENT STATE` block in `README.md`.
- **Session `arena/82031087-gemsdoe87` (`AXIS = PRUNE`):**
  - `scripts/build_prune_variants.py`: verifies all SHA-256 pins in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `37,654` dots) with exact byte-level SHA-256 identity (`c55bafc4…` zeros / `baeae321…` NaN), builds three fixed-count (`37,654` dots) `AXIS = PRUNE` variants (`PRUNE3`, `PRUNE1`, `PRUNE4`) on `R0`'s own `H19-5` parent ridges ranked by exact sequential DTI marginal gain (`vendor/gems57/metric.py`, `R = 300 m` kernel, `FIXED_SEED = 0`, deterministic row-major tie-break), runs re-read GeoTIFF format/catalogue/hash gates, and computes report-only `PROXY` diagnostics (`releases/manifest.json`).
  - `tests/test_dti_algebra_and_prune.py` & `tests/test_refresh_feed.py`: unit-tests derived DTI algebra (`DTI = T / (0.2T + 0.2(S-M) + 0.8|G|)`), isolated vs. line-like truth marginal-gain behavior, `drivendata.org`/`dropbox.com` fetch blocking in `scripts/refresh_feed.py`, and re-read GeoTIFF receipts.
- **Session `arena/6743515f-gemsdoe87` (`AXIS = CONCENTRATION`):**
  - `src/gems87/concentration.py`, `scripts/generate_concentration_variants.py`, `scripts/restore_r0_inputs.py`, `ledger/mechanism_cards.json`, `tests/test_concentration_axis.py`, `tests/test_ledger_concentration.py`.
- **Shared Ledger & Documentation:** `ledger/submissions.csv`, `ledger/lineage_claims.csv`, `SLOT_PLAN.md`, `docs/SUBMIT.md`, `IRREGULARITIES.md`, `AI_USE.md`, and the `CURRENT STATE` block in `README.md`.

## 2. What AI Did NOT Do

- Did **not** access `drivendata.org` or `dropbox.com`, log in, scrape leaderboard numbers, read/store credentials, or upload/submit any file.
- Did **not** invent `TOP_PUBLIC`, remaining submission slots, or organizer `RECEIPT` scores (all projections are labeled `MODEL`, all local holdouts `PROXY`).

## 3. What the Human Competitor (`buffedlizard55-lab`) Decides & Supplies

- Supplies `TOP_PUBLIC` (with observation date), confirms competition deadline (`2026-12-03`) and remaining weekly/total submission quota on DrivenData, and records actual submission-page `RECEIPT` scores and dates in `ledger/submissions.csv`.
- Chooses the session `AXIS` when overriding the default plan, decides which single validated GeoTIFF (`releases/<id>.tif` primary NaN-outside or `<id>-zeros.tif` fallback) to upload per slot from their own single registered account, and selects the single blind final submission.
