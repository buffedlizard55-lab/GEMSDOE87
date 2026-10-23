# AI_USE — Generative-AI disclosure per NLR Rules §3.6

**Human:** `buffedlizard55-lab` (entity owner, submitter, approver). **AI:** Arena.ai Agent Mode (branch `arena/6743515f-gemsdoe87`). Copy into the final technical narrative.

## What AI wrote (this session, 2026-10-23)

- `src/gems87/concentration.py` and `scripts/generate_concentration_variants.py`: verify pinned SHAs, rebuild R0 as GEMSDOE25 ∩ {d>2} and assert pixel identity with `c55bafc4…`, relocate 10/15/20% of dots from lowest-H19-5 1 km blocks to highest-H19-5 blocks at fixed count / 2 px collar / √8 spacing, write NaN-outside + zeros-outside GeoTIFFs, re-read, validate, ledger rows.
- `SLOT_PLAN.md`, `docs/SUBMIT.md`, `ledger/submissions.csv`, `ledger/mechanism_cards.json`, `IRREGULARITIES.md`, README CURRENT STATE block, `tests/test_concentration_axis.py`.
- Predicted live deltas (+0.004, +0.002, −0.006) are **MODEL**, not scores.

## What the human decided

- AXIS for this session was unfilled in the brief; MASS was already built in GEMSDOE88, so CONCENTRATION was taken as the next unused axis (default wk1–2 plan). Human may override.
- Human fills TOP_PUBLIC, weekly slot timestamps, and `receipt_score` / `date` after authenticated submission. Human chooses the one final file blind.
- Human must confirm deadline 2026-12-03 on the competition page.

## Reproducibility

Inputs (sha256 verified before use): `sample_submission.tif` `2176d08e…`, `existing_faults.tif` `7ba308cc…`, R0 zeros `c55bafc4…`, R0 nan `baeae321…`, GEMSDOE25 nan `91eae1ca…`, H19-5 `ec1f9b56…`. No dropbox.com, no drivendata.org fetch, no credentials. Git SHA logged in `docs/evidence/exp87_concentration_build.json`.
