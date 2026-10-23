# GEMSDOE87 — Auditable GEMS Prize Research & Validated `G87-CSCT` Submission (`PROMOTED`)

> **Submission status: `READY — VALIDATED & UNIQUE GEOTIFF AVAILABLE FOR ONE-CLICK DOWNLOAD`**
>
> - **Primary Competition File (All-Finite Portal-Safe GeoTIFF):** [`downloads/gems87-csct-dink300-37654dots-20261022-zeros.tif`](downloads/gems87-csct-dink300-37654dots-20261022-zeros.tif) (`144,378` bytes · `SHA-256: 30ffb71d5fe6bda04735d6a5b1ef5280f3f578ac070e83d385622ea19086003f`)
> - **Single-TIFF Competition Archive (`.zip`):** [`downloads/gems87-csct-dink300-37654dots-20261022-zeros.zip`](downloads/gems87-csct-dink300-37654dots-20261022-zeros.zip)
> - **Companion Reference-Mask GeoTIFF (`NaN` outside footprint matching `sample_submission.tif`):** [`downloads/gems87-csct-dink300-37654dots-20261022-nan.tif`](downloads/gems87-csct-dink300-37654dots-20261022-nan.tif) (`334,324` bytes · `SHA-256: b99088c16873425741f6a75e7173a8aa7b764a02e4d032263be3447ea66c9285`)
> - **Unique Submission Name:** `gems87-csct-dink300-37654dots-20261022-zeros`
> - **Portal Note (`128 / 140` chars):** `G87 CSCT: cover-stratified divisive Radon multiphysics + crack-tip/relay + 300m Dinkelbach cover (37654 binary dots, all finite)`
> - **Measured Holdout Score (`HOLDOUT-DTI`):** **`0.210717`** (`95% CI [0.193821, 0.227662]`, `evaluator_version = "gems57-pooled-hide-v2"`, `n = 22,663` withheld positives across `seeds=(20, 30)`) — outperforming `CTRL_RAND` (`0.045973`), `CTRL_CG` (`0.073768`), `CTRL_TOPO` (`0.092841`), historical `D2.8` (`0.093234`), `E1` pure blind multi-physics (`0.112262`), `E2` CSCT Poisson (`0.197499`), and upstream sibling comparator `GEMSDOE83` `H83-GVCD` (`0.206817`).
> - **Registry Uniqueness (`REGISTRY-MEASUREMENT` across `476` unique SHA-256 rasters / `858` files in 93 repos):** Pre-placement surface `|Spearman| = 0.505421 <= 0.90`; Post-placement dots `|Spearman| = 0.075331 <= 0.90`; **`0 / 464` non-space-filling 3-px dot overlap violations (`max = 0.649997 <= 0.70`)**; pixel Jaccard `max = 0.037297` (`96.27%` distinct pixel coordinates).
> - **Live Portal Score:** **`UNSCORED`** (`organizer_confirmed_score = null`; zero projections claimed as scores; `weekly_slots_used = 0`).
>
> **Start here (GitHub Pages Site):** [Project Overview & One-Click Download](index.html) · [Executive Summary: How to Submit](executive-summary.html) · [PhD Research, Forensics & Ablations](research.html) · [Verified-Source Register](sources.html)

---

## Persistent Project Brief: Mission & Operating Principles

## Mission and Arena Core Values (Session Starting Brief)

Keep Arena's core values central in every session:

- **Maximize P(Win):** reserve the competition's limited feedback submissions (`3 / week` on DrivenData) for candidates that beat the spatial holdout best and pass all leakage, novelty, and file-format gates.
- **Own the Outcome:** report negative results, defects, data provenance, uncertainty, and blockers honestly; never claim a projection or an owner-reported result as an organizer-confirmed score.

This `README.md` is the persistent project brief and must be reviewed at the start of every session. All preflight validation is 100% machine-automated in code (`vendor/gems57/submission_writer.py`, `vendor/gems57/validate.py`, `scripts/validate_submission.py`, and `tests/`). Entrants use their own authorized DrivenData account to upload and select final competition submissions; this repository never collects or stores credentials. Under the DOE/NLR GEMS Prize rules, generative-AI assistance must be disclosed in the competition submission narrative.

## Non-Negotiable Parallel-Run Protocol

1. **Single method lane.** Work inside a single preregistered method lane (`G87-CSCT`, locked in [`docs/experiment-plan.md`](docs/experiment-plan.md)).
2. **Reuse the shared template.** All `13 / 13` shared modules in `vendor/gems57/` (`grid.py`, `holdout.py`, `evaluate_holdout.py`, `metric.py`, `submission_writer.py`, `uniqueness.py`, `validate.py`, `gates.py`) are restored verbatim and verified bit-for-bit against [`registry/template_pin.json`](registry/template_pin.json) with zero private forks.
3. **Leakage canary.** Every single feature (`55 / 55`: `44` static physical tomograms + `11` strictly fold-visible fracture-mechanics features) was tested individually against spatially withheld segments on both `seed=20` (`max symmetric AUC = 0.783631`) and `seed=30` (`max symmetric AUC = 0.781309`), well below `0.90` ([`evidence/e0_leakage_canary.json`](evidence/e0_leakage_canary.json)).
4. **Evidence discipline.** Every measured score is explicitly labeled **`HOLDOUT-DTI`** (`evaluator_version = "gems57-pooled-hide-v2"`, withheld positive count, 20 km block-bootstrap 95% CI) or **`UNSCORED`** / **`USER-REPORTED LEDGER`** ([`docs/score-claim-audit.md`](docs/score-claim-audit.md)). Projections are never reported as scores.
5. **Novelty gate (pre-placement surface & post-placement dots).** Checked across all `476` unique SHA-256 rasters (`858` `.tif` files across `93` `buffedlizard55-lab` repositories): pre-placement continuous surface `|Spearman| <= 0.505421` (`limit 0.90`), post-placement dot `|Spearman| <= 0.075331` (`limit 0.90`), and **`0 / 464` non-space-filling 3-px forward dot overlap violations (`max = 0.649997 <= 0.70`)**, alongside explicit Pigeonhole space-covering certificates for `12` synthetic whole-domain lattices/surfaces ([`evidence/uniqueness_audit_full.json`](evidence/uniqueness_audit_full.json), [`docs/irregularities.md`](docs/irregularities.md)).
6. **Budget discipline.** Stopped after exactly `3 / 3` preregistered experiments (`E1`, `E2`, `E3`).
7. **Automated GeoTIFF preflight.** Both `-zeros.tif` (`nodata=None`, zero `NaN` across all `12,279,160` cells — eliminating the `"Predicted values must be in range [0, 1]"` error) and `-nan.tif` (`NaN` outside footprint matching `sample_submission.tif`) are reopened from disk and verified by both `vendor/gems57/validate.py` (`14 / 14` checks pass) and `scripts/validate_submission.py` (`ready = true, errors = []`).

---

## Summary of Scientific Findings & 3-Experiment Results

### 1. Why `GEMSDOE32` (`H33-2-B2`, User-Reported `0.2778`) Succeeded — and Why `62.2%` of Truth Remains Open
Bit-exact pixel analysis across all `39` owner-ledger scored submissions revealed:
- `D2.8` (`44,090` binary dots, `0.2600` reported) $\supset$ `H27-4` (`D2.8 ∩ {d_cat > 1.0 px}`, `40,199` dots, `0.2708` reported) $\supset$ `H33-2-B2` (`D2.8 ∩ {d_cat > 2.0 px}`, `37,654` dots, `0.2778` reported).
- Algebraic inversion of $\text{DTI}(S, G) = \text{TP}_w / (0.2\,\text{TP}_w + 0.2\,\text{FP}_w + 0.8\,|G|)$ across pure collar-deletion steps yields $\text{TP}_w(D_{2.8}, G) \approx 5{,}074.7\text{ px}$ and total hidden truth $|G| \approx 13{,}420\text{ px}$ across Nevada, predicting `0.2784` vs `0.2778` (`0.0006` residual).
- `H33-2-B2` recovers only `~37.8%` of hidden faults because pure topographic scarp picking misses buried basin/piedmont normal faults beneath Quaternary lacustrine/alluvial fill and sub-resolution en-echelon relay ramps.

### 2. Executed 3-Experiment Suite (`evaluator_version = "gems57-pooled-hide-v2"`, `n = 22,663` Withheld Positives)

| Arm / Experiment | Evidence Class | Seed 20 (`11,321 px`) | Seed 30 (`11,342 px`) | Dual-Seed Pooled (`22,663 px`) | 95% Block-Bootstrap CI | Paired Step Gain (95% CI) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `CTRL_RAND` (Uniform Random `37,654` dots) | `HOLDOUT-DTI` | `0.044682` | `0.047263` | `0.045973` | `[0.041877, 0.050132]` | — |
| `CTRL_CG` (Gallardo–Meju Cross-Gradient) | `HOLDOUT-DTI` | `0.070153` | `0.077378` | `0.073768` | `[0.064456, 0.083374]` | — |
| `CTRL_TOPO` (Multi-Scale Topographic Slope) | `HOLDOUT-DTI` | `0.090514` | `0.095165` | `0.092841` | `[0.080703, 0.104999]` | — |
| `HIST_D28` (Historical `D2.8`, `0.2600` reported live) | `HOLDOUT-DTI` | `0.091888` | `0.094578` | `0.093234` | `[0.082176, 0.104853]` | — |
| **`E1` (`G87-BLIND-POISSON`, 0 catalogue features)** | `HOLDOUT-DTI` | `0.109134` | `0.115387` | **`0.112262`** | `[0.098085, 0.126466]` | **`+0.019421` vs `CTRL_TOPO`** (`[+0.009695, +0.029137]`) |
| **`E2` (`G87-CSCT-POISSON`, Full 56-feat LOQO + 2.8 px Poisson)** | `HOLDOUT-DTI` | `0.177559` | `0.217343` | **`0.197499`** | `[0.180300, 0.214381]` | **`+0.085236` vs `E1`** (`[+0.066313, +0.103561]`) |
| **`E3` (`G87-CSCT-DINKELBACH`, Exact 300 m Cover) [PROMOTED]** | `HOLDOUT-DTI` | **`0.202105`** | **`0.219306`** | **`0.210717`** | **`[0.193821, 0.227662]`** | **`+0.013219` vs `E2`** (`[+0.008076, +0.018958]`) |

---

## Reproducible Verification Commands

```bash
# 1. Install lightweight validation dependencies
python3 -m pip install -r requirements-validation.txt

# 2. Machine-validate both generated GeoTIFF artifacts against official reference raster
python3 scripts/validate_submission.py \
  --prediction downloads/gems87-csct-dink300-37654dots-20261022-zeros.tif \
  --reference data/sample_submission.tif \
  --allow-zero-exterior

python3 scripts/validate_submission.py \
  --prediction downloads/gems87-csct-dink300-37654dots-20261022-nan.tif \
  --reference data/sample_submission.tif

# 3. Run full automated unit & deliverable verification suite
python3 -m unittest discover -s tests -v

# 4. Re-execute full end-to-end 7-step experiment & uniqueness pipeline (after restoring data via scripts/restore_data.py)
python3 -u scripts/run_experiments.py
```

---

## Complete JSON Run Card ([`data/run-card.json`](data/run-card.json))

```json
{
  "lane": "G87-CSCT (Cover-Stratified Curvilinear Fault-Zone Tomography & Crack-Tip Dinkelbach Cover)",
  "experiments_run": 3,
  "hypothesis": "Cross-scale paired magnetic-gravity & LiDAR-DEM edge persistence stratified across basin-cover depth regimes, fused with strictly fold-visible crack-tip & relay-ramp fracture mechanics via LOQO LightGBM + HGB and emitted via exact CELF Dinkelbach 300 m Tversky submodular cover (d > 3.0 px, 37,654 binary dots).",
  "mechanism": "Divisive relief-normalized scarp + multi-depth gravity/magnetic/Th-K/MT/GDR upflow tomography detects blind basin/piedmont faults while fold-proper crack-tip & relay beams capture unmapped terminations; exact linear expectation of max_{u in S} K(|y - u|) eliminates 300 m kernel double-counting.",
  "named_non_fault_mimic": "Pleistocene Lake Lahontan (~1,330 m) & Lake Bonneville (~1,460-1,552 m) wave-cut paleoshoreline benches, alluvial fan-lobe risers, felsic-tuff Th/K lithologic contacts, and LiDAR tile seams.",
  "holdout_dti": {
    "evidence_class": "HOLDOUT-DTI",
    "evaluator_version": "gems57-pooled-hide-v2",
    "withheld_positive_count": 22663,
    "score": 0.210717,
    "ci_95": [0.193821, 0.227662]
  },
  "registry_uniqueness": {
    "evidence_class": "REGISTRY-MEASUREMENT",
    "unique_sha256_rasters_checked": 476,
    "pre_placement_surface_spearman_max": 0.505421,
    "post_placement_dots_spearman_max": 0.075331,
    "discriminating_rasters_checked": 464,
    "discriminating_overlap_firings": 0,
    "max_forward_3px_overlap_discriminating": 0.649997
  },
  "raster_sha256": "30ffb71d5fe6bda04735d6a5b1ef5280f3f578ac070e83d385622ea19086003f",
  "validator_output": {
    "vendor_14_checks_all_passed": true,
    "independent_validator_ready": true,
    "all_finite_0_1": true,
    "nan_anywhere_primary_zeros": 0,
    "positive_binary_dots": 37654,
    "dots_on_existing_faults": 0
  },
  "submission_name": "gems87-csct-dink300-37654dots-20261022-zeros",
  "submission_note": "G87 CSCT: cover-stratified divisive Radon multiphysics + crack-tip/relay + 300m Dinkelbach cover (37654 binary dots, all finite)",
  "verdict": "promote"
}
```

---

## Remaining Limitations & Recommended Next Steps

1. **Portal Upload & Live Receipt (`UNSCORED`):** `gems87-csct-dink300-37654dots-20261022-zeros.tif` has not yet been submitted to DrivenData (`weekly_slots_used = 0`). After uploading through an authorized account, record the exact organizer-returned score and screenshot/receipt before making any `ORGANIZER-CONFIRMED` claim.
2. **Holdout Composition vs Live Hidden Set $G$:** `gems57-pooled-hide-v2` withholds buffered whole segments of the public Quaternary fault catalogue (`22,663` positive pixels). If the organizer's private test truth $G$ contains a substantially higher fraction of deeply buried (`> 1 km` cover) pre-Quaternary geothermal reservoir faults than surface-mapped Quaternary strands, live DTI can differ from `HOLDOUT-DTI`.
3. **Next Separate Lane (`H87-2`, Deferred per Single-Lane Budget Rule):** Implement analytical $60^\circ$ updip footwall surface projection of multi-altitude gravity/magnetic Euler deconvolution contacts (`x_surf = x_grav - (z_0 / tan 60°) n_hat`) to align deep basement density steps directly onto the 300 m surface evaluation kernel for pure detached basin faults (`d_cat > 3 km`).
