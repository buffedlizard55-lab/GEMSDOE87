#!/usr/bin/env python3
"""Named submission-writer entry point; delegates to the fail-closed release gate."""
from __future__ import annotations

import runpy
from pathlib import Path

# Keeping this entry point explicit satisfies the shared-template convention:
# `evaluate_holdout.py` creates the evidence; `submission_writer.py` reads it
# and refuses an output if the evidence does not promote the candidate.
runpy.run_path(str(Path(__file__).with_name("build_submission.py")), run_name="__main__")
