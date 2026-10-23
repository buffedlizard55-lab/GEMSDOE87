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
    def test_landing_page_prominently_exposes_validated_download(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("READY — VALIDATED FILE AVAILABLE", html)
        self.assertIn("gems87-csct-dink300-37654dots-20261022-zeros.tif", html)
        self.assertIn("30ffb71d5fe6bda04735d6a5b1ef5280f3f578ac070e83d385622ea19086003f", html)

    def test_submission_status_and_html_download_targets_match_on_disk(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["submission_ready"])
        self.assertEqual(status["status"], "ready")
        dl_path = status["download"]["path"]
        self.assertTrue((ROOT / dl_path).is_file())
        for filename in ("index.html", "executive-summary.html"):
            parser = _Links()
            parser.feed((ROOT / filename).read_text(encoding="utf-8"))
            self.assertIn(dl_path, parser.hrefs, f"missing validated download link in {filename}")

    def test_executive_summary_explains_submission_format_and_validation(self) -> None:
        html = (ROOT / "executive-summary.html").read_text(encoding="utf-8")
        for phrase in ("submission format", "sample submission", "validation", "Note", "Predicted values must be in range [0, 1]"):
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

    def test_run_card_is_promoted_complete_and_within_note_limit(self) -> None:
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        self.assertEqual(card["verdict"], "promote")
        self.assertEqual(card["experiments_run"], 3)
        self.assertEqual(card["holdout_dti"]["evidence_class"], "HOLDOUT-DTI")
        self.assertEqual(card["holdout_dti"]["evaluator_version"], "gems57-pooled-hide-v2")
        self.assertEqual(card["holdout_dti"]["withheld_positive_count"], 22663)
        self.assertGreater(card["holdout_dti"]["score"], 0.21)
        self.assertLessEqual(len(card["submission_note"]), 140)
        self.assertIsNone(card["organizer_confirmed_scores"]["candidate_gems87_csct_dink300"])


if __name__ == "__main__":
    unittest.main()
