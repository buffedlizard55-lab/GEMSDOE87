# Local competition data (not committed)

`data/` is intentionally ignored by Git. The organizer's competition-data page is login-walled, so this checkout uses hash-pinned **owner mirrors on GitHub only after verification**. A matching SHA-256 proves that the downloaded mirror matches the recorded mirror bytes; it does **not** prove organizer provenance.

## Reproduce the local placement

```bash
python scripts/fetch_competition_mirrors.py --core
python scripts/prepare_data.py
```

The current execution verified these core files against `registry/data_manifest.json`:

| file | SHA-256 | role |
|---|---|---|
| `raw/training_features.tif` | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` | 19-band input feature raster |
| `raw/labels.tif` | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | visible fault catalogue used only for spatial holdout/training |
| `raw/sample_submission.tif` | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | submission-grid template |

Do not commit these files, use them as organizer-authenticated data, or use an unverified download to produce a submission.
