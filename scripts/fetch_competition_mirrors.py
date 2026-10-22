#!/usr/bin/env python3
"""Fetch hash-pinned owner mirrors and fail closed on every mismatch.

No DrivenData credential is sent or requested.  Read data/README.md before use:
a matching hash verifies a mirror record, not organizer authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.paths import DATA, REGISTRY  # noqa: E402


def download(repo: str, ref: str, remote_path: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    endpoint = f"repos/{repo}/contents/{remote_path}?ref={ref}"
    with destination.open("wb") as out:
        subprocess.run(
            ["gh", "api", endpoint, "-H", "Accept: application/vnd.github.raw"],
            stdout=out,
            check=True,
        )


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1 << 20), b""):
            h.update(piece)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", action="store_true", help="fetch core files (the only group currently registered)")
    parser.add_argument("--dest", type=Path, default=DATA)
    parser.add_argument("--manifest", type=Path, default=REGISTRY / "data_manifest.json")
    args = parser.parse_args()
    if not args.core:
        parser.error("pass --core explicitly: this downloads a ~419 MB feature raster")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    receipt: list[dict] = []
    failures = []
    for item in manifest["files"]:
        if item.get("group") != "core":
            continue
        target = args.dest / item["dest"]
        temporary = target.with_suffix(target.suffix + ".partial")
        temporary.unlink(missing_ok=True)
        try:
            if "parts" in item:
                for number, remote in enumerate(item["parts"]):
                    part = target.parent / f".{target.name}.part-{number:03d}"
                    part.unlink(missing_ok=True)
                    download(item["repo"], item["ref"], remote, part)
                    with temporary.open("ab") as merged, part.open("rb") as source:
                        while chunk := source.read(1 << 20):
                            merged.write(chunk)
                    part.unlink(missing_ok=True)
            else:
                download(item["repo"], item["ref"], item["path"], temporary)
            got_bytes = temporary.stat().st_size
            got_hash = digest(temporary)
            ok = got_bytes == int(item["bytes"]) and got_hash == item["sha256"]
            rec = {"id": item["id"], "target": str(target), "bytes": got_bytes, "sha256": got_hash, "passed": ok}
            if not ok:
                temporary.unlink(missing_ok=True)
                failures.append(item["id"])
            else:
                temporary.replace(target)
            receipt.append(rec)
            print(("PASS" if ok else "FAIL"), item["id"], got_bytes, got_hash)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            failures.append(item["id"])
            receipt.append({"id": item["id"], "passed": False, "error": str(exc)})
            print("FAIL", item["id"], exc, file=sys.stderr)
    summary = {"manifest": str(args.manifest), "dest": str(args.dest), "files": receipt, "failures": failures, "all_passed": not failures,
               "provenance_warning": "Hashes pin owner mirrors only; organizer authentication is NOT established."}
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
