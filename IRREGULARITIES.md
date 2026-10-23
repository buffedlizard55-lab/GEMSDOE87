# IRREGULARITIES — Decision-Changing Items Only (Agent Brief v2)

## IR-87-V2-01 — R0 re-encode SHA vs. exact `predictor=3, zlevel=9` byte match (2026-10-23)

- **Observed:** Default rasterio deflate/tiled-256 (`predictor=1/2`, default `zlevel`) did not match R0's SHA-256 in the prior `CONCENTRATION` run (`registry/r0_parent.json`), whereas inspecting `GEMSDOE32/src/gems32/submission.py` (`compress="deflate", predictor=3, zlevel=9, tiled=True, blockxsize=256, blockysize=256`) and running `dot_thin_geodesic_bfs(h19_5 & foot & ~cat, 2.8) & (d_cat > 2.0)` in `scripts/build_prune_variants.py` and `scripts/build_snap_variants.py` reproduces **exact byte-for-byte SHA-256 identity** on both R0 twins (`c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` zeros and `baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd` NaN).
- **Decision:** Both pixel identity and byte-level R0 rebuild are verified from all 25 pinned `registry/data_manifest.json` inputs before building any variant.

## IR-87-V2-02 — 2 px parent collar vs. Brief §4.4 (`>= 3 px` unless `AXIS=PRUNE`) & Brief §5 (`SNAP: Same count, same exclusions`)

- **Observed:** R0 (`h33-h33-2-b2`) has `min d_cat = 2.2361 px` and **`2,171` dots with `2 < d_cat <= 3 px`** (`1,611` strictly `< 3 px`). Enforcing `>= 3 px` inside a non-`PRUNE` axis confounds two mechanisms; moreover, Brief §5 explicitly specifies for `SNAP`: *"Same count, same exclusions; report mean displacement."*
- **Decision:** `PRUNE3` (`bc00a06c`, `min d_cat = 3.1623 px`) isolates the `>= 3 px` collar change at fixed count (`37,654`), while `CONCENTRATION` and `SNAP` preserve R0's exact exclusion mask (`footprint & ~catalogue & (d_cat > 2.0)`, `0` on catalogue) and `sqrt(8)` spacing so single-axis experiments remain unconfounded and combinable in Weeks 3–4.

## IR-87-V2-03 — Unassigned `AXIS`; `MASS`, `CONCENTRATION`, and `PRUNE` already in `ledger/submissions.csv`

- **Observed:** `AXIS`, `TOP_PUBLIC`, and `Slots left` were blank in the pasted brief. `ledger/submissions.csv` already contained `MASS` (`GEMSDOE88`: `m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`c10`, `c15`, `c20`), and `PRUNE` (`3`, `1`, `4`), and `SLOT_PLAN.md` queued `SNAP` next in the Brief §7 default sequence (`MASS, CONCENTRATION, SNAP, PRUNE, RELIEF`).
- **Decision:** Built `AXIS = SNAP` (`values = rtp2, tg2, scarp2`) strictly from organizer-provided `training_features.tif` channels (zero external lidar rasters used per Brief §5) with zero `(parent, axis, value)` or SHA-256 overlap across all 12 `ledger/submissions.csv` rows; left `TOP_PUBLIC` and `Slots left` blank for human entry.

## IR-87-V2-04 — Competition input rasters mirrored in public sibling repos (data-use terms unchecked)

- **Observed:** `registry/data_manifest.json` restores login-walled competition files (`training_features.tif`, `labels.tif`, `existing_faults.tif`, `sample_submission.tif`) from public GitHub commits in `buffedlizard55-lab/GEMSDOE` and `buffedlizard55-lab/GEMSDOE24` ([data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)). Redistribution terms cannot be checked in-sandbox because fetching `drivendata.org` is banned ([DrivenData ToS](https://www.drivendata.org/termsofuse/)).
- **Decision:** Restored competition inputs strictly into gitignored `.cache/raw/`; committed zero competition input rasters to this repo or `releases/`. Human should check sibling public mirrors against DrivenData data-use rules.

## IR-87-V2-05 — Scheduled `scripts/refresh_feed.py` configured to fetch `drivendata.org`

- **Observed:** `.github/workflows/pages.yml` runs `scripts/refresh_feed.py` on cron, and `data/sources.json` previously had `"feed_check": true` on three `drivendata.org` URLs, conflicting with Hard Constraint 1 and [DrivenData ToS](https://www.drivendata.org/termsofuse/).
- **Decision:** Removed `drivendata.org` from `ALLOWED_HOSTS` in `scripts/refresh_feed.py`, set `"feed_check": false` on all `drivendata.org` entries in `data/sources.json`, and enforced unit tests blocking `drivendata.org` and `dropbox.com`.

## IR-87-V2-06 — Submission quota & inherited `docs/source-audit.md` metadata drift

- **Observed:** Inherited prose cited `"3 per 24h"`, `18` bands (`c0eb1eff…`), and `142,272` fault pixels, whereas the [DOE/NLR Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) specifies **3 scored submissions per rolling week per entity** and **1 blind final file**, and byte-verified `registry/data_manifest.json` has **19 float32 bands** (`4371c82e…`) and **60,988** fault pixels (`7ba308cc…`).
- **Decision:** Planned `SLOT_PLAN.md` at 3 slots/rolling week for ONE entity and verified all 25 manifest files directly from bytes.

## IR-87-V2-07 — `Band 18` (`iso_grav_anom_hg`) is directional $\partial g/\partial x$, NOT isotropic $|\nabla_H g|$ (2026-10-23)

- **Observed:** Across all `5,164,312` valid footprint pixels of `training_features.tif`, `Band 18` (`iso_grav_anom_hg`) is signed (`[-15.44, +12.86]`) and correlates `r = +0.9482` with the East–West derivative $\partial B_{13}/\partial x$ (`r = +0.0499` with $\partial B_{13}/\partial y$, `r = +0.0278` with $|\nabla_H B_{13}|$), whereas `Band 05` (`iso_grav_anom_slope`, `[0.0014, 0.6517]`) is the true isotropic horizontal gradient magnitude (`r = +0.9619` with $|\nabla_H B_{13}|$). In addition, snapping unconditionally in a 13-pixel `<= 2 px` disk moves `92.3%` (`12/13`) of basin dots onto gridding noise and slides dots uphill on regional ramps.
- **Decision:** Used `Band 05` (`iso_grav_anom_slope`) rather than directional `Band 18` for gravity edge strength, paired with 1-D Blakely-Simpson Hessian ridge crests $-\lambda_{\min}(\nabla^2 \log(1+G))$ and cross-strike projection (`|\mathbf{u}\cdot\mathbf{n}_\perp| \ge 0.80`) on `Band 02` (`rtp`), `Band 03` (`tmi_hg`), and `Band 19` (`det_elev_slope`).
