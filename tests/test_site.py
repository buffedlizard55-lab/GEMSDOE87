from __future__ import annotations

import hashlib
import json
import re
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
    def test_landing_page_and_executive_summary_expose_validated_download(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["submission_ready"])
        self.assertEqual(status["status"], "ready")
        self.assertIsNotNone(status["download"])
        dl_path = status["download"]["path"]
        self.assertEqual(dl_path, f"downloads/{status['artifact']['filename']}")
        tif_file = ROOT / dl_path
        self.assertTrue(tif_file.is_file(), f"Missing primary submission GeoTIFF: {tif_file}")
        actual_sha = hashlib.sha256(tif_file.read_bytes()).hexdigest()
        self.assertEqual(actual_sha, status["artifact"]["sha256"])
        self.assertEqual(actual_sha, status["validation"]["receipt_sha256"])

        for filename in ("index.html", "executive-summary.html"):
            html = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("READY — VALIDATED FILE AVAILABLE", html)
            parser = _Links()
            parser.feed(html)
            tif_links = [href for href in parser.hrefs if href.lower().endswith((".tif", ".tiff", ".zip"))]
            self.assertIn(dl_path, tif_links, f"{filename} must link directly to {dl_path}")

    def test_submission_status_passes_all_client_side_readiness_gates(self) -> None:
        status = json.loads((ROOT / "data/submission-status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["submission_ready"])
        self.assertEqual(status["status"], "ready")
        self.assertTrue(all(g["status"] == "passed" for g in status["gates"]))

        h = status["holdout_dti"]
        self.assertEqual(h["evidence_class"], "HOLDOUT-DTI")
        self.assertEqual(h["evaluator_version"], "gems57-pooled-hide-v2")
        self.assertEqual(h["withheld_positive_count"], 22663)
        self.assertGreater(h["score"], 0.17)
        self.assertEqual(len(h["ci_95"]), 2)
        self.assertTrue(h["beats_current_best"])

        nov = status["novelty"]
        self.assertEqual(nov["status"], "passed")
        self.assertLessEqual(nov["rank_correlation_max"], 0.90)
        self.assertLessEqual(nov["fraction_within_3px_max"], 0.70)
        self.assertEqual(nov["registry_rasters_checked"], 202)

        val = status["validation"]
        self.assertEqual(val["status"], "passed")
        self.assertTrue(val["no_nan_inside_footprint"])
        self.assertTrue(val["finite_values_in_0_1"])
        self.assertTrue(val["crs_shape_transform_match"])
        self.assertRegex(val["receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertLessEqual(len(status["submission_note"]), 140)

    def test_executive_summary_explains_submission_and_validation(self) -> None:
        html = (ROOT / "executive-summary.html").read_text(encoding="utf-8")
        for phrase in ("submission format", "sample_submission.tif", "validate_submission.py", "Note", "[0, 1]"):
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
        self.assertGreaterEqual(len(sources["sources"]), 10)
        self.assertTrue(feed["numeric_scores_omitted"])
        self.assertTrue(any(source["id"] == "competition_problem" for source in sources["sources"]))
        self.assertTrue((ROOT / "docs/review-log.md").is_file())

    def test_run_card_and_evidence_receipts_are_promoted_and_consistent(self) -> None:
        card = json.loads((ROOT / "data/run-card.json").read_text(encoding="utf-8"))
        self.assertEqual(card["verdict"], "promote")
        self.assertEqual(
            card["raster_sha256"],
            "1c28a4c991111dd201281ccdb05e7792344ba00a6a8efedfceab976117cf2c69",
        )
        self.assertAlmostEqual(card["holdout_dti"]["score"], 0.171555, places=5)
        self.assertLessEqual(card["leakage_canary"]["max_symmetric_auc"], 0.90)
        self.assertFalse(card["correlation_overlap_vs_registry"]["duplicate"])
        self.assertLessEqual(len(card["submission"]["note"]), 140)

        exp1 = json.loads((ROOT / "docs/evidence/exp87_1_leakage_canary.json").read_text(encoding="utf-8"))
        exp2 = json.loads((ROOT / "docs/evidence/exp87_2_holdout_ablation.json").read_text(encoding="utf-8"))
        exp3 = json.loads((ROOT / "docs/evidence/exp87_3_promotion_audit.json").read_text(encoding="utf-8"))
        self.assertTrue(exp1["passed"])
        self.assertEqual(exp1["n_flagged_channels"], 0)
        self.assertTrue(exp2["beats_all_controls_on_holdout"])
        for ctrl, diff in exp2["paired_differences_vs_a5"].items():
            self.assertGreater(diff["delta_holdout_dti"], 0.0, f"A5 must beat {ctrl}")
            self.assertGreater(diff["ci95"][0], 0.0, f"A5 95% CI lower bound must be > 0 vs {ctrl}")
        self.assertFalse(exp3["registry_uniqueness"]["dots_phase_binding"]["duplicate"])
        self.assertTrue(exp3["artifacts"]["primary_nan_geotiff"]["repo_validator"]["ready"])
        self.assertTrue(exp3["artifacts"]["companion_zeros_geotiff"]["gems57_validator"]["all_checks_passed"])


if __name__ == "__main__":
    unittest.main()
