#!/usr/bin/env python3
"""Restore SHA-256-pinned R0/grid inputs via GitHub API (api.github.com only)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "registry" / "data_manifest.json"

FETCH = [
    (
        "buffedlizard55-lab/GEMSDOE24",
        "data/bridge/sample_submission.tif",
        ROOT / "data/bridge/sample_submission.tif",
        "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    ),
    (
        "buffedlizard55-lab/GEMSDOE24",
        "data/bridge/existing_faults.tif",
        ROOT / "data/bridge/existing_faults.tif",
        "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    ),
    (
        "buffedlizard55-lab/GEMSDOE32",
        "docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif",
        ROOT / ".cache/raw/scored/GEMSDOE32__h33-2-b2-zeros.tif",
        "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
    ),
    (
        "buffedlizard55-lab/GEMSDOE32",
        "docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif",
        ROOT / ".cache/raw/scored/GEMSDOE32__h33-2-b2-nan.tif",
        "baeae3219bba6a19bc8cfe79224e28555c50184b7c1ca65c2a822f54807c77dd",
    ),
    (
        "buffedlizard55-lab/GEMSDOE32",
        "docs/downloads/gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
        ROOT / ".cache/raw/scored/GEMSDOE25__dotted-h19-5-d2-8-nan.tif",
        "91eae1ca42ec845eaa8c2ba32da49806e24751743459b8a10017c479bbe639b8",
    ),
    (
        "buffedlizard55-lab/GEMSDOE24",
        "inputs/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
        ROOT / ".cache/raw/scored/H19-5-nan.tif",
        "ec1f9b56b83ce33cad781ceb9f104b18fb4f2ff785263a4e89616af4aabdee8d",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(repo: str, path: str, dest: Path, expected: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and sha256(dest) == expected:
        print(f"ok {dest} {expected[:12]}")
        return
    cmd = [
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github.raw",
        f"repos/{repo}/contents/{path}",
    ]
    dest.write_bytes(subprocess.check_output(cmd))
    actual = sha256(dest)
    if actual != expected:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"sha mismatch {dest}: {actual} != {expected}")
    print(f"fetched {dest} {expected[:12]}")


def main() -> int:
    for repo, path, dest, expected in FETCH:
        fetch(repo, path, dest, expected)
    sample = ROOT / "data/bridge/sample_submission.tif"
    cache_sample = ROOT / ".cache/raw/sample_submission.tif"
    cache_ef = ROOT / ".cache/raw/existing_faults.tif"
    cache_sample.parent.mkdir(parents=True, exist_ok=True)
    cache_sample.write_bytes(sample.read_bytes())
    cache_ef.write_bytes((ROOT / "data/bridge/existing_faults.tif").read_bytes())
    pins = json.loads(MANIFEST.read_text())
    print(f"manifest files pinned: {len(pins['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
