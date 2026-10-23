# Preregistered hypotheses — session 2026-10-23

Written **before** H87-LWD construction or holdout evaluation. The frozen H87-BMTD lane remains a completed negative (`evidence/budget.json` status `stopped-by-duplicate`) and is not rerun.

## Lane, uniqueness resolution, and budget

The brief still supplies no single-method paragraph (IR87-001). This session adopts **H87-LWD: magnetic tilt local-wavenumber contact locator** as the only implemented hypothesis. At most three experiments or two hours. Fixed parameters; no holdout-driven sweep. No competition uploads.

**Uniqueness resolution (next-step 1 from the frozen run, explicit):** the protocol names two tests — rank-correlation of the *raster* (>0.90) and 3 px overlap of *dots* (>0.70). The shared template already implements `uniqueness.two_phase_summary`: the inherited *literal* reading treats every positive pixel as a dot (so a saturated continuous prior fires on every nonempty candidate), and a *like-for-like* reading applies the same overlap threshold only to dot-fields while Spearman still applies to every raster. Thresholds are not changed and dense fields are not silently exempted. Lane-drift stop uses Spearman plus like-for-like overlap. Literal dense-field overlap is reported as the known degeneracy. Complete inventory clearance is not claimed from a scoped comparison set.

## Ranked queue (qualitative expectations, not projected scores)

| Priority | Hypothesis and exact layers | Targeted signature / transform | Why potentially unmapped, not just catalogued | Distinction / implementation cost | Non-fault mimic |
|---|---|---|---|---|---|
| 1 | **H87-LWD — tilt local wavenumber**; `tmi_hg` (band 3) and `tmi_vg` (band 9) enter the candidate. `iso_grav_anom_hg` (18) and `det_elev_slope` (19) are controls only, with band 3 also as the magnetic-HGM control | Miller–Singh tilt `atan2(VDR, THDR)`; Thurston–Smith local wavenumber `k = \|grad tilt\|`; ranking `k × AS/(AS+median AS)`, label-free max-normalization. Binary diagnostic uses shared `emit_decimated` (`tile_px=3`) and 37,654 area-allocated dots | USGS Qfaults / INGENIOUS traces are Quaternary *surface* ruptures. Buried basin-fill faults can still juxtapose magnetic layers (Grauch et al. 2001) without a mapped scarp. No catalogue distance, tips, or prior prediction enters the feature | Not H87-BMTD (no texture NCC / tangential shift). Not H33 (not a 200 m catalogue-flank prune of a parent). Not HGM magnitude: k uses *both* vertical and horizontal derivatives and is theoretically magnetization-direction independent for 2-D contacts. Low CPU cost; bands already in the pinned stack. Highest research priority, **not** a numerical score prediction | Lithologic contacts, dikes, volcanic flow edges, GeoDAWN flight-line / terrain-clearance artifacts |
| 2 | **H87-GCF — paired opposite-sign gravity-curvature flanks**; `iso_grav_anom` (13), `iso_grav_anom_hg` (18) | Antisymmetric second-derivative pair across a narrow basement-flexure corridor, not the maximum gravity gradient | Buried throw with no scarp. No fault-map input | Signed pair test, not HGM ridge / basement-step magnitude. Moderate cost. Lower than LWD because regional gravity smoothing may erase the pair | Sedimentary pinch-outs, buried intrusive margins, smooth basin edges |
| 3 | **H87-FABRIC — magnetic fabric termination at a conductive seam**; `rtp` (2), `cond_surf` (17), `tmi_vg` (9) | Orientation structure tensor of RTP texture ending at a thin conductivity-gradient boundary | Altered concealed intersection under cover | Termination, not co-located clay-cap fusion. Moderate-to-high cost; no new external data | Volcanic contacts, saline playas, irrigation conductivity |
| 4 | **H87-EQRES — off-catalogue earthquake-density residual**; `ieq_n100a15` (16) | High earthquake density where the public catalogue is absent | Seismogenic blind structures omitted from Qfaults | Residual, not raw density. **Leakage canary is mandatory** (AUC >0.90 blocks). Low cost | Mining blasts, induced seismicity, catalogue-correlated kernels |
| 5 | **H87-STRANS — dilatational transfer at a gravity step**; `geod_dilaterate` (8), `geod_shearrate` (7), `iso_grav_anom_hg` (18) | Localized dilatation (or shear/dilatation rotation) on a gravity discontinuity | Poorly mapped stepovers / relay ramps | Ratio-gradient, not strain magnitude gating. Low-to-moderate cost; scalar bands cannot reconstruct a full tensor | Groundwater subsidence, interpolation seams |

All five use only layers already present in the integrity-verified competition mirror. No untested external-data dependency is presented as viable. Band 6 (`tc`) and band 15 (`depth_to_base_surf`) remain unused: GeoTIFF descriptions conflict with the organizer page’s radiometric “tc” visualization and “top-of-crustal magnetic source depth” wording (IR87-014). Official original download is login-protected; mirror consistency is not organizer authentication.

## Physical evidence and limits

- [DrivenData problem / metric / submission](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/): target is **fault presence**, not geothermal vent coordinates. Hidden labels are expert-identified faults absent from the public catalogue.
- [Miller & Singh 1994, Geophysics, doi:10.1190/1.1443674](https://doi.org/10.1190/1.1443674): tilt angle as a contact locator.
- [Thurston & Smith 1997 SPI, Geophysics, doi:10.1190/1.1444190](https://doi.org/10.1190/1.1444190) and [SEG Wiki: SPI](https://wiki.seg.org/wiki/Dictionary:Source_parameter_imaging_method_(SPI)): local wavenumber maxima over 2-D contacts; depth = 1/k only *at those maxima*.
- [Grauch, Hudson & Minor 2001, USGS / Geophysics, doi:10.1190/1.1444961](https://www.usgs.gov/publications/aeromagnetic-expression-faults-offset-basin-fill-albuquerque-basin-new-mexico): aeromagnetic linear anomalies from faults that offset basin fill, including a thin–thick growth-fault model. Different basin; supports the *possibility*, not this detector’s precision.
- [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), DOI 10.5066/P93LGLVQ: E–W flight lines, N–S tie lines, variable terrain clearance are documented artifact risks.
- [DrivenData staff masking clarification](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2): known-fault *pixels* are excluded; neighborhoods are not automatically excluded.

## Fixed experimental design (H87-LWD-01)

1. Reuse the unmodified `gems57` template pinned to `60GEMSDOE@b99591eede63c6d45c8a896255b8cd34824fa00b`. Reuse the inherited physical-band cache.
2. Four fixed grid quadrants; whole intersecting 8-connected catalogue components withheld; 80-pixel training buffer; pixel-exact masking of visible faults. Zero catalogue-derived model features.
3. Canary each derived channel, both magnetic inputs, and each control. AUC >0.90 blocks trust.
4. Binary emission density 37,654 points, area-allocated, `tile_px=3`. Pooled official-formula DTI, α=0.2, β=0.8, 300 m triangular kernel. Shared physical 20 km cluster bootstrap, 2,000 draws, seed 87122.
5. Controls: magnetic HGM (band 3), gravity HGM magnitude (`abs` of signed band 18), topographic slope (band 19). Beating these cannot establish beating all prior projects.
6. Surface then dots compared to H33, H27-4, D28-poisson (sparse family) and the 57GEMSDOE saturated witness. Spearman >0.90 or like-for-like overlap >0.70 is a lane-drift stop.
7. No weekly slot. Negative artifacts remain downloadable research files.

**No public/private leaderboard improvement can be predicted or certified by this holdout.**

---

# Archive — 2026-10-22 H87-BMTD (completed negative)

The following lane was implemented and stopped. It is not this session’s candidate.

Lane **H87-BMTD: bilateral magnetic texture dislocation** used only RTP (band 2). HOLDOUT-DTI binary diagnostic 0.043385, 95% CI [0.035700, 0.051025], 60,988 withheld positives, evaluator `gems57-pooled-hide-v2`; paired delta versus magnetic HGM −0.000288, CI includes zero. Literal overlap with a saturated continuous prior was 1.0. Frozen TIFF: `gems87-bmtd-20261022-50041440adba-RESEARCH-DO-NOT-SUBMIT.tif`. Post-run defect IR87-016 (outer-grid guard) was not remeasured after the stop.
