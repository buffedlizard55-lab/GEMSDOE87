# Score & Claim Provenance Audit (`GEMSDOE87`)

Strict separation between **measured holdout performance (`HOLDOUT-DTI`)**, **registry geometry measurements (`REGISTRY-MEASUREMENT`)**, and **user-reported / owner-ledger live leaderboard figures (`UNVERIFIED-LEDGER-CLAIM`)**. Zero live projections are reported as scores.

| Metric / Claim | Value | Mandatory Label | Provenance / Verification |
| :--- | :---: | :---: | :--- |
| `E3_CSCT_DINKELBACH` Dual-Seed Pooled Score | **`0.210717`** (`95% CI [0.193821, 0.227662]`) | **`HOLDOUT-DTI`** | `vendor/gems57/evaluate_holdout.py` (`gems57-pooled-hide-v2`, `n = 22,663` withheld positives across `seeds=(20, 30)`, `2,000` paired 20 km spatial block-bootstrap draws; `evidence/e1_e2_e3_holdout_results.json`) |
| `E3_CSCT_DINKELBACH` Seed 20 / Seed 30 | **`0.202105`** / **`0.219306`** | **`HOLDOUT-DTI`** | `gems57-pooled-hide-v2` (`n = 11,321` / `11,342` withheld positives; `evidence/e1_e2_e3_holdout_results.json`) |
| `E2_CSCT_POISSON` Dual-Seed Pooled Score | **`0.197499`** (`95% CI [0.180300, 0.214381]`) | **`HOLDOUT-DTI`** | `gems57-pooled-hide-v2` (`n = 22,663` withheld positives; paired `E3 - E2 = +0.013219`, `95% CI [+0.008076, +0.018958]`) |
| `E1_BLIND_POISSON` (Zero Catalogue Input) | **`0.112262`** (`95% CI [0.098085, 0.126466]`) | **`HOLDOUT-DTI`** | `gems57-pooled-hide-v2` (`n = 22,663` withheld positives; paired `E1 - CTRL_TOPO = +0.019421`, `95% CI [+0.009695, +0.029137]`; pure `detached` Seed 20 = `0.110227`) |
| `CTRL_RAND` / `CTRL_CG` / `CTRL_TOPO` / `HIST_D28` | `0.045973` / `0.073768` / `0.092841` / `0.093234` | **`HOLDOUT-DTI`** | Identical `gems57-pooled-hide-v2` instrument & matched active domain (`evidence/e1_e2_e3_holdout_results.json`) |
| `GEMSDOE83` `H83-GVCD` Upstream Comparator | `0.206817` (`95% CI [0.192711, 0.219822]`) | **`HOLDOUT-DTI`** | Verified directly from `buffedlizard55-lab/GEMSDOE83/evidence/h83_run_card.json` on identical `gems57-pooled-hide-v2` (`22,663` withheld positives) |
| Single-Feature Leakage Canary (`55` features) | `Seed 20 max = 0.783631`, `Seed 30 max = 0.781309` (`<= 0.90`) | **`CANARY-ROC-AUC`** | `evidence/e0_leakage_canary.json` (`55 / 55` features pass on both draws) |
| Registry Uniqueness (`476` unique SHA-256 rasters) | Pre-surface `|rho| = 0.5054 <= 0.90`; Post-dot `0 / 464` discriminating firings (`max = 0.6500 <= 0.70`) | **`REGISTRY-MEASUREMENT`** | `evidence/uniqueness_audit_full.json` across `858` local `.tif` files spanning `93` repos |
| `gems87-csct-dink300-37654dots-20261022-zeros.tif` Live Score | `null` (*Not yet uploaded to DrivenData*) | **`UNSCORED`** | No organizer portal upload performed from sandbox; `weekly_slots_used = 0` |
| `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` (`0.2778`), `0.3195`, `0.4413` | `0.2778` / `0.3195` / `0.4413` | **`USER-REPORTED / UNVERIFIED LEDGER`** | Cited strictly from user prompt & sibling `60GEMSDOE` ledger; no organizer screenshot/receipt exists in repo |
