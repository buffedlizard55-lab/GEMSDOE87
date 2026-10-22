# Three-pass implementation review log

**Review date:** 2026-10-22 UTC. This log records implementation checks, not a geological experiment result.

## Pass 1 — implement the requested safe foundation

- Reviewed the branch and confirmed the starting checkout had no competition data, cached features, model, shared holdout/writer, validator, or site.
- Read the official DrivenData problem/data/metric/format pages, current public leaderboard page, official September 2026 DOE/NLR rules PDF, official reference-solution README, USGS GeoDAWN release, GBCGE INGENIOUS page, DOE GDR dataset page, and EPSG entry. Links and claim scope are in [`source-audit.md`](source-audit.md).
- Preregistered four geological candidates before implementing any model change, ranked them qualitatively, and selected a provisional top lane. No geological candidate was implemented because the shared stack and data are absent.
- Added a GitHub Pages site with an unmistakable blocked state, an executive submission guide, hypothesis page, source register, and score-claim audit.
- Added a read-only GeoTIFF preflight; it does not write a TIFF, repair values, compute a competition score, or replace the shared writer/evaluator.
- Added a score-free source feed and a scheduled GitHub Pages refresh workflow.

## Pass 2 — audit bugs, edge cases, and misleading states

- Confirmed the site has no TIFF download anchor while `submission_ready` is false; the runtime gate also requires every gate to pass, a valid holdout record, novelty bounds, a passing TIFF receipt, matching SHA-256, a safe local TIFF path, a unique name, and a note within the requested character limit.
- Made the validator reject range violations anywhere in the raster, including finite nodata sentinels; reject NaN/Inf inside the footprint; reject non-null outside cells; and fail closed on band/dtype/CRS/EPSG/resolution/shape/transform/bounds mismatch.
- Changed the example validator invocation to use the official sample's own mask by default. An optional footprint mask is only valid after it is independently confirmed to match the competition footprint; no feature-band mask is assumed equivalent.
- Added explicit irregularity records for the H33 score attribution, conflicting leaderboard claims, missing shared assets, unverified Dropbox mirrors, the unspecified lane paragraph, and the distinction between automated file validation and portal submission.
- Tested with tiny synthetic GeoTIFF fixtures only. These tests validate software behavior and do not validate a competition raster or count as HOLDOUT-DTI.

## Pass 3 — re-check against the full request

- Confirmed the README captures the mission, core values, session-start rule, one-lane protocol, data/access limitations, source list, holdout/leakage/novelty/budget gates, and final run card.
- Confirmed the landing page puts submission readiness first, the executive page explains the upload process and the `[0,1]` error, the source feed never copies leaderboard scores, and no unsupported TIF is offered.
- Confirmed internal page links resolve, Python files compile, the unit test suite passes, and `git diff --check` is clean.
- The live external source refresh cannot be run inside this sandbox's network allowlist; the GitHub Actions workflow is designed to run it after the site is configured for Actions-based Pages. Until that succeeds, the static feed reflects this review's source reads, not a verified automated refresh.
- Final scientific result: negative / blocked. No geological experiment was run, no competition slot was used, no candidate GeoTIFF was generated, and no competition score is claimed.
