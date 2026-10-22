> **Historical concurrent source-check snapshot at `a7a7c77`, not the current implemented experiment.** Current decoded H33-to-parent forensics and actual research TIFF are in [the scientific report](science.html). Owner-reported projections discussed here are separate from any dated official public-leader observation; matching digits do not authenticate an artifact.

# H33-2-B2 claim check — line-by-line verification

**Checked:** 2026-10-22 UTC from this sandbox. **Reachable from the sandbox:** `github.com`, `api.github.com`, `pypi.org`, `registry.npmjs.org` only. **Not reachable:** DrivenData, the GEMSDOE Pages sites (`buffedlizard55-lab.github.io`), USGS, OpenEI, NLR/docs.nlr.gov, EPSG, Dropbox. Everything below is therefore read from GitHub-hosted source files (the repo a Pages site is built from), not from the rendered pages.

**Evidence classes used here**

- **REPO-VERIFIED** — bytes or text read from a named GitHub commit; I re-computed the hash or quoted the line.
- **OWNER-CLAIM** — a number written by the sibling project's owner; not linked to an organizer receipt.
- **PROJECTION** — a model output (surrogate or drift-corrected estimate); never a score.
- **ORGANIZER-CONFIRMED** — none exists in this check.

## 1. The question

The prompt asserts that `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` scored **0.2778** and was the highest GEMSDOE result, and asks why, and whether we can beat 0.2778.

## 2. Line-by-line verification

| # | Claim | What the source says | Evidence class | Link |
|---|---|---|---|---|
| 1 | The file exists under this name | `gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, 219,065 bytes, in `docs/downloads/` of GEMSDOE32 @ `780a5a5` | REPO-VERIFIED | [file](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif) |
| 2 | SHA-256 matches the audit | Downloaded via the GitHub API and hashed: `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`. Audit JSON records the same value. | REPO-VERIFIED | [audit JSON](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-audit.json) |
| 3 | Raster format | 1 band, float32, 3730 × 3292, EPSG:32611, transform (100, 0, 243350, 0, −100, 4508550), nodata = none, all 12,279,160 cells finite, min 0, max 1 | REPO-VERIFIED (read with rasterio 1.4.4) | audit JSON `zeros_tif` block |
| 4 | Content | Binary: 37,654 cells equal 1.0, every other cell 0.0. No NaN. | REPO-VERIFIED | — |
| 5 | Status | Audit `submission_note_zeros` ends "**UNSCORED**"; `holdout_metrics.predicted_leaderboard_dti` = 0.2747 is a model output | REPO-VERIFIED (quoted) | [audit JSON](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-audit.json) |
| 6 | "0.2778" is the H33 score | **The string `0.2778` does not occur anywhere** in the GEMSDOE32 working tree or in the full 50-commit history (`git log -S`). No registry file contains it. | REPO-VERIFIED (negative search) | [registry](https://github.com/buffedlizard55-lab/GEMSDOE32/tree/main/registry) |
| 7 | Gain from the removal rule | Owner's surrogate: live-mirror **+0.004870** in 4/4 folds; safety factor 2.08; "UNSCORED". Projected live value 0.2747. | PROJECTION / OWNER-CLAIM | [README §H33](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/README.md) |
| 8 | The 0.2708 base | Audit: "0.2708 base with every dot at d(catalogue) ≤ 2 px deleted (37,654 dots)". The base therefore has 40,199 dots (37,654 + 2,545 removed, consistent with README "B = 2 removes 2,545 further dots"). | REPO-VERIFIED (arithmetic on quoted counts) | README §H33 |
| 9 | Other GEMSDOE32 values | `0.4413` appears in the owner README as a **refuted** projection: "1.35× the entire public leaderboard's top score. The live record refutes it." | REPO-VERIFIED (quoted) | [README IR-33-LM-01](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/README.md) |
| 10 | Official leaderboard snapshot (owner's read, 2026-10-04) | Top 0.3262 (`nchuzhoy`), 0.3222, **0.3195 (`DARD`, rank 3)**, 0.2708 (`smashi34`). Snapshot marked "verified" by the owner, but read through a browsing path, not by this sandbox. | OWNER-CLAIM (official-page transcription, dated) | [snapshot](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/registry/leaderboard_snapshot_2026-10-04.json) · [live page](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) |
| 11 | Live leaderboard today | Could not be read from this sandbox. The prompt's "0.4413" and "0.3195 is the highest score" conflict with each other and with the 2026-10-04 snapshot (top 0.3262). | UNVERIFIED — conflicting | live page (user must check) |

## 3. Answer: why did H33-2-B2 get a high value, and how?

**Short answer.** The repository does not show that H33-2-B2 got a high official score. Its own audit labels it UNSCORED and gives only a model projection (0.2747). The number 0.2778 is not in the source. What the repo does show is a plausible *mechanism* and a *small* projected gain.

**Mechanism (owner's design).** Start from a 0.2708 emission (40,199 dots). Delete every dot within 2 px of the public fault catalogue (2,545 dots, 6.3 % of mass). The owner's surrogate estimates those deleted dots carry 1.5 % of off-catalogue weighted credit against a budget of 125.1 — a safety factor of 2.08 — and the change wins in all four quadrants of the owner's holdout.

**PhD-level judgement.**

1. *The metric favours deletion only if deleted mass earns little credit.* The distance-weighted Tversky score uses α = 0.2 and β = 0.8, so false negatives cost four times as much as false positives. Deleting predicted mass therefore lowers the score unless the deleted dots lie where hidden-set credit is near zero. The owner's whole case rests on that single assumption: dots hugging *already-mapped* faults earn little credit on the *new* (hidden) faults.
2. *That assumption is plausible but unmeasured.* Hidden-set faults may extend or branch from mapped faults, which would make catalogue-flank dots valuable. The owner's own holdout (`catalogue_hidden_mean` = 0.0046) and drift-corrected value (0.0450) are both small relative to the claimed gain (+0.0049), so the signal is within the noise the owner reports (IR-33-LM-01).
3. *Named non-fault mimic.* A catalogue-flank effect can arise from the feature stack itself if any feature was derived from the catalogue (leakage). Removing dots near the catalogue would then reward the leak, not a better fault model. This must be ruled out with the leakage canary before any gain is credited.
4. *Magnitude vs. uncertainty.* A +0.005 projected change is small, and the owner's README (IR-33-LM-01) states the live mirror is only licensed for small, mechanism-matched perturbations of a live-scored base — which the H33-2-B2 file is not, since its base has no organizer receipt either. A single unpaired projection cannot resolve it.

## 4. Can we beat 0.2778?

**Not demonstrated, and not demonstrable from this sandbox.** There are no competition rasters, no holdout evaluator, and no validated candidate here. The only defensible path is the one in `README.md`: build a matched baseline/candidate pair on the authorized data, test the removal rule with a leakage canary and paired holdout CI, and check the novelty gate. A value of 0.2778 is not a target that can be computed from anything in this checkout.

## 5. Reusable facts for the next session

- The H33 TIF grid (EPSG:32611, 100 m, 3730 × 3292, origin 243350 / 4508550) is **the owner's claim** of the competition grid. It must be checked against the official `sample_submission.tif`, which is not reachable here.
- GEMSDOE32's `registry/` and `docs/downloads/` are on GitHub and downloadable through the API. They can serve as a **registry for the novelty gate** (rank-correlation and 3-px overlap), which resolves part of the "registry rasters absent" blocker. They must not be submitted as our own output.
- The official reference notebook writes float64 (see [IR-87-17](irregularities.md)); any output must be re-cast and re-validated as float32.

## 6. Run card (this check)

```json
{
  "hypothesis": "H33-2-B2 removal rule (delete base dots within 2 px of catalogue) raises DTI",
  "evidence_class": "REPO-VERIFIED for artifact bytes and status; PROJECTION for the value",
  "holdout_dti": {"evidence_class": "OWNER-CLAIM/PROJECTION", "evaluator_version": null, "withheld_positive_count": null, "score": null, "ci_95": null, "note": "owner projection 0.2747 and +0.00487 are not HOLDOUT-DTI measured here"},
  "organizer_confirmed_score": null,
  "reported_0_2778": "not found in any GEMSDOE32 file or commit",
  "sha256_h33_zeros_tif": "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
  "grid": {"crs": "EPSG:32611", "shape": [3730, 3292], "transform": [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0], "match_to_official_sample": "not checked: sample unreachable"},
  "mechanism": "catalogue-flank deletion of low-credit mass",
  "non_fault_mimic": "catalogue-derived feature leakage",
  "verdict": "negative for the 0.2778 claim; unresolved for the removal rule"
}
```

## Sources

- GEMSDOE32 repository, commit `780a5a534269c79adfe6d1d7d5aadead161332aa`: [repo](https://github.com/buffedlizard55-lab/GEMSDOE32) · [H33 audit JSON](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-audit.json) · [submissions manifest](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/submissions_manifest.json) · [claims ledger](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/registry/claims.json) · [leaderboard snapshot 2026-10-04](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/registry/leaderboard_snapshot_2026-10-04.json)
- Official reference solution, commit `aebe92f7c8a990f0e3443451b7a825d9afd6336b`: [notebook](https://github.com/drivendataorg/gems-prize-reference-solution/blob/main/unet-mc-cv-reference-solution.ipynb)
- Official competition pages (not reachable from this sandbox; links for manual review): [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [data](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) · [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
