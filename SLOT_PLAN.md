# SLOT_PLAN — GEMS Prize (brief v2)

Parent R0: `h33-h33-2-b2` (37,654 dots, CLAIM 0.2778, no receipt yet).
TOP_PUBLIC: ____ (human fills, with date) · Slots left this week: __ / total: __
Deadline 2026-12-03 (unconfirmed — competition page not fetched, per brief §4.1).
Quota: 3 scored submissions / rolling week / entity, 1 final. Built ≠ submitted:
the human submits; nothing here spends a slot by itself.
Built so far (ledger): MASS −10%, MASS +10%, SNAP-mag, SNAP-grav, SNAP-comb.

## Next 3 slots, in order

1. **SNAP-comb** (`h33-2-b2-snapcomb-20261023-083a43ca`, BUILT). Positional
   test with two-sensor consensus; strongest predicted SNAP gain.
   If Δ ≥ +0.01: position was the binding loss → read SNAP-mag next to find
   which sensor carries it, and plan a SNAP×(best axis) combination.
   If Δ ≤ −0.01: gradient edges sit off-trace → SNAP is falsified as a
   family; fall back to slot 2 and do not spend more slots on position.
2. **MASS −10%** (`h33-2-b2-massminus10-20261023-a00d6355`, BUILT). Tests
   whether the lowest-marginal-gain decile is redundant mass.
   If Δ ≥ +0.01: ranked pruning is real → deepen once (−20%). If ≤ −0.01:
   LOO-ranked pruning is falsified; keep R0 mass in all later builds.
   Read together with slot 1: position vs mass, one change each.
3. **SNAP-mag** (`h33-2-b2-snapmag-20261023-bf6ffd04`, BUILT) — only if slot 1
   is non-negative; otherwise **MASS +10%** (BUILT) to bracket the mass
   optimum. SNAP-grav is held in reserve: its prediction is the shallowest
   and it only earns a slot if SNAP-mag ≫ SNAP-comb (sensor attribution).
   Any |Δ| < 0.01 is no evidence (public chunks only; private may differ).

## Weeks to the deadline (≈6 weeks from 2026-10-23)

- Wk 1–2: the 3 slots above, then remaining singles (CONCENTRATION,
  PRUNE-refill, RELIEF), one (axis, value) each, max 3/week.
- Wk 3–4: combine the two best-supported axes (one change at a time off the
  then-incumbent; never stack two untested changes in one file).
- Wk 5–6: confirm the best file once, choose final + fallback, re-validate
  both formats (NaN + zeros) end-to-end, freeze. Final chosen blind.

## Proposed better axes (not built this session)

- **CONCENTRATION:** move 10–20% of dots from lowest- to highest-prior
  km-blocks; report block-density CV before/after (best files reportedly
  0.51–0.59). Confounder: block prior inherits parent-field bias. Falsifier:
  Δ ≤ −0.01 at higher concentration.
- **PRUNE-refill:** widen the catalogue collar to 3 px but refill to constant
  count from the parent ranking — separates collar value from mass value,
  which the historical 0.2600→0.2778 climb confounds.
- **RELIEF:** shift 10–15% of mass between basin/piedmont/range-front
  terciles from the detrended-elevation bands, count fixed. Confounder:
  relief covaries with exposure/mapping completeness, not just faulting.
