#!/usr/bin/env python3
"""Compatibility entry point for the pinned, label-free feature cache preparation."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent / 'scripts/prepare_data.py'), run_name='__main__')
