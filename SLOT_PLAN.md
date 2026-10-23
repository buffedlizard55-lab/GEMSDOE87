# SLOT_PLAN — GEMS Prize (#306, ONE entity, 3 scored slots / rolling week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, rebuilt this session byte-for-byte: NaN `baeae321…`, zeros `c55bafc4…`; `0.2778` = `CLAIM` until a receipt is in `ledger/`).
**Ledger (`ledger/submissions.csv`, 12 rows, 0 receipts):** `MASS` (`m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`c10`, `c15`, `c20`), `PRUNE` (`1`, `3`, `4`), `SNAP` (`tmi-hg`, `scarp`, `grav-argmax`). Treat `|Δ live| < 0.01` on public chunks as **no evidence**.

## 1. Next 3 slots, in order

1. **`h33-h33-2-b2-PRUNE3-20261023-bc00a06c`** (`PRUNE=3`, `37,654` dots, `5.77%` changed, pred `+0.005…+0.012` [`MODEL`]).
   Lowest-risk edit in the ledger and the only parent that satisfies Hard Constraint 4 (`>= 3 px`), so it is the compliance baseline as well as a mechanism test (known-fault halo FP vs. mass).
   * `Δ >= +0.01` → adopt `PRUNE3` as `R1`; Slot 2 becomes `PRUNE4` (tests 400 m GeoDAWN halo at fixed mass).
   * `|Δ| < 0.01` → collar is neutral at fixed mass; keep `R0` as the incumbent, Slot 2 as planned below.
   * `Δ <= -0.01` → re-mapped strands of known systems sit in the 200–300 m collar; Slot 2 becomes `PRUNE1` (inward recovery at fixed mass).
2. **`h33-h33-2-b2-SNAPtmi-hg-20261023-95057a8a`** (`SNAP=tmi-hg`, `21.60%` of dots moved, mean `1.95 px`/`195 m`, pred `-0.006…+0.008` [`MODEL`]).
   First genuinely new mechanism since the H19-5 → R0 climb: it tests whether R0's dot positions, not just its lineament field, carry the signal. Its two report-only proxies disagree in sign, so only a receipt can decide.
   * `Δ >= +0.01` → SNAP is live; Slot 3 becomes `SNAPscarp` (different sensor, same operator; biggest dose).
   * `|Δ| < 0.01` → position within ±200 m is invisible to the metric; stop the SNAP axis and give Slot 3 to `CONCc10`.
3. **`h33-h33-2-b2-CONCc10-20261023-a9e67bab`** (`CONCENTRATION=c10`, `10%` moved between 1 km blocks, pred `+0.004` [`MODEL`]) — unless Slot 2 fires the SNAP branch above.
   Tests whether new-fault mass is km-clustered; it is the only axis in the ledger with a stated target density band (`CV` 0.51–0.59) that the parent misses (R0 `CV_10km = 0.638`).

`SNAPgrav-argmax` is a deliberate misplacement control and should **not** take a slot unless Slots 1–3 all fail to separate from R0; it is the arm that bounds how much any SNAP edit could gain.

## 2. Schedule to the deadline (2026-10-23 → 2026-12-03, ≤ 18 weekly slots + 1 blind final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** Slots 1–3 above; then `RELIEFF`/`CONCc15` in the same one-per-axis discipline. Never spend two slots on one axis without a receipt showing `Δ >= +0.01`.
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** combine the two axes with `RECEIPT Δ >= +0.01` on the winning parent (e.g. `PRUNE3 + SNAPscarp`), each combination built as one controlled edit of the best receipted parent.
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + 1 blind final):** confirm the combined winner, build the Phase-2 `TRACKB` traces (`>= 1 km` strike-consistent GeoJSON + raster with one evidence paragraph per trace), lock the blind final file plus a fallback, re-validate both formats.

## 3. Proposed better axes for weeks 3–4 (do not build this session)

1. **`DIP_COLLAR` (asymmetric hanging-wall vs. footwall collar).** Great Basin normal faults dip 45–60° basinward, so the subsurface basement step sits 300–800 m into the hanging wall while the footwall scarp reflects erosional retreat. *Confounder:* antithetic graben faults flip polarity. *Falsifier:* `RECEIPT Δ <= 0` vs. symmetric `PRUNE3`.
2. **`TIP_RELAY` (along-strike termination and relay-ramp reallocation).** Shift 15% of the lowest-marginal-gain flank dots into 0.3–2.5 km along-strike cones ahead of mapped fault tips and 0.5–3 km en-echelon step-overs ([Faulds/INGENIOUS prior](https://gdr.openei.org/submissions/1391)). *Confounder:* fan-head channels at canyon mouths. *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent.
3. **`DENSIFY_2PX` (packing-aware re-allocation).** This session measured that R0 is already packed at its own `sqrt(8) = 2.83 px` minimum, so every SNAP edit necessarily creates sub-283 m pairs (2,345–2,396 dots). A future axis should *use* that: drop the weaker dot of each new near-duplicate pair and re-spend the freed mass on the highest exact-DTI-marginal-gain ridge pixels. *Confounder:* any gain may be pure mass redistribution. *Falsifier:* `RECEIPT Δ < +0.01` vs. the same-count control.
