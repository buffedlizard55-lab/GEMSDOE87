# IRREGULARITIES — items that change a decision

## IR-87-V2-01 — R0 re-encode SHA vs pixel identity (2026-10-23)

**Reported:** Rebuild R0 and match its sha256; never approximate the parent.

**Observed:** GEMSDOE25 nan (`91eae1ca…`, 44,090 dots) ∩ {d(catalogue)>2} is pixel-identical to R0 zeros (`c55bafc4…`, 37,654 dots) across the full 3730×3292 grid. Writing that array with rasterio deflate/tiled 256 does **not** reproduce sha256 `c55bafc4…` (size 148,876 vs 219,065). Original R0 bytes from GEMSDOE32 match `c55bafc4…`.

**Decision:** Use original R0 bytes as parent. Do not ship a re-encoded “R0”. Variants start from the verified pixel support.

## IR-87-V2-02 — 2 px collar vs brief ≥3 px (non-PRUNE)

**Reported:** Zero catalogue mass and keep ≥3 px from catalogue unless AXIS=PRUNE.

**Observed:** R0 has min d=2.236 and **2,171 dots with 2<d≤3**. Enforcing 3 px on CONCENTRATION would also change PRUNE.

**Decision:** Inherit parent 2 px for this axis. PRUNE-3px is a later slot. CONCc10/c15/c20 have 2,575 / 2,724 / 2,877 dots with d≤3 after relocation (still 0 with d≤2).

## IR-87-V2-03 — MASS already built (GEMSDOE88)

**Reported:** Each (AXIS, value) pair is built once; AXIS assigned by human (blank this session).

**Observed:** GEMSDOE88 ledger already has MASS m10minus / m10plus / m20minus. No CONCENTRATION rows.

**Decision:** This session built CONCENTRATION only. MASS hashes are recorded in `ledger/submissions.csv` for dedupe, not rebuilt.

## IR-87-V2-04 — TOP_PUBLIC unfilled; H19-5 is binary

**Reported:** TOP_PUBLIC = ____ (human fills). Parent ranking from recorded recipe.

**Observed:** Leaderboard was not fetched (terms ban automated access). H19-5 (`ec1f9b56…`) is a **binary** 121,131-dot field, not a continuous ranking; R0 ⊂ H19-5. Block prior = H19-5 count per 1 km cell.

**Decision:** No TOP_PUBLIC number is written as a target. Ranking is H19-5 block mass, not a fabricated per-dot score.

## IR-87-V2-05 — Catalogue count 60,988 vs older 142,272 prose

**Observed:** Pinned `existing_faults.tif` (`7ba308cc…`) has 60,988 positives, identical to finite-1 cells of `sample_submission.tif`. Older GEMSDOE87 prose cited 142,272.

**Decision:** Use the pinned raster. Collar statistics in this session are against 60,988 cells.
