from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_feed import build_feed, classify_page, fetch_source


class RefreshFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = {
            "id": "problem",
            "label": "GEMS problem description",
            "url": "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "expected_terms": ["distance-weighted", "epsg 32611"],
        }

    def test_classifies_expected_official_page_without_extracting_scores(self) -> None:
        result = classify_page(
            self.source,
            http_status=200,
            final_url=self.source["url"],
            title="GEMS Prize Problem Description",
            text="Distance-weighted Tversky uses UTM zone 11N EPSG 32611.",
            body_sha256="a" * 64,
        )
        self.assertEqual(result["status"], "reachable_verified")
        self.assertEqual(result["body_sha256"], "a" * 64)
        self.assertNotIn("score", result)

    def test_flags_missing_expected_marker(self) -> None:
        result = classify_page(
            self.source,
            http_status=200,
            final_url=self.source["url"],
            title="Unexpected page",
            text="A generic page with no source claims.",
        )
        self.assertEqual(result["status"], "content_check_failed")

    def test_detects_login_redirect(self) -> None:
        result = classify_page(
            self.source,
            http_status=200,
            final_url="https://www.drivendata.org/accounts/login/?next=%2Fdata%2F",
            title="Login",
            text="Email Password Log in",
        )
        self.assertEqual(result["status"], "login_required")

    def test_http_error_is_not_misreported_as_verified(self) -> None:
        result = classify_page(
            self.source,
            http_status=503,
            final_url=self.source["url"],
            title="Unavailable",
            text="Temporary error",
        )
        self.assertEqual(result["status"], "http_error")

    def test_build_feed_filters_non_feed_sources_and_writes_score_free_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "sources.json"
            output = root / "feed.json"
            config.write_text(
                json.dumps(
                    {
                        "sources": [
                            {**self.source, "feed_check": True},
                            {"id": "pdf", "label": "rules", "url": "https://docs.nlr.gov/a.pdf", "feed_check": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch("scripts.refresh_feed.fetch_source", return_value={"id": "problem", "status": "reachable_verified"}):
                feed = build_feed(config, output, fetched_at="2026-10-22T00:00:00Z")
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(feed["entries"]), 1)
            self.assertEqual(saved["checked_at"], "2026-10-22T00:00:00Z")
            self.assertTrue(saved["numeric_scores_omitted"])
            self.assertNotIn("scores", saved)

    def test_fetch_source_blocks_drivendata_and_dropbox(self) -> None:
        for url in (
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
            "https://drivendata.org/competitions/306/",
            "https://www.dropbox.com/s/example/file.tif",
        ):
            res = fetch_source({"id": "blocked", "label": "Blocked", "url": url})
            self.assertEqual(res["status"], "blocked_url")


if __name__ == "__main__":
    unittest.main()
