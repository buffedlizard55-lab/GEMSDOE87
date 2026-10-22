from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[str] = []

    def handle_starttag(self, tag, attrs):  # type: ignore[no-untyped-def]
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.values.append(value)


def test_site_generator_and_local_links() -> None:
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / "scripts" / "build_site.py")], cwd=root, check=True)
    pages = sorted((root / "docs").glob("*.html"))
    assert len(pages) >= 7
    feed = json.loads((root / "docs" / "feed.json").read_text(encoding="utf-8"))
    assert feed["version"] == "https://jsonfeed.org/version/1.1"
    assert feed["items"][0]["attachments"][0]["mime_type"] == "image/tiff"
    for page in pages:
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        broken = []
        for value in parser.values:
            if value.startswith(("#", "http://", "https://", "mailto:", "data:")):
                continue
            if not (page.parent / value).is_file():
                broken.append(value)
        assert not broken, f"{page.name}: {broken}"
