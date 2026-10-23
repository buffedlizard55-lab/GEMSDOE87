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

## IR-87-V2-07 — `SNAP` inherits R0's `2 px` collar (Brief §4.4 vs §5 "same exclusions")

- **Observed:** §5 specifies SNAP as "same count, same exclusions", while §4.4 requires `>= 3 px` from the catalogue for every non-`PRUNE` axis. R0 carries `2,171` dots in `2 < d_cat <= 3 px`, so honouring §4.4 inside SNAP would also apply a `PRUNE` edit and confound two mechanisms in one file. All three SNAP arms therefore inherit R0's exact exclusions: destinations and sources stay at `d_cat > 2.0 px`, emitted catalogue mass is `0`, and the measured minimum stays `2.2361 px`.
- **Decision:** Report the inherited collar explicitly in every receipt and in `docs/SUBMIT.md`, keep the `>= 3 px` compliance question on the `PRUNE` axis (`PRUNE3`, `min d_cat = 3.1623 px`), and treat `PRUNE3` — not a SNAP file — as the compliance baseline.

## IR-87-V2-08 — Two measured operator limits: R0 is packed at `sqrt(8)`, and the provided gravity gradient resolves no crest

- **Observed (packing):** R0's minimum nearest-neighbour distance is `2.8284 px` (`p01 = p05 = 2.8284`, median `3.0`) — it is a maximal packing for that spacing, so it contains no hole `>= 2.8284 px` from every dot. Enforcing "the snap may not create a tighter pair than the parent" was implemented and measured to give **zero admissible moves for all three arms**, i.e. it would silently turn SNAP into a copy of R0. The constraint is therefore not enforced; instead every arm reports the full nearest-neighbour census. Cost: `2,345` (tmi-hg), `2,396` (scarp) and `1,519` (grav-argmax) dots end up in a new sub-`2 px` pair while the median spacing increases (`3.0 -> 3.1623 px`). This is the geometric price of any `<= 200 m` reposition of a `37,654`-dot set and is the seed of the `DENSIFY_2PX` axis proposed in `SLOT_PLAN.md`.
- **Observed (gravity sensor):** the provided isostatic-gravity horizontal gradient (`training_features.tif` band 18) yields only `3,330` crest px in `5,171,373` footprint px after a 2 km high-pass (`tmi_hg`: `94,769`; `det_elev_slope`: `264,859`), so the crest operator moves `363` dots (`0.96%`). A gravity-only crest arm therefore cannot test the SNAP mechanism.
- **Decision:** Keep one honest mid-strength magnetic arm, one scarp arm (the only organizer-provided sensor that images surface rupture, and a non-lidar DEM derivative), and make the gravity arm an explicitly labelled window-argmax *misplacement control* that is not a slot candidate. No lidar-derived raster was used, per §5.

## IR-87-V2-09 — Two parallel sessions both built `SNAP`; the literal edge-argmax operator rewrites ~99% of dots (2026-10-23, session `arena/e89a6f6d-gemsdoe87`)

- **Observed:** Sessions `arena/d76a6a5f` (crest operator, `tmi-hg`/`scarp`/`grav-argmax`, `21–63%` of dots moved) and `arena/e89a6f6d` (edge-argmax operator, `tmi2`/`grav2`/`comb2`) both built `AXIS = SNAP` before either merged, colliding on `scripts/build_snap_variants.py` and `tests/test_snap_axis.py` (add/add). The six `(parent, axis, value)` pairs and all SHA-256s are unique, so both families stay in the ledger. The literal brief operator ("move each dot `<= 2 px` to the strongest edge response in its window", implemented in session `arena/e89a6f6d`) moved **`98.75–99.78%`** of R0's dots (mean displacement `1.78–1.95 px`, `86–88%` landing off `H19-5` ridges, min NN spacing dropping from `2.83` to `1.0 px`), because the argmax of the `3x3`-smoothed `100 m` gradient fields almost always sits at the window edge — closer to a partial field replacement than a positional nudge. Its fold-proper `PROXY` (never a gate) was neutral for `comb2` (`Δ -0.0003 [−0.0027, +0.0023]`) and `grav2` (`Δ -0.0023 [−0.0073, +0.0035]`) but negative for `tmi2` (`Δ -0.0074 [−0.0116, −0.0029]`, CI excludes 0); the conservative crest family sits at or slightly above `R0_fp` on the same harness (`scarp` `0.098196`, `tmi-hg` `0.096323` vs `R0_fp` `0.097493`).
- **Decision:** (a) Resolved the file collision by keeping the crest session's files canonical (`scripts/build_snap_variants.py`, `tests/test_snap_axis.py`) and renaming the edge-argmax session's to `scripts/build_snap_edge_variants.py` / `tests/test_snap_edge_axis.py`; the ledger test now checks per-family value subsets with global hash/pair uniqueness. (b) The merged `SLOT_PLAN.md` ranks the conservative crest arms first for Slot 2+; the edge-argmax arms remain `BUILT` falsifiers (single-sensor `tmi2` bounds the raw-argmax failure mode) and are not slot candidates on current evidence. (c) All six rows keep `MODEL` predictions; the live `RECEIPT`, not the `PROXY`, closes the lane.
