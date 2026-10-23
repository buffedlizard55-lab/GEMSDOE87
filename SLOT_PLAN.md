# SLOT_PLAN — GEMS Prize (#306, ONE Entity, 3 Scored Slots / Rolling Week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, exact rebuilt SHA-256 `baeae321...` NaN / `c55bafc4...` zeros; `0.2778` = `CLAIM` until receipt in `ledger/`).
**Ledger Inventory (`ledger/submissions.csv`, 12 rows):** `MASS` (`GEMSDOE88`: `m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`CONCc10`, `CONCc15`, `CONCc20`), `PRUNE` (`PRUNE3`, `PRUNE1`, `PRUNE4`), and **`SNAP` (built this session: `tmi2`, `grav2`, `comb2`; `<= 2 px` edge-crest re-centering at fixed `37,654` count)**. Treat `|Δ live| < 0.01` on public chunks as **no evidence**.

## 1. Next 3 Slots in Order & Decision Rules

1. **Slot 1 — `h33-h33-2-b2-PRUNE3-20261023-bc00a06c` (`AXIS=PRUNE, value=3`, `37,654` dots, `5.77%` changed, pred `+0.005` to `+0.012` [`MODEL`]):**
   Removes `2,171` R0 dots in `2 < d_cat <= 3 px` (`200–300 m`) and refills onto uncovered `H19-5` ridge gaps (`d_cat > 3 px`) by exact DTI marginal gain `dT`. Brings the baseline into `>= 3 px` compliance (Brief §4.4).
   - **If `Δ >= +0.01` (`RECEIPT`):** Known-fault halo FP dominates inside `300 m`. Adopt `PRUNE3` as parent `R1`; test `PRUNE4` (`f5c53782`, `400 m` [GeoDAWN line spacing](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) in **Slot 2**.
   - **If `|Δ| < 0.01` (`RECEIPT`):** `2–3 px` vs `>3 px` is neutral at fixed mass. Adopt `PRUNE3` as `>= 3 px`-compliant parent and spend **Slot 2** on `CONCc10` (`a9e67bab`, `+0.004` [`MODEL`]).
   - **If `Δ <= -0.01` (`RECEIPT`):** New-fault strands of existing systems ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516), [#11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) sit within `200–300 m`. Spend **Slot 2** on `PRUNE1` (`4679d91c`) to test `100–200 m` inward recovery at fixed mass.
2. **Slot 2 — `h33-h33-2-b2-CONCc10-20261023-a9e67bab` (`CONCENTRATION`, `10.00%` changed) OR conditional `PRUNE4` / `PRUNE1`:**
   Tests 1 km block relocation if `PRUNE3` is neutral, or follows the active `PRUNE` slope if `|Δ(PRUNE3)| >= 0.01`. Never burn all 3 slots on one axis without a receipt.
3. **Slot 3 — `h33-h33-2-b2-SNAPcomb2-20261023-bf0a7e2b` (`AXIS=SNAP, value=comb2`, `98.90%` moved, mean `1.80 px`):**
   Rank-composite (TMI-HGM ⊕ isostatic-gravity-HG) edge-crest re-centering, `<= 2 px`, same `37,654` count and `d_cat > 2 px` exclusions. Chosen first among the three SNAP twins because it is the only `PROXY`-neutral arm (fold-proper paired `Δ` vs `R0_fp`: `comb2` `-0.0003` `[−0.0027, +0.0023]`, `grav2` `-0.0023` `[−0.0073, +0.0035]`, `tmi2` `-0.0074` `[−0.0116, −0.0029]` — `PROXY`, never a gate). Fallbacks: `SNAPgrav2` (`ac2bdb06`), `SNAPtmi2` (`b87ddfc5`, kept as the single-sensor falsifier).
   - **If `Δ >= +0.01` (`RECEIPT`):** Airborne-position offset is real; build `SNAP_CONSERVATIVE` (Section 3.4) on the winning parent.
   - **If `|Δ| < 0.01` (`RECEIPT`):** Position within the `300 m` kernel is not the binding constraint; close the `SNAP` lane and spend wk3–4 on axis combinations.
   - **If `Δ <= -0.01` (`RECEIPT`):** Raw-gradient argmax chasing walks dots off fault traces (the `PROXY` direction confirmed live); close the lane and keep `R0`'s ridge placement.

## 2. Six-Week Schedule to Deadline (2026-10-23 → 2026-12-03, Max 18 Weekly Slots + 1 Final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** 1 informative variant per axis with a receipt: `PRUNE3`, then `CONCc10`/`PRUNE4`/`PRUNE1` per Slot-1 branch, then `SNAPcomb2`. Next build session: `RELIEF` (basin/piedmont/range-front tercile shift on `det_elev`, count fixed) — the only wk1–2 axis left unbuilt.
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** Combine the two orthogonal axes with `RECEIPT Δ >= +0.01` on the winning parent; test top proposed structural axes below as single-factor edits (`1–50%` changed).
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + 1 blind final):** Confirm combined winner, build Phase 2 `TRACKB` (`>= 1 km` strike-consistent GeoJSON + raster traces with geologist evidence notes), lock 1 blind final file + 1 fallback, and re-verify format and `AI_USE.md`.

## 3. Proposed Better Axes for Weeks 3–4 (Do Not Build This Session)

1. **`DIP_COLLAR` (Asymmetric Hanging-Wall vs. Footwall Collar):** Great Basin normal faults dip `45°–60°` basinward, shifting subsurface magnetic/gravity basement steps `300–800 m` into the hanging wall (`depth_to_base_surf` gradient) while footwall scarps reflect erosional retreat. *Confounder:* antithetic graben faults flip polarity. *Falsifier:* `RECEIPT Δ < +0.01` vs. symmetric `PRUNE3`.
2. **`TIP_RELAY` (Along-Strike Termination & Relay-Ramp Reallocation):** Shift `15%` of lowest-`dT` flank dots into `0.3–2.5 km` along-strike cones ahead of mapped fault tips and `0.5–3 km` en-echelon step-overs ([Faulds/INGENIOUS prior](https://gdr.openei.org/submissions/1391)). *Confounder:* radiating fan-head channels at canyon mouths. *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent.
3. **`STRIKE_AGREE` (Cross-Field Orientation Agreement >= 1 km):** Retain/promote dots where magnetic and gravity structure-tensor strikes agree over `>= 1 km` vs. closed caldera/shoreline rims. *Confounder:* plutonic contacts. *Falsifier:* `RECEIPT Δ < +0.01` vs. parent.
4. **`SNAP_CONSERVATIVE` (Gain-Gated `<= 1 px` Snap):** This session's literal `SNAP` moved `98.7–99.8%` of dots (mean `~1.8–1.9 px`, `86–88%` landing off `H19-5` ridges) because the argmax of the `3x3`-smoothed `100 m` gradient fields usually sits at the window edge; the fold-proper `PROXY` was neutral-to-negative. A gated variant moves a dot only when the smoothed edge gain exceeds a pinned threshold `τ` and caps displacement at `1 px`, changing `~10–30%` of dots instead of `~99%`. *Confounder:* threshold `τ` tuned against `PROXY` (fit the gate on `PROXY`, confirm on `RECEIPT` only). *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent, or `<=` the ungated `SNAPcomb2` receipt.
