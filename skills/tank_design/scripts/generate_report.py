"""Write the calculation report (HTML + PDF) for a calculated package.

    python .claude/skills/tank_design/scripts/generate_report.py <package dir>
"""

import sys

from _common import bootstrap

bootstrap()
from pressure_vessel.cli import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(["report", sys.argv[1]]))
