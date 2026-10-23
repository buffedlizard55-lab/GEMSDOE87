# Ledger

`submissions.csv` is the single record of built variants (`18` `BUILT` rows across all five Week 1–2 axes). Rows: `MASS` (`GEMSDOE88`, not rebuilt here), `CONCENTRATION` (built 2026-10-23, PR #25), `PRUNE` (built 2026-10-23, `scripts/build_prune_variants.py`), `SNAP` ×6 built 2026-10-23 by two parallel sessions — crest operator (`tmi-hg`, `scarp`, `grav-argmax`; `scripts/build_snap_variants.py`, session `arena/d76a6a5f`) and edge-argmax operator (`tmi2`, `grav2`, `comb2`; `scripts/build_snap_edge_variants.py`, session `arena/e89a6f6d`, human-assigned axis) — and `RELIEF` (built 2026-10-23, `scripts/build_relief_variants.py`, session `arena/c677fe69`). `receipt_score` / `date` stay empty until the human pastes a submission-page receipt; a fill is `RECEIPT`, everything else is `MODEL`/`CLAIM`/`PROXY`.

Mechanism cards: `mechanism_cards.json` (`CONCENTRATION` + edge-argmax `SNAP`), `mechanism_cards_snap.json` (crest `SNAP`, keyed by variant id), and `mechanism_cards_relief.json` (`RELIEF`, keyed by variant id). `lineage_claims.csv` holds the collapsed pre-existing lineage (`CLAIM`, `receipt = N`).

Do not delete rows: dedupe is exact-hash plus repeated `(parent, axis, value)`, and every builder refuses to write a duplicate.
