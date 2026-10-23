from __future__ import annotations

import hashlib
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _AssetRefs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag.lower() == "a" and "href" in values:
            self.hrefs.append(values["href"])
        if tag.lower() in {"img", "script"} and "src" in values:
            self.srcs.append(values["src"])


class SiteTests(unittest.TestCase):
    def test_landing_and_exec_pages_promote_validated_download(self) -> None:
        for fname in ("index.html", "executive-summary.html"):
            html = (ROOT / fname).read_text(encoding="utf-8")
            self.assertIn("READY — VALIDATED FILE AVAILABLE", html)
            self.assertIn("gems87-h87-kdmi-dualhead-dinkelbach-37654-20261022-zeros.tif", html)
            self.assertIn("f791861ac185c5dde434f04c6177b66f8c1dd6b4fc335462b2e0e733ca6ca4ce", html)

    def test_submission_status_satisfies_every_site_js_runtime_gate(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["submission_ready"])
        self.assertEqual(status["status"], "ready")
        self.assertGreaterEqual(len(status["gates"]), 5)
        self.assertTrue(all(g["status"] == "passed" for g in status["gates"]))

        holdout = status["holdout_dti"]
        self.assertEqual(holdout["evidence_class"], "HOLDOUT-DTI")
        self.assertIsInstance(holdout["evaluator_version"], str)
        self.assertGreater(holdout["withheld_positive_count"], 20000)
        self.assertGreater(holdout["score"], 0.23)
        self.assertEqual(len(holdout["ci_95"]), 2)
        self.assertLess(holdout["ci_95"][0], holdout["ci_95"][1])
        self.assertTrue(holdout["beats_current_best"])

        novelty = status["novelty"]
        self.assertEqual(novelty["status"], "passed")
        self.assertLessEqual(novelty["rank_correlation_max"], 0.90)
        self.assertLessEqual(novelty["fraction_within_3px_max"], 0.70)
        self.assertGreaterEqual(novelty["registry_rasters_checked"], 120)

        val = status["validation"]
        art = status["artifact"]
        self.assertEqual(val["status"], "passed")
        self.assertTrue(val["no_nan_inside_footprint"])
        self.assertTrue(val["finite_values_in_0_1"])
        self.assertTrue(val["crs_shape_transform_match"])
        self.assertRegex(art["sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(art["sha256"].lower(), val["receipt_sha256"].lower())
        self.assertEqual(status["download"]["path"], f"downloads/{art['filename']}")
        self.assertTrue(1 <= len(status["submission_note"]) <= 140)

        disk_tif = ROOT / status["download"]["path"]
        self.assertTrue(disk_tif.is_file())
        self.assertEqual(hashlib.sha256(disk_tif.read_bytes()).hexdigest(), art["sha256"])

    def test_executive_summary_explains_submission_format_and_note_limit(self) -> None:
        html = (ROOT / "executive-summary.html").read_text(encoding="utf-8")
        for phrase in ("submission format", "sample_submission.tif", "[0.0, 1.0]", "Note", "AI-assisted"):
            self.assertIn(phrase.lower(), html.lower())
        self.assertIn("drivendata.org/competitions/306/competition-doe-gems/data/", html)

    def test_all_local_html_links_and_embedded_images_resolve(self) -> None:
        for page in ROOT.glob("*.html"):
            parser = _AssetRefs()
            parser.feed(page.read_text(encoding="utf-8"))
            for ref in parser.hrefs + parser.srcs:
                if not ref or ref.startswith(("#", "https://", "http://", "mailto:")):
                    continue
                target = (page.parent / ref.split("#", 1)[0].split("?", 1)[0]).resolve()
                self.assertTrue(target.exists(), f"broken local ref in {page.name}: {ref}")

    def test_pages_workflow_packages_downloads_and_all_json_receipts(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("if [ -d downloads ]; then", workflow)
        self.assertIn("cp -R downloads/. _site/downloads/", workflow)
        self.assertIn("cp data/*.json _site/data/", workflow)

    def test_source_register_and_feed_are_parseable_and_score_free(self) -> None:
        sources = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
        feed = json.loads((ROOT / "data/feed.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(sources["sources"]), 10)
        self.assertTrue(feed["numeric_scores_omitted"])
        self.assertTrue(any(source["id"] == "competition_problem" for source in sources["sources"]))
        self.assertTrue((ROOT / "docs/review-log.md").is_file())

    def test_run_card_matches_promoted_candidate_and_protocol_schema(self) -> None:
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        self.assertEqual(card["verdict"], "promote")
        self.assertEqual(
            card["raster_sha256"],
            "f791861ac185c5dde434f04c6177b66f8c1dd6b4fc335462b2e0e733ca6ca4ce",
        )
        self.assertEqual(card["holdout_dti"]["evidence_class"], "HOLDOUT-DTI")
        self.assertAlmostEqual(card["holdout_dti"]["score"], 0.238779, places=6)
        self.assertTrue(1 <= len(card["submission"]["note"]) <= 140)
        self.assertTrue(re.match(r"^[a-z0-9-]+$", card["submission"]["name"]))


if __name__ == "__main__":
    unittest.main()
