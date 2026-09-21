#!/usr/bin/env python3
"""DEPRECATED: use the wbb CLI instead (uv run wbb scrape ...).

This shim keeps the documented `uv run python rosters.py ...` commands working;
all scraping logic now lives in the wbb package at the repo root.
"""
import sys
from pathlib import Path

# Ensure `import wbb` works even before `uv sync` installs the package
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from wbb.cli import main

if __name__ == "__main__":
    sys.exit(main())