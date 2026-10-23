# SLOT_PLAN — GEMS Prize (brief v2)

Parent R0: `h33-h33-2-b2` (37,654 dots, CLAIM 0.2778, no receipt yet).
TOP_PUBLIC: ____ (human fills, with date) · Slots left this week: __ / total: __
Deadline 2026-12-03 (unconfirmed — competition page not fetched, per brief §4.1).
Quota: 3 scored submissions / rolling week / entity, 1 final. Built ≠ submitted:
the human submits; nothing here spends a slot by itself.

## Next 3 slots, in order

1. **MASS −10%** (`h33-2-b2-massminus10-20261023-a00d6355`, BUILT).
   Tests whether the lowest-marginal-gain decile is redundant mass.
   If live Δ ≥ +0.01: ranking-pruning is real → next MASS step is −20% by the
   same ranking. If Δ ≤ −0.01: LOO ranking is falsified → abandon ranked
   pruning, keep R0 mass. If |Δ| < 0.01: no evidence (public chunks only).
2. **MASS +10%** (`h33-2-b2-massplus10-20261023-70e3d289`, BUILT).
   Tests whether the parent field is under-sampled. Note the disclosed
   spacing side-effect (saturated parent disk) before spending the slot.
   If Δ ≥ +0.01: mass binds → densify further. If Δ ≤ −0.01: mass is past
   optimum → favour slot 1's direction. Read slots 1+2 as a pair: opposite
   signs bracket the mass optimum.
3. **Best remaining single axis** (CONCENTRATION, then SNAP, then PRUNE-refill,
   then RELIEF — one per week-slot, each built once, mechanism card first).
   Spend only after slots 1–2 are read; if MASS shows a clear winner, slot 3
   instead deepens that direction once (±20%) before opening a new axis.

## Weeks to the deadline (≈6 weeks from 2026-10-23)

- Wk 1–2: MASS pair (above), then CONCENTRATION / SNAP / PRUNE / RELIEF
  singles as slots allow (max 3/week). No axis is repeated at the same value.
- Wk 3–4: combine the two best-supported axes (one change at a time off the
  then-incumbent; never stack two untested changes in one file).
- Wk 5–6: confirm the best file once, choose final + fallback, re-validate
  both formats (NaN + zeros) end-to-end, freeze. Final is chosen blind —
  no last-week experiments that cannot be read before the deadline.

## Proposed better axes (not built this session)

- **CONCENTRATION:** move 10–20% of dots from lowest- to highest-prior
  km-blocks; report block-density CV before/after (best files reportedly
  0.51–0.59). Confounder: block prior inherits parent-field bias. Falsifier:
  Δ ≤ −0.01 at higher concentration.
- **SNAP:** shift dots ≤2 px to the strongest TMI/gravity-gradient edge —
  matches the ~300 m positional uncertainty of 400 m-spaced GeoDAWN lines.
  Confounder: edges of intrusives/calderas. Falsifier: |Δ| < 0.01 both ways
  across two snap radii.
- **PRUNE-refill:** widen the catalogue collar to 3 px but refill to constant
  count from the parent ranking — separates collar value from mass value,
  which the historical 0.2600→0.2778 climb confounds.
