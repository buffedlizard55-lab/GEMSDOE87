# SLOT_PLAN — GEMS Prize (#306, ONE Entity, 3 Scored Slots / Rolling Week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, exact rebuilt SHA-256 `baeae321...` NaN / `c55bafc4...` zeros; `0.2778` = `CLAIM` until receipt in `ledger/`).
**Ledger Inventory (`ledger/submissions.csv`):** `MASS` (`GEMSDOE88`: `m10minus`, `m10plus`, `m20minus`), `CONCENTRATION` (`c10`, `c15`, `c20`), `PRUNE` (`3`, `1`, `4`), and **`SNAP` (built this session: `scarp2`, `rtp2`, `tg2`)**. Treat `|Δ live| < 0.01` on public chunks as **no evidence**.

## 1. Next 3 Slots in Order & Decision Rules

1. **Slot 1 — `h33-h33-2-b2-PRUNE3-20261023-bc00a06c` (`AXIS=PRUNE, value=3`, `37,654` dots, `5.77%` changed, pred `+0.005` to `+0.012` [`MODEL`]):**
   Removes `2,171` R0 dots in `2 < d_cat <= 3 px` (`200–300 m`) and refills `2,171` dots on `H19-5` (`d_cat > 3 px`) by exact DTI marginal gain `dT`, bringing the parent into `>= 3 px` compliance (Brief §4.4) at fixed count.
   - **If `Δ >= +0.01` (`RECEIPT`):** Known-fault halo FP dominates inside `300 m`; adopt `PRUNE3` as `R1` (test `PRUNE4` `f5c53782` only if testing `400 m` [GeoDAWN spacing](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)).
   - **If `|Δ| < 0.01` (`RECEIPT`):** `2–3 px` vs `>3 px` is neutral at fixed mass; adopt `PRUNE3` as `>= 3 px`-compliant base and advance directly to **Slot 2 (`SNAPscarp2`)**.
   - **If `Δ <= -0.01` (`RECEIPT`):** Re-mapped strands of known systems ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516), [#11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) sit within `200–300 m`; retain `2 px` collar (`R0`) or probe `PRUNE1` (`4679d91c`).
2. **Slot 2 — `h33-h33-2-b2-SNAPscarp2-20261023-065e17a9` (`AXIS=SNAP, value=scarp2`, `37,654` dots, `36.03%` changed, `mean disp = 0.54 px` all / `1.50 px` moved, pred `+0.005` to `+0.012` [`MODEL`]):**
   Snaps `R0` dots `<= 2 px` cross-strike onto 1-D Hessian crests of provided `|\nabla_H(\text{RTP})|` (`Band 02`), isotropic `iso_grav_anom_slope` (`Band 05`), and `det_elev_slope` (`Band 19`), preserving `R0` exclusions (`d_cat > 2 px`) and `sqrt(8)` spacing (no external lidar).
   - **If `Δ >= +0.01` (`RECEIPT`):** Cross-strike crest centering beats `400 m` gridding + BFS ribbon offset; combine `SNAPscarp2` + winning collar in Wk 3–4.
   - **If `Δ <= -0.01` (`RECEIPT`):** Erosional scarp retreat / pluvial benches pull dots off fault traces; test pure subsurface `SNAPrtp2` (`3d8bcc8a`, `mean disp = 0.48 px`, no DEM scarp) before retiring `SNAP`.
3. **Slot 3 — `h33-h33-2-b2-CONCc10-20261023-a9e67bab` (`AXIS=CONCENTRATION, value=c10`, `10.00%` changed, pred `+0.004` [`MODEL`]) OR `RELIEF` (build next session):**
   Tests 1 km `H19-5` block reallocation (`CV_occ 0.619 -> 0.748`) vs. shifting `10–15%` of mass across `det_elev` (`Band 12`) basin/piedmont/range-front terciles so Wk 1–2 spans orthogonal geometry, positioning, and domain-prior axes.

## 2. Six-Week Schedule to Deadline (2026-10-23 → 2026-12-03, Max 18 Weekly Slots + 1 Final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** Score 1 informative variant each across `PRUNE` (`PRUNE3`), `SNAP` (`SNAPscarp2` / `SNAPrtp2`), `CONCENTRATION` (`CONCc10`), `MASS` (`GEMSDOE88`), and `RELIEF` (next unbuilt default axis).
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** Combine the two orthogonal axes with `RECEIPT Δ >= +0.01` (e.g., `PRUNE3 + SNAPscarp2`); test top proposed structural axes below as single-factor edits (`1–50%` changed).
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + 1 blind final):** Confirm combined winner, build Phase 2 `TRACKB` (`>= 1 km` strike-consistent GeoJSON + raster traces with geologist evidence paragraphs), lock 1 blind final file + 1 fallback, and re-verify format and `AI_USE.md`.

## 3. Proposed Better Axes for Weeks 3–4 (Do Not Build This Session)

1. **`DIP_COLLAR` (Asymmetric Hanging-Wall vs. Footwall Collar):** Great Basin normal faults dip `45°–60°` basinward, shifting subsurface magnetic/gravity basement steps `300–800 m` into the hanging wall (`depth_to_base_surf` gradient) while footwall scarps reflect erosional retreat. *Confounder:* antithetic graben faults flip polarity. *Falsifier:* `RECEIPT Δ < +0.01` vs. symmetric `PRUNE3`.
2. **`TIP_RELAY` (Along-Strike Termination & Relay-Ramp Reallocation):** Shift `15%` of lowest-`dT` flank dots into `0.3–2.5 km` along-strike cones ahead of mapped fault tips and `0.5–3 km` en-echelon step-overs ([Faulds/INGENIOUS prior](https://gdr.openei.org/submissions/1391)). *Confounder:* radiating fan-head channels at canyon mouths. *Falsifier:* `RECEIPT Δ <= -0.01` vs. parent.
3. **`STRIKE_AGREE` (Cross-Field Orientation Agreement >= 1 km):** Retain/promote dots where magnetic and gravity structure-tensor strikes agree over `>= 1 km` vs. closed caldera/shoreline rims. *Confounder:* plutonic contacts. *Falsifier:* `RECEIPT Δ < +0.01` vs. parent.
