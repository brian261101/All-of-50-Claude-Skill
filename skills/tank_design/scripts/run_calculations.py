"""Validate, calculate and verify; writes 00_INPUT and 01_CALCULATION.

    python .claude/skills/tank_design/scripts/run_calculations.py <input.yaml> --out <package dir> [--pv-elite results.csv]

Exit 0 = calculated and verification passed (the design itself may still be
PRELIMINARY or contain FAILs: read the printed stage and blockers),
2 = input rejected, 3 = verification discrepancy.
"""

import argparse

from _common import bootstrap

bootstrap()
from pressure_vessel.cli import main  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pv-elite")
    a = ap.parse_args()
    args = ["calc", a.input, "--out", a.out] + (["--pv-elite", a.pv_elite] if a.pv_elite else [])
    raise SystemExit(main(args))
