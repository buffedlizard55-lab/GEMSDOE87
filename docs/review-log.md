> **Historical readiness snapshot:** retained from concurrent `main` at `f4f5944` before the implemented H87 run was integrated. This is not current data/artifact status. See [the current research dashboard](index.html), [measured result](science.html), and [current verification](verification.html). No extra scientific lane was executed during integration.

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
- The initial push-triggered GitHub Pages workflow succeeded after PR #3 merged (run [39862945753](https://github.com/buffedlizard55-lab/GEMSDOE87/actions/runs/39862945753)). The live [landing page](https://buffedlizard55-lab.github.io/GEMSDOE87/) shows the blocked status, and its [published feed](https://buffedlizard55-lab.github.io/GEMSDOE87/data/feed.json) was refreshed at 2026-10-22 22:10 UTC. It reports the official data tab as login-required and public source pages as reachable; it does not collect or publish scores. This verifies one automated refresh and deployment, not the daily schedule, which has not yet run.
- Final scientific result: negative / blocked. No geological experiment was run, no competition slot was used, no candidate GeoTIFF was generated, and no competition score is claimed.

## Follow-up review in this session (2026-10-22 UTC)

- Read the project brief, research plan, status/run-card JSON, source and irregularity audits, Pages scripts, workflows, and tests before making changes.
- Found a deployment gap: the readiness page could point to `downloads/<file>.tif`, but the Pages packaging step did not copy the `downloads/` directory into the published site. Updated the workflow to publish that directory when it exists; no file is present now and the status remains blocked.
- Updated the test workflow's push branch to this session's fixed branch, so CI can run on this work branch.
- Fixed a small landing-page typo in the P(Win) value statement and recorded the conflicting user-reported leaderboard maxima (0.4413 and 0.3195) as unverified claims, not scores.
- The first local test invocation could not import optional raster libraries. Installed only the pinned project validation requirements into the repository's ignored `.venv/`; the complete suite then passed: 22 tests, using synthetic rasters strictly for validator behavior.
- Final checks still confirm the scientific work is blocked: competition inputs, shared evaluator/writer, and registry are absent. No TIFF, score, novelty result, or eligibility to submit can be honestly claimed.

## Branch synchronization and pull-request review

- While PR #7 was open, `main` advanced concurrently. Updated this branch from `origin/main` and resolved conflicts by retaining this branch's push trigger (not another active Arena branch) and preserving both sets of review notes.
- GitHub Actions test check passed for PR #7. The first local hook invoked the system Python before the ignored environment was active, so it reported missing optional libraries; rerunning the full suite with `.venv/bin/python` passed all 22 tests.
- No geological experiment was run; all competition-score, holdout, registry, and TIFF fields remain unmeasured/blocked.

## Session 2026-10-22 — second review (passes 1–3)

**Pass 1 — implement and verify.** The sandbox could reach only GitHub, PyPI and npm (see [source audit addendum](source-audit.md)). No competition data, sample grid, shared evaluator, or registry raster is available, so no candidate TIF was produced and none is offered. Verified instead, from GitHub-hosted sources: the H33-2-B2 file hash (`c55bafc4…ab6fa9`), its grid and binary content, the UNSCORED audit status, and the absence of 0.2778 from the full GEMSDOE32 history. Output: [`h33-claim-check-2026-10-22.md`](h33-claim-check-2026-10-22.md).

**Pass 2 — review for bugs and wrong assumptions.**
- `scripts/validate_submission.py` was read in full. Its CRS, shape, transform, bounds, float32, single-band, NaN-inside, [0,1], and outside-null checks match the stated gate. No change was needed. Its unit tests passed in a venv (numpy 2.4.6, rasterio 1.4.4) before the merge. **After merging `origin/main` (PR #8, which changed only report-path handling: alias refusal and atomic JSON writes), the core checks are unchanged; re-ran all 25 tests in the venv (all pass) and in the base interpreter (13 raster tests skipped, rest pass).**
- Found: the README install command fails under PEP 668 (system Python). Fixed to use a venv.
- Found: the official reference notebook writes float64 output (`np.zeros` default dtype, `dtype=y_final.dtype`). Recorded as IR-87-17.
- Found: the prompt's 0.2778 and 0.4413 values conflict with the owner's own repo (0.4413 is a refuted projection there; 0.2778 is absent). Recorded as IR-87-14 and IR-87-15.
- Found: the README and source audit still say "read directly" for pages that are unreachable from this sandbox. Flagged in IR-87-16 rather than silently kept.

**Pass 3 — recheck against the original request.** Requested items and their status:
- Submission TIF that is easy to download: **not delivered.** The download gate is still blocked, and the reason is stated at the top of the README and on the landing page.
- Answer why H33 scored and whether 0.2778 can be beaten: **answered** with evidence classes, a PhD-level mechanism assessment, and no claim beyond the sources.
- Limitations and access needed: **written** in the README.
- Uniqueness and novelty: **not run**; the registry is obtainable from GitHub but was not built in this session.
- Run card: unchanged (negative, no measurement). No DTI, correlation, or hash is claimed.
## Follow-up code review — active Arena branch

**Review date:** 2026-10-22 UTC. This review is limited to the currently checked-out branch and does not adopt work from another open branch.

### Pass 1 — inspect actual checkout

- Read the repository brief, experiment plan, source/score audits, status JSON, site pages, source-feed code, TIFF validator, test suite, and workflows.
- Confirmed from the tracked tree and `data/` directory that this branch has no competition TIFFs, labels/features, cached feature stack, shared holdout evaluator/writer, registry rasters, or candidate. The site correctly remains **NOT READY TO SUBMIT** and exposes no TIFF download.
- The historical source audit was not re-fetched in this follow-up; no new external-source or scientific claim is made here.

### Pass 2 — look for failure paths

- Found a destructive CLI edge case: `scripts/validate_submission.py --report <same path as prediction>` validated the TIFF, then overwrote it with JSON. The same risk applied to reference/mask paths and hard-link aliases.
- Found an optional-dependency test bug: `nodata=np.nan` was evaluated while importing the test module, so an environment without NumPy errored instead of cleanly skipping raster tests.
- Fixed report/input alias rejection (including hard links), atomic JSON report writes, and the test fixture default. Added regression tests for successful receipt writes and collision refusal.

### Pass 3 — verify fixes and original scope

- In an isolated `.venv`, installed the declared validation dependencies and ran compileall, all **24 unit tests**, and `git diff --check`; all passed. The TIFF tests use tiny synthetic fixtures only and are software tests, not geological validation.
- Re-ran the suite under the base interpreter without raster dependencies; tests now complete successfully and explicitly skip only the rasterio/NumPy cases.
- No holdout, leakage canary, DTI, confidence interval, registry comparison, TIFF generation, or competition entry was performed. No numerical score is claimed. No external data or credentials were used.
- `origin/main` advanced during this review; synchronized the active branch with the merged Pages download-packaging change, current landing-page typo fix, and prior CI updates. Updated the push trigger to this fixed branch and preserved the existing review history.
- After synchronization, re-ran compileall, all **25 unit tests** in both the base interpreter (raster-only tests skipped because optional libraries are absent) and the isolated validation environment, plus `git diff --check`; all passed.

---

## Session 2026-10-23 — Full H87B-STFD Scientific & Engineering Review (Passes 1–3)

- **Pass 1 (Implement & Execute):** Restored SHA-256-verified competition + public USGS/DOE rasters and `34` cross-repo prediction rasters; discovered `IR87-028` (`Band 06 = GeoDAWN TC`, `r = +0.997140`), `IR87-029` (`Bands 10 & 16` swarm/background density), `IR87-030` (Session 1 `B02/B19/B08` swap), and `IR87-031` (`GEMSDOE32` reverse label self-masking); trained all `12/12` out-of-fold workers (`comp:0..7` + `quad:0..3`) and generated `gems87-stfd-h87b-37654dots-20261023-1d3f50ffd13f-RESEARCH-DO-NOT-SUBMIT.{tif,zip,json}`.
- **Pass 2 (Edge Cases & Calibration Audit):** Replaced single-head `m3` placement with leak-free dual-head `0.55 * logit(m3) + 0.45 * logit(m1)` fusion (`3,058` frontier dots `> 2.5 km`, `LOQO-Comp = 0.138160` vs `H33_2_B2_fold_fair = 0.097493`, `Spatial-4Q = 0.133386` vs `EXP2 = 0.121746`), fixed un-zeroed `bmtd_dots` comparison, and fixed `IR87-033` hardcoded date in `scripts/update_feed.py`.
- **Pass 3 (Full Prompt Reconciliation):** Confirmed both `H87B-STFD` (`1d3f50ffd13f`) and frozen `H87-BMTD-01` (`50041440adba`) are clearly presented at the top of `docs/index.html`, `docs/executive-summary.html`, and `README.md` with unmistakable `DO NOT SUBMIT` badges, complete `HOLDOUT-DTI` CIs, `31/31` real fault-candidate uniqueness + `3` dense witness disclosure, embedded figures, and full `pytest` + Chromium smoke coverage.
