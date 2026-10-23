# SLOT PLAN — GEMS Prize (DrivenData #306)

> **Deadline:** 2026-12-03 (confirm on the competition page). **Quota:** 3 scored submissions / rolling week, 1 final blind pick. **Week of 2026-10-23:** slots left __ / 3 (0 receipts in this ledger). **Weeks to deadline:** ~6 (not independently confirmed).

Parent **R0 = h33-h33-2-b2**: 37,654 dots, 0 within 2 px, sha `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`, 0.2778 CLAIM. MASS (m10minus / m10plus / m20minus) already built in GEMSDOE88 — not repeated.

## This session (AXIS=CONCENTRATION) — built 2026-10-23

Block size **10 px = 1 km**. Prior = H19-5 block sum (parent field). Count fixed, 2 px collar, min sep √8. Occupied-block CV 0.619 → 0.748 / 0.786 / 0.795 (best-file band reportedly 0.51–0.59).

| ID | Value | n_dots | % changed | sha8 | CV_occ after | Predicted live Δ | Status |
|---|---|---|---|---|---|---|---|
| h33-h33-2-b2-CONCc10-20261023-a9e67bab | c10 | 37,654 | 10.00 | a9e67bab | 0.748 | +0.004 MODEL | BUILT |
| h33-h33-2-b2-CONCc15-20261023-25e403d0 | c15 | 37,654 | 15.00 | 25e403d0 | 0.786 | +0.002 MODEL | BUILT |
| h33-h33-2-b2-CONCc20-20261023-03244051 | c20 | 37,654 | 20.00 | 03244051 | 0.795 | −0.006 MODEL | BUILT |

Do **not** spend three slots on c10/c15/c20 in one week. One CONC receipt teaches the axis.

## Next 3 slots in order

1. **CONCc10** — least aggressive concentration. If live RECEIPT Δ ≥ +0.01, km-clustering is real → next CONCc15. If Δ ≤ −0.01, abandon CONC, go SNAP. |Δ|<0.01 is no evidence (public chunks only).
2. **SNAP ≤2 px** (next session) if CONCc10 is null/negative; else **CONCc15**. SNAP: same count, move each dot ≤2 px to strongest TMI/gravity-gradient pixel in its window; report mean displacement. Needs pinned gradient bands (`training_features.tif` sha `4371c82e…`).
3. **PRUNE 3 px** — parent has 2,171 dots with 2 < d ≤ 3 px (5.76%). Drop them and refill to 37,654 from the H19-5 pool at d>3. Tests brief §4.4 vs inherited 2 px collar. Do not mix with CONC in the same file.

## Weeks to deadline (provisional)

- **Wk1–2 (now → ~11-05):** MASS (built, GEMSDOE88), CONCENTRATION (this session), then SNAP, PRUNE, RELIEF. One (AXIS, value) each. Check ledger first.
- **Wk3–4:** Combine the two best axes by live Δ (e.g. CONCc10 + SNAP). Pre-register; keep 1–50% change; no new field.
- **Wk5–6:** Confirm, pick one final + fallback blind, re-validate format of both (EPSG:32611 3730×3292 float32 [0,1] NaN outside). Disclose `AI_USE.md`.

## Better axes — not built this session

- **Strike-agreement at matched count:** require magnetic and gravity edges to share orientation over ≥1 km. Confounder: lithologic contacts. Falsifier: RECEIPT Δ ≤ −0.01 vs parent.
- **Open vs closed edges:** prefer persistent open lineaments over closed topographic rims (calderas, shorelines). Confounder: lava-flow margins. Falsifier: no ≥0.01 RECEIPT gain.

Treat Δ<0.01 live as no evidence. PROXY holdout is not a gate.
