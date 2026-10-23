"""Validate a vessel or tank input file.

    python .claude/skills/tank_design/scripts/validate_input.py <input.yaml>

Exit 0 = valid (warnings/questions may remain), 2 = errors.
"""

import sys

from _common import bootstrap

bootstrap()
from pressure_vessel.cli import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(["validate", sys.argv[1]]))
