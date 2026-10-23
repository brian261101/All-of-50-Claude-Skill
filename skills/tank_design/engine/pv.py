"""Launcher: python pv_design/pv.py <command> ...  (see pressure_vessel/cli.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pressure_vessel.cli import main  # noqa: E402

raise SystemExit(main())
