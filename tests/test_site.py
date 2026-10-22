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
        self.assertIn("DO NOT SUBMIT", html)
        self.assertIn("research", html.lower())
        self.assertIn("docs/index.html", html)

    def test_no_download_link_exists_while_status_is_blocked(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertFalse(status["submission_ready"])
        self.assertIsNone(status["download"])
        self.assertIn("DO NOT SUBMIT", status["research_download_status"])
        self.assertTrue((ROOT / status["research_download"]).is_file())
        for filename in ("index.html", "executive-summary.html"):
            parser = _Links()
            parser.feed((ROOT / filename).read_text(encoding="utf-8"))
            tif_links = [href for href in parser.hrefs if href.lower().endswith((".tif", ".tiff", ".zip"))]
            self.assertEqual(tif_links, [], f"unready page exposes a downloadable TIFF: {filename}")

    def test_executive_summary_explains_submission_and_current_block(self) -> None:
        redirect = (ROOT / "executive-summary.html").read_text(encoding="utf-8")
        self.assertIn("docs/executive-summary.html", redirect)
        html = (ROOT / "docs/executive-summary.html").read_text(encoding="utf-8")
        for phrase in ("submission", "sample grid", "validation", "not approved", "Note"):
            self.assertIn(phrase.lower(), html.lower())
        self.assertIn("drivendata.org/competitions/306/competition-doe-gems/submissions/", html)

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

    def test_pages_workflow_publishes_a_validated_download_directory(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("if [ -d downloads ]; then", workflow)
        self.assertIn("cp -R downloads/. .cache/pages-publish/downloads/", workflow)

    def test_source_register_and_feed_are_parseable(self) -> None:
        sources = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
        feed = json.loads((ROOT / "data/feed.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sources["sources"]), 8)
        self.assertTrue(feed["numeric_scores_omitted"])
        self.assertTrue(any(source["id"] == "competition_problem" for source in sources["sources"]))
        self.assertTrue((ROOT / "docs/review-log.md").is_file())

    def test_run_card_is_negative_and_has_only_recorded_measurements(self) -> None:
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        self.assertEqual(card["verdict"], "negative")
        canonical = json.loads((ROOT / "run_card.json").read_text(encoding="utf-8"))
        self.assertEqual(card, canonical)
        self.assertFalse(card["safe_to_submit"])
        measured = card["holdout_dti"]["downloadable_continuous_artifact"]
        self.assertEqual(measured["evaluator_version"], "gems57-pooled-hide-v2")
        self.assertEqual(measured["withheld_positive_pixels"], 60988)
        self.assertEqual(len(measured["ci95"]), 2)


if __name__ == "__main__":
    unittest.main()
