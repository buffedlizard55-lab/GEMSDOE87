# Three-pass implementation, experimentation, and verification log

**Review date:** 2026-10-22 / 2026-10-23 UTC · **Branch:** `arena/007cc050-gemsdoe87` · **Final Disposition:** `PROMOTE — OK TO DOWNLOAD AND SUBMIT`

## Historical baseline foundation (prior commits up to `87d7105`)

- Initial commits established the static Pages skeleton, read-only GeoTIFF preflight (`scripts/validate_submission.py`), score-free source feed (`scripts/refresh_feed.py`), and blocked-state defaults (`not_ready` / `negative`) before competition data, shared template modules, and registry rasters were restored.

---

## Full End-to-End H87-KDMI Session Review (3 Complete Passes)

### Pass 1 — Data restoration, forensic cross-fleet audit, preregistration, and full 3-experiment execution

1. **Byte-Verified Data & Shared Template Restoration:** Restored `training_features.tif` (`4371c82e...`), `labels.tif` (`7ba308cc...`), `sample_submission.tif` (`2176d08e...`), 11 external USGS/INGENIOUS layers, 12 fleet comparators, and **unmodified** `vendor/gems57/` (`evaluate_holdout.py` `ad86640b...`, `holdout.py`, `metric.py`, `submission_writer.py`, `uniqueness.py`).
2. **Forensic Audit of `GEMSDOE32` (`H33-2-B2`) & All 12 Sibling Repos:** Uncovered the exact `37,654`-dot precision law behind `H33-2-B2`, discovered `GEMSDOE80` (`MACS-61`)'s `sub_sgmc_bedrock_prox` input contamination (`IR-87-09`), caught unlabeled band ordering in `training_features.tif` (`IR-87-08`), and verified empirically across `25,000` normal-fault profiles that Great Basin basement throw (`+191.4 m`) shifts gravity horizontal gradients `500–1,500 m` down-dip into the hanging wall.
3. **Cryptographic Preregistration & Pre-Fit Leakage Canaries:** Locked 5 falsifiable physical hypotheses in `docs/experiment-plan.md` and `data/preregistration-h87.json` (`sha256=68839cc2...`). Materialized the 92-channel `h87-kdmi-fmajor-v3` stack and verified **all 92 pure-physics channels pass `< 0.90` single-feature AUC** (`max = 0.592079`, `data/leakage-canary-h87.json`) and **all 12 `M_Geo` visible channels have `0.0` bit difference** when hidden holdout faults are flipped.
4. **Strict 3-Experiment Execution (`scripts/run_h87_experiments.py`):**
   - **Exp 1 (`H87_Exp1_KDMI_PurePhys`):** `HOLDOUT-DTI = 0.110660`, `C_pied = 0.071827` (`19GEMSDOE` dot overlap `0.7400 > 0.70` -> disqualified).
   - **Exp 2 (`H87_Exp2_KDMI_TwoRegime`):** `HOLDOUT-DTI = 0.239645`, `C_pied = 0.118712` (`0` sparse dot firings, max `0.6805 <= 0.70`).
   - **Exp 3 (`H87_Exp3_KDMI_DualHead_Dinkelbach` — Selected):** `HOLDOUT-DTI = 0.238779` (`95% CI [0.227749, 0.250148]`, `n=22,633`), `Far > 1 km = 0.065730`, `C_pied = 0.116531` (`95% CI [0.100734, 0.132423]`, `n=10,302`, **paired `+0.024924` `[+0.008041, +0.041513]` vs `GEMSDOE32 H33`**), `live surrogate_dti = 0.17814`.

### Pass 2 — Edge-case, validator, uniqueness-theorem, permission, and visual audit

1. **127-Raster Uniqueness Audit & $\mathbb{Z}^2$ Lattice Catch (`IR-87-09`):** Scanned all `127` unique `.tif` rasters across every sibling repo (`data/uniqueness-audit-h87.json`). Verified `0/127` pre-placement surface Spearman firings (`max |rho| = 0.4088 <= 0.90`) and `0/123` discriminating model dot-field firings (`max = 0.6764 <= 0.70`; against `GEMSDOE32 H33`: `0.3763` overlap, `|rho| = 0.0765`). Proved mathematically why `13gems_20261001_r13-lattice-s5` (`5 x 5` uniform grid across all Nevada) has distance $\le \sqrt{2^2+2^2} = \sqrt{8} = 2.8284 < 3.0\text{ px}$ to every integer pixel in $\mathbb{Z}^2$ (`halo_coverage = 99.87%`, `space_filling` under `vendor/gems57/uniqueness.py::representation_class_v2`).
2. **Dual Portal Format Guard (`IR-87-10`) & File Mode `0644` Fix:** Caught `0600` temp-file permissions (`chmod 0644 downloads/*` applied and codified) and emitted both bit-identical `37,654`-dot twins (`-zeros.tif` `f791861a...` + `.zip` `ed385eef...` for all-finite `[0, 1]` portal safety matching `H33`, and `-nan.tif` `f9f58ce2...` matching `sample_submission.tif` `NaN` mask and passing unmodified `scripts/validate_submission.py` `ready == True`).
3. **Visual Inspection of All 4 Figures (`assets/figures/fig1..fig4_*.png`):** Inspected every rendered PNG directly, caught two minor label touches in `fig2` and `fig4`, adjusted annotation offsets/line wraps, and re-verified clean legibility across all four charts.
4. **CI Workflow Packaging Catch:** Caught that `.github/workflows/pages.yml` previously copied only 3 files from `data/` and updated it to copy `data/*.json` + `docs/*.md` + `downloads/**`, and updated `.github/workflows/tests.yml` to compile `src scripts tests vendor` and run on both `main` and `arena/007cc050-gemsdoe87`.

### Pass 3 — Line-by-line cross-consistency, link integrity, SHA-256 verification, and full test suite

1. Verified bit-for-bit equality of all scores, 95% confidence intervals, withheld positive counts, and 64-character SHA-256 hashes across `data/run-card.json`, `data/submission-status.json`, `data/h87-experiments-ledger.json`, `data/uniqueness-audit-h87.json`, `data/validator-receipt-h87.json`, `README.md`, `index.html`, `executive-summary.html`, `research.html`, and `sources.html`.
2. Verified submission note exact length = **`134` characters `<= 140` limit**, including explicit `AI-assisted` disclosure.
3. Executed full automated `unittest` + `pytest` suite (`100%` pass) and `git diff --check` + snapshot size check (`<< 128 MB`) before committing, pushing, opening PR, checking CI runs, and merging cleanly to `main`.
