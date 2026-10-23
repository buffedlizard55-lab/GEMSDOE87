# IRREGULARITIES — Decision-Changing Items Only (Agent Brief v2)

## IR-87-V2-01 — R0 re-encode SHA vs. exact `predictor=3, zlevel=9` byte match (2026-10-23)

- **Observed:** Default rasterio deflate/tiled-256 (`predictor=1/2`, default `zlevel`) did not match R0's SHA-256 in the prior `CONCENTRATION` run (`registry/r0_parent.json`), whereas inspecting `GEMSDOE32/src/gems32/submission.py` (`compress="deflate", predictor=3, zlevel=9, tiled=True, blockxsize=256, blockysize=256`) and running `dot_thin_geodesic_bfs(h19_5 & foot & ~cat, 2.8) & (d_cat > 2.0)` in `scripts/build_prune_variants.py` reproduces **exact byte-for-byte SHA-256 identity** on both R0 twins (`c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` zeros and `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd` NaN).
- **Decision:** Both pixel identity and byte-level R0 rebuild are now verified from pinned `registry/data_manifest.json` inputs without approximating the parent.

## IR-87-V2-02 — 2 px parent collar vs. Brief §4.4 (`>= 3 px` unless `AXIS=PRUNE`)

- **Observed:** R0 (`h33-h33-2-b2`) has `min d_cat = 2.2361 px` and **`2,171` dots with `2 < d_cat <= 3 px`** (`1,611` strictly `< 3 px`). Enforcing `>= 3 px` inside a non-`PRUNE` axis confounds two mechanisms; keeping `d_cat > 2 px` leaves `< 3 px` dots in place.
- **Decision:** Session `arena/82031087-gemsdoe87` built `AXIS = PRUNE` (`PRUNE3`, `PRUNE1`, `PRUNE4` at fixed `37,654` count on `H19-5` ranked by exact DTI marginal gain `dT`), establishing `PRUNE3` (`min d_cat = 3.1623 px`) as a clean `>= 3 px`-compliant candidate parent while keeping `CONCENTRATION` (`2 px` inherited) unconfounded.

## IR-87-V2-03 — Unassigned `AXIS`; `MASS` and `CONCENTRATION` already in `ledger/submissions.csv`

- **Observed:** `AXIS`, `TOP_PUBLIC`, and `Slots left` were blank in the pasted brief. `MASS` (`m10minus`, `m10plus`, `m20minus`) was built in `GEMSDOE88` (moreover, `19GEMSDOE`'s continuous `p_h19_5` ranking depends on 15 unpinned `dem10/*.npy` and `context_detector_prob_*.tif` files absent from `registry/data_manifest.json`), and `CONCENTRATION` (`c10`, `c15`, `c20`) was built in PR #25.
- **Decision:** Built `AXIS = PRUNE` (`values = 3, 1, 4`) with zero `(parent, axis, value)` or SHA-256 overlap across all 9 `ledger/submissions.csv` rows; left `TOP_PUBLIC` and `Slots left` blank for human entry.

## IR-87-V2-04 — Competition input rasters mirrored in public sibling repos (data-use terms unchecked)

- **Observed:** `registry/data_manifest.json` restores login-walled competition files (`training_features.tif`, `labels.tif`, `existing_faults.tif`, `sample_submission.tif`) from public GitHub commits in `buffedlizard55-lab/GEMSDOE` and `buffedlizard55-lab/GEMSDOE24` ([data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)). Redistribution terms cannot be checked in-sandbox because fetching `drivendata.org` is banned ([DrivenData ToS](https://www.drivendata.org/termsofuse/)).
- **Decision:** Restored competition inputs strictly into gitignored `.cache/raw/`; committed zero competition input rasters to this repo or `releases/`. Human should check sibling public mirrors against DrivenData data-use rules.

## IR-87-V2-05 — Scheduled `scripts/refresh_feed.py` configured to fetch `drivendata.org`

- **Observed:** `.github/workflows/pages.yml` runs `scripts/refresh_feed.py` on cron, and `data/sources.json` previously had `"feed_check": true` on three `drivendata.org` URLs, conflicting with Hard Constraint 1 and [DrivenData ToS](https://www.drivendata.org/termsofuse/).
- **Decision:** Removed `drivendata.org` from `ALLOWED_HOSTS` in `scripts/refresh_feed.py`, set `"feed_check": false` on all `drivendata.org` entries in `data/sources.json`, and added unit tests blocking `drivendata.org` and `dropbox.com`.

## IR-87-V2-06 — Submission quota & inherited `docs/source-audit.md` metadata drift

- **Observed:** Inherited prose cited `"3 per 24h"`, `18` bands (`c0eb1eff…`), and `142,272` fault pixels, whereas the [DOE/NLR Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) specifies **3 scored submissions per rolling week per entity** and **1 blind final file**, and byte-verified `registry/data_manifest.json` has **19 float32 bands** (`4371c82e…`) and **60,988** fault pixels (`7ba308cc…`).
- **Decision:** Planned `SLOT_PLAN.md` at 3 slots/rolling week for ONE entity and verified all manifest files directly from bytes.

## IR-87-V2-07: AXIS, TOP_PUBLIC and slots blank again; SNAP chosen by default (2026-10-23)

- **Observed:** The brief again left AXIS, TOP_PUBLIC and slots blank. I asked the human in-session; the question was skipped. MASS, CONCENTRATION and PRUNE already have 3 values each in the ledger.
- **Decision:** Built `AXIS = SNAP`, which SLOT_PLAN had already scheduled as slot 3. TOP_PUBLIC and slots stay blank for the human. If the human meant a different axis, the SNAP files are inert until uploaded.

## IR-87-V2-08: The lidar-scarp raster is pinned but was not used for SNAP

- **Observed:** `registry/data_manifest.json` pins `external/lidar_scarp_features_u8.tif` (owner-derived from USGS 3DEP). The brief allows lidar-derived rasters for SNAP "only if the human supplies them".
- **Decision:** SNAP used only provided competition bands: b03 `tmi_hg`, b18 `iso_grav_anom_hg`, b19 `det_elev_slope`. A lidar SNAP goes ahead only if the human confirms the manifest file counts as human-supplied **and** SNAPslope gives a live `Δ >= +0.01`.

## IR-87-V2-09: H19-5 contains zero catalogue pixels, which biases any snap-to-catalogue proxy

- **Observed:** No H19-5 pixel lies on the catalogue (`h19_5 & catalogue = 0`). Near-trace parent dots can therefore never sit on catalogue truth, and any move raises their catalogue credit on average. A random-crest snap gains +0.015.
- **Decision:** The catalogue snap PROXY is read against a 5-seed random-crest null, normalised per moved dot, never against "stay". It is report-only and never a gate.

## IR-87-V2-10: README body labels R0's 0.2778 as ORGANIZER-CONFIRMED

- **Observed:** A heading in README.md, outside the CURRENT STATE block, calls `0.2778` "ORGANIZER-CONFIRMED". There is no receipt in `ledger/`.
- **Decision:** It is treated as a CLAIM everywhere in this session's outputs. I did not edit that heading, because the brief limits README edits to the CURRENT STATE block. The human should correct it or paste a receipt.
