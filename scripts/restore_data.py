#!/usr/bin/env python3
"""Restore + SHA-256 verify every competition / external / historical file in registry/data_manifest.json.

Every byte is fetched from a GitHub mirror pinned by commit SHA and verified against a SHA-256
recorded in the manifest.  Nothing here is organizer-authenticated: the manifest's `provenance`
field states, per file, where the bytes originally came from and what that does and does not prove.

Usage:
    python scripts/restore_data.py                 # core group only
    python scripts/restore_data.py --groups core external scored
    python scripts/restore_data.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "registry" / "data_manifest.json"
DATA = ROOT / "data"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gh_raw(repo: str, ref: str, path: str, out_fh) -> None:
    """Stream one file from GitHub using the authenticated gh CLI (raw media type)."""
    subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}",
         "-H", "Accept: application/vnd.github.raw"],
        stdout=out_fh, check=True,
    )


def restore(entry: dict, force: bool = False) -> dict:
    dest = DATA / entry["dest"]
    if dest.exists() and not force:
        got = sha256_file(dest)
        if got == entry["sha256"]:
            return {"id": entry["id"], "status": "cached", "sha256": got,
                    "bytes": dest.stat().st_size}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    try:
        with tmp.open("wb") as out:
            for p in entry.get("parts", [entry.get("path")]):
                if p is None:
                    raise ValueError(f"{entry['id']}: manifest has neither 'path' nor 'parts'")
                gh_raw(entry["repo"], entry["ref"], p, out)
        got = sha256_file(tmp)
        if got != entry["sha256"]:
            raise ValueError(f"{entry['id']}: sha256 mismatch\n  expected {entry['sha256']}\n  got      {got}")
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"id": entry["id"], "status": "restored", "sha256": got, "bytes": dest.stat().st_size}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups", nargs="*", default=["core"],
                    help="manifest groups to restore (core, external, scored). 'all' for everything.")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    files = manifest["files"]
    if args.list:
        for f in files:
            print(f"{f['id']:46s} {f.get('group',''):9s} {f.get('bytes',0)/1e6:8.1f} MB  -> data/{f['dest']}")
        return 0

    groups = set(args.groups)
    sel = files if "all" in groups else [f for f in files if f.get("group") in groups]
    receipts = []
    for entry in sel:
        try:
            r = restore(entry, force=args.force)
        except Exception as exc:  # noqa: BLE001 - we want the id attached to every failure
            r = {"id": entry["id"], "status": "FAILED", "error": str(exc)}
            print(f"[FAIL] {entry['id']}: {exc}", file=sys.stderr)
        else:
            print(f"[{r['status']:8s}] {r['id']:46s} {r['bytes']/1e6:8.1f} MB  {r['sha256'][:16]}")
        receipts.append(r)

    out = ROOT / "registry" / "restore_receipt.json"
    out.write_text(json.dumps({"groups": sorted(groups), "files": receipts}, indent=2) + "\n")
    bad = [r for r in receipts if r["status"] == "FAILED"]
    print(f"\n{len(receipts)-len(bad)}/{len(receipts)} verified -> {out.relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
