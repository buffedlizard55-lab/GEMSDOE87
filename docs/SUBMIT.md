# SUBMIT — human uploads ONE file per slot, from their own account

Agent never submits. Both files below are BUILT + validated, not submitted.
Fill `receipt_score`/`receipt_date` in `ledger/submissions.csv` after upload.

## Slot candidate 1 — MASS −10% (submit first, per SLOT_PLAN)

- File: `releases/h33-2-b2-massminus10-20261023-a00d6355.tif` (NaN outside footprint)
- Fallback (upload only if the portal rejects NaN encoding): `releases/h33-2-b2-massminus10-20261023-a00d6355-zeros.tif`
- Name: `h33-2-b2-massminus10-20261023-a00d6355.tif`
- Note (≤140 chars): `parent h33-2-b2; MASS -10% lowest marginal-gain dots; 33,889 dots; pred <0.01 MODEL`
- Format receipt: validator `ready: true, errors: []` vs `sample_submission.tif`;
  float32, 1 band, EPSG:32611, 3730×3292, transform of the sample; values in
  [0,1]; no NaN inside footprint (5,167,373 px); 0 dots / 0 mass on catalogue;
  min catalogue distance 2.236 px; sha256 `a00d63556a22dacc8af41f8d6e24209bbeee75b9774a0bd840004a4529a7aa78`.

## Slot candidate 2 — MASS +10%

- File: `releases/h33-2-b2-massplus10-20261023-70e3d289.tif` (NaN outside footprint)
- Fallback: `releases/h33-2-b2-massplus10-20261023-70e3d289-zeros.tif`
- Name: `h33-2-b2-massplus10-20261023-70e3d289.tif`
- Note (≤140 chars): `parent h33-2-b2; MASS +10% next-ranked marginal-gain dots; 41,419 dots; pred <0.01 MODEL`
- Format receipt: validator `ready: true, errors: []`; same grid/ CRS/range
  checks as above; 0 on catalogue; min catalogue distance 2.236 px;
  min inter-dot separation 1.0 px (disclosed spacing side-effect — see
  `docs/mechanism-cards-mass.md`); sha256 `70e3d289f368e9197ca4f7834dfed7b86f4aeec5d94e8fc6334727b29ec8ad1e`.

Predicted changes are MODEL (brief §8), never scores. A live |Δ| < 0.01 is
no evidence. Mechanism cards: `docs/mechanism-cards-mass.md`.
