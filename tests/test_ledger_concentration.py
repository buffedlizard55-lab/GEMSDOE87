from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LedgerConcentrationTests(unittest.TestCase):
    def test_ledger_has_unique_conc_rows_and_mass_dedupe(self) -> None:
        with (ROOT / "ledger/submissions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 6)
        axes = {(r["parent"], r["axis"], r["value"]) for r in rows}
        self.assertEqual(len(axes), len(rows))
        conc = [r for r in rows if r["axis"] == "CONCENTRATION"]
        self.assertEqual({r["value"] for r in conc}, {"c10", "c15", "c20"})
        shas = [r["sha256"] for r in conc]
        self.assertEqual(len(set(shas)), 3)
        for r in conc:
            self.assertEqual(r["parent"], "h33-h33-2-b2")
            self.assertEqual(r["n_dots"], "37654")
            self.assertEqual(r["status"], "BUILT")
            self.assertEqual(r["receipt_score"], "")
            self.assertTrue(1.0 <= float(r["pct_changed"]) <= 50.0)
            self.assertEqual(len(r["sha256"]), 64)
            self.assertTrue(
                (ROOT / "releases" / f"{r['id']}.tif").is_file(),
                f"missing {r['id']}.tif",
            )
            self.assertTrue(
                (ROOT / "releases" / f"{r['id']}-zeros.tif").is_file(),
                f"missing {r['id']}-zeros.tif",
            )

    def test_mechanism_cards_and_r0_pin(self) -> None:
        cards = json.loads((ROOT / "ledger/mechanism_cards.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cards), 3)
        for card in cards.values():
            for key in ("hypothesis", "mechanism", "non_fault_mimic", "predicted_sign_size", "falsifier"):
                self.assertIn(key, card)
            self.assertEqual(card["block_px"], 10)
        pin = json.loads((ROOT / "registry/r0_parent.json").read_text(encoding="utf-8"))
        self.assertEqual(
            pin["sha256_zeros"],
            "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9",
        )
        self.assertTrue(pin["parent_rebuild_pixel_identity"])
        self.assertFalse(pin["parent_reencode_sha_matched"])

    def test_notes_fit_140_and_readme_has_current_state(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## CURRENT STATE (agent brief v2", readme)
        submit = (ROOT / "docs/SUBMIT.md").read_text(encoding="utf-8")
        for line in submit.splitlines():
            if line.startswith("- **Note"):
                note = line.split(":**", 1)[1].strip().strip("`")
                self.assertLessEqual(len(note), 140, note)

    def test_slot_plan_exists_and_irregularities_are_decision_items(self) -> None:
        plan = (ROOT / "SLOT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("CONCENTRATION", plan)
        self.assertIn("SNAP", plan)
        irr = (ROOT / "IRREGULARITIES.md").read_text(encoding="utf-8")
        self.assertIn("IR-87-V2-01", irr)
        self.assertIn("IR-87-V2-02", irr)


if __name__ == "__main__":
    unittest.main()
