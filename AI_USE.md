# Generative-AI Use Disclosure — GEMSDOE87 (DOE GEMS Prize #306)

Prepared per Section 3 of the [DOE/NLR GEMS Prize Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) and Agent Brief v2 Hard Constraint 6.

## 1. What Generative AI Wrote in Session `arena/82031087-gemsdoe87` (2026-10-23 UTC)

- **`scripts/build_prune_variants.py`:** Deterministic Python pipeline that verifies all 23 SHA-256 checksums in `registry/data_manifest.json`, rebuilds Parent `R0` (`h33-h33-2-b2`, `GEMSDOE32`, `37,654` dots) byte-for-byte (`c55bafc4...` zeros / `baeae321...` NaN), builds three fixed-count (`37,654` dots) `AXIS = PRUNE` variants (`PRUNE3`, `PRUNE1`, `PRUNE4`) using exact sequential DTI marginal gain (`vendor/gems57/metric.py`, `R = 300 m` kernel, `FIXED_SEED = 0`, row-major tie-break), runs format/catalogue/hash preflight checks, and computes report-only `PROXY` diagnostics.
- **`tests/test_dti_algebra_and_prune.py` & `tests/test_refresh_feed.py`:** Unit tests verifying the derived DTI algebra (`DTI = T / (0.2T + 0.2(S-M) + 0.8|G|)`), isolated vs. line-like truth marginal-gain behavior, `drivendata.org`/`dropbox.com` fetch blocking in `scripts/refresh_feed.py`, and re-read GeoTIFF format/SHA-256 gates on `releases/*.tif`.
- **Ledger & Documentation:** `ledger/submissions.csv`, `releases/manifest.json`, `SLOT_PLAN.md`, `docs/SUBMIT.md`, `IRREGULARITIES.md`, `AI_USE.md`, and the `CURRENT STATE` block in `README.md`.
- **Prior Inherited Repo Code (`2b59f5d`):** Earlier sessions on `GEMSDOE87` used generative AI to author `src/gems87/`, `scripts/validate_submission.py`, `scripts/refresh_feed.py`, and static documentation pages.

## 2. What AI Did NOT Do

- Did **not** access `drivendata.org` or `dropbox.com`, log in, scrape leaderboard numbers, read/store credentials, or submit any file.
- Did **not** invent `TOP_PUBLIC`, remaining submission slots, or organizer `RECEIPT` scores.

## 3. What the Human Competitor Decides & Supplies

- Supplies `TOP_PUBLIC` (with observation date), confirms competition deadline (`2026-12-03`) and remaining weekly/total submission quota on DrivenData, and records actual submission-page `RECEIPT` scores and dates in `ledger/submissions.csv`.
- Chooses the session `AXIS` when overriding the default plan, decides which single validated GeoTIFF (`releases/<id>.tif` primary NaN-outside or `<id>-zeros.tif` fallback) to upload per slot from their own single registered account, and selects the single blind final submission.
