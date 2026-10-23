# GEMSDOE87 — Kirchhoff Dip-Migrated Multi-Modal Impedance (`H87-KDMI`)

> ### STATUS: **PROMOTE — OK TO DOWNLOAD AND SUBMIT (`READY — VALIDATED FILE AVAILABLE`)**
>
> - **Direct Primary GeoTIFF (`140 KB`, all-finite `[0, 1]` portal-safe format matching `H33-2-B2`):** [`downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif`](downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif) (`SHA-256: f791861ac185c5dde434f04c6177b66f8c1dd6b4fc335462b2e0e733ca6ca4ce`)
> - **Single-TIFF ZIP (`107 KB`):** [`downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.zip`](downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.zip) (`SHA-256: ed385eefcdc74d6cd134029e93aec1238d25f0bb06a09695873c5bbb8a4a6b09`)
> - **Companion `NaN`-Outside Twin (`328 KB`, matches `sample_submission.tif` `NaN` mask pixel-for-pixel, identical `37,654` dots):** [`downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-nan.tif`](downloads/gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-nan.tif) (`SHA-256: f9f58ce2f23c293b4cdb3b2aa52976755c2f1e577264375dd70f4f8473ec8e1c`)
> - **Unique Portal Submission Name (`56` chars):** `gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros`
> - **Concise Portal Submission Note (`134 / 140` chars):** `H87-KDMI Exp3: dip-migrated 92ch physics + 2-regime Noisy-OR + 37,654 Dinkelbach dots; Holdout-DTI 0.2388 [0.2277,0.2501]; AI-assisted`
>
> **Start here on GitHub Pages:** [Project overview & 1-click download](index.html) · [Executive summary: how to submit](executive-summary.html) · [Hypotheses & experiments](research.html) · [Verified-source register](sources.html)

---

## Mission and Arena Core Values (Session Starting Brief)

This repository is the persistent project brief and reproducible research package for the **DOE Geothermal Exploration from Machine Learning and Geoscience (GEMS) Prize** ([DrivenData Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)). Every work session starts from this brief and enforces Arena's two foundational principles:

- **Maximize P(Win):** Reserve limited weekly competition feedback submissions exclusively for preregistered, physically grounded candidates that (1) pass feature-by-feature holdout leakage canaries (`AUC <= 0.90`), (2) beat every clean spatial holdout baseline with 95% block-bootstrap confidence intervals, (3) clear pre-placement continuous rank-correlation (`|rho| <= 0.90`) and post-placement 3-pixel dot-overlap (`<= 0.70`) uniqueness gates across the entire organization registry, and (4) pass automated machine GeoTIFF validation (`EPSG:32611`, `3730 x 3292`, single-band `float32`, strict `[0, 1]`, zero `NaN` inside the `5,167,373`-pixel footprint).
- **Own the Outcome:** Report every number strictly as **HOLDOUT-DTI** (with exact evaluator version, withheld positive pixel count, and 95% confidence interval) or **ORGANIZER-CONFIRMED** (copied from an actual submission-page receipt). Never present a projection as a score; surface negative ablations, cross-repo contamination catches, and provenance caveats transparently.

---

## Key Scientific Breakthrough & Cross-Fleet Results (`3` Strictly Budgeted Experiments)

### 1. Why `GEMSDOE32` (`H33-2-B2`) scored `0.2778` (owner-reported) — and where its ceiling lies

Forensic inspection of exact artifact bytes (`57GEMSDOE/registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif`) revealed:
1. **Why it won previously (`37,654`-dot precision law):** Under official DTI (`alpha=0.2, beta=0.8, 300 m` triangular kernel), dense `120k–260k` predictions suffer massive `0.2 * FP` denominator drag. Spacing `37,654` dots (`0.729%` of footprint) outside the `d_cat <= 2.5 px` mapped-catalogue halo preserves `300 m` triangular fault coverage while cutting false positives by **3x–7x**.
2. **Why it hits a hard physical ceiling (`0.0916` on concealed piedmont faults, `~0.068` on whole-segment range-front holdout):** Great Basin normal faults dip $\theta \in [45^\circ, 60^\circ]$ into hanging-wall basins. Empirical profiling across `25,000` Great Basin normal-fault cross-sections (`assets/figures/fig1_kdmi_dip_migration_profile.png`) proved that basement depth steps by **`+191.4 m`** across fault traces, laterally shifting horizontal gravity/magnetic gradient maxima **500–1,500 m down-dip into the hanging wall** — outside the `300 m` DTI scoring kernel! Furthermore, `H33` treats unmapped range-front relay bridges and concealed intra-basin faults with one uncalibrated single-regime model without calibrating across Nevada's `43.4% / 56.6%` `has_lidar` boundary.

### 2. Measured Head-to-Head Results Across All 3 Preregistered Experiments & 12 Fleet Comparators

All metrics below are **HOLDOUT-DTI** measured via unmodified `vendor/gems57/evaluate_holdout.py` (`sha256=ad86640b...`, `alpha=0.2, beta=0.8, 300 m` triangular kernel) and zero-`SGMC` out-of-fold Concealed Piedmont Proxy `Instrument C_pied` (`n=10,302` pixels; full JSON ledger in [`data/h87-experiments-ledger.json`](data/h87-experiments-ledger.json)):

| Arm / Repository | Positive Dots | SGMC in `X`? | Holdout-DTI `A` (`n=22,633`, 95% CI) | Concealed Piedmont `C_pied` (`n=10,302`, 95% CI) | Paired $\Delta C_{\text{pied}}$ vs `H33` (95% CI) | Uniqueness Gate (`127` TIFs) |
|---|---:|---|---|---|---|---|
| **`H87_Exp3_KDMI_DualHead_Dinkelbach` (PROMOTED)** | **37,654** | **No (`0`)** | **`0.238779` `[0.227749, 0.250148]`** | **`0.116531` `[0.100734, 0.132423]`** | **`+0.024924` `[+0.008041, +0.041513]`** | **PASS (`max |rho|=0.4088`, `max dot=0.6764`)** |
| `H87_Exp2_KDMI_TwoRegime` (Ablation) | 37,654 | No (`0`) | `0.239645` `[0.228306, 0.251600]` | `0.118712` `[0.100309, 0.138573]` | `+0.027105` `[+0.009128, +0.044530]` | PASS (`max dot=0.6805`) |
| `H87_Exp1_KDMI_PurePhys` (`0` cat, `0` SGMC) | 37,654 | No (`0`) | `0.110660` `[0.100708, 0.121936]` | `0.071827` `[0.059217, 0.084692]` | `-0.019780` `[-0.033610, -0.005144]` | Disqualified (`0.7400 > 0.70` vs `19GEMSDOE`) |
| `GEMSDOE83` (`GVCD` Two-Regime) | 38,000 | No (`0`) | `0.141200` (repo receipt) | `0.100706` `[0.083247, 0.117873]` | `+0.009099` | Baseline |
| `GEMSDOE70` (`P9` Piedmont Submod) | 37,937 | No (`0`) | `0.109970` (repo receipt) | `0.098654` `[0.080640, 0.116230]` | `+0.007047` | Baseline |
| `GEMSDOE78` (`GSC` Coupled) | 37,654 | No (`0`) | `0.189840` (repo receipt) | `0.091639` `[0.076642, 0.106866]` | `+0.000032` | Baseline |
| **`GEMSDOE32` (`H33-2-B2` Baseline)** | **37,654** | **No (`0`)** | `0.068200` (fold) / `0.004379` (static) | **`0.091607` `[0.076869, 0.106683]`** | `0.000000` (reference) | `0.3763` dot overlap vs `Exp 3` |
| `GEMSDOE70` (`P8` OOF 38k) | 37,937 | No (`0`) | `0.061000` (repo receipt) | `0.082658` `[0.069100, 0.096523]` | `-0.008949` | Baseline |
| `19GEMSDOE` (`H19-5` Ridge 37.6k) | 37,654 | No (`0`) | `0.070023` `[0.062304, 0.078821]` | `0.061739` `[0.050773, 0.073115]` | `-0.029868` | Baseline |
| `GEMSDOE80` (`MACS-61`, **SGMC-in-X**) | 37,654 | **YES (`sub_sgmc_bedrock_prox`)** | `0.117250` (repo receipt) | `0.161871` *(contaminated)* | *Invalid (`SGMC` in `X`)* | Flagged (`IR-87-09`) |

---

## Reproducibility & Automated Verification

```bash
# 1. Run fast unit, GeoTIFF byte-validation, math kernel, and HTML/JSON integrity suite
python -m unittest discover -s tests -v

# 2. Full end-to-end regeneration from raw competition rasters (~30 min total on CPU)
bash scripts/download_competition_data.sh
python scripts/restore_data.py
python scripts/prepare_data.py
python scripts/run_h87_experiments.py
python scripts/build_h87_submission_and_audit.py
```

---

## Single Official JSON Run Card ([`data/run-card.json`](data/run-card.json))

```json
{
  "hypothesis": "H87-KDMI (Kirchhoff Dip-Migrated Multi-Modal Impedance + Dual-Head Two-Regime Bayesian Noisy-OR + Dinkelbach 37,654-Dot Allocation): unmapped Great Basin normal faults are governed by two distinct physical regimes — (1) unmapped relay ramps, step-overs, and tip splays along active mapped range fronts, and (2) concealed intra-basin / alluvial-piedmont faults whose subsurface density, basement-depth, magnetic, and clay-cap impedance steps are laterally offset into the hanging wall along local dip n(x) = -grad(B)/||grad(B)||.",
  "mechanism": "Normal faults dipping theta in [45 deg, 60 deg] displace basement and basin-fill density/susceptibility boundaries down-dip by s = z(x)/tan(theta) into the hanging wall, placing raw geophysical horizontal-gradient peaks 200-1,500 m off the surface trace (outside the 300 m DTI kernel). H87-KDMI back-projects 3D geophysical step operators across three dip ensembles (45 deg, 55 deg, 65 deg), fuses 92 zero-catalogue physical channels with 12 leak-free visible-only fracture-mechanics channels via mass-calibrated Bayesian Noisy-OR calibrated on LiDAR coverage, and allocates exact 37,654 positive pixels under the 300 m triangular DTI kernel.",
  "non_fault_mimic": "Non-tectonic lithologic pluton/volcanic contacts, erosional pediment scarps and incised alluvial fan channels, play-margin shoreline paleoscarps, and non-faulted basin-margin unconformities.",
  "holdout_dti": {
    "evidence_class": "HOLDOUT-DTI",
    "evaluator_version": "gems57-pooled-hide-v2",
    "withheld_positive_count": 22633,
    "score": 0.238779,
    "ci_95": [0.227749, 0.250148],
    "concealed_piedmont_proxy_c_pied": {
      "evidence_class": "HOLDOUT-DTI",
      "withheld_positive_count": 10302,
      "score": 0.116531,
      "ci_95": [0.100734, 0.132423],
      "paired_delta_vs_gemsdoe32_h33": 0.024924,
      "paired_ci95_vs_gemsdoe32_h33": [0.008041, 0.041513]
    }
  },
  "correlation_overlap_vs_registry": {
    "rank_correlation": 0.408804,
    "fraction_within_3px": 0.676396,
    "registry_rasters_audited": 127,
    "discriminating_dot_fields_audited": 123,
    "status": "passed"
  },
  "raster_sha256": "f791861ac185c5dde434f04c6177b66f8c1dd6b4fc335462b2e0e733ca6ca4ce",
  "zip_sha256": "ed385eefcdc74d6cd134029e93aec1238d25f0bb06a09695873c5bbb8a4a6b09",
  "companion_nan_raster_sha256": "f9f58ce2f23c293b4cdb3b2aa52976755c2f1e577264375dd70f4f8473ec8e1c",
  "validator_output": {
    "no_nan_inside_footprint": true,
    "finite_values_in_0_1": true,
    "crs_shape_transform_match": true,
    "positive_dot_count": 37654,
    "status": "passed"
  },
  "submission": {
    "name": "gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros",
    "note": "H87-KDMI Exp3: dip-migrated 92ch physics + 2-regime Noisy-OR + 37,654 Dinkelbach dots; Holdout-DTI 0.2388 [0.2277,0.2501]; AI-assisted"
  },
  "verdict": "promote"
}
```
