# SLOT_PLAN — GEMS Prize (#306, ONE Entity, 3 Scored Slots / Rolling Week)

**As of:** 2026-10-23 UTC · **Deadline:** 2026-12-03 (human to confirm on [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) · **Quota:** 3 scored submissions/rolling week, 1 blind final file ([official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
**Parent R0:** `h33-h33-2-b2` (`37,654` dots, `d_cat > 2 px`, rebuilt exact SHA-256 `baeae321...` / `c55bafc4...`; `0.2778` = `CLAIM` until receipt in `ledger/`).
**Evidence threshold:** Treat `|Δ live| < 0.01` on public chunks as **no evidence** (private Phase 1 chunks and expert-expanded Phase 2 labels differ).

## 1. Next 3 Slots in Order & Decision Rules

1. **Slot 1 — `h33-h33-2-b2-PRUNE3-20261023-bc00a06c` (`AXIS=PRUNE, value=3`, `37,654` dots, `5.77%` changed):**
   Removes the `2,171` R0 dots in `2 < d_cat <= 3 px` (`200–300 m`) and refills `2,171` dots onto uncovered `H19-5` ridge gaps (`d_cat > 3 px`) by exact DTI marginal gain `dT`. Predicted change: **`+0.005` to `+0.012` [`MODEL`]**.
   - **If `Δ >= +0.01` (`RECEIPT`):** Confirms known-fault halo FP dominates inside `R = 300 m` even at fixed mass. Adopt `PRUNE3` as new parent `R1` (now strictly `>= 3 px` compliant for all non-PRUNE axes) and spend **Slot 2** on `PRUNE4` to test whether GeoDAWN's `400 m` line-spacing halo ([USGS GeoDAWN](https://data.usgs.gov/datacatalog/data/USGS:657e1d85d34e23d3533209f7)) extends the gain.
   - **If `|Δ| < 0.01` (`RECEIPT`):** Collar `2–3 px` vs `>3 px` is neutral at fixed mass. Adopt `PRUNE3` as `>= 3 px`-compliant parent (Hard Constraint 4) and **do not spend Slot 2 on `PRUNE4`**; advance **Slot 2** to `SNAP` and **Slot 3** to `CONCENTRATION`.
   - **If `Δ <= -0.01` (`RECEIPT`):** Falsifies halo dominance; proves newly mapped strands of existing systems ([forum #11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516), [#11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)) sit within `200–300 m` of known traces. Spend **Slot 2** on `PRUNE1` (`h33-h33-2-b2-PRUNE1-20261023-4679d91c`) to test `100–200 m` inward recovery at fixed mass.
2. **Slot 2 — Conditional (`PRUNE4` `f5c53782` if Slot 1 `>= +0.01`; `PRUNE1` `4679d91c` if Slot 1 `<= -0.01`; else `SNAP` on `PRUNE3`):**
   Isolates the active side of the collar curve without spending slots on a flat slope (`PRUNE4` pred `-0.004` to `+0.006` [`MODEL`]; `PRUNE1` pred `-0.012` to `-0.005` [`MODEL`]).
3. **Slot 3 — `SNAP` (or `PRUNE4` if Slot 2 went to `PRUNE1` and won `>= +0.01`):**
   Move each dot `<= 2 px` (`200 m`) onto the local TMI/isostatic-gravity horizontal-gradient crest at fixed count (`37,654`) and fixed exclusion (`>= 3 px`), correcting GeoDAWN `400 m` flight-line gridding offset.

## 2. Six-Week Schedule to Deadline (2026-10-23 → 2026-12-03, Max 18 Weekly Slots + 1 Final)

- **Wk 1 (Oct 23–29, 3 slots):** Anchor `R0` receipt if unconfirmed; run `PRUNE` (`PRUNE3`, conditional `PRUNE1`/`PRUNE4`) and `SNAP` on the `>= 3 px` parent.
- **Wk 2 (Oct 30–Nov 5, 3 slots):** Run `CONCENTRATION` (`15 km` block-density CV shift from `0.53` toward `0.58` toward structural-interaction blocks), `RELIEF` (piedmont/basin vs. range-front tercile shift on `det_elev`/`det_elev_slope`), and `MASS` (`±10%` along exact `H19-5` DTI marginal-gain ranking).
- **Wk 3 (Nov 6–12, 3 slots):** Test the top two proposed structural axes below (`DIP_COLLAR` and `TIP_RELAY`) as single-factor edits on the Wk 1–2 winner.
- **Wk 4 (Nov 13–19, 3 slots):** Pairwise orthogonal combination (`A + B`) of the two axes that achieved `Δ >= +0.01` (`RECEIPT`), checking additivity vs. interference.
- **Wk 5 (Nov 20–26, 3 slots):** Confirmation / ablation of the combined candidate + build `TRACKB` (`>= 1 km` strike-consistent GeoJSON + raster traces with structural evidence paragraphs for Phase 2 expert review).
- **Wk 6 (Nov 27–Dec 3, final week):** Freeze final blind submission + 1 conservative fallback (no late unvalidated edits); re-verify SHA-256, `sample_submission.tif` grid/CRS/NaN format, and `AI_USE.md` disclosure before deadline.

## 3. Proposed Better Axes for Weeks 3–4 (Do Not Build This Session)

1. **`DIP_COLLAR` (Asymmetric Hanging-Wall vs. Footwall Collar):**
   - *Mechanism:* Great Basin range-bounding normal faults dip `45°–60°` basinward; subsurface magnetic/gravity basement steps lie `300–800 m` downdip in the hanging wall while footwall topographic scarps are erosional recession mimics (`det_elev_slope` sign relative to `depth_to_base_surf` gradient). Prune `<= 5 px` on footwall side, `<= 3 px` on hanging-wall side at fixed `37,654` count.
   - *Confounder:* Antithetic intrabasin graben faults dip back toward the range front, flipping hanging-wall polarity if `depth_to_base_surf` is locally flat.
   - *Falsifier:* Live change `< +0.01` vs. symmetric `PRUNE3`, or symmetric `PRUNE4` matches it at equal count.
2. **`TIP_RELAY` (Along-Strike Termination & En-Echelon Step-Over Corridor Reallocation):**
   - *Mechanism:* New faults disproportionately extend unmapped beyond mapped fault tips (`|cos(θ - θ_tip)| > 0.85` within `0.3–2.5 km` of degree-1 catalogue endpoints) and across `0.5–3 km` relay ramps ([Faulds inventory prior](https://gdr.openei.org/submissions/1391)), whereas broad flank parallels are mostly digitization halos. Shift `15%` of lowest-`dT` flank dots into along-strike tip cones (`>= 3 px` from catalogue) on `H19-5` / geopotential ridges.
   - *Confounder:* Alluvial fan apex channels radiating from range-front canyon mouths align near fault segment boundaries and mimic tip splays.
   - *Falsifier:* Live change `<= -0.01` vs. parent, indicating hidden labels sit in isolated basin interiors rather than connected fault-system extensions.
