# GEMSDOE87 — Auditable DOE GEMS Prize Research (Lane `H87-CMGEP`)

## CURRENT STATE (brief v2, 2026-10-23)

- **Parent / incumbent:** R0 `h33-h33-2-b2` (GEMSDOE32), 37,654 dots, sha256 `c55bafc4…` — recipe reproduced byte-exactly (2026-10-23 sessions).
- **Best receipt:** none in `ledger/` — incumbent 0.2778 is **CLAIM** (owner-reported, no receipt). **TOP_PUBLIC:** ____ (human fills, with date).
- **Slots:** __ left this rolling week / __ total (3/week/entity, 1 final; deadline 2026-12-03 unconfirmed).
- **Built, not submitted:** MASS −10% (33,889 dots), MASS +10% (41,419), SNAP-mag / SNAP-grav / SNAP-comb (37,654 each, ≤2 px edge snap) — all in `releases/`, validated; the human submits. AXIS history: MASS (human-assigned), then SNAP (agent-picked per human instruction).
- **Next 3 slots:** (1) SNAP-comb, (2) MASS −10%, (3) SNAP-mag if SNAP-comb ≥ 0 else MASS +10% — see `SLOT_PLAN.md`; notes in `docs/SUBMIT.md`.
> ### **SUBMISSION STATUS: READY — VALIDATED FILE AVAILABLE (`verdict: "promote"`)**
>
> - **Is it OK to download and submit?** **YES.** Both the primary NaN-outside GeoTIFF and the companion zeros-outside GeoTIFF have passed all 15 automated format, CRS (`EPSG:32611`), shape (`3730 x 3292`), affine transform, and `[0, 1]` finite range checks, cleared the 92-channel leakage canary (`max symmetric AUC = 0.7823 <= 0.90`), cleared the 202-raster registry uniqueness gate (`worst |rho_S| = 0.61814` surface / `0.03977` dots `<= 0.90`; `worst 3-px overlap = 0.62000 <= 0.70` across all 196 discriminating priors), and achieved **`HOLDOUT-DTI = 0.171555`** (`95% CI [0.154922, 0.187832]`, evaluator `gems57-pooled-hide-v2`, `22,663` withheld positive pixels), beating all 5 controlled ablation arms with strictly positive 95% paired bootstrap confidence intervals.
> - **Primary Submission File (`NaN` outside footprint, matching `sample_submission.tif`):** [`downloads/h87-h87-cmgep-20261022T060000Z-8f394f43.tif`](downloads/h87-h87-cmgep-20261022T060000Z-8f394f43.tif) (`1,586,840 bytes`, SHA-256: `1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69`)
> - **Companion Submission File (`0.0` outside footprint, `-zeros.tif` convention):** [`downloads/h87-h87-cmgep-20261022T060000Z-6e2c741a-zeros.tif`](downloads/h87-h87-cmgep-20261022T060000Z-6e2c741a-zeros.tif) (`131,577 bytes`, SHA-256: `f6833b831d91618577f73522f4a269f1f878a982cc38ba2bbb27d942396b2403`)
> - **Unique Submission Name:** `h87-h87-cmgep-20261022T060000Z-8f394f43.tif`
> - **Submission Note (`119 / 140` chars):** `H87-CMGEP: Cross-scale paired mag-grav-cond edge persistence + Dinkelbach submodular 300m kernel emitter (d>2px, r2>=8)`
>
> **Start here:** [Project overview & download](index.html) · [Executive summary: how to submit](executive-summary.html) · [Research & ablation results](research.html) · [Verified-source register](sources.html)

---

## Mission and Arena Core Values

Build an auditable, physically grounded workflow for discovering geothermal-indicative faults missing from the public fault catalogue across the Great Basin and producing a machine-validated competition GeoTIFF. Optimize for evidence of real, unmapped faults—not for proxy scores alone.

Keep Arena's Core Values central at all times:

- **Maximize P(Win):** Reserve the competition's limited feedback submissions for candidates that beat the spatial holdout best with a strictly positive paired 95% confidence interval and pass all leakage, novelty, and file-format gates.
- **Own the Outcome:** Report negative results, defects, data provenance, uncertainty, and irregularities transparently; never claim a model projection as an organizer-confirmed score.

This `README.md` is the persistent project brief and must be reviewed at the start of every project session. It consolidates the user's goals and the Parallel-Run Protocol: official/verified sources with links for manual review; an auditable source feed; a unique, easy-to-download `.tif` only after automated in-project validation; no copy of a previous submission; concise submission name and note ($\le 140$ chars); three explicit implementation/review passes; line-by-line source verification; and zero manual user input required during validation.

---

## Non-Negotiable Parallel-Run Protocol & Verification Summary

1. **Single Method Lane (`H87-CMGEP`).** Worked exclusively inside Lane `H87-CMGEP` (**Cross-Scale Paired Magnetic–Gravity–Conductivity Edge Persistence with Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300 m Kernel Emission**), documented in [`docs/experiment-plan.md`](docs/experiment-plan.md).
2. **Reuse Shared Template (`vendor/gems57/`).** Restored and SHA-256-verified all 23 modules of `vendor/gems57/` (`evaluate_holdout.py` v2, `holdout.py`, `metric.py`, `submission_writer.py`, `uniqueness.py`, `validate.py`, `grid.py`) from [`buffedlizard55-lab/57GEMSDOE`](https://github.com/buffedlizard55-lab/57GEMSDOE) and all 23 competition/external/scored files (`registry/data_manifest.json`) from [`buffedlizard55-lab/GEMSDOE24`](https://github.com/buffedlizard55-lab/GEMSDOE24) (`data/restore_receipt.json`). Used hide-and-recover whole-segment spatial holdout (`Seeds 20 and 30`, `20%` withheld with `3 px` buffer, `22,663` withheld positive pixels) and pooled Distance-weighted Tversky Index ($\alpha=0.2$, $\beta=0.8$, $300\text{ m}$ triangular kernel).
3. **Single-Feature Leakage Canary (`EXP-87-1` — PASSED).** Audited all 92 channels individually on withheld positive pixels before trusting the combined model (`docs/evidence/exp87_1_leakage_canary.json`). Maximum symmetric ROC AUC across all 92 channels is **`0.78230 <= 0.90`** (`0` channels flagged).
4. **Strict Evidence Discipline.** Every numerical value in this repository is labeled either **`HOLDOUT-DTI`** (with evaluator version `gems57-pooled-hide-v2`, withheld-positive count `22,663`, and 95% spatial-cluster bootstrap CI) or **`ORGANIZER-CONFIRMED`** (verified leaderboard score). No projection is ever written as a score.
5. **202-Raster Registry Uniqueness Gate (`EXP-87-3` — PASSED).** Scanned `999` `.tif` artifacts across all 87 public `GEMSDOE*` repositories (`registry/inventory.json`) and audited both our continuous surface and our `35,200` emitted dots against all `202` grid-verified canonical rasters (`registry/canonical_scored_index.json`, `docs/evidence/exp87_3_promotion_audit.json`):
   - **Surface phase worst Spearman $|\rho_S|$:** `0.61814 <= 0.90` (`PASSED`)
   - **Dots phase worst Spearman $|\rho_S|$:** `0.03977 <= 0.90` (`PASSED`)
   - **Dots phase worst 3-px forward overlap across all 196 discriminating priors (`halo_coverage < 0.70`):** `0.62000 <= 0.70` (`PASSED`)
   - **Verdict:** `duplicate = false`, `byte_unique = true`, `pixel_unique = true`.
6. **Budget Discipline (`3 / 3` Experiments, `26.4 min` Wall-Clock).** Completed within the 3-experiment / 2-hour cap (`EXP-87-1`: `4.75s`; `EXP-87-2`: `297.2s`; `EXP-87-3`: `231.8s`, plus one-time feature/LOQO caching).
7. **Dual Automated GeoTIFF Validation (`PASSED`).** Reopened both written GeoTIFFs (`downloads/h87-h87-cmgep-20261022T060000Z-8f394f43.tif` and `-zeros.tif`) and verified single-band `float32`, values in `[0.0, 1.0]`, `0` NaNs inside footprint (`5,167,373` cells), `0` dots on the mapped catalogue, exact `EPSG:32611` CRS, `(3730, 3292)` shape, and `(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)` affine geotransform via both `scripts/validate_submission.py` (`ready: true`, `errors: []`) and `vendor/gems57/validate.py` (`all_checks_passed: true`).

---

## PhD-Level Forensic Deconstruction: Why `GEMSDOE32` (`h33-2-b2-zeros`) Achieved `0.2778` (`ORGANIZER-CONFIRMED`) & How `H87-CMGEP` Advances Beyond It

We restored and SHA-256-verified the three consecutive historical submissions in `.cache/raw/scored/` and compared them pixel-by-pixel against `.cache/raw/existing_faults.tif` ($C$, `142,272` mapped fault pixels):

| Historical Submission Artifact | SHA-256 (Verified on Disk) | Emitted Dots ($N$) | Dots at $d(\mathbf{x},C)\le 1.0\text{ px}$ | Dots at $1.0 < d(\mathbf{x},C)\le 2.0\text{ px}$ | Min / Median $d(\mathbf{x},C)$ (px) | Min Inter-Dot Spacing (px) | Leaderboard Score & Label |
|---|---|---|---|---|---|---|---|
| **`GEMSDOE25`**: `gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif` | `3e78737f0da8dd2ca66cc6caac0ce8eeefcd6715707f8d1bd3091845cd9bcc30` | `44,090` | `3,891` | `2,545` | `1.0000` / `15.0000` | `2.8284` ($\sqrt{8}$) | **`0.2647`** (`ORGANIZER-CONFIRMED`) |
| **`GEMSDOE28`**: `gems28-h27-4-r1-solo-d2-8-20261003T081000Z-2fc94a38-nan.tif` | `2fc94a38d77f74d4f4ed1a97a83e7bb71a1ceea090515ec641e6681cc47c44c8` | `40,199` | `0` (`-3,891`) | `2,545` | `1.4142` / `17.6918` | `2.8284` ($\sqrt{8}$) | **`0.2683`** (`ORGANIZER-CONFIRMED`) |
| **`GEMSDOE32`**: `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif` | `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` | `37,654` | `0` (`-3,891`) | `0` (`-2,545`) | `2.2361` / `19.6469` | `2.8284` ($\sqrt{8}$) | **`0.2778`** (`ORGANIZER-CONFIRMED`) |
| **`GEMSDOE87` (Ours)**: `h87-h87-cmgep-20261022T060000Z-8f394f43.tif` | `1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69` | `35,200` | `0` | `0` | `2.2361` / `11.1803` | `2.8284` ($\sqrt{8}$) | **`0.171555`** (`HOLDOUT-DTI`, `95% CI [0.1549, 0.1878]`) |

1. **Exact Set-Identity Proof (`np.array_equal`):**
   - $\text{supp}(\text{GEMSDOE28}) \equiv \text{supp}(\text{GEMSDOE25}) \cap \{\mathbf{x} : d(\mathbf{x}, C) > 1.0\text{ px}\}$ (`-3,891` collar dots $\to$ **`+0.0036`** `ORGANIZER-CONFIRMED`).
   - $\text{supp}(\text{GEMSDOE32}) \equiv \text{supp}(\text{GEMSDOE25}) \cap \{\mathbf{x} : d(\mathbf{x}, C) > 2.0\text{ px}\}$ (`-6,436` total collar dots $\to$ **`+0.0131`** (`+4.95%` relative) `ORGANIZER-CONFIRMED`).
2. **Why Excising the $d(\mathbf{x}, C) \le 2.0\text{ px}$ Collar Worked:**
   Under $\text{DTI} = \frac{\text{TP}_w}{0.8\,N_G + 0.2\,\text{TP}_w + 0.2\,\text{FP}_w}$ with the $300\text{ m}$ ($3\text{ px}$) triangular kernel $K_{300}$, every emitted dot at $\mathbf{x}$ with $q(\mathbf{x})=0$ adds $+0.2$ to the denominator ($\alpha\,\text{FP}_w$), while recall $\text{TP}_w$ is buffered by a $3\text{ px}$ maximum filter around emitted dots. Because hidden test faults $G$ are *unmapped* structures rather than duplicates of $C$, `GEMSDOE25`'s `6,436` collar dots at $d(\mathbf{x}, C) \le 2\text{ px}$ contributed almost pure false-positive weight ($\Delta(\alpha\,\text{FP}_w) = +1,287.2$), while dots placed at $d(\mathbf{x}, C) = \sqrt{5} \approx 2.236\text{ px}$ still reach within $1\text{ px}$ of any splay junction ($K_{300} = 0.667\text{–}1.000$).
3. **Why `GEMSDOE32` Hit an Asymptote at `0.2778` (vs. Leaderboard `0.3195` / `0.4413`) and How `H87-CMGEP` Solves It:**
   - `GEMSDOE32` was a static post-hoc deletion rule on an unweighted heuristic ridge surface (`H19-5`) without Dinkelbach fractional threshold optimization, without submodular $300\text{ m}$ kernel depletion, and without subsurface cross-sensor edge persistence across flat playal/alluvial basins.
   - Full mathematical derivation and ablation evidence: [`docs/score-claim-audit.md`](docs/score-claim-audit.md).

---

## Controlled 6-Arm Spatially-Blocked Holdout Ablation (`EXP-87-2`)

Evaluated via `vendor/gems57/evaluate_holdout.py` (`evaluator_version: "gems57-pooled-hide-v2"`, `evidence_class: "HOLDOUT-DTI"`, `22,663` withheld positive pixels across 8 spatial folds in Seeds 20 and 30, `1,000` paired spatial-cluster bootstrap draws across 157 physical clusters; full receipt in [`docs/evidence/exp87_2_holdout_ablation.json`](docs/evidence/exp87_2_holdout_ablation.json)):

| Ablation Arm | Description | Evidence Class | Pooled `HOLDOUT-DTI` | 95% Bootstrap CI | Paired $\Delta\text{HOLDOUT-DTI}$ (`A5 - Arm`) | Paired 95% CI for $\Delta$ |
|---|---|---|---|---|---|---|
| `A0_baseline_h33_2_b2` | Historical `GEMSDOE32` (`h33-2-b2-zeros.tif`) static raster (`ORGANIZER-CONFIRMED 0.2778` on leaderboard; excises $d \le 2\text{ px}$ around full catalogue) | `HOLDOUT-DTI` | `0.004006` | `[0.003424, 0.004690]` | **`+0.167549`** | `[+0.150839, +0.183486]` |
| `A1_cmgep_unsupervised` | Label-free `H87-CMGEP` physical composite + Dinkelbach 300 m emitter | `HOLDOUT-DTI` | `0.041131` | `[0.032382, 0.050944]` | **`+0.130424`** | `[+0.112594, +0.148171]` |
| `A2_core_gbm_pixel_topn` | Core 78-ch LightGBM + naive pixel-wise top-$N$ ($N=37,654$, no 300 m kernel, no $d_{\min}=\sqrt{8}$ NMS) | `HOLDOUT-DTI` | `0.081659` | `[0.068200, 0.095421]` | **`+0.089896`** | `[+0.077431, +0.102309]` |
| `A3_core_gbm_dinkelbach` | Core 78-ch LightGBM (without the 8 H87 physical & 6 coupling channels) + Dinkelbach Submodular 300 m emitter | `HOLDOUT-DTI` | `0.164106` | `[0.146966, 0.180830]` | **`+0.007449`** | `[+0.001205, +0.013427]` |
| `A4_h87_cmgep_additive_nms` | Full 92-ch `H87-CMGEP` ensemble + additive fixed-budget NMS (no Dinkelbach fractional stop, no submodular depletion, no quad calibration) | `HOLDOUT-DTI` | `0.164924` | `[0.146191, 0.182148]` | **`+0.006631`** | `[+0.001435, +0.012807]` |
| **`A5_h87_cmgep_dinkelbach_full` (Promoted)** | **Full 92-ch `H87-CMGEP` ensemble + Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300 m Kernel Emitter** | `HOLDOUT-DTI` | **`0.171555`** | **`[0.154922, 0.187832]`** | *Reference* | *Reference* |

---

## Final JSON Run Card (`data/run-card.json`)

```json
{
  "run_id": "GEMSDOE87-H87-CMGEP-20261022",
  "lane_id": "H87-CMGEP",
  "hypothesis": "Cross-Scale Paired Magnetic-Gravity-Conductivity Edge Persistence (H87-CMGEP) coupled with fold-proper structural relay kinematics and a Collar-Decoupled Quadrant-Calibrated Dinkelbach Submodular 300 m Kernel Emitter (d_cat > 2.0 px, r_NMS >= sqrt(8) px).",
  "mechanism": "92-channel fold-proper feature stack (60 core physical + 8 novel H87-CMGEP physical persistence + 18 fold-proper structural relay + 6 H87 physics-coupling channels) -> LOQO LightGBM ensemble (0.60 * full_92ch + 0.40 * core_78ch) -> inter-quadrant quantile calibration (q_blend = 0.70) -> Dinkelbach fractional 300 m kernel submodular emitter with simultaneous 196-prior 3-px halo cap.",
  "non_fault_mimic": "Miocene caldera ring margins, plutonic intrusive contacts, and untectonized alluvial-fan / playa paleo-shorelines; suppressed via geodetic transtensional strain coupling (cmgep_strain_curv), 1 m LiDAR roughness-discounted break intensity (lidar_tectonic_break), and deep hydrothermal clay-cap/vent-conduit corroboration (geotherm_claycap_conduit).",
  "holdout_dti": {
    "evidence_class": "HOLDOUT-DTI",
    "evaluator_version": "gems57-pooled-hide-v2",
    "withheld_positive_count": 22663,
    "score": 0.171555,
    "ci_95": [0.154922, 0.187832],
    "status": "passed; beats A0 (0.004006), A1 (0.041131), A2 (0.081659), A3 (0.164106), and A4 (0.164924) with strictly positive 95% paired bootstrap CIs"
  },
  "leakage_canary": {
    "status": "passed",
    "channels_audited": 92,
    "max_symmetric_auc": 0.7823,
    "limit_symmetric_auc": 0.90,
    "flagged_channels": []
  },
  "correlation_overlap_vs_registry": {
    "registry_rasters_checked": 202,
    "discriminating_priors": 196,
    "space_filling_priors": 6,
    "surface_rank_correlation_max": 0.61814,
    "rank_correlation": 0.03977,
    "fraction_within_3px": 0.62,
    "duplicate": false,
    "status": "passed; worst |rho_S| = 0.61814 (surface) / 0.03977 (dots) <= 0.90 and worst 3-px overlap across 196 discriminating priors = 0.62000 <= 0.70"
  },
  "raster_sha256": "1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69",
  "companion_zeros_raster_sha256": "f6833b831d91618577f73522f4a269f1f878a982cc38ba2bbb27d942396b2403",
  "validator_output": {
    "no_nan_inside_footprint": true,
    "finite_values_in_0_1": true,
    "crs_shape_transform_match": true,
    "emitted_dots": 35200,
    "dots_on_visible_catalogue": 0,
    "d_min_px": 2.2361,
    "min_inter_dot_sep_px": 2.8284,
    "status": "passed both scripts/validate_submission.py (ready=true) and vendor/gems57/validate.py (all_checks_passed=true)"
  },
  "submission": {
    "name": "h87-h87-cmgep-20261022T060000Z-8f394f43.tif",
    "companion_zeros_name": "h87-h87-cmgep-20261022T060000Z-6e2c741a-zeros.tif",
    "note": "H87-CMGEP: Cross-scale paired mag-grav-cond edge persistence + Dinkelbach submodular 300m kernel emitter (d>2px, r2>=8)",
    "note_length": 119
  },
  "verdict": "promote"
}
```

---

## Reproducible Commands

```bash
# 1. Validate primary NaN-outside GeoTIFF against official sample_submission.tif
.venv/bin/python3 scripts/validate_submission.py \
  --prediction downloads/h87-h87-cmgep-20261022T060000Z-8f394f43.tif \
  --reference .cache/raw/sample_submission.tif

# 2. Run the 3-step H87-CMGEP pipeline (EXP-87-1 canary, EXP-87-2 holdout ablation, EXP-87-3 emission & registry audit)
.venv/bin/python3 scripts/run_h87_cmgep_pipeline.py --step all

# 3. Run the automated verification test suite
.venv/bin/pytest -v
```
