"""Locations of the bundled data, resolved relative to the package."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parents[1]          # pv_design/
DATA_DIR = PROJECT_DIR / "data"
