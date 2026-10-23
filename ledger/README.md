# Ledger

`submissions.csv` holds one row per built variant of R0 (`h33-h33-2-b2`):
- MASS rows copied from GEMSDOE88 (not rebuilt here)
- CONCENTRATION and PRUNE rows built in GEMSDOE87
- SNAP rows built in GEMSDOE87 on 2026-10-23 by `scripts/build_snap_variants.py`

`receipt_score` and `date` stay empty until the human pastes a receipt from the submission page.

Mechanism cards:
- `mechanism_cards.json`: CONCENTRATION
- `mechanism_cards_snap.json`: SNAP
- `../releases/manifest.json`: PRUNE
