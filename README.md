# GEMSDOE87 — auditable GEMS submission research

> **Current status: BLOCKED / NO SUBMISSION FILE.** This checkout contains only this README. It has no cached feature stack, labels, sample-submission raster, evaluator, holdout implementation, submission writer, or source data. Therefore this repository cannot honestly produce or validate a competition-ready GeoTIFF or report HOLDOUT-DTI. Do not download or submit a fabricated/placeholder TIFF. The first actionable step is to make the official competition data and the shared template/evaluator available, then run the reproducible holdout gate below. No weekly slot has been selected or spent.

## Project brief (starting point for every session)

Build an auditable, science-grounded system for discovering geothermal-indicative faults missing from the USGS/INGENIOUS catalogue and producing a legally formatted, downloadable single-band GeoTIFF for the DOE GEMS Prize challenge. Prioritize evidence over projected scores; validate autonomously with spatially blocked hide-and-recover evaluation before any real submission. Keep official, verifiable sources and data provenance; distinguish HOLDOUT-DTI from ORGANIZER-CONFIRMED; prevent catalogue leakage; compare every candidate against registry rasters for duplication; clearly explain file eligibility and the submission steps. Maintain a current research feed and a clean, accessible GitHub Pages interface with an executive-summary submission guide. Flag limitations and irregularities rather than inventing results.

Core values: **Maximize P(Win)**—treat each scarce weekly submission slot as a gated experiment; **Own the Outcome**—measure and disclose failures, fix shared defects once, and never relabel a projection as a score.

### Operating protocol (required at the start of project work)

1. Stay in the assigned scientific lane and method; before and after placement compare rank correlation against each registry raster and dot proximity. A rank correlation >0.90 or >70% of candidate dots within 3 pixels of a registry raster means duplicate: record and stop.
2. Reuse the shared cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`; do not create a private fork. Hide whole fault segments with a buffer. Derive catalogue features from visible faults only; mask visible faults pixel-exactly. Score pooled DTI with alpha=0.2, beta=0.8 and the 300 m triangular kernel. Test each feature alone first; AUC >0.90 is a leakage canary until proven otherwise.
3. Label every score either **HOLDOUT-DTI** (evaluator version, withheld-positive count, 95% CI) or **ORGANIZER-CONFIRMED** (copied from a submission-page receipt). A projection is not a score.
4. Maximum three experiments or two hours per session. Negative results are valid deliverables. Promotion to a real slot is a separate selector step under the submission page's weekly cap.
5. End an experiment with a JSON run card containing hypothesis, mechanism, named non-fault mimic, holdout DTI and CI, registry correlation/overlap, raster SHA-256, validator outcome (footprint finite; values [0,1]; CRS/shape/transform match), submission name/note (<=140 chars), and verdict `promote` or `negative`.

## Review findings and evidence boundary

- The repository at review time had one tracked file, this README, and no scripts, tests, data, or cached artifacts. This is directly verified by the Git tree, not inferred from the linked projects.
- User-provided leaderboard figures and score histories are claims supplied in the request, not organizer receipts. The cited GEMSDOE32 page is a project mirror, not proof of an organizer score. The page describes the `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` raster and labels its 0.2747 figure as projected and unscored; it separately cites 0.2708 as an existing base. These are mirror statements, not independently verified competition outcomes.
- The prompt also states a current leaderboard high of 0.3195 and elsewhere 0.4413. These conflict, and neither is accompanied here by an organizer receipt. Treat current leaderboard position and all listed scores as **unverified** until checked on the official leaderboard.
- No competition TIFF has been generated in this checkout. A unique filename or altered raster alone would not establish a scientifically distinct or eligible prediction. An “all-zero” file is not an acceptable substitute.

## Preliminary hypothesis slate (not validated; no experiment has been run)

These are candidate ideas only. This checkout has no implementation to compare against, so “not implemented here” is the only verifiable novelty claim; do not treat these as novel relative to other GEMSDOE projects. Each requires the official competition stack and shared holdout before any submission decision.

| Rank | Hypothesis and layers/signature | Why it may find uncatalogued faults; named mimic | Relative cost / expected value |
|---|---|---|---|
| 1 | **Multi-scale magnetic-gradient edge coherence:** magnetic intensity / magnetic derivatives, using scale-space horizontal gradient maxima and orientation coherence (not a raw anomaly threshold). | Faults can juxtapose or offset magnetic lithologies and produce linear gradients; faults absent from the registry can still define edges. Lithologic contacts and survey-line artifacts mimic this signature. | Medium / moderate, uncertain. Official GeoDAWN airborne magnetic data are listed in the competition context; verify the stack's bands and provenance before use. |
| 2 | **Radiometric contact discontinuities:** K, eTh, eU channels (only if supplied), robust local contrast and co-located edge orientation. | Fracturing/alteration may redistribute or expose radioelements near structures; an independent sensor can add evidence beyond fault geometry. Bedrock-unit boundaries, regolith, moisture, and flight-line seams are strong mimics. | Medium-high / low-to-moderate, uncertain. Requires confirming that these channels are present in authorized features; do not fetch substitutes without checking access and licensing. |
| 3 | **DEM curvature–drainage lineament concordance:** official DEM, profile/plan curvature plus drainage-network deflection and ridge/valley alignment at multiple scales. | Near-surface scarps and structurally guided drainage may expose unrecorded traces. Lithologic boundaries, landslides, erosion, roads, and DEM artifacts mimic faults. | Medium / low-to-moderate, uncertain. 1 m DEM links are referenced by the competition materials but require official access/data availability verification. |
| 4 | **Magnetic edge × topographic lineament interaction:** multiply calibrated magnetic edge coherence by DEM lineament persistence, with spatially independent feature ablation. | Independent geophysical and geomorphic evidence may improve precision while revealing concealed structure; unlike either signal alone, tests concordance rather than single-layer intensity. Contacts plus coincidental landforms can mimic concordance. | High / moderate, uncertain. Needs both layers and leakage-safe holdout; do not claim gain before evaluation. |
| 5 | **Radiometric alteration–magnetic structure cross-gradient:** local radiometric contrast conditioned on magnetic structural edge, with distance-to-edge controls. | Targets alteration adjacent to a structural boundary rather than the catalogue trace itself, potentially identifying omitted geothermal structures. Lithologic contacts and surficial geochemistry can mimic it. | High / low-to-moderate, uncertain. Only viable if authorized bands exist and each feature passes the leakage canary. |

**Ranking is a prioritization judgment, not a measured DTI ranking.** No candidates are validated and no expected numeric improvement is asserted. The shared template and holdout must be inspected first; candidates already implemented there must be marked duplicate/previously tried rather than rebuilt. The official competition stack is the first source to check. No unverified external layer is proposed as an experiment; if the required bands are absent, stop and consult the official USGS GeoDAWN portal and competition data page for availability and permitted use before proposing download.

## Why the cited 0.2778 result cannot be explained as a verified win here

The linked GEMSDOE32 mirror's page reports a raster named `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` and provides its own rationale: pruning points close to the known catalogue from an earlier dotted prediction. It also explicitly describes the 0.2747 value as a model projection, and says no organizer score exists for that artifact. The mirror content retrieved for this review does not substantiate an organizer-confirmed 0.2778 score for that filename; the user prompt supplies that association. Thus we cannot claim why it earned 0.2778 or validate that score without an official receipt and artifact. In general, thinning can improve a precision-sensitive spatial score if it removes redundant false-positive mass while preserving useful coverage, but it can reduce recall; only the official metric and leakage-safe blocked validation can establish the tradeoff. Do not state that any candidate will exceed 0.2778 or the stated 0.3195 leaderboard figure.

## Official links for manual audit

- [DrivenData competition overview/rules](https://www.drivendata.org/competitions/306/competition-doe-gems/)
- [Competition problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Competition about/resources](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/)
- [Competition data page (login may be required)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
- [Official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [DrivenData reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)
- [DOE/NLR submission guidance PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [USGS GeoDAWN survey data page](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [INGENIOUS project](https://gbcge.org/current-projects/ingenious/)
- [EPSG:32611 — WGS 84 / UTM zone 11N](https://epsg.io/32611)
- [GEMSDOE32 mirror (community project, not an official score receipt)](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

Links are pointers for review; this checkout did not download gated competition data or verify the contents of every linked document. The data page may require DrivenData authentication; this environment has no competition login session. Never put credentials in the repository.

## Submission procedure and gates

1. Obtain the competition-provided `training_features.tif`, `labels.tif`, `sample_submission.tif`, any permitted DEM/features, and shared template tools from their official authorized locations. Keep large/private competition files out of Git.
2. Inspect the complete shared template and call its cached stack/evaluator/writer; record versions and hashes. Confirm the evaluator exactly matches the published metric, including spatial kernel and masking behavior.
3. Run the spatially blocked segment holdout and feature-alone leakage canary. Report withheld positive count, fold design, evaluator version, confidence interval, and all-fold results. Compare only like-for-like holdout estimates. Do not use catalogue-derived feature information from withheld segments.
4. Before/after placement calculate rank correlation and dot overlap against every available registry raster; abort and record duplicate if either threshold in the run protocol is crossed.
5. Only if the candidate beats the established holdout best, passes duplicate/leakage/format gates, and has an approved selector decision, write the file with the shared writer. Re-open the written bytes and verify one band; float values finite and in `[0,1]` throughout the required footprint; exact CRS, dimensions, and geotransform match the sample raster; record SHA-256. Confirm handling of cells outside the footprint against the current official validator rather than assuming NaN or a nodata sentinel is safe.
6. Present a prominent, plainly labeled “Download submission GeoTIFF” with unique competition name and <=140-character note only after those checks pass. Explain exactly how to upload it at the official DrivenData submission form. Never imply a local validator guarantees organizer acceptance or score.

## Limitations and next work

**Blocking:** official data, template/cache, evaluator and writer are absent. Competition page data access may require an authenticated account; this agent cannot bypass access controls. No experiment, TIFF, holdout estimate, CI, validator receipt, or unique-submission claim can be made. The user's pasted result lists also contain missing scores and conflicting leaderboard highs. Research claims must be checked against primary sources and competition artifacts.

**Next:** (1) obtain permitted data through the logged-in official competition page and place it under ignored `data/`; (2) populate/reuse the shared template tools; (3) run one selected candidate under the three-experiment/two-hour limit, starting with baseline reproduction and leakage canary; (4) implement/test the shared validator and accessible Pages executive summary; (5) only then create any download artifact or PR for a complete implementation. No submission slot should be spent on an unvalidated candidate.

## Session run card (this review)

```json
{
  "hypothesis": "No experiment run; candidate slate is preliminary",
  "mechanism": "Not evaluated: required cached stack and leakage-safe holdout are absent",
  "named_non_fault_mimic": "Lithologic contacts (for magnetic-edge candidate)",
  "holdout_dti_ci": null,
  "holdout_label": "NOT RUN; evaluator and withheld-positive count unavailable",
  "correlation_overlap_vs_registry": null,
  "raster_sha256": null,
  "validator_output": "NOT RUN; no raster; CRS/shape/transform reference unavailable",
  "submission_name": null,
  "submission_note": null,
  "verdict": "negative"
}
```
