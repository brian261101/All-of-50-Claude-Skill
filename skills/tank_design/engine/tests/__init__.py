"""Test package: puts pv_design/src on the import path (stdlib unittest only).

Run from pv_design/:   python -m unittest discover -s tests -t .
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "tests" / "fixtures"
