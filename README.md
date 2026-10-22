# GEMSDOE87 — auditable GEMS Prize research

> **Submission status: NOT READY.** No competition TIFF is currently available to download or submit. This checkout does not contain the training rasters, the cached feature stack, the shared holdout evaluator/writer, registry rasters, or a validated candidate. Do not upload a placeholder.
>
> **Start here:** [Project overview](index.html) · [Executive summary: how to submit](executive-summary.html) · [Research plan](research.html) · [Verified-source register](sources.html)

## Mission and operating principles

Build an auditable workflow for finding geothermal-indicative faults missing from the public fault catalogue and for preparing a correctly formatted competition GeoTIFF. Optimize for evidence of real, unmapped faults—not for proxy scores alone.

Keep Arena's principles central:

- **Maximize P(Win):** reserve the competition's limited feedback submissions for candidates that beat the spatial holdout best and pass all leakage, novelty, and file-format gates.
- **Own the Outcome:** report negative results, defects, data provenance, uncertainty, and blockers; never claim a projection or an owner-reported result as an organizer-confirmed score.

This README is the persistent project brief and must be reviewed at the start of every project session. It consolidates the user's goals and the working protocol: official/verified sources; an auditable research feed; a unique, easy-to-download TIFF only after automated in-project validation; no copy of a previous submission; concise submission name/note; multiple implementation/review passes; line-by-line source verification; and a clearly documented limits/access section. Validation must be machine-checked rather than left to a human-only inspection. The entrant still must use their authorized DrivenData account to upload/select the final entry; this project does not collect credentials.

## Non-negotiable experiment and submission protocol

1. **Single method lane.** Work on one preregistered method only. The request does not identify a specific method paragraph for this checkout; the provisional candidate is documented in [`docs/experiment-plan.md`](docs/experiment-plan.md). Do not claim global novelty until exact registry checks pass.
2. **Reuse the shared template.** Use its cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`; do not privately fork or recreate those tools. Hide whole fault segments with a buffer; derive catalogue features only from visible faults; mask visible labels pixel-exactly; calculate pooled distance-weighted Tversky with alpha=0.2, beta=0.8 and the 300 m triangular kernel. None of those requested shared artifacts exists in this checkout.
3. **Leakage canary.** Test each feature alone on spatially blocked holdout before trusting a combination. AUC above 0.90 is a leakage warning until investigated.
4. **Evidence discipline.** Label numerical scores only as **HOLDOUT-DTI** (include evaluator version, withheld-positive count, and 95% CI) or **ORGANIZER-CONFIRMED** (copied from a submission-page receipt). A projection is never a score. The live public leaderboard is linked, but its rows do not establish which TIFF produced a given score.
5. **Novelty gate.** Before placement and again on final dots, compare surface rank-correlation and dot overlap against every registry raster. If rank-correlation exceeds 0.90 or over 70% of dots fall within 3 pixels of one registry-dot raster, log a duplicate and stop.
6. **Budget and selection.** Stop after three experiments or two hours. Negative results are deliverables. Do not select a competition slot here; selection is a separate decision under the current competition limit.
7. **Format gate.** Reopen the written TIFF and verify one band, float32, values in [0,1], no NaN inside the footprint, null/NaN outside, and exact CRS/shape/transform/bounds against the official sample raster. Record SHA-256, unique submission name, and note at most 140 characters. A download is offered only when every gate passes.
8. **Contest entry.** The official rules require participant registration and portal submission; the rules PDF read for this review says feedback submissions are limited by the competition website and one final submission is selected for both prize phases. Do not collect or store competition credentials here. Generative-AI use must be disclosed in the final narrative under the rules read in this review.

## Current checkout review (2026-10-22 UTC)

The local tracked tree initially contained only a title in `README.md`. Before this work, `git ls-tree -r HEAD` confirmed no data, source, tests, site, or GeoTIFF. The branch was fast-forwarded to the latest `origin/main` commit before changes; that commit contained only the project's initial research/readiness README. It did not supply the shared template or data. Current additions provide the static project site, source feed, an independent read-only TIFF preflight, and tests; they do **not** implement a model or holdout evaluator.

Direct unauthenticated reads of official sources established:

- The DrivenData problem description targets faults; it states the public catalogue is incomplete and may contain inaccuracies, describes the feature raster as EPSG:32611 at 100 m, specifies the distance-weighted Tversky metric and the GeoTIFF constraints, and gives the required [0,1] value range.
- The data tab redirected this session to DrivenData sign-in; no competition data were retrieved.
- The September 2026 DOE/NLR rules PDF states that participants register for data access, may submit feedback entries subject to a limit of three per week on the competition site, must choose one final submission across the two prize phases, and must disclose generative-AI use in the submission narrative.
- USGS identifies GeoDAWN as an airborne magnetic/radiometric data release and links its DOI; the DOE Geothermal Data Repository lists INGENIOUS source resources and a CC BY 4.0 license; EPSG identifies EPSG:32611 as WGS 84 / UTM zone 11N.

The line-by-line source audit and caveats are in [`docs/source-audit.md`](docs/source-audit.md). User-provided Dropbox mirrors were not downloaded or independently authenticated; they are not treated as official records. The three implementation/review passes are recorded in [`docs/review-log.md`](docs/review-log.md).

## H33 claim: mechanism versus evidence

The request attributes a high result to `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`. The linked [GEMSDOE32 page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) describes H33-2-B2 as a catalogue-flank **removal** from a previous sparse field, but labels the exact artifact unscored and its modeled live value a projection, not an organizer score. Its [leaderboard/claims page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/leaderboard.html) separates official leaderboard rows from owner claims and says those claims are not linked to receipts. That conflicts with attributing the prompt's H33 value to an organizer-confirmed score for the exact file.

A plausible mechanism is that deleting low-credit predictions near already mapped faults reduces false-positive mass while keeping enough coverage of the hidden new-fault set. This is a hypothesis about why a *removal rule* might help, not proof of causation or proof that the specific file scored as reported. We need the exact file hash, a submission-page receipt that names the file, a matched baseline/candidate pair, and the scoring/evaluator version. Full analysis: [`docs/score-claim-audit.md`](docs/score-claim-audit.md). Open items are tracked in [`docs/irregularities.md`](docs/irregularities.md).

No evidence in this checkout establishes that a new candidate can beat the reported value or the current live leaderboard. The number of candidates and the live standings are not performance guarantees.

## Research candidates and chosen next lane

Four unvalidated candidates are ranked in [`docs/experiment-plan.md`](docs/experiment-plan.md):

1. Cross-scale paired magnetic–gravity edge persistence.
2. Strain–curvature coincidence.
3. Conductive-base boundary with potential-field corroboration.
4. Anisotropic earthquake-density/strain fabric.

The first is the provisional top candidate because it requires only feature families named by the official problem description and asks for cross-sensor, multi-scale persistence rather than a single-channel edge. The named mimic is a lithologic contact, intrusive margin, or basin edge. This is a research priority, **not a measured DTI improvement**. The lane is not implemented and cannot be validated until the shared cache/tools and registry arrive.

## Website and validation tooling

- [`index.html`](index.html) is the GitHub Pages landing page. It prominently shows **NOT READY TO SUBMIT** and does not expose a download while `data/submission-status.json` is blocked.
- [`executive-summary.html`](executive-summary.html) explains the end-to-end portal submission workflow and the prior range-validation error.
- [`research.html`](research.html) lists candidate hypotheses and the preregistered holdout gates.
- [`sources.html`](sources.html) links to verified sources and the current source feed. The initial push-triggered Pages workflow succeeded and published a feed checked at 2026-10-22 22:10 UTC; the workflow is configured for daily source-availability refreshes, but a scheduled run has not yet occurred. It does not log in or scrape leaderboard scores.
- [`scripts/validate_submission.py`](scripts/validate_submission.py) is a read-only final-byte preflight; it is not a model writer or holdout evaluator. Example after the authorized files are present:

  ```bash
  python -m pip install -r requirements-validation.txt
  python scripts/validate_submission.py \\
    --prediction path/to/candidate.tif \\
    --reference data/sample_submission.tif \\
    --report evidence/validation.json
  ```

Run the local test suite with `python -m unittest discover -s tests -v`. The official sample's validity mask and any optional footprint mask must be confirmed against the actual competition files before using the validator for a real submission.

## Run card — this checkout

```json
{
  "hypothesis": "Not tested; provisional lane is cross-scale paired magnetic–gravity edge persistence",
  "mechanism": "Persistent orientation-consistent magnetic and gravity boundaries may indicate buried structural discontinuities",
  "non_fault_mimic": "Lithologic contacts, intrusive margins, and basin edges",
  "holdout_dti": {
    "evidence_class": "HOLDOUT-DTI",
    "evaluator_version": null,
    "withheld_positive_count": null,
    "score": null,
    "ci_95": null,
    "status": "not run"
  },
  "correlation_overlap_vs_registry": {
    "rank_correlation": null,
    "fraction_within_3px": null,
    "status": "not measured; registry rasters absent"
  },
  "raster_sha256": null,
  "validator_output": {
    "no_nan_inside_footprint": null,
    "finite_values_in_0_1": null,
    "crs_shape_transform_match": null,
    "status": "not run; no candidate TIFF or official sample grid"
  },
  "submission": {"name": null, "note": null},
  "verdict": "negative"
}
```

## Next steps and limitations

1. Locate/restore the shared template and its exact `evaluate_holdout.py`, `submission_writer.py`, cached feature stack, and registry rasters into the working environment; do not reimplement them here.
2. Obtain competition data via authorized DrivenData access. The public page read in this review redirected to login, and no credentials are available in this environment. Do not put secrets or large data files in Git.
3. Re-read the official sample submission metadata and actual footprint before running the validator; the official EPSG/resolution page does not specify the sample's exact dimensions or affine transform.
4. Run only the top preregistered lane first, with spatial segment withholding, feature-wise leakage checks, pooled DTI, paired CI, and pre/post novelty comparisons. Do not use a slot unless it beats the holdout best.
5. Refresh the current rules, leaderboard, and weekly limit at decision time. A public leaderboard score is not a receipt tied to one specific TIFF.
6. After a real artifact passes every gate, fill `data/submission-status.json` with its actual artifact path/hash, validation receipt, HOLDOUT-DTI details, name and <=140-character note; only then will the site enable a download.
