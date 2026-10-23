# SLOT_PLAN — GEMS Prize (#306, ONE Entity, 3 Scored Slots / Rolling Week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, exact rebuilt SHA-256 `baeae321...` NaN / `c55bafc4...` zeros; `0.2778` = `CLAIM` until receipt in `ledger/`).
**Ledger Inventory (`ledger/submissions.csv`):** `MASS` (`GEMSDOE88`: `m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`CONCc10`, `CONCc15`, `CONCc20`), and **`PRUNE` (built this session: `PRUNE3`, `PRUNE1`, `PRUNE4`)**. Treat `|Δ live| < 0.01` on public chunks as **no evidence**.

## 1. Next 3 Slots in Order & Decision Rules

1. **Slot 1 — `h33-h33-2-b2-PRUNE3-20261023-bc00a06c` (`AXIS=PRUNE, value=3`, `37,654` dots, `5.77%` changed, pred `+0.005` to `+0.012` [`MODEL`]):**
   Removes `2,171` R0 dots in `2 < d_cat <= 3 px` (`200–300 m`) and refills `2,171` dots onto uncovered `H19-5` ridge gaps (`d_cat > 3 px`) by exact DTI marginal gain `dT`. Resolves mass vs. collar confounding and brings the baseline into `>= 3 px` compliance (Brief §4.4).
   - **If `Δ >= +0.01` (`RECEIPT`):** Known-fault halo FP dominates inside `300 m`. Adopt `PRUNE3` as parent `R1`; test `PRUNE4` (`f5c53782`, `400 m` [GeoDAWN line spacing](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) in **Slot 2**.
   - **If `|Δ| < 0.01` (`RECEIPT`):** `2–3 px` vs `>3 px` is neutral at fixed mass. Adopt `PRUNE3` as `>= 3 px`-compliant parent and spend **Slot 2** on `CONCc10` (`h33-h33-2-b2-CONCc10-20261023-a9e67bab`, `+0.004` [`MODEL`]).
   - **If `Δ <= -0.01` (`RECEIPT`):** New-fault strands of existing systems ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516), [#11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) sit within `200–300 m`. Spend **Slot 2** on `PRUNE1` (`4679d91c`) to test `100–200 m` inward recovery at fixed mass.
2. **Slot 2 — `h33-h33-2-b2-CONCc10-20261023-a9e67bab` (`CONCENTRATION`, `10.00%` changed) OR Conditional `PRUNE4` / `PRUNE1`:**
   Tests 1 km block relocation if `PRUNE3` is neutral (`|Δ| < 0.01`), or follows the active `PRUNE` slope if `|Δ(PRUNE3)| >= 0.01`. Never burn all 3 slots on one axis without a receipt.
3. **Slot 3 — `SNAP` (`<= 2 px` TMI/isostatic-gravity horizontal-gradient crest alignment, next session):**
   Same count (`37,654`), same `>= 3 px` exclusion; corrects `~300–400 m` airborne gridding offset; report mean displacement.

## 2. Six-Week Schedule to Deadline (2026-10-23 → 2026-12-03, Max 18 Weekly Slots + 1 Final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** Score 1 informative variant each across `PRUNE` (`PRUNE3`), `CONCENTRATION` (`CONCc10`), `MASS` (`GEMSDOE88`), `SNAP`, and `RELIEF` (basin/piedmont/range-front tercile shift on `det_elev`).
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** Combine the two orthogonal axes with `RECEIPT Δ >= +0.01` on the winning parent; test top proposed structural axes below as single-factor edits (`1–50%` changed).
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + 1 blind final):** Confirm combined winner, build Phase 2 `TRACKB` (`>= 1 km` strike-consistent GeoJSON + raster traces with geologist evidence notes), lock 1 blind final file + 1 fallback, and re-verify format and `AI_USE.md`.

## 3. Proposed Better Axes for Weeks 3–4 (Do Not Build This Session)

1. **`DIP_COLLAR` (Asymmetric Hanging-Wall vs. Footwall Collar):** Great Basin normal faults dip `45°–60°` basinward, shifting subsurface magnetic/gravity basement steps `300–800 m` into the hanging wall (`depth_to_base_surf` gradient) while footwall scarps reflect erosional retreat. *Confounder:* antithetic graben faults flip polarity. *Falsifier:* `RECEIPT Δ < +0.01` vs. symmetric `PRUNE3`.
2. **`TIP_RELAY` (Along-Strike Termination & Relay-Ramp Reallocation):** Shift `15%` of lowest-`dT` flank dots into `0.3–2.5 km` along-strike cones ahead of mapped fault tips and `0.5–3 km` en-echelon step-overs ([Faulds/INGENIOUS prior](https://gdr.openei.org/submissions/1391)). *Confounder:* radiating fan-head channels at canyon mouths. *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent.
3. **`STRIKE_AGREE` (Cross-Field Orientation Agreement >= 1 km):** Retain/promote dots where magnetic and gravity structure-tensor strikes agree over `>= 1 km` vs. closed caldera/shoreline rims. *Confounder:* plutonic contacts. *Falsifier:* `RECEIPT Δ < +0.01` vs. parent.
