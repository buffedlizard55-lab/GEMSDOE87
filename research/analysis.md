# H87 research finding and H33 forensic explanation

## Session 2026-10-23 (H87-LWD and H87-GCF)

The frozen H87-BMTD lane was left stopped. This session preregistered five hypotheses, then ran two fixed experiments against the same hide-and-recover instrument (`gems57-pooled-hide-v2`, 60,988 withheld catalogue positives, 95% physical-cluster CI).

**Uniqueness resolution:** shared `uniqueness.two_phase_summary` reports the inherited literal reading (dense continuous priors fire on every nonempty candidate) and a like-for-like reading (3 px overlap only vs dot-fields; Spearman vs every raster). Thresholds were not changed. Lane-drift stop = Spearman >0.90 or like-for-like overlap >0.70.

All values below are **HOLDOUT-DTI**, evaluator **gems57-pooled-hide-v2**, **60,988 withheld positives**.

| Arm | HOLDOUT-DTI | 95% CI |
|---|---:|---|
| H87-GCF sparse dots (downloadable file) | 0.049057 | [0.041359, 0.056931] |
| H87-LWD sparse dots | 0.041641 | [0.033968, 0.049153] |
| Gravity HGM control (`abs` band 18) | 0.058476 | [0.042655, 0.075295] |
| Magnetic HGM control (band 3) | 0.043673 | [0.032318, 0.055570] |
| Topographic slope control (band 19) | 0.022435 | [0.017370, 0.027722] |

GCF minus gravity HGM: **HOLDOUT-DTI delta −0.009419**, 95% CI **[−0.025607, 0.005533]** (includes zero). Neither candidate beat every comparable control. Canaries: no two-sided AUC >0.90.

Like-for-like sparse overlap of GCF dots vs H33 / H27-4 / D28: **17.2%** (under 70%). Worst Spearman **0.021**. Literal overlap vs the saturated 57GEMSDOE continuous witness remains **1.0**. GCF placed 37,654 off-catalogue dots. **Verdict: negative. DO NOT SUBMIT.** No weekly slot.

Why H33 could still look strong on a leaderboard while these holdout numbers are ~0.05: holdout truth is the public catalogue; the official test is hidden expert faults. H33 is a 200 m catalogue-flank prune of a parent, not a new detector. The 0.2778 figure remains an unverified historical claim, not ORGANIZER-CONFIRMED. Public leaderboard observation 0.4413 is not an artifact receipt.

## What was actually established (2026-10-22 H87-BMTD archive)

This checkout began with only a repository title. There was no existing local training pipeline, holdout best, cached dataset, or prior-session task list to resume. We recovered the required feature stack and grid files autonomously from immutable owner GitHub mirrors, verified their SHA-256 hashes, and reused the inherited physical-band cache. These are **integrity-verified mirrors**, not organizer-authenticated originals. The sample's positive values were never used as predictions or features.

Four hypotheses were recorded in `research/hypotheses.md` before implementation. Only H87-BMTD was implemented. This is a deterministic CPU image-statistic model, not a claimed neural-network training run. No earlier prediction raster entered the candidate. The scientific experiment stopped on the duplicate gate; packaging and software validation afterwards did not resume scientific optimization.

## Registry-wide quick review: explicit scope

The quick cross-project review covered **93 pinned repository trees** and the inherited registry's **812 historical claim references**. It is an artifact/metadata inventory, **not** an editorial reading and independent revalidation of every site or every claimed result. The [per-repository catalog](../docs/data/prior_catalog.json) preserves immutable tree links, representative filenames, and explicitly filename-only approach tags. The original numerical claims remain quarantined and are not promotion evidence.

| Prior family encountered in artifact names / sources | Scientific lesson and what was actually checked |
|---|---|
| Ridge, gradient and physical-layer names | Edge strength can identify lithologic contacts as well as faults. Filenames alone do not establish a physical mechanism or a controlled result. H87 instead tests similarity restored by lateral texture displacement and compares against fresh physical-gradient controls. |
| Sparse emission, thinning, pruning and decile names | These can change prediction mass and redundancy without detecting a new geological structure. Only the H33-to-parent pruning relation below was verified pixel by pixel; no universal thinning benefit is asserted. |
| Blend, fusion, weighting and ensemble names | Combining old fields can inherit their correlated errors and catalogue bias. No such prediction is an H87 input, and weights or reported historical values are not copied. |
| Continuous/soft confidence representations | Positive support can saturate the study area even with different ranks. This was directly confirmed for the universal-overlap witness; a low rank correlation does not defeat the separate overlap rule. |
| Official U-Net reference | The pinned notebook's cells 0, 1 and 16 were inspected, not trained. It uses ordinary Tversky loss and random-patch Monte Carlo splits; these are not the official distance-weighted evaluation and do not replace required whole-component holdout. It is a future modelling reference, not a comparable measured best. |

A full mechanism-by-mechanism code review or organizer revalidation of all historical artifacts was **not completed**. The negative decision does not require such a clearance: one valid overlap witness is sufficient to stop. This scope limit is retained instead of claiming that an inventory authenticates all previous approaches and results.

## Why H33 could have improved — and what we cannot know

The requested historical value for H33 is a **user-reported claim without a submission-page receipt**. GEMSDOE32's own retrieved page calls the artifact unscored. It would be false to classify this number as ORGANIZER-CONFIRMED. A public leaderboard observation cannot authenticate the score of a particular unlinked artifact either.

What we independently verified by decoding the prior files:

- H33-2-B2 contains 37,654 positive pixels.
- The corresponding GEMSDOE31 solo-D28 parent contains 40,199 positive pixels.
- H33 adds **zero** pixels to this parent and removes **2,545**.
- Every removed pixel is within 200 m of the public catalogue, and the mask `parent & (distance_to_catalogue > 2 pixels)` equals H33 **exactly**.
- H33 has no positive pixels within 200 m of that catalogue.

Evidence: [`h33_forensics.json`](../docs/evidence/h33_forensics.json). The prior files were read for education and comparison only, not reused to generate H87.

The organizer's [published metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric) and [staff clarification on exact known-fault masking](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2) explain a plausible mechanism. Known pixels are excluded, but their **neighborhoods are not automatically excluded**. A dot on a near-catalogue flank can therefore incur false-positive cost against new-fault truth. Removing low-credit flank dots can reduce that cost. This is not evidence that all flanks are false: an unmapped splay can lie near a mapped trace, so blind pruning can remove genuine discovery signal.

Let `T = TPw`, `S = sum(p)`, `C = sum(p * nearest_truth_kernel)`, and `K = |G|` on the **active** evaluation domain. Then `FPw = S-C`, `FNw = K-T`, and the official formula is exactly

```
DTI = T / (0.2*T + 0.2*(S-C) + 0.8*K + epsilon)
```

For an additional unit-confidence dot, let `deltaT` be its marginal truth-coverage gain and `k_self` its own nearest-truth kernel credit. Ignoring only the negligible denominator epsilon in the displayed algebra, inclusion improves DTI when

```
deltaT * (1 - 0.2*DTI) > 0.2*DTI * (1 - k_self)
```

This is a conditional marginal test, **not** a universal threshold on the raw model confidence. A dot redundant with nearby predictions can have almost no marginal coverage even if it lies on a high-valued surface. Deleting such dots can improve the metric; it does not constitute a new geological detector. The same reasoning applies to removal with the inequality reversed for lost marginal coverage.

**Causal limitation:** Without hidden truth, a receipt, and controlled organizer evaluations of parent and child, we cannot establish why a particular reported leaderboard value changed. Historical "live-mirror", translated truth, prevalence-corrected, or projected values are not accepted here as holdout or organizer scores. GEMSDOE32's audit also contains internally inconsistent summary-versus-fold entries; those numbers are not imported as a benchmark.

## Can this approach beat the requested historical targets?

A stronger detector could in principle outperform those artifacts, but no defensible numerical projection follows from the available public labels. The current [official public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) was observed to lead at 0.4413 on 2026-10-22. This is a **PUBLIC-LEADERBOARD-OBSERVATION**, not an ORGANIZER-CONFIRMED submission-page receipt for our artifact. Lower targets in the original brief are stale.

The key scientific objective is a better *ranking of previously unlabelled fault evidence*, not further re-encoding or re-spacing of a successful prior map. The top new hypothesis tried to detect lateral texture displacement that an edge-strength detector does not measure. The official [USGS Tintina study](https://pubs.usgs.gov/sir/2007/5289/SIR2007-5289-C.pdf) supports magnetic pattern restoration as a displacement interpretation, but at a very different scale and location. The [USGS Albuquerque study](https://www.usgs.gov/publications/aeromagnetic-expression-faults-offset-basin-fill-albuquerque-basin-new-mexico) establishes magnetic expressions of concealed basin-fill faults, not the validity of our chosen filter. These sources motivate a test, not a favorable conclusion.

## H87 test result

All following performance values are **HOLDOUT-DTI**, evaluator **gems57-pooled-hide-v2**, **60,988 withheld positive pixels**, pooled across four fixed spatial quadrants. The bootstrap resamples **158 physical 20 km clusters**, **2,000 draws**, with conditional **95% intervals**. It is not a private-test or leaderboard interval.

| Fixed arm | HOLDOUT-DTI | 95% conditional CI | Interpretation |
|---|---:|---|---|
| H87 BMTD binary placement diagnostic | 0.043385 | [0.035700, 0.051025] | Preregistered fixed-density diagnostic; no final submission dots were placed |
| Magnetic horizontal-gradient control | 0.043673 | [0.032136, 0.056598] | Strongest comparable control in this initially empty checkout |
| Detrended-elevation slope control | 0.022435 | [0.017474, 0.028086] | Independent supplied physical control |
| H87 continuous research surface | 0.038534 | [0.034066, 0.042790] | The representation actually serialized for download |

Paired H87 binary diagnostic minus magnetic control: **HOLDOUT-DTI delta -0.000288**, **95% CI [-0.009126, 0.008212]**, same evaluator and withheld positives. It does **not** demonstrate improvement. No new experiment was run to tune the result after seeing this interval.

Canaries covered every candidate input/derived feature and both controls, eight scalar channels per quadrant. The largest two-sided held-out AUC was **0.592483**, below the stop threshold of **0.90**. This is **HOLDOUT-AUC-CANARY**, not a DTI score, and does not prove that all forms of leakage are absent. Physical model functions accept no catalogue input. The inherited feature cache contains no catalogue-derived feature in this candidate.

The shared split withholds entire intersecting 8-connected catalogue components, including tails in other quadrants, and applies an 80-pixel buffer to training eligibility. The candidate has no fitted weights, so no held labels can alter its transform. Every fold masks visible known pixels exactly. Unsupported physical coverage remains in the truth denominator; it is not silently dropped.

**Post-run defect IR87-016:** the 40-pixel internal missing-data guard did not explicitly pad the outer array boundaries as missing. We measured 101,560 positive surface pixels within 40 px of the outer grid boundary, where edge-replicated texture can contaminate the signature. The original implementation is preserved exactly in `research/frozen/features_h87_01.py` with its measured source hash. Current source code fixes the guard by padding the boundary; the fix is tested only on synthetic fixtures. The frozen negative TIFF and its reported holdout values were **not recomputed after the duplicate stop**, and must not be described as measurements of the corrected implementation. This is an additional reason not to trust/promote the artifact.

## Literal uniqueness creates a proved no-go

The inventory scanned **93 accessible owner repositories**, unioned with historical Git blob pins, and restored **1,164 valid single-band grid-matching raster files**. One additional candidate TIFF is malformed (`GEMSDOE63:docs/downloads/smoke.tif`, missing StripOffsets), so complete inventory clearance is unavailable. Private, unlinked, external, and later-written files remain outside the accessible scope.

The shared `gems57.uniqueness.saturation_certificate` independently found an earlier continuous field:

`57GEMSDOE:docs/downloads/h57-continuous-anatomy-20261009T201252Z-f44b207a70f0.tif`

Its positive support covers all **5,106,385** allowed off-catalogue cells within 3 px. Under the brief's literal rule—every positive finite pixel is a dot, any forward overlap greater than 70% is a duplicate—**every nonempty allowed dot set is blocked by this one raster**. This is a mathematical incompatibility in the requirements, not proof that the newly computed H87 field copied the old one. We did not silently exempt dense surfaces or alter the threshold.

A single valid counterexample is sufficient for rejection. Candidate-specific comparisons therefore stop at the educational H33 reference and this saturated witness; no complete candidate-versus-all-raster clearance is claimed. Both the pre-placement continuous surface and serialized research artifact have **1.0 literal overlap** with the witness. Their rank correlations are low; the explicit overlap rule still requires rejection. Final submission dot placement was not performed after the pre-placement stop.

The new TIFF's bytes differ from every restored valid registry file. The candidate is physically generated anew, but **byte freshness is not protocol uniqueness**. Its correct verdict is **negative**. The continuous GeoTIFF and ZIP are research deliverables, not a competition-approved submission.

## Range-error prevention and automated validation

The original failing downloaded document is not present, so its root cause cannot be diagnosed. Out-of-range model values and Float32-min nodata sentinels are plausible failures. The public specification permits NaN outside the footprint; it would be incorrect to assert that NaN necessarily caused the portal message.

The unmodified shared writer rejects invalid input rather than silently clipping it, writes temporary files, reopens the TIFF, validates grid/range/finite values, verifies the one-TIFF ZIP by bytes, then publishes atomically. An independent script reopens the final artifact again and validates its TIFF, decoded pixel hash, ZIP membership, CRC, exact ZIP/TIFF equality, footprint, known-pixel mask, CRS, shape, and transform. Every cell is finite and in [0,1], no nodata tag is carried, and outside-footprint values are zero by conservative project policy. There is no human inspection gate in this local workflow. This is still not proof of authenticated portal acceptance.

## Next-session priorities (not performed after the stop)

1. **Resolve the registry contradiction explicitly with the protocol owner.** Separate continuous-surface correlation from like-for-like sparse-dot overlap, or specify another justified treatment of saturated supports. Do not change this unilaterally and do not erase this run's negative verdict.
2. Obtain official sample/feature hashes or an organizer-authenticated provenance receipt through an authorized connection. Never request or store passwords/tokens in chat. Existing mirrors allow CPU experimentation but not provenance certification.
3. Acquire actual submission-page receipts for the historical high-value claims and the current account-specific cap/usage. Preserve exact artifact hashes; do not use leaderboard position as an artifact receipt.
4. Resolve the malformed registry TIFF at its source. It remains an error, not a quietly skipped comparison.
5. In a separately authorized new run, investigate whether the magnetic texture detector is dominated by acquisition directions or curved lithologic contacts. Read the GeoDAWN flight-line metadata before any orientation-specific correction. No public-geometry correction was fitted here.
6. Consider H87's lower-ranked signed-pair/fabric-termination hypotheses only under a new lane/budget. Confirm ambiguous feature definitions first; the supplied `tc` metadata and the depth-band interpretation should not be guessed.
7. Train a learned image model only when a compatible official-data provenance chain and spatial validation design are in place. GPU access is useful for that future work, not required for the deterministic CPU experiment completed here.

## AI disclosure

An Arena.ai coding agent assisted with hypothesis drafting, code development, source retrieval, validation orchestration, documentation, and website generation. No synthetic geological labels, AI-generated measurements, or organizer scores were fabricated. A participant must include the required AI-use disclosure in any eventual competition narrative, as specified in section 3.2 of the [official rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf). This run did not submit a competition entry.
