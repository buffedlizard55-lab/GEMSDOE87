"""Repository-relative paths; all commands are safe from an arbitrary current directory."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
WORK = ROOT / "work"
REGISTRY = ROOT / "registry"
EVIDENCE = ROOT / "evidence"
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"


def ensure_local_dirs() -> None:
    for path in (RAW, WORK, EVIDENCE, DOWNLOADS):
        path.mkdir(parents=True, exist_ok=True)
