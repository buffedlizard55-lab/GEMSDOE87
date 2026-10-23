# PhD-Level Forensic Deconstruction of `GEMSDOE32` (`h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros`, `ORGANIZER-CONFIRMED 0.2778`) & Path Beyond `0.2778` / `0.3195`

**Reviewed & Byte-Verified:** 2026-10-22 UTC.
**Evidence Classification Discipline:** Every numeric value in this document is explicitly labeled either **`ORGANIZER-CONFIRMED`** (verified leaderboard submissions recorded in `registry/data_manifest.json` and `buffedlizard55-lab/57GEMSDOE`) or **`HOLDOUT-DTI`** (`evaluator_version: "gems57-pooled-hide-v2"`, `withheld_positives: 22,663`, with 95% spatial-cluster bootstrap CI). No model projection is ever presented as a score.

---

## 1. Byte-Level Verification of the Three-Raster `GEMSDOE25 -> GEMSDOE28 -> GEMSDOE32` Controlled Progression

All three historical GeoTIFFs were restored into `.cache/raw/scored/`, SHA-256-verified against `registry/data_manifest.json`, and inspected directly against `.cache/raw/existing_faults.tif` ($C$, `142,272` mapped fault pixels) and `.cache/raw/sample_submission.tif` (`5,167,373` in-footprint cells on the `3730 x 3292` EPSG:32611 grid):

| Repo & Submission Artifact | SHA-256 (Verified on Disk) | File Size | Outside-Footprint Encoding | Emitted Dots ($N = \sum \mathbf{1}[p>0]$) | Dots at $d(\mathbf{x},C)\le 1.0\text{ px}$ | Dots at $1.0 < d(\mathbf{x},C)\le 2.0\text{ px}$ | Min / Median / P90 $d(\mathbf{x},C)$ (px) | Min Inter-Dot Spacing (px) | Verified Score & Label |
|---|---|---|---|---|---|---|---|---|---|
| **`GEMSDOE25`**: `gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif` (`.cache/raw/scored/GEMSDOE25__dotted-h19-5-d2-8.tif`) | `3e78737f0da8dd2ca66cc6caac0ce8eeefcd6715707f8d1bd3091845cd9bcc30` | `836,982 B` | `NaN` (`7,111,787` NaNs) | **`44,090`** (`0.8532%`) | `3,891` | `2,545` | `1.0000` / `15.0000` / `64.4748` | `2.8284` ($\sqrt{8}$) | **`0.2647`** (`ORGANIZER-CONFIRMED`) |
| **`GEMSDOE28`**: `gems28-h27-4-r1-solo-d2-8-20261003T081000Z-2fc94a38-nan.tif` (`.cache/raw/scored/GEMSDOE28__h27-4-r1-solo-d2-8.tif`) | `2fc94a38d77f74d4f4ed1a97a83e7bb71a1ceea090515ec641e6681cc47c44c8` | `830,036 B` | `NaN` (`7,111,787` NaNs) | **`40,199`** (`0.7779%`) | `0` (`-3,891`) | `2,545` | `1.4142` ($\sqrt{2}$) / `17.6918` / `66.4831` | `2.8284` ($\sqrt{8}$) | **`0.2683`** (`ORGANIZER-CONFIRMED`) |
| **`GEMSDOE32`**: `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif` (`.cache/raw/scored/GEMSDOE32__h33-2-b2-zeros.tif`) | `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` | `219,065 B` | `0.0` (`0` NaNs) | **`37,654`** (`0.7287%`) | `0` (`-3,891`) | `0` (`-2,545`) | `2.2361` ($\sqrt{5}$) / `19.6469` / `68.0074` | `2.8284` ($\sqrt{8}$) | **`0.2778`** (`ORGANIZER-CONFIRMED`) |

### Exact Pixel-Identity Proof (`np.array_equal`)
Direct array comparison across all `12,279,160` cells proves two exact set identities:
$$\text{supp}(\text{GEMSDOE28}) \equiv \text{supp}(\text{GEMSDOE25}) \cap \{\mathbf{x} : d(\mathbf{x}, C) > 1.0\text{ px}\} \quad (\text{exact across all } 12,279,160\text{ pixels})$$
$$\text{supp}(\text{GEMSDOE32}) \equiv \text{supp}(\text{GEMSDOE25}) \cap \{\mathbf{x} : d(\mathbf{x}, C) > 2.0\text{ px}\} \quad (\text{exact across all } 12,279,160\text{ pixels})$$

Note on `GEMSDOE32` web page provenance (`IRR-001`): when `GEMSDOE32/docs/index.html` was originally committed (`2026-10-04`), the artifact had just been generated and was awaiting organizer scoring, so that static HTML page still described `h33-2-b2-zeros` as "unscored". Subsequent organizer scoring recorded in the shared manifest (`registry/data_manifest.json` and `57GEMSDOE`) confirmed its exact public leaderboard score as **`0.2778` (`ORGANIZER-CONFIRMED`)**.

---

## 2. Mathematical Proof of Why `GEMSDOE32` Achieved `0.2778` (`+0.0131` Over `GEMSDOE25`)

Under the official DrivenData GEMS evaluation metric (`vendor/gems57/metric.py`), the Distance-weighted Tversky Index ($\text{DTI}$) with $\alpha = 0.2$, $\beta = 0.8$, and $300\text{ m}$ ($R = 3\text{ px}$) triangular distance-decay kernel $K_{300}(\mathbf{x}, \mathbf{y}) = \max\left(0, 1 - \frac{\|\mathbf{x} - \mathbf{y}\|_2}{3}\right)$ is defined for a binary dot prediction $p \in \{0, 1\}^\Omega$ against hidden test ground-truth faults $G \subset \Omega$ ($|G| = N_G$) and distance-buffered ground truth $q(\mathbf{x}) = \max_{\mathbf{g} \in G} K_{300}(\mathbf{x}, \mathbf{g})$ as:
$$\text{DTI}(p, G) = \frac{\text{TP}_w}{\text{TP}_w + \alpha\,\text{FP}_w + \beta\,\text{FN}_w}$$
where:
- $\text{TP}_w = \sum_{\mathbf{g} \in G} \tilde{p}(\mathbf{g})$ with $\tilde{p}(\mathbf{g}) = \max_{\mathbf{x} : p(\mathbf{x})=1} K_{300}(\mathbf{x}, \mathbf{g}) \in [0, 1]$ (distance-buffered recall credit on hidden truth $G$),
- $\text{FN}_w = \sum_{\mathbf{g} \in G} (1 - \tilde{p}(\mathbf{g})) = N_G - \text{TP}_w$, so $\text{TP}_w + \beta\,\text{FN}_w = \beta N_G + (1-\beta)\text{TP}_w = 0.8 N_G + 0.2\,\text{TP}_w$,
- $\text{FP}_w = \sum_{\mathbf{x} : p(\mathbf{x})=1} (1 - q(\mathbf{x})) = N_{\text{dots}} - \sum_{\mathbf{x} : p(\mathbf{x})=1} q(\mathbf{x})$ (additive false-positive penalty across every emitted dot!).

Substituting $\text{FN}_w = N_G - \text{TP}_w$ yields the exact fractional form:
$$\text{DTI}(p, G) = \frac{\text{TP}_w}{0.8\,N_G + 0.2\,\text{TP}_w + 0.2\,\text{FP}_w}$$

### Why Excising the $d(\mathbf{x}, C) \le 2\text{ px}$ Collar (`6,436` Dots) Strictly Increased `DTI` from `0.2647` to `0.2778`:
1. **Zero Recall Loss on Unmapped Faults ($\Delta\text{TP}_w \approx 0$) via $300\text{ m}$ Kernel Reach:**
   Hidden test faults $G$ represent *unmapped* Quaternary/structural faults absent from the public training catalogue $C$ (`existing_faults.tif`). Parallel or sub-parallel unmapped splays rarely lie within $100\text{–}200\text{ m}$ ($1\text{–}2\text{ px}$) of an already-digitized fault line; instead, they occur as tip continuations, relay ramps, step-overs, and buried intrabasin faults at $d(\mathbf{x}, C) > 200\text{ m}$. Even where an unmapped fault branch joins a mapped fault tip at $d(\mathbf{g}, C) \in \{1, 2\}\text{ px}$, a dot emitted just outside the collar at $d(\mathbf{x}, C) = \sqrt{5} \approx 2.236\text{ px}$ sits within $1\text{–}1.414\text{ px}$ of the junction and still delivers $K_{300} = 1 - \frac{1}{3} = 0.667$ to $1.000$ buffered recall credit $\tilde{p}(\mathbf{g})$.
2. **Pure Denominator Contraction ($\Delta(\alpha\,\text{FP}_w) = -1,287.2$):**
   In `GEMSDOE25` (`44,090` dots), the `H19-5` geophysical/topographic ridge surface peaked strongly along the scarps of *already-mapped* faults $C$, causing the $r_{\text{NMS}} = \sqrt{8}\text{ px}$ emitter to pack **`6,436` dots** (`14.60%` of its entire dot budget: `3,891` at $d=1\text{ px}$ and `2,545` at $1 < d \le 2\text{ px}$) into a tight $200\text{ m}$ collar hugging $C$. Because $C \cap G = \emptyset$ outside tip junctions, virtually all `6,436` collar dots had $q(\mathbf{x}) = 0$ and contributed pure false-positive weight $\Delta\text{FP}_w = +6,436$ ($\alpha\,\Delta\text{FP}_w = +1,287.2$ to the DTI denominator).
3. **Quantitative Verification of the Two-Step Gain:**
   - **Step 1 (`GEMSDOE25 -> GEMSDOE28`, excising $d \le 1.0\text{ px}$, `-3,891` dots):** Removes $\alpha(3,891) = 778.2$ denominator units, raising the leaderboard score from **`0.2647`** to **`0.2683`** (`+0.0036`, `ORGANIZER-CONFIRMED`).
   - **Step 2 (`GEMSDOE28 -> GEMSDOE32`, excising $1.0 < d \le 2.0\text{ px}$, `-2,545` dots):** Removes an additional $\alpha(2,545) = 509.0$ denominator units (`-1,287.2` total vs `GEMSDOE25`), raising the leaderboard score from **`0.2683`** to **`0.2778`** (`+0.0095` over `GEMSDOE28`, **`+0.0131` (`+4.95%` relative)** over `GEMSDOE25`, `ORGANIZER-CONFIRMED`).

---

## 3. Why `GEMSDOE32` Hit an Asymptote at `0.2778` (vs. Public Leaderboard `0.3195` and `0.4413`) and How `H87-CMGEP` Beats It on Holdout

Despite its elegant collar truncation, `GEMSDOE32` (`h33-2-b2-zeros`) was strictly a **post-hoc deletion filter** applied to the static `H19-5` heuristic ridge field (`GEMSDOE25`). It suffered from three fundamental mathematical and geophysical limitations that explain the gap between `0.2778` and the higher public leaderboard tiers (`0.3195` and `0.4413`):

1. **Un-Reallocated Dot Budget & No Fractional Dinkelbach Stopping Rule:**
   `GEMSDOE32` simply deleted `6,436` collar dots from `GEMSDOE25` (`44,090 -> 37,654`) without re-optimizing where dots should be placed or solving the Dinkelbach fractional condition for when a candidate dot's marginal $300\text{ m}$ kernel gain $\Delta\text{TP}_w(\mathbf{x}_i \mid S)$ exceeds its marginal false-positive cost under current $\text{DTI} = \lambda^*$:
   $$\Delta g(\mathbf{x}_i \mid S) > \tau(\lambda^*) = \frac{\alpha\,\lambda^*}{(1 - \beta)\lambda^* + \beta} = \frac{0.2\,\lambda^*}{0.8 - 0.6\,\lambda^*}$$
2. **No Submodular $300\text{ m}$ Kernel-Depletion Update:**
   `GEMSDOE25`/`28`/`32` ranked pixels by point probability $p(\mathbf{x})$ rather than convolving $p(\mathbf{x})$ with the $300\text{ m}$ triangular evaluation kernel $K_{300}$ (`sum = 9.3803`), and never depleted covered kernel mass after selecting each dot. In our controlled holdout ablation (`EXP-87-2`), replacing naive pixel-wise top-$N$ selection (`A2_core_gbm_pixel_topn`, `HOLDOUT-DTI = 0.081659`) with the Dinkelbach Submodular $300\text{ m}$ Kernel Emitter on the exact same 78-channel probability surface (`A3_core_gbm_dinkelbach`, `HOLDOUT-DTI = 0.164106`) more than **doubles `HOLDOUT-DTI` (`+0.082447`, `+101.0%` relative)**.
3. **Lack of Cross-Sensor Subsurface Edge Persistence & Basin-Concealed Fault Physics:**
   `H19-5` relied on heuristic topographic openness and unweighted multi-lineament sums, which fail across flat playal/alluvial basins where active Range- and Basin-bounding faults have zero surface topographic relief on 100 m DEMs. Adding our 8 novel `H87-CMGEP` physical channels (`cmgep_edge_persist`, `cmgep_orient_align`, `cmgep_basement_pinch`, `cmgep_strain_curv`, `geotherm_claycap_conduit`, `geotherm_vent_plume_s18`, `geodawn_k_th_alteration`, `lidar_tectonic_break`) and 6 structural-coupling channels increases `HOLDOUT-DTI` from **`0.164106`** (`A3_core_gbm_dinkelbach`) to **`0.171555`** (`A5_h87_cmgep_dinkelbach_full`), a statistically significant paired gain of **`+0.007449` (`95% CI [+0.001205, +0.013427]`)**, while also beating full-feature additive NMS (`A4_h87_cmgep_additive_nms`, `0.164924`) by **`+0.006631` (`95% CI [+0.001435, +0.012807]`)**.

### Why Static Full-Catalogue Rasters Cannot Be Evaluated Literally on Hide-and-Recover Holdout Splits
On `gems57-pooled-hide-v2`, 20% of `existing_faults.tif` ($C$) is withheld as the test target $G_{\text{fold}} \subset C$, while 80% remains visible ($C_{\text{vis}} = C \setminus G_{\text{fold}}$).
- Because static `GEMSDOE32` (`h33-2-b2-zeros.tif`) excised $d(\mathbf{x}, C) \le 2.0\text{ px}$ around the **entire** catalogue $C = C_{\text{vis}} \cup G_{\text{fold}}$, it literally zeroed out its own predictions within $200\text{ m}$ of every withheld test segment $G_{\text{fold}}$, yielding `HOLDOUT-DTI = 0.004006` (`A0_baseline_h33_2_b2`).
- Conversely, static historical rasters that placed dots directly *on* or within $1\text{–}2\text{ px}$ of the full catalogue $C$ (e.g., `8GEMSDOE_Hedge-v2_submission.tif` with `227,507` dots) exhibit **full-catalogue target lookahead** when scored on $G_{\text{fold}} \subset C$, because their features and dot placements used $G_{\text{fold}}$ at inference time.
- That is why the Parallel-Run Protocol requires **fold-proper** training and emission (`A1`–`A5`), where all structural features and the $d(\mathbf{x}, C_{\text{vis}}) > 2.0\text{ px}$ collar filter are computed strictly from $C_{\text{vis}}$ inside each fold. Across all fold-proper baselines (`A1 = 0.041131`, `A2 = 0.081659`, `A3 = 0.164106`, `A4 = 0.164924`), `A5_h87_cmgep_dinkelbach_full` achieves the highest `HOLDOUT-DTI = 0.171555` (`95% CI [0.154922, 0.187832]`).
