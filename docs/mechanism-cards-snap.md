# Mechanism cards — SNAP variants of R0 (h33-h33-2-b2)

Written for a structural geologist. Parent: 37,654 unit-mass dots, CLAIM
0.2778 (no receipt in `ledger/`). Each variant holds the count, the unit
mass and the parent exclusion (d(catalogue) > 2 px, zero catalogue mass);
only positions move, each by ≤ 2 px to the strongest provided
horizontal-gradient response in its window (deterministic greedy claim,
no collisions). Live changes under 0.01 count as no evidence.

Why position should matter at all: GeoDAWN Area 2 (most of the region)
was flown at 400 m line spacing, 150–200 m above terrain, so a gridded
lineament's position is uncertain by roughly the 300 m (3 px) scoring-
kernel radius. R0's dots inherit the parent field's pixel picks, not the
geophysical edge positions. SNAP tests whether the kernel credit is
being lost to sub-kernel mis-registration rather than to wrong lines.

## SNAP-mag — `h33-2-b2-snapmag-20261023-bf6ffd04` (tmi_hg, band 3)

- **Hypothesis:** magnetic horizontal-gradient maxima mark the basement
  contacts that offset faults juxtapose; R0 dots sit up to 2 px off them.
- **Mechanism:** 36,978 dots moved (98.20%), mean 1.77 px. Gradient
  maxima over steep contacts are sharper than the anomaly itself, so
  snapped dots should earn kernel credit on new-fault pixels that the
  parent placement straddled.
- **Non-fault mimic:** plutonic intrusive contacts and caldera ring
  margins are magnetic edges with no Quaternary slip; snapping
  concentrates dots onto them just as efficiently.
- **Predicted live change:** +0.000 to +0.010 (MODEL, not a score).
- **Falsifier:** Δ ≤ −0.01 — dipping magnetic contacts put the gradient
  maximum systematically off the fault trace at sensor altitude, so the
  magnetic edge is the wrong target at 100 m scale.

## SNAP-grav — `h33-2-b2-snapgrav-20261023-eb8beda9` (iso_grav_anom_hg, band 18)

- **Hypothesis:** isostatic gravity gradient maxima mark range-front
  basement steps — the deep expression of the basin-bounding faults.
- **Mechanism:** 37,571 dots moved (99.78%, most of any variant — the
  gravity field is smooth, so its local maximum is rarely the current
  pixel), mean 1.95 px.
- **Non-fault mimic:** basement steps under inactive or pre-Quaternary
  structures, and basin-edge sediment thickness changes with no active
  fault above them.
- **Predicted live change:** 0.000 to +0.006 (MODEL) — shallowest of the
  three; gravity edges are broader than the 3 px kernel, so the
  positional correction is intrinsically blurrier.
- **Falsifier:** Δ ≤ −0.01 while SNAP-mag is ≥ 0 — gravity edges are
  offset from the seismogenic trace (deep step ≠ shallow fault).

## SNAP-comb — `h33-2-b2-snapcomb-20261023-083a43ca` (rank-sum of both)

- **Hypothesis:** a fault worth mapping offsets both magnetic basement
  and density structure; requiring consensus (mean footprint percentile
  rank of the two gradient bands) filters single-sensor mimics.
- **Mechanism:** 37,066 dots moved (98.44%), mean 1.79 px. Consensus
  picks are less sharp per sensor but far less often a pure lithologic
  contact, so a larger share of moved dots should land on real traces.
- **Non-fault mimic:** long-lived basement terrane boundaries — strong
  in both fields, possibly inactive through the Quaternary.
- **Predicted live change:** +0.002 to +0.012 (MODEL) — the recommended
  first SNAP slot.
- **Falsifier:** Δ ≤ −0.01, or SNAP-comb underperforms the better single
  sensor by ≥ 0.01 — consensus averaging dilutes the true edge rather
  than vetoing mimics.

Shared side-effect (all three): snapping crowds dots onto 1-D edges, so
minimum inter-dot separation falls to 1.0 px (parent 2.83 px). That is
inherent to SNAP, is disclosed in every receipt, and is why a positive
SNAP result should next be read against a spacing control (SLOT_PLAN).
