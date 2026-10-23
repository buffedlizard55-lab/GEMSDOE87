# Session-2 hypotheses (new authorized run, 2026-10-23)

Written before implementing session-2 code. The session-1 lane (H87-BMTD) was
negative (see `run_card.json`); it is not rerun. This is a new lane/budget
(max 3 experiments / 2 h), explicitly authorized by the re-issued brief.
Historical scores in the brief are unverified claims, not receipts.

| Rank | Hypothesis | Layer(s) | Physical signature | Why an uncatalogued fault, not a catalogued one | Differs from repo so far | Cost |
|---|---|---|---|---|---|---|
| 1 | **H87-PGF — paired opposite-sign gravity-curvature flanks** | `iso_grav_anom` (band 13) primary; band 15 diagnostic only; bands 3/19 controls only | Cross-normal 2nd derivative `D2` sampled at ±6 px has opposite signs (geometric-mean pair), max over 4 orientations | A buried basement throw flexes gravity without a surface scarp or magnetic texture offset; no catalogue feature is used | Session 1 measured magnetic texture *restoration*; PGF measures a *signed flank pair* in gravity. Queue item 2 in `research/hypotheses.md`, never implemented | Low–moderate CPU, bands already cached |
| 2 | Terminating magnetic fabric at a conductive seam | `rtp` (2), `cond_surf` (17), `tmi_vg` (9) | Structure-tensor fabric ends at a thin conductivity-gradient boundary | Altered concealed intersection can kill magnetic fabric under cover | Termination, not co-located edges; not implemented | Moderate–high |
| 3 | Localized strain-gradient mismatch | `geod_shearrate` (7), `geod_dilaterate` (8), `iso_grav_anom_hg` (18) | Sharp rotation of shear/dilatation gradient ratio at a gravity discontinuity | Transfer boundaries missed by catalogue continuation | Ratio-gradient rotation vs magnitude gating; not implemented | Low–moderate, weak identifiability |
| 4 | Paired opposite-sign *magnetic* tilt flanks | `tc` (6), `tmi_vg` (9) | Same paired-flank test on magnetic tilt instead of gravity | Shallow magnetic basement step under alluvium | Same transform family as #1 but different layer/physics; kept separate so #1 stays single-layer | Low |
| 5 | Radiometric K/Th ratio scarp-parallel low | radiometric bands in stack (exact band IDs to confirm from cache receipt before use) | Ratio low elongated parallel to (not on) a DEM slope break | Weathering along a concealed fractured zone can deplete K off-trace | Off-trace parallel halo, not on-trace scarp detection; band IDs unconfirmed → not viable until verified | Unknown |

**Non-fault mimic for #1:** sedimentary pinch-outs, buried intrusive margins,
smooth basin edges, and gravity interpolation boundaries can all produce
opposite-sign curvature flanks.

Decision rule (fixed before running): promote only if the candidate's paired
HOLDOUT-DTI 95% CI vs the best comparable control (magnetic HGM, topographic
slope; same evaluator `gems57-pooled-hide-v2`, same folds, same 37,654-dot
budget) lies entirely above 0, every leakage canary ≤0.90 two-sided AUC, and
sparse-dot registry checks pass (Spearman ≤0.90, ≤70% of dots within 3 px of
the H33 sparse reference). The saturated continuous registry witness
(IR: covers all 5,106,385 allowed cells) makes the literal any-raster overlap
rule unsatisfiable for *any* non-empty submission; that contradiction is
flagged, not hidden — like-for-like comparison is against sparse dot rasters.

## Experiment 2 (registered before running, 2026-10-23)
**H87-PGF-GM:** geometric mean of the band-13 paired-flank score and the same
paired-flank transform (identical orientations/step/flank, no new parameters)
applied to `depth_to_base_surf` (band 15). Mechanism: a real buried throw
flexes both gravity and the basement-depth surface; a gravity-only pinch-out
or interpolation edge should not. Same folds/evaluator/budget/controls and
promotion rule as experiment 1. This is the last PGF-family variant; any
further family change would be holdout-driven tuning.

## Experiment 3 (registered before running, 2026-10-23 — final in budget)
**H87-PGF×HGM fusion:** geometric mean of the experiment-1 PGF score (band 13)
and the bounded magnetic horizontal-gradient surface (band 3, the strongest
control, rescaled by its own label-free q99 rule in `bounded_control`).
Mechanism: a buried throw should flex gravity *and* offset magnetic basement;
either signal alone has non-fault mimics. Same folds/evaluator/budget/promotion
rule. If this does not clear the promotion rule, the session verdict is
negative and no further variants are tried.

## Session-2 irregularities flagged
- IR-S2-01: the legacy `scripts/validate_submission.py` requires NaN/null
  outside the footprint and therefore reports the new zeros-outside file as
  not "ready", while the shared `gems57` writer/validator requires all-finite
  zeros-outside. Both policies exist in-repo. We ship zeros-outside because
  every cell is then literally in [0,1] (the portal error class reported by
  the user cannot occur); the shared writer's on-disk validator PASSes.
  Receipt: `evidence/pgf_validation.json` (legacy view) vs the writer receipt
  `docs/downloads/gems87-pgf1-37654dots-20261023.json` (shared view).
- IR-S2-02 (carried): saturated continuous registry raster makes the literal
  any-raster 3-px overlap rule unsatisfiable for any non-empty submission.
- Session-1 BMTD and all three session-2 experiments: no organizer-confirmed
  score exists for any artifact; holdout numbers must not be quoted as
  leaderboard scores. Beating 0.2778/0.3195/0.4413 is unproven and unpromised.
