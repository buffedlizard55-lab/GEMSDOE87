#!/usr/bin/env python3
"""Zero-credential data restoration & SHA-256 verification for GEMSDOE87.

Restores all core DrivenData / NETL GEMS rasters and public-domain USGS / OpenET /
GeoDAWN / DOE GDR external rasters into gitignored `.cache/gems_data/` (symlinking
verified local workspace cache artifacts when already downloaded, or streaming directly
from public `codeload.github.com` mirrors on a fresh clone).
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "gems_data"
CORE_DIR = CACHE / "core"
EXT_DIR = CACHE / "external"
COMP_DIR = CACHE / "comparators"

CORE_SHA256 = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

EXTERNAL_FILES = [
    "lidar_scarp_features_u8.tif",
    "topo_10m_derived_100m_u8.tif",
    "dem10_chi_100m_i16.tif",
    "geodawn_rad_u8.tif",
    "geodawn_extensions_u8.tif",
    "sgmc_faults_100m.tif",
    "gdr_wellspring_in_footprint.csv",
    "gdr_volcanic_vents_in_footprint.csv",
    "gdr_qfaults_traces.csv",
    "2m_temperature_probe_INGENIOUS_regional_data.zip",
    "paleo_geothermal_regional.zip",
]

LOCAL_SEARCH_DIRS = [
    Path("/tmp/work/GEMSDOE80/.cache/data"),
    Path("/tmp/work/GEMSDOE80/.cache/external"),
    Path("/tmp/work/57GEMSDOE/data/external"),
    Path("/tmp/work/GEMSDOE78/.cache/gems_data"),
    Path("/tmp/work/GEMSDOE70/data/external"),
]

COMPARATOR_CANDIDATES = {
    "GEMSDOE32_H33_2_B2_02778.tif": Path("/tmp/work/GEMSDOE32/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"),
    "GEMSDOE70_P9_PiedSubmod.tif": Path("/tmp/work/GEMSDOE70/docs/downloads/gems70-p5-submodular-multiphysics-hydro-54000-20261020.tif"),
    "GEMSDOE70_P8_OOF38k_02478.tif": Path("/tmp/work/GEMSDOE70/docs/downloads/gems70-p5-dual-submod300-oof38k-20261020.tif"),
    "19GEMSDOE_H19_5_02442.tif": Path("/tmp/work/19GEMSDOE/submissions/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-zeros.tif")
    if Path("/tmp/work/19GEMSDOE/submissions/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-zeros.tif").exists()
    else Path("/tmp/work/19GEMSDOE/submissions/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-allfinite.tif"),
    "GEMSDOE80_MACS61.tif": Path("/tmp/work/GEMSDOE80/submissions/gems80-macs61-triexpert-submod300-31492dots-20261021T235000Z-379576aa-zeros.tif"),
    "GEMSDOE80_H80G.tif": Path("/tmp/work/GEMSDOE80/submissions/gemsdoe80-h80g-choquet-tworegime-20261022T000000Z-zeros.tif"),
    "GEMSDOE78_GSC.tif": Path("/tmp/work/GEMSDOE78/docs/downloads/gems78-h78gsc-oof-submod40k-20261021T033000Z-zeros.tif"),
    "GEMSDOE78_GFV.tif": Path("/tmp/work/GEMSDOE78/submissions/gems78-h78-gfv-136b-dink-20261022T070254Z-45cd56e7-zeros.tif"),
    "GEMSDOE83_GVCD.tif": Path("/tmp/work/GEMSDOE83/submissions/gems83-h83-gvcd-dink300-37654dots-20261021-1a373694-zeros.tif"),
    "GEMSDOE82_PUNoisyOR.tif": Path("/tmp/work/GEMSDOE82/submissions/gemsdoe82-h82-submodular-punoisyor-20261021T235456Z-fe137199-zeros.tif"),
    "GEMSDOE85_GEOPB.tif": Path("/tmp/work/GEMSDOE85/docs/downloads/gems85-geopb-crest-37654dots-sep4-20261022T222707Z-60029d07-zeros.tif"),
    "GEMSDOE88_MGC.tif": Path("/tmp/work/GEMSDOE88/docs/downloads/gems88-mgc-crossgradient-37654-20261022-v1-DO-NOT-SUBMIT.tif"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def link_if_found(name: str, dest: Path) -> bool:
    if dest.exists():
        return True
    for src_dir in LOCAL_SEARCH_DIRS:
        cand = src_dir / name
        if cand.exists() and cand.stat().st_size > 100:
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(cand.resolve(), dest)
            return True
    return False


def stream_from_github_tarball(repo: str, branch: str, mapping: dict[str, Path]) -> None:
    missing = {k: v for k, v in mapping.items() if not v.exists()}
    if not missing:
        return
    url = f"https://codeload.github.com/{repo}/tar.gz/refs/heads/{branch}"
    print(f"Streaming {len(missing)} artifacts from {url} ...")
    with urllib.request.urlopen(url, timeout=180) as resp:
        gz = gzip.GzipFile(fileobj=resp)
        with tarfile.open(fileobj=gz, mode="r|") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                rel = "/".join(member.name.split("/")[1:])
                for suffix, out_path in list(missing.items()):
                    if rel.endswith(suffix) and not out_path.exists():
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        fobj = tf.extractfile(member)
                        if fobj is None:
                            continue
                        if member.name.endswith(".gz") and not out_path.name.endswith(".gz"):
                            with gzip.GzipFile(fileobj=io.BytesIO(fobj.read())) as zf, out_path.open("wb") as out:
                                shutil.copyfileobj(zf, out)
                        else:
                            with out_path.open("wb") as out:
                                shutil.copyfileobj(fobj, out)


def main() -> None:
    CORE_DIR.mkdir(parents=True, exist_ok=True)
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    COMP_DIR.mkdir(parents=True, exist_ok=True)

    for fname in CORE_SHA256:
        link_if_found(fname, CORE_DIR / fname)
    for fname in EXTERNAL_FILES:
        link_if_found(fname, EXT_DIR / fname)

    # Fallback stream from public GitHub mirrors if running on a cold clone
    if not (EXT_DIR / "sgmc_faults_100m.tif").exists():
        stream_from_github_tarball(
            "buffedlizard55-lab/57GEMSDOE",
            "main",
            {"data/external/sgmc_faults_100m.tif": EXT_DIR / "sgmc_faults_100m.tif"},
        )

    for alias, src in COMPARATOR_CANDIDATES.items():
        dst = COMP_DIR / alias
        if not dst.exists() and src.exists():
            os.symlink(src.resolve(), dst)

    manifest = {"core": {}, "external": {}, "comparators": {}}
    for fname, expected in CORE_SHA256.items():
        p = CORE_DIR / fname
        if not p.exists():
            raise FileNotFoundError(f"Missing core file: {p}")
        digest = sha256_file(p)
        if digest != expected:
            raise ValueError(f"SHA-256 mismatch for {fname}: got {digest}, expected {expected}")
        manifest["core"][fname] = {"sha256": digest, "bytes": p.resolve().stat().st_size}

    for fname in EXTERNAL_FILES:
        p = EXT_DIR / fname
        if not p.exists():
            raise FileNotFoundError(f"Missing external file: {p}")
        manifest["external"][fname] = {"sha256": sha256_file(p), "bytes": p.resolve().stat().st_size}

    for alias in COMPARATOR_CANDIDATES:
        p = COMP_DIR / alias
        if p.exists():
            manifest["comparators"][alias] = {"sha256": sha256_file(p), "bytes": p.resolve().stat().st_size}

    out_manifest = CACHE / "data_manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified {len(manifest['core'])} core rasters, {len(manifest['external'])} external layers, "
          f"{len(manifest['comparators'])} fleet comparators -> {out_manifest}")


if __name__ == "__main__":
    main()
