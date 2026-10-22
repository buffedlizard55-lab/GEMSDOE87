# GEMSDOE87 — auditable GEMS Prize research

> **Status: not ready to submit.** This checkout contains only this README. It has no competition rasters, cached feature stack, holdout evaluator, writer, validator, or generated GeoTIFF. No submission score or validation result can honestly be reported from this checkout. **Do not download or submit a fabricated placeholder.**

## Mission and operating principles

Build an auditable workflow for discovering geothermal-indicative faults missing from the public catalogue, and produce a single-band GeoTIFF that conforms to the DrivenData submission grid. Optimize for the chance of finding real unmapped faults, not for a proxy score alone. Preserve Arena's principles: **Maximize P(Win** — reserve scarce submission opportunities for evidence-backed candidates) and **Own the Outcome** — report defects, negative findings, uncertainty, and blockers rather than claiming success without evidence.

The project brief requires: use official/publicly licensed sources; keep evidence and links reviewable; make a validated `.tif` easy to download with a unique name and short note; maintain a current, auditable research feed; never present a projection as a measured score; do not spend a competition slot unless the candidate beats the established spatial holdout best; and verify submission range, CRS, shape, and transform. This README is the durable project brief and should be reviewed before each project session. The full prior request is represented here as requirements rather than duplicated verbatim.

### Non-negotiable experiment protocol

1. **Method lane:** work on one preregistered method only. Stop if surface-raster rank correlation with a registry raster is >0.90 or >70% of emitted dots lie within 3 px of a registry-dot raster; record the duplicate and stop. The prompt supplied no actual method paragraph to define the lane, so a method must be explicitly selected before experiments.
2. **Shared tooling:** reuse the template's cached feature stack and shared `evaluate_holdout.py` / `submission_writer.py`; fix shared-tool defects in the template, not in a private fork. Use spatially held-out whole fault segments plus a buffer; derive catalogue features only from visible faults; mask visible faults pixel-exactly; score pooled DTI with alpha=0.2, beta=0.8 and the 300 m triangular kernel. Do not claim this protocol ran unless its artifacts and logs exist.
3. **Evidence labels:** every numerical score must be marked **HOLDOUT-DTI** (evaluator version, withheld-positive count, 95% CI) or **ORGANIZER-CONFIRMED** (submission-page receipt). A model projection is not a score.
4. **Leakage canary:** evaluate each input feature alone on holdout before trusting combinations. AUC >0.90 is a leakage warning until investigated.
5. **Novelty gate:** compare surface rank-correlation and dot overlap against every available registry raster both before placement and on final dots. Do not claim novelty when the registry files are absent.
6. **Budget:** at most 3 experiments or 2 hours; do not select a competition slot here. Slot selection is a separate decision under the competition's current weekly cap.
7. **Submission gate:** independently reopen the written TIFF and verify one band; values in [0,1]; no NaN inside the footprint; correct CRS, dimensions, and affine transform against the official sample submission; include SHA-256, a unique submission name, and a note <=140 characters. If any prerequisite is missing, verdict is **negative / not ready**, not submit.

## Initial repo review and verified state (2026-10-22)

`git ls-tree -r HEAD` and a filesystem inventory found only `README.md`. There is no `data/`, no scripts, no tests, no website, and no GeoTIFF. The branch starts from a single initial commit. Therefore this repository cannot presently run the requested holdout, leakage canary, correlation/overlap gate, raster validator, or TIFF writer. The request mentions `evaluate_holdout.py`, `submission_writer.py`, a cached feature stack, and a template, but none is present in this checkout. No experiment has been run and no candidate is validated.

The DrivenData problem description states that the target is geological faults, that public USGS/INGENIOUS fault labels are incomplete and may contain inaccuracies, and that newly expert-labelled faults form the competition's test set. It describes the supplied `training_features.tif` as UTM zone 11N / EPSG:32611 at 100 m resolution and lists conductivity/depth, detrended elevation/slope, strain, gravity, magnetic, and earthquake-density variables. Data access is via the competition data page; this environment has no authenticated competition download or local data. The official reference solution's README instructs competitors to download the competition data and place it in `data/` before running its notebook. These are source-backed facts; this checkout itself does not prove a data download is obtainable without login.

### What the cited H33 result does and does not establish

The user's supplied result says `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778` and names it the highest score on GEMSDOE32. The linked GEMSDOE32 page is a group project page, not an organizer receipt. It describes a candidate GeoTIFF and explicitly labels its modeled live score as a projection, not an organizer score. Neither that page nor the supplied text is an organizer-confirmed receipt for the 0.2778 entry. Thus **0.2778 is an unverified reported score here**, not a score we reproduce or can attribute causally.

A mechanistic explanation cannot be established from a filename and score alone. The group page's general account is that thinner, better-targeted predictions can improve a precision-penalizing distance-weighted Tversky score by reducing predicted mass away from truth while retaining coverage. That is a plausible explanation, not proof that it caused this H33 result. Causal attribution requires the exact TIFF, scoring split, evaluator/version, baseline comparison, and an official receipt. The supplied `zeros` suffix is not enough to infer the TIFF's nodata/value behavior. Claims in the prompt that the current leader is 0.3195 or 0.4413 conflict; the live leaderboard must be checked at decision time. No claim that this project can beat either value is warranted.

## Candidate hypotheses to preregister (not validated; no experiment spent)

These are research proposals, not findings. Novelty versus all GEMSDOE projects cannot be proven from a list of titles and this empty checkout. Their distinctness is tentative and must be checked against the exact prior code/raster registry before implementation. Each uses layers the official problem page says are provided, so no additional external data is required merely to compute the transform. That does **not** establish the data are locally available.

| Rank | Hypothesis and layers | Targeted physical signature | Why it might identify unmapped faults | Distinction from approaches named in the supplied history | Expected DTI / cost |
|---|---|---|---|---|---|
| 1 | **Cross-scale magnetic edge persistence:** reduced-to-pole anomaly, TMI, horizontal/vertical TMI slopes. Compare oriented edge responses across smoothing scales; retain edges persistent in scale and supported by independent magnetic channels. | Scale-persistent, spatially coherent magnetic gradients, not a single-scale lineament maximum. | A buried or subtle lithologic/contact discontinuity may produce a coherent magnetic boundary even where no mapped fault trace exists; this is only a proxy and can equally reflect non-fault contacts. | The supplied history mentions magnetic/geophysical baselines and lineaments, but does not establish whether scale-persistence consensus was tested. Novelty unknown. | **Potentially positive, high uncertainty / medium**; no local data, so no validation. |
| 2 | **Curvature–strain co-localization:** detrended elevation plus dilatation, shear strain rate, and second invariant; calculate signed multi-scale profile/planform curvature and require independent strain agreement. | Curvature ridges or breaks that spatially coincide with strain concentration across scales. | Fault-related deformation can shape terrain and strain fields; requiring co-evidence may suppress isolated terrain edges and expose unrecorded structures. | Topographic ridge/scarp and geophysical combinations appear in the supplied history; this exact scale-dependent curvature × strain gate is not evidenced as implemented. Novelty unknown. | **Potentially positive / high**; medium-high cost. |
| 3 | **Conductive-base discontinuity with magnetic confirmation:** surface conductivity and depth to conductive base, paired with magnetic gradients. | Abrupt depth-to-conductor / conductivity transitions that align with magnetic boundaries. | Faults can juxtapose or channel conductive units/fluids, potentially revealing structures omitted from surface fault catalogues. Hydrothermal alteration, lithology, and acquisition artifacts are major confounders. | Prior list includes alteration, radiometric, geophysical, and geothermal proxies; exact paired discontinuity test is unknown. Novelty unknown. | **Uncertain / medium**; medium cost. |
| 4 | **Earthquake-density anisotropy:** earthquake density plus strain layers; estimate directional anisotropy/coherence at scales wider than individual events. | Elongated seismicity-density fabric coherent with regional strain orientation. | Active or reactivated unmapped structures may organize seismicity; spatially coherent fabric is more fault-like than a local density peak. | Prior list includes earthquake / swarm ideas (e.g., seismicity-related titles), so this is particularly at risk of duplication. Novelty unknown. | **Uncertain / medium-low**; medium cost; likely confounded by sparse events. |

**Ranking is a qualitative research priority, not a numerical performance prediction.** The top candidate cannot be validated here because the feature TIFF, labels, cached stack, exact holdout evaluator and writer, and registry rasters are absent. Do not implement a separate fork or generate a competition TIFF from guessed grid metadata. After restoring the shared template and data, run exactly the top preregistered candidate first; only consider a submission if it beats the current holdout best under the specified evaluator, reports its 95% CI, passes the one-feature leakage canary and both novelty checks, and passes the file-format gate. If it fails, record a negative result and stop or use the remaining experiment budget.

## Official source register

| Source | What it supports | Link |
|---|---|---|
| DrivenData GEMS problem description | Task, dataset overview, supplied feature families, metric overview, prize-round context | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| DrivenData competition page | Competition rules and entry point; access current rules before submission | [Competition](https://www.drivendata.org/competitions/306/competition-doe-gems/) |
| DrivenData data tab | Official download location; sign-in may be required | [Data](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) |
| DrivenData about page | Competition background | [About](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/) |
| DrivenData leaderboard | Current leaderboard; mutable and must be checked live | [Leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) |
| DrivenData / sponsor reference code | Baseline implementation; its repository README says to place downloaded data in `data/` | [Reference solution](https://github.com/drivendataorg/gems-prize-reference-solution) |
| USGS GeoDAWN dataset | Official geophysical survey context/data portal | [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) |
| Great Basin Center for Geothermal Energy | INGENIOUS project context | [INGENIOUS](https://gbcge.org/current-projects/ingenious/) |
| EPSG registry | EPSG:32611 coordinate reference system reference | [EPSG:32611](https://epsg.io/32611) |
| US DOE/NLR report supplied in the brief | Submission-related document (review exact current competition requirements before relying on it) | [PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| GEMSDOE32 group project page | Group's reported artifact/analysis only; not an organizer confirmation | [GEMSDOE32](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) |

The competition page says additional datasets may be used if licensing permits use in the challenge and sharing with the sponsor for evaluation. Before using any external dataset, verify its official provenance, terms/license, spatial/temporal coverage, and sponsor-sharing permission. No external dataset has been downloaded or assessed in this checkout.

## Limitations and next steps

1. Restore the shared GEMSDOE template into this branch (including feature cache, evaluator, writer, tests and registry rasters) or establish the official source repository/path; do not silently recreate shared tools privately.
2. Obtain the competition data through the official data page using authorized access, including the sample submission and labels/features. Keep credentials out of the repository. The previous claim that data requires login is not independently verified in this checkout; direct data-tab access is user/account dependent.
3. Confirm the current official leaderboard, weekly submission cap, accepted format, and scoring rules from the live competition site.
4. Establish the method lane and exact baseline/holdout best, then test the top candidate within the prescribed budget. Keep a machine-readable run card per experiment.
5. Build an automated independent TIFF validator and clear submission-download page only after reproducible artifact generation. Show its validation receipt, SHA-256, unique name, and <=140-character note beside the download. Do not expose a file as ready when any gate fails.
6. A GitHub Pages site, automatic data feed, scientific literature library, and automated competition submission integration are not implemented in this checkout. Competition login/data and organizer-side submission receipts cannot be fabricated or bypassed.

### Run card for this checkout

```json
{
  "hypothesis": "Not tested: candidate 1, cross-scale magnetic edge persistence",
  "mechanism": "Scale-persistent gradients in provided magnetic layers may indicate structural discontinuities; lithologic contacts are a named non-fault mimic",
  "holdout_dti": null,
  "holdout_ci_95": null,
  "evaluator_version": null,
  "withheld_positives": null,
  "correlation_overlap_vs_registry": "Not measured; registry rasters absent",
  "raster_sha256": null,
  "validator_output": "Not run; no raster, sample grid, validator, or feature stack present",
  "submission_name": null,
  "submission_note": null,
  "verdict": "negative — blocked; not ready to submit"
}
```
