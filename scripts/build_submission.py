#!/usr/bin/env python3
"""Fail-closed H87-FRB submission builder.

A GeoTIFF is written only after (1) the spatial holdout promotion gate and (2)
both registry duplicate screens pass.  This script never uploads to DrivenData.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems87.data import read_template  # noqa: E402
from gems87.paths import DOWNLOADS, EVIDENCE, RAW  # noqa: E402
from gems87.registry import compare_final_dots, compare_surface  # noqa: E402
from gems87.submission import build_h87_frb_surface, place_h87_frb_mask, write_submission  # noqa: E402


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_card(path: Path, card: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")


def base_card(experiment: dict) -> dict:
    candidate = experiment.get("summary", {}).get("h87_frb_hgb", {})
    return {
        "schema_version": 1,
        "generated_utc": now(),
        "hypothesis": "H87-FRB Fabric-rotation boundary under active strain",
        "mechanism": "Multiscale axial fabric rotation in topography, magnetics, and gravity corroborated by strain and conductivity gradients; no distance-to-catalogue feature.",
        "non_fault_mimic": "Lithologic/volcanic contacts, drainage divides, and processing seams can produce the same texture rotation.",
        "holdout_dti": {
            "evidence_label": "HOLDOUT-DTI",
            "evaluator_version": experiment.get("evaluator_version"),
            "n_withheld_positive_pixels": candidate.get("n_withheld_positive_pixels"),
            "mean": candidate.get("mean"),
            "ci95": [candidate.get("ci95_low"), candidate.get("ci95_high")],
            "organizer_confirmed_score": None,
        },
        "organizer_confirmed": {"evidence_label": "ORGANIZER-CONFIRMED", "receipt": None, "score": None},
        "weekly_submission_slot_used": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", type=Path, default=EVIDENCE / "experiment_h87_frb.json")
    ap.add_argument("--registry", type=Path, default=EVIDENCE / "registry_materialization.json")
    ap.add_argument("--out-card", type=Path, default=EVIDENCE / "run_card_h87_frb.json")
    ap.add_argument("--timestamp", default="20261022T000000Z", help="UTC filename tag; default uses the task date")
    args = ap.parse_args()
    experiment = load(args.experiment)
    card = base_card(experiment)
    gate = experiment.get("promotion_gate", {})
    if gate.get("verdict") != "PROMOTE":
        card.update({
            "correlation_overlap_vs_registry": {"status": "NOT RUN: holdout promotion gate was negative"},
            "raster_sha256": None,
            "validator_output": {"status": "NOT RUN: no candidate may be written"},
            "submission": {"name": None, "note": None, "ready_to_download_and_submit": False},
            "verdict": "negative",
            "reason": "Holdout gate did not beat the current matched holdout baseline with a strictly positive 95% paired CI.",
        })
        write_card(args.out_card, card)
        print(json.dumps(card, indent=2))
        return 0

    registry = load(args.registry)
    footprint, _, _ = read_template(RAW / "sample_submission.tif")
    surface_build = build_h87_frb_surface()
    surface = np.load(surface_build["surface_path"], mmap_mode="r")
    # Parallel-run gate 1: rank correlation of the continuous surface is checked
    # before any NMS/dot placement is allowed.
    surface_report = compare_surface(surface, footprint, registry)
    (EVIDENCE / "surface_uniqueness_h87_frb.json").write_text(json.dumps(surface_report, indent=2) + "\n")
    if surface_report["verdict"] != "UNIQUE":
        card.update({
            "correlation_overlap_vs_registry": {"surface": surface_report, "final": "NOT RUN"},
            "raster_sha256": None,
            "validator_output": {"status": "NOT RUN: surface duplicate/unresolved"},
            "submission": {"name": None, "note": None, "ready_to_download_and_submit": False},
            "verdict": "negative",
            "reason": "Surface duplicate gate failed closed; no dot placement or downloadable TIFF was produced.",
        })
        write_card(args.out_card, card)
        print(json.dumps(card, indent=2))
        return 0

    tentative = place_h87_frb_mask(surface_build["surface_path"], emission_fraction=surface_build["emission_fraction"])
    # Parallel-run gate 2: exact binary-rank correlation and 3-pixel dot overlap.
    dot_report = compare_final_dots(tentative["mask"], footprint, registry)
    (EVIDENCE / "final_uniqueness_h87_frb.json").write_text(json.dumps(dot_report, indent=2) + "\n")
    if dot_report["verdict"] != "UNIQUE":
        card.update({
            "correlation_overlap_vs_registry": {"surface": surface_report, "final": dot_report},
            "raster_sha256": None,
            "validator_output": {"status": "NOT RUN: final dots duplicate/unresolved"},
            "submission": {"name": None, "note": None, "ready_to_download_and_submit": False},
            "verdict": "negative",
            "reason": "Final-dot duplicate gate failed closed; no downloadable TIFF was produced.",
        })
        write_card(args.out_card, card)
        print(json.dumps(card, indent=2))
        return 0

    output = write_submission(tentative["mask"], out_dir=DOWNLOADS, slug="h87-frb", timestamp_tag=args.timestamp)
    note = f"H87-FRB fabric-rotation strain gate; local holdout passed; sha {output['sha256'][:8]}; unscored"
    if len(note) > 140:
        raise RuntimeError("submission note unexpectedly exceeds 140 characters")
    card.update({
        "correlation_overlap_vs_registry": {
            "surface": surface_report,
            "final": dot_report,
            "status": "UNIQUE: no registry comparison crossed the configured duplicate threshold",
        },
        "raster_sha256": output["sha256"],
        "validator_output": output,
        "submission": {
            "name": output["submission_name"],
            "note": note,
            "note_characters": len(note),
            "ready_to_download_and_submit": True,
            "download_path": f"docs/downloads/{output['submission_name']}",
        },
        "verdict": "promote",
        "reason": "Local proxy and uniqueness gates passed. This is not an organizer-confirmed score or portal acceptance receipt.",
    })
    write_card(args.out_card, card)
    # A co-located sidecar lets the static site show the exact validation state.
    sidecar = DOWNLOADS / (Path(output["submission_name"]).stem + ".run-card.json")
    write_card(sidecar, card)
    print(json.dumps(card, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
