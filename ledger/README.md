# Ledger

`submissions.csv` is the single record of built variants. Rows: `MASS` (`GEMSDOE88`, not rebuilt here), `CONCENTRATION` (built 2026-10-23, PR #25), `PRUNE` (built 2026-10-23, `scripts/build_prune_variants.py`) and `SNAP` (built 2026-10-23, `scripts/build_snap_variants.py`). `receipt_score` / `date` stay empty until the human pastes a submission-page receipt; a fill is `RECEIPT`, everything else is `MODEL`/`CLAIM`/`PROXY`.

Mechanism cards: `mechanism_cards.json` (`CONCENTRATION`), `mechanism_cards_snap.json` (`SNAP`, keyed by variant id). `lineage_claims.csv` holds the collapsed pre-existing lineage (`CLAIM`, `receipt = N`).

Do not delete rows: dedupe is exact-hash plus repeated `(parent, axis, value)`, and both builders refuse to write a duplicate.
