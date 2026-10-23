# Submission checklist — human uploads ONE file per slot

No CONCENTRATION variant is marked for upload until the human assigns a weekly slot. All three pass format checks (EPSG:32611, 3730×3292, float32, [0,1], 0 NaN inside, NaN outside + zeros fallback, 0 catalogue mass, 0 dots with d≤2 px). Parent 0.2778 is CLAIM.

## 1. CONCc10 — recommended Slot 1 this week (if MASS is not used)

- **File (NaN outside, per spec):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab.tif`
  sha256 `a9e67bab4ab3ddc01027383ba47f8febc6232e0c8bd42ba62cc4e782737c84ec`
- **Fallback (zeros outside):** `releases/h33-h33-2-b2-CONCc10-20261023-a9e67bab-zeros.tif`
  sha256 `c79400032488ed92002f897a078b8143272f35787e843f179073aab686dae6f0`
- **Name:** `h33-h33-2-b2-CONCc10-20261023-a9e67bab`
- **Note (81/140):** `h33-2-b2 CONCc10 37654 move10% lo->hi 1km; pred +0.004 MODEL; parent 0.2778 CLAIM`
- **Format receipt:** 37,654 dots, 10.00% changed, CV_occ 0.619→0.748, min sep √8, min d_cat 2.236, 0 on catalogue. Re-read verified. `scripts/validate_submission.py` ready=true; `gems57.validate` all_checks_passed=true on zeros.

## 2. CONCc15 — only after a positive CONCc10 receipt

- **File:** `releases/h33-h33-2-b2-CONCc15-20261023-25e403d0.tif`
  sha256 `25e403d041015ff95789a07187df47b18c7e2d33f4011833612597699324b6d5`
- **Fallback:** `releases/h33-h33-2-b2-CONCc15-20261023-25e403d0-zeros.tif`
  sha256 `d632f28b50b0fec93392ce2849cb3e8003a40499ca4d7f3ea33f2fa752d81ddc`
- **Name:** `h33-h33-2-b2-CONCc15-20261023-25e403d0`
- **Note (81/140):** `h33-2-b2 CONCc15 37654 move15% lo->hi 1km; pred +0.002 MODEL; parent 0.2778 CLAIM`

## 3. CONCc20 — elasticity bound, not a first slot

- **File:** `releases/h33-h33-2-b2-CONCc20-20261023-03244051.tif`
  sha256 `03244051b856f952a24919c5e9af050a6d33495c2bbfd853c695ea1dd3330c1f`
- **Fallback:** `releases/h33-h33-2-b2-CONCc20-20261023-03244051-zeros.tif`
  sha256 `a9b0a226404ca91f34f91026313a68a0b168728481bf0eb9b8f7b3bb7ad6fb2f`
- **Name:** `h33-h33-2-b2-CONCc20-20261023-03244051`
- **Note (81/140):** `h33-2-b2 CONCc20 37654 move20% lo->hi 1km; pred -0.006 MODEL; parent 0.2778 CLAIM`

## Human steps (own authenticated account)

1. Restore pins: `python scripts/restore_r0_inputs.py` (sample `2176d08e…`, existing_faults `7ba308cc…`, R0 zeros `c55bafc4…`).
2. `python -m pytest -q` and `python scripts/validate_submission.py --prediction releases/<id>.tif --reference data/bridge/sample_submission.tif`.
3. Upload **one** GeoTIFF (NaN or zeros; inside pixels identical) + note. Copy receipt score/date into `ledger/submissions.csv` as RECEIPT.

Do not fetch drivendata.org from this sandbox. Generative-AI disclosure: `AI_USE.md`.
