"""Re-run the independent verification on a package's stored results (and an
optional PV Elite CSV), then the library unit tests.

    python .claude/skills/tank_design/scripts/run_verification.py <package dir> [--pv-elite results.csv] [--no-tests]

Writes 01_CALCULATION/verification.json and verification_report.md (the
release gate reads them on the next `calc`). Exit 0 = no discrepancies and
tests passed.
"""

import argparse
import json
from pathlib import Path

from _common import bootstrap, emit

bootstrap()
from pressure_vessel.package.manifest import run_tests  # noqa: E402
from pressure_vessel.verification.runner import run_verification, verification_markdown  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--pv-elite")
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args()
    pkg = Path(a.package)
    calc = pkg / "01_CALCULATION"
    res = json.loads((calc / "calculation_results.json").read_text(encoding="utf-8"))
    geo_p = calc / "design_geometry.json"
    geo = json.loads(geo_p.read_text(encoding="utf-8")) if geo_p.is_file() else None
    v = run_verification(res, geo, a.pv_elite)
    (calc / "verification.json").write_text(json.dumps(v, indent=1, default=str), encoding="utf-8")
    (calc / "verification_report.md").write_text(verification_markdown(v), encoding="utf-8")
    tests = None
    if not a.no_tests:
        (pkg / "05_QA").mkdir(parents=True, exist_ok=True)
        tests = run_tests(pkg)
    emit({"verification_passed": v["passed"], "checks": v["n_checks"], "discrepancies": v["discrepancies"],
          "pv_elite": v["pv_elite"], "tests": tests})
    raise SystemExit(0 if v["passed"] and (tests is None or tests["passed"]) else 3)
