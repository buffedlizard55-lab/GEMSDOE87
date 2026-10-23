# Official Source & Data Verification Audit (`GEMSDOE87`)

Every dataset, competition specification, reference repository, and sibling code pin used in `GEMSDOE87` is verified line by line below with exact URLs and cryptographic SHA-256 checksums.

## 1. Competition & Public Reference Sources (`data/sources.json`)
1. **DrivenData — DOE GEMS Prize Problem Description:** `https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/` — Defines the Distance-Weighted Tversky Index ($\alpha = 0.2$, $\beta = 0.8$, $300\text{ m}$ triangular kernel) over Great Basin hidden Quaternary/geothermal faults.
2. **DrivenData — Competition Data Tab:** `https://www.drivendata.org/competitions/306/competition-doe-gems/data/` — Defines single-band `float32` GeoTIFF submission format (`EPSG:32611`, `3730 x 3292`, `100 m` pixel spacing, values in `[0, 1]`).
3. **DrivenData — Public Leaderboard:** `https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/` — Live organizer ranking board (`numeric_scores_omitted: true` in automated feed).
4. **DrivenData — Official Reference Solution Repository (Verified HTTP 200 inside sandbox):** `https://github.com/drivendataorg/gems-prize-reference-solution` — Official baseline workflow and GeoTIFF packaging reference.
5. **USGS Quaternary Fault & Fold Database / INGENIOUS Great Basin Compilation:** Source of `data/existing_faults.tif` (`60,988` mapped fault cells inside the `5,167,373`-cell Nevada study footprint).
6. **USGS 3D Elevation Program (`3DEP` 1 m LiDAR) & GeoDAWN Aeromagnetics/Radiometrics:** Restored and verified against SHA-256 manifest in `registry/data_manifest.json` (`12` LiDAR channels + `8` GeoDAWN channels).
7. **DOE Geothermal Data Repository (`GDR #1391` — Great Basin Play Fairway / INGENIOUS Thermal Springs & Wells):** Restored and SHA-256 verified (`doe_gdr_1391_springs.csv`, `doe_gdr_1391_wells.csv`).
8. **Sibling Repository Inventory (`buffedlizard55-lab/GEMSDOE*`):** All `93` accessible repositories enumerated; `13 / 13` shared template modules in `vendor/gems57/` verified bit-for-bit against `registry/template_pin.json`; `23 / 23` data artifacts verified against `registry/data_manifest.json`; `858` sibling `.tif` files (`476` unique SHA-256 digests) audited on disk.

## 2. Generated Deliverable Checksums
- **Primary Portal-Safe Submission GeoTIFF (`downloads/gems87-csct-dink300-37654dots-20261022-zeros.tif`):**  
  `SHA-256 = 30ffb71d5fe6bda04735d6a5b1ef5280f3f578ac070e83d385622ea19086003f` (`144,378` bytes)
- **Single-TIFF Competition Archive (`downloads/gems87-csct-dink300-37654dots-20261022-zeros.zip`):**  
  Contains byte-identical `gems87-csct-dink300-37654dots-20261022-zeros.tif`
- **Companion Reference-Mask GeoTIFF (`downloads/gems87-csct-dink300-37654dots-20261022-nan.tif`):**  
  `SHA-256 = b99088c16873425741f6a75e7173a8aa7b764a02e4d032263be3447ea66c9285` (`334,324` bytes)
