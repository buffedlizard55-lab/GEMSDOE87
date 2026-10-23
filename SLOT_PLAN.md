# SLOT_PLAN — GEMS Prize (#306, ONE entity, 3 scored slots / rolling week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, rebuilt this session byte-for-byte: NaN `baeae321…`, zeros `c55bafc4…`; `0.2778` = `CLAIM` until a receipt is in `ledger/`).
**Ledger (`ledger/submissions.csv`, 15 rows, 0 receipts):** `MASS` (`m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`c10`, `c15`, `c20`), `PRUNE` (`1`, `3`, `4`), `SNAP` (`tmi-hg`, `scarp`, `grav-argmax`), `RELIEF` (`r2p12`, `r2b10`, `b2r15`). Treat `|Δ live| < 0.01` on public chunks as **no evidence**.

## 1. Next 3 slots, in order

1. **`h33-h33-2-b2-PRUNE3-20261023-bc00a06c`** (`PRUNE=3`, `37,654` dots, `5.77%` changed, pred `+0.005…+0.012` [`MODEL`]).
   Lowest-risk edit in the ledger and the only candidate satisfying Hard Constraint 4 (`>= 3 px`), serving as both compliance baseline and collar-vs-mass mechanism test.
   * `Δ >= +0.01` → adopt `PRUNE3` as `R1`; Slot 2 tests `RELIEFr2p12` (or `PRUNE4` if pushing collar halo first).
   * `|Δ| < 0.01` → 200–300 m collar is neutral at fixed mass; keep `R0` as incumbent and proceed to Slot 2.
   * `Δ <= -0.01` → re-mapped strands of known systems sit in 200–300 m; Slot 2 becomes `PRUNE1` (inward recovery at fixed mass).
2. **`h33-h33-2-b2-RELIEFr2p12-20261023-0689ea4c`** (`RELIEF=r2p12`, `12.00%` = `4,518` dots shifted `Range-Front -> Piedmont`, `min_sep = sqrt(8)` preserved, pred `+0.004…+0.012` [`MODEL`]).
   Cleanest geomorphic label-regime probe (`SPACING`, `MASS`, and `2 px` collar 100% invariant; `T0 Basin` untouched): Quaternary hide-and-recover (`+0.0004` fold / `+0.0009` static [`PROXY`]) and USGS SGMC bedrock (`-0.0065` [`PROXY`]) flip cleanly in opposite directions across `RELIEF`, so one live receipt identifies the undisclosed test-label regime ([organizer thread #11527](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).
   * `Δ >= +0.01` → concealed Quaternary piedmont/bajada faults dominate; test `RELIEFr2b10` (`Range -> Basin 10%`) next week.
   * `|Δ| < 0.01` → geomorphic relief shift alone is within chunk noise; give Slot 3 to `SNAPtmi-hg`.
   * `Δ <= -0.01` → unmapped range-block bedrock faults dominate; pivot to `RELIEFb2r15` (`Basin -> Range 15%`, `+0.0019` on SGMC [`PROXY`]).
3. **`h33-h33-2-b2-SNAPtmi-hg-20261023-95057a8a`** (`SNAP=tmi-hg`, `21.60%` moved `<= 2 px`, mean `1.95 px`, pred `-0.006…+0.008` [`MODEL`]) — or `CONCc10` (`a9e67bab`) if testing 1 km block clustering before sub-200 m re-centering.
   Tests whether sub-200 m magnetic-crest re-seating raises kernel credit `T`. Never spend a slot on `SNAPgrav-argmax` (`Band 18` is directional $\partial g/\partial x$, see `IR-87-V2-09`).

## 2. Schedule to the deadline (2026-10-23 → 2026-12-03, ≤ 18 weekly slots + 1 blind final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** Slots 1–3 above (`PRUNE3`, `RELIEFr2p12`, `SNAPtmi-hg`), then `CONCc10`, `MASSm10plus`, and the winning `RELIEF`/`PRUNE` follow-up (`r2b10`, `b2r15`, or `PRUNE4`) — strictly one slot per axis until a `RECEIPT` shows `|Δ| >= 0.01`.
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** combine the two orthogonal axes with `RECEIPT Δ >= +0.01` on the best receipted parent (e.g. `PRUNE3 + RELIEFr2p12`), plus one proposed structural axis below.
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + 1 blind final):** confirm combined winner, build Phase-2 `TRACKB` traces (`>= 1 km` strike-consistent GeoJSON + raster + 1 geologist evidence paragraph per trace), and lock the single blind final file + zeros fallback.

## 3. Proposed better axes for weeks 3–4 (do not build this session)

1. **`DIP_COLLAR` (asymmetric hanging-wall vs. footwall collar).** Normal faults dip 45–60° basinward, placing subsurface basement steps 300–800 m into the hanging wall (`Band 12 det_elev` polarity). *Confounder:* antithetic graben faults. *Falsifier:* `RECEIPT Δ <= 0` vs. symmetric `PRUNE3`.
2. **`TIP_RELAY` (along-strike termination & relay-ramp reallocation).** Shift 12–15% of lowest-`dT` flank dots into 0.3–2.5 km along-strike tip cones and 0.5–3 km step-overs ([Faulds/INGENIOUS inventory](https://gdr.openei.org/submissions/1391)). *Confounder:* canyon-mouth fan channels. *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent.
3. **`ISOTROPIC_GRAV_SNAP` / `DENSIFY_2PX` (Band 05 isotropic $|\nabla_H g|$ + packing-aware re-allocation).** Replace signed `Band 18` ($\partial g/\partial x$) with isotropic `Band 05` (`iso_grav_anom_slope`) + `|grad_H(RTP)|` (`Band 02`) while pruning sub-`2 px` snap pairs onto high-`dT` ridge gaps. *Confounder:* pluton/caldera margins. *Falsifier:* `RECEIPT Δ < +0.01` vs. `SNAPtmi-hg`.
