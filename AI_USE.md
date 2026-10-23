# AI_USE — disclosure (competition rules require it)

Session 2026-10-23, agent brief v2, AXIS=MASS.

**What the AI wrote/ran:** input hash verification and parent-recipe
reproduction; `scripts/build_mass_variants.py` + `scripts/dot_thin_ref.py`
(vendored parent thinning reference); the two MASS rasters in `releases/`;
`tests/test_mass_algebra.py`; `ledger/submissions.csv`; `SLOT_PLAN.md`;
`IRREGULARITIES.md`; `docs/mechanism-cards-mass.md`; `docs/SUBMIT.md`; the
README CURRENT STATE block.

**What the human decided:** assigned AXIS=MASS; owns TOP_PUBLIC, slot counts,
and the deadline confirmation (left blank for the human); will review the
mechanism cards and decide whether either file spends a slot; submits (or
not) from their own registered account.

**What the AI never did:** no submission, no login, no scraping, no contact
with dropbox.com or drivendata.org. External bytes came only from the pinned
GitHub mirrors named in `registry/data_manifest.json` /
`registry/canonical_scored_index.json`, each sha256-verified before use.
Scores labelled CLAIM/PROXY/MODEL follow brief §8; nothing here calls a
MODEL a score.

**Session addendum (later, 2026-10-23, agent-picked axis):** the human
instructed the agent not to prompt over the axis and to pick its own;
the agent picked SNAP. The AI then wrote `scripts/build_snap_variants.py`
and `tests/test_snap.py`, restored + sha256-verified the pinned
`training_features.tif`, built the three SNAP rasters in `releases/`,
and updated the ledger, slot plan, mechanism cards, submit notes and
irregularities. Still no submission, login, scraping, or contact with
dropbox.com / drivendata.org by the AI.
