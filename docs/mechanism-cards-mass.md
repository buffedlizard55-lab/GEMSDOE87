# Mechanism cards — MASS variants of R0 (h33-h33-2-b2)

Written for a structural geologist. Parent: 37,654 unit-mass dots, none within
2 px of the catalogue, CLAIM 0.2778 (no receipt in `ledger/`). Ranking: the
parent stored no continuous ranking (H19-5 artifact is binary; dotting was
label-free BFS thinning, reproduced byte-exactly), so dots are ranked by exact
leave-one-out (LOO) marginal loss in R0's own 300 m triangular-kernel
max-coverage — the brief §2 metric-code ranking. LOO quantiles (kernel-mass
units; full kernel = 9.3803): min 2.37, p10 4.78, median 6.84, p90/max 9.38.
Live changes under 0.01 count as no evidence.

## MASS −10% — `h33-2-b2-massminus10-20261023-a00d6355` (33,889 dots)

- **Hypothesis:** R0's lowest-LOO decile is redundant mass: neighbouring dots
  already cover the same 300 m kernel footprint, so these dots mostly pay the
  0.2 false-positive charge without adding recall on new faults.
- **Mechanism:** DTI = T/(0.2T + 0.2(S−M) + 0.8|G|). Deleting a dot whose
  truth credit is below ~0.2·DTI (≈0.056 at 0.28) shrinks the denominator
  faster than the numerator. The dropped decile carries only 6.24% of R0's
  self-coverage (15,948 of 255,556 kernel units) for 10% of the dots.
- **Non-fault mimic:** dense lineament corridors that are not faults —
  caldera ring margins, intrusive contacts, aligned drainage — also produce
  clustered, mutually redundant dots; trimming there is harmless, but if part
  of the dropped decile instead sits on genuine sub-parallel splays of new
  systems, recall is lost there first.
- **Predicted live change:** +0.000 to +0.008 (MODEL, not a score). Below the
  0.01 evidence threshold by design — this slot buys a sign, not a headline.
- **Falsifier:** live Δ ≤ −0.01. That would show low self-coverage ≠ low
  truth credit (dropped dots were load-bearing for unmapped faults), killing
  LOO-ranked pruning as an axis.

## MASS +10% — `h33-2-b2-massplus10-20261023-70e3d289` (41,419 dots)

- **Hypothesis:** the parent field is under-sampled: the next-ranked parent-
  pool pixels (H19-5 mask, >2 px from catalogue) still carry marginal kernel
  coverage the incumbent never bought, some of it over unmapped faults.
- **Mechanism:** same algebra, opposite sign — each added dot pays 0.2·(1−q).
  It only raises live DTI if its truth credit exceeds ~0.056. Additions were
  chosen by exact greedy marginal coverage gain, i.e. maximum new 300 m
  footprint per dot inside the parent field.
- **Non-fault mimic:** additions densify along every strong parent-field
  lineament, including lithologic/drainage lineaments with no slip; those
  dots are pure denominator. Disclosed side-effect: the parent disk is
  saturated (only 609 dots fit at the parent's 2.8 px spacing), so additions
  relax spacing (min inter-dot separation 1.0 px vs parent 2.83 px) — a
  SPACING confound the live result cannot fully separate from MASS.
- **Predicted live change:** −0.008 to 0.000 (MODEL, not a score).
- **Falsifier:** live Δ ≥ +0.01. That would show the parent field holds real,
  finer-spaced fault mass the saturated disk was leaving behind, and mass
  (not ranking quality) is the binding constraint.

## Proposed better axes (build in a later session, not this one)

Logged in `SLOT_PLAN.md`: CONCENTRATION (km-block density CV vs the reported
0.51–0.59 band), SNAP (positional error ≈ kernel radius per GeoDAWN 400 m
line spacing), PRUNE refill (mass-neutral collar test). Each needs its own
mechanism card before it is built.
