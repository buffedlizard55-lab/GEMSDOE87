# SLOT_PLAN — GEMS Prize #306 (one entity, 3 scored slots per rolling week, 1 blind final)

**As of:** 2026-10-23. **Deadline:** 2026-12-03 (confirm on the [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)). **Rules:** [rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf).
**Parent R0:** `h33-h33-2-b2`, `37,654` dots, rebuilt byte-exact. `0.2778` is a CLAIM. TOP_PUBLIC `____`; slots left `__` (human fills both).
**Built (ledger):**
- MASS (m10minus, m10plus, m20minus)
- CONCENTRATION (c10, c15, c20)
- PRUNE (3, 1, 4)
- **SNAP (slope, tmihg, gravhg)**

A live `|Δ| < 0.01` counts as no evidence. That covers public chunks only.

## Next 3 slots, in order

1. **`h33-h33-2-b2-PRUNE3-20261023-bc00a06c`** (5.77% changed; pred +0.005 to +0.012 MODEL). This is the cleanest single-mechanism test, and it makes the parent compliant with the `>= 3 px` collar.
   - `Δ >= +0.01`: adopt PRUNE3 as R1. Score PRUNE4 next.
   - `|Δ| < 0.01`: adopt PRUNE3 as R1 anyway (compliance). Go to slot 2.
   - `Δ <= -0.01`: new strands hug the known traces. Score PRUNE1 next.
2. **`h33-h33-2-b2-CONCc10-20261023-a9e67bab`** (10% changed; pred +0.004 MODEL). If slot 1 moved by `>= 0.01`, follow the PRUNE slope instead.
3. **`h33-h33-2-b2-SNAPslope-20261023-81ae160f`** (89.4% of dots moved, mean 1.33 px; pred +0.004 MODEL, range -0.006 to +0.012). It is the only SNAP variant that beat the random-crest null on the catalogue PROXY (+4.1% of near-trace credit). TMI-HG lost to the null (-0.6%), and gravity-HG barely moves.
   - `Δ >= +0.01`: positioning error is resolvable at 100-200 m and new faults are topographically expressed. Build SNAP on the R1 parent, and ask the human whether to use the pinned 3DEP lidar-scarp raster.
   - `Δ <= -0.01`: H19-5 positions beat 100 m slope crests. Retire SNAP; never score SNAPtmihg or SNAPgravhg.
   - `|Δ| < 0.01`: SNAP is unresolvable at this metric. Retire it and spend the slots on combining axes.

Do not score SNAPtmihg or SNAPgravhg unless SNAPslope gives `Δ >= +0.01`. Never spend 3 slots on one axis without a receipt.

## Weeks to the deadline (about 6 weeks, up to 18 slots + 1 final)

- **Wk 1–2 (Oct 23 – Nov 5, 6 slots):** the 3 slots above, then MASS m10plus, RELIEF (not built yet), and the PRUNE follow-up the receipts call for.
- **Wk 3–4 (Nov 6 – Nov 19, 6 slots):** combine the two axes with `Δ >= +0.01` receipts on the winning parent (for example PRUNE3 + CONCc10, or PRUNE3 + SNAPslope). Test one proposed axis below as a single-factor edit.
- **Wk 5–6 (Nov 20 – Dec 3, 6 slots + final):** confirm the combined winner with one repeat-free variant. Choose the blind final file and a fallback, re-validate both against `sample_submission.tif`, and finish AI_USE.md. Build TRACKB (Phase 2 traces) in parallel; it uses no slot.

## Proposed better axes (not built this session)

1. **SNAP_CONTROL (random-crest snap at matched displacement).** *Mechanism:* separates "being moved" from "being moved to a crest". If SNAPslope gives `Δ >= +0.01`, a matched random snap is the only way to attribute the gain to slope. *Confounder:* density changes from blocked moves. *Falsifier:* the random snap scores within 0.01 of SNAPslope.
2. **DIP_COLLAR (asymmetric hanging-wall shift).** *Mechanism:* normal faults dipping 45–60° put the potential-field step basinward of the surface trace, so moving collar dots toward the footwall side should help. *Confounder:* antithetic faults flip polarity. *Falsifier:* `Δ < +0.01` against PRUNE3.
3. **TIP_RELAY (along-strike tips and step-overs).** *Mechanism:* move 15% of the lowest-gain dots into 0.3–2.5 km cones ahead of mapped fault tips and into en-echelon step-overs, using the [Faulds/INGENIOUS prior](https://gdr.openei.org/submissions/1391) only as a zone prior. *Confounder:* fan-head channels at canyon mouths. *Falsifier:* `Δ <= -0.01`.
