# H33 result and leaderboard claim audit

**Reviewed:** 2026-10-22 UTC. This note distinguishes public-source statements, user-supplied claims, and model projections. It does not assert a score for a GEMSDOE87 artifact.

## Question asked

The request attributes a high reported value to `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` and asks why it performed well and whether a new submission can exceed it.

## What the linked GEMSDOE32 site says

The [GEMSDOE32 landing page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) describes H33-2-B2 as a *removal* of predictions near the existing catalogue from a pre-existing sparse field. It reports the candidate as **unscored** and explicitly says its live DTI projection is a model, not an organizer score. The page also says no organizer score exists for artifacts in that repository. Its linked [leaderboard page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/leaderboard.html) separates the official public leaderboard rows from the group's own owner claims and states that the latter are not linked to organizer receipts.

This directly conflicts with a reading of the prompt's H33 value as an organizer-confirmed score for that exact TIFF. The supplied page is a project mirror, not a DrivenData submission-page receipt. The exact file-to-receipt association was not available in this checkout. **The claimed value is therefore unverified and is not entered here as a score.** See [`docs/irregularities.md`](irregularities.md) for the tracked review flag.

## Plausible mechanism — not causal attribution

The linked project describes H33-2-B2 as pruning low-priority prediction pixels near already mapped faults. That mechanism is plausible under the competition's target: the public fault catalogue is known to be incomplete, while the challenge asks for additional faults. The official metric uses distance-weighted overlap; predictions that spend mass far from hidden fault pixels add false-positive cost, whereas removing redundant or low-credit pixels can improve the ratio if sufficient coverage is retained. A deletion rule can therefore improve a score without discovering a new physical feature.

This is a mechanistic explanation of why a *catalogue-flank removal* might help; it is not evidence that this exact change caused the reported H33 value. H33-2-B2 also changes how emitted mass is distributed, so a causal test needs an exact baseline/candidate pair and the same scoring split/evaluator. A filename suffix such as `zeros` is not evidence of the file's nodata or pixel-value behavior.

## Can GEMSDOE87 beat it?

Not established. This checkout has no training features, labels, sample grid, cached feature stack, holdout evaluator, writer, registry rasters, or prediction file. Thus there is no HOLDOUT-DTI, confidence interval, novelty test, or portal-format receipt to support a prediction of success. The official leaderboard is live and mutable; the [current official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) was reachable during this review. Leaderboard rows are not a substitute for a receipt that ties one particular TIFF to one result. No numeric live-leaderboard value is copied into this project's run card.

The only responsible answer is: **it is scientifically possible to outperform a reported result, but there is no evidence from this checkout that we will.** Do not spend a weekly entry until the selected hypothesis beats the shared spatial holdout baseline and all leakage, novelty, and format gates pass. The user-supplied comparison and any score claim need a submission-page receipt before being treated as ORGANIZER-CONFIRMED.

## Evidence needed to close the discrepancy

- Exact H33 GeoTIFF bytes and SHA-256.
- DrivenData submission-page receipt or equivalent organizer record identifying the filename and public score.
- Exact evaluator/split version and evaluation date.
- A controlled baseline TIFF differing by only the H33-2-B2 rule.
- A re-read of both TIFFs verifying grid, mask, dtype, nodata, and values.

None of these associations was recreated in this checkout.
