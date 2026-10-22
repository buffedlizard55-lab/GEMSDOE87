from __future__ import annotations

import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() == "a":
            values = dict(attrs)
            if "href" in values:
                self.hrefs.append(values["href"])


class SiteTests(unittest.TestCase):
    def test_landing_page_explicitly_blocks_unvalidated_download(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("NOT READY TO SUBMIT", html)
        self.assertIn("No validated GeoTIFF", html)

    def test_no_download_link_exists_while_status_is_blocked(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertFalse(status["submission_ready"])
        self.assertIsNone(status["download"])
        for filename in ("index.html", "executive-summary.html"):
            parser = _Links()
            parser.feed((ROOT / filename).read_text(encoding="utf-8"))
            tif_links = [href for href in parser.hrefs if href.lower().endswith((".tif", ".tiff", ".zip"))]
            self.assertEqual(tif_links, [], f"unready page exposes a downloadable TIFF: {filename}")

    def test_executive_summary_explains_submission_and_current_block(self) -> None:
        html = (ROOT / "executive-summary.html").read_text(encoding="utf-8")
        for phrase in ("submission format", "sample submission", "validation", "not ready", "Note"):
            self.assertIn(phrase.lower(), html.lower())
        self.assertIn("drivendata.org/competitions/306/competition-doe-gems/data/", html)

    def test_all_local_html_links_resolve(self) -> None:
        for page in ROOT.glob("*.html"):
            parser = _Links()
            parser.feed(page.read_text(encoding="utf-8"))
            for href in parser.hrefs:
                if not href or href.startswith("#"):
                    continue
                if href.startswith(("https://", "http://", "mailto:")):
                    continue
                target = (page.parent / href.split("#", 1)[0].split("?", 1)[0]).resolve()
                self.assertTrue(target.exists(), f"broken local link in {page.name}: {href}")

    def test_source_register_and_feed_are_parseable(self) -> None:
        sources = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
        feed = json.loads((ROOT / "data/feed.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sources["sources"]), 8)
        self.assertTrue(feed["numeric_scores_omitted"])
        self.assertTrue(any(source["id"] == "competition_problem" for source in sources["sources"]))
        self.assertTrue((ROOT / "docs/review-log.md").is_file())

    def test_run_card_is_negative_and_has_no_claimed_measurement(self) -> None:
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        self.assertEqual(card["verdict"], "negative")
        self.assertIsNone(card["raster_sha256"])
        self.assertIsNone(card["holdout_dti"]["score"])


if __name__ == "__main__":
    unittest.main()
