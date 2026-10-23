"""Finish a package after the calculation: BOM, CAD (MCP snippets or
headless), drawings, consistency checks, tests, manifest.

    python .claude/skills/tank_design/scripts/build_package.py <package dir> [--headless] [--no-tests]

Without --headless and without an existing 02_CAD_3D/cad_check.json it prints
the FreeCAD MCP execute_code snippets and stops; run them, then call this
script again.
"""

import argparse
from pathlib import Path

from _common import bootstrap

bootstrap()
from pressure_vessel.cli import main  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args()
    pkg = a.package
    for step in (["report", pkg], ["bom", pkg]):
        rc = main(step)
        if rc:
            raise SystemExit(rc)
    if a.headless:
        rc = main(["cad", pkg, "--headless"])
        if rc:
            raise SystemExit(rc)
    elif not (Path(pkg) / "02_CAD_3D" / "cad_check.json").is_file():
        main(["cad", pkg])
        raise SystemExit("CAD pending: send the snippets above through the FreeCAD MCP, then re-run this script.")
    rc = main(["cad-status", pkg])
    if rc:
        raise SystemExit(rc)
    rc = main(["drawings", pkg])
    if rc:
        raise SystemExit(rc)
    raise SystemExit(main(["package", pkg] + (["--no-tests"] if a.no_tests else [])))
