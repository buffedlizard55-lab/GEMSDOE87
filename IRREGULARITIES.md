# IRREGULARITIES — Decision-Changing Items Only (Agent Brief v2)

1. **`IR-V2-01` — Unassigned `AXIS` + Hard Constraint 4 (`>= 3 px` unless `AXIS=PRUNE`) forces `PRUNE` first:**
   - *Observation:* The pasted brief left `AXIS`, `TOP_PUBLIC`, and `Slots left` unfilled and `ledger/` absent. Parent `R0` (`h33-h33-2-b2`, `37,654` dots) sits at `d_cat > 2 px` (`2,171` dots in `2 < d_cat <= 3 px`, `1,611` at `< 3 px`), while `19GEMSDOE`'s continuous pre-threshold `p_h19_5` ranking depends on 15 unpinned `dem10/*.npy` and `context_detector_prob_*.tif` files absent from `registry/data_manifest.json`.
   - *Decision changed:* Running any non-`PRUNE` axis on `R0` would either violate Hard Constraint 4 (`keep >=3 px from them unless AXIS=PRUNE`) or confound its treatment with a `<= 3 px` prune; running `MASS` would require approximating `p_h19_5` (forbidden). Built `AXIS = PRUNE` (`values = 3, 1, 4` at fixed `n_dots = 37,654` on exact rebuilt `R0`) so `PRUNE3` establishes a `>= 3 px`-compliant parent for all subsequent axes, and left `TOP_PUBLIC` / `Slots left` blank for the human to fill.

2. **`IR-V2-02` — Login-walled competition input rasters mirrored in public sibling repos (data-use terms unchecked):**
   - *Observation:* `registry/data_manifest.json` pins `training_features.tif`, `labels.tif`, `existing_faults.tif`, and `sample_submission.tif` from public GitHub commits in `buffedlizard55-lab/GEMSDOE` and `buffedlizard55-lab/GEMSDOE24` ([DrivenData data page](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)). Redistribution terms cannot be checked in-sandbox because fetching `drivendata.org` is banned ([DrivenData ToS](https://www.drivendata.org/termsofuse/)).
   - *Decision changed:* Restored competition inputs strictly into gitignored `.cache/raw/` for SHA-256 verification and validation; committed zero competition input rasters to this repo or `releases/`. Human should audit sibling public mirrors against DrivenData data-use rules.

3. **`IR-V2-03` — Inherited `scripts/refresh_feed.py` + `data/sources.json` scheduled automated fetches to `drivendata.org`:**
   - *Observation:* `.github/workflows/pages.yml` runs `scripts/refresh_feed.py` on a daily cron (`17 9 * * *`), and `data/sources.json` had `"feed_check": true` on three `drivendata.org` URLs, conflicting with Hard Constraint 1 and [DrivenData ToS](https://www.drivendata.org/termsofuse/).
   - *Decision changed:* Removed `drivendata.org` from `ALLOWED_HOSTS` in `scripts/refresh_feed.py`, set `"feed_check": false` on all `drivendata.org` entries in `data/sources.json`, and added a unit test blocking `drivendata.org` and `dropbox.com`.

4. **`IR-V2-04` — Submission quota discrepancy (`3 per 24h` in inherited prose vs. `3 per rolling week` in official rules):**
   - *Observation:* Inherited `data/sources.json` / `data/feed.json` described the limit as `"3 per 24h"`, whereas Brief v2 and the [DOE/NLR Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) specify **3 scored submissions per rolling week per entity** and **1 blind final submission** (deadline `2026-12-03`, UNVERIFIED live in-sandbox; human to confirm on competition page).
   - *Decision changed:* Budgeted `SLOT_PLAN.md` strictly at 3 slots/rolling week for ONE entity (`PRUNE3` first, conditional Slot 2) instead of burning all 3 variants blindly.

5. **`IR-V2-05` — Stale 18-band prose and mismatched SHA-256s in inherited `docs/source-audit.md`:**
   - *Observation:* Inherited `docs/source-audit.md` cited an 18-band `training_features.tif` (`c0eb1eff...`) and `142,272` fault pixels, whereas actual byte-verified `registry/data_manifest.json` has **19 float32 bands** (`4371c82e...`) and **60,988** fault pixels (`7ba308cc...`).
   - *Decision changed:* Verified all `23/23` files directly from restored bytes against `registry/data_manifest.json` before rebuilding `R0`.
