"""Shared helpers for the tests."""

from __future__ import annotations

import copy

from pressure_vessel.codes.asme_viii_1 import design
from pressure_vessel.inputs import read_input, validate_vessel
from pressure_vessel.materials import MaterialDatabase
from pressure_vessel.references import ReferenceRegister

from . import EXAMPLES, FIXTURES

DEMO = EXAMPLES / "PV-DEMO-001" / "vessel_input.yaml"
TANK = EXAMPLES / "TK-DEMO-001" / "tank_input.yaml"
MINIMAL = FIXTURES / "verified_minimal.yaml"


def demo_raw():
    return read_input(DEMO)


def run_raw(raw, verify_all_refs=False):
    mdb, refs = MaterialDatabase.load(), ReferenceRegister.load()
    raw = copy.deepcopy(raw)
    if verify_all_refs:
        raw["code_reference_verification"] = {"verified": [
            {"id": rid, "edition": "TEST", "verified_by": "TEST FIXTURE", "verified_on": "2026-10-23"}
            for rid in refs.entries]}
    vi, rep = validate_vessel(raw, mdb)
    if vi is None:
        raise AssertionError("validation failed: " + "; ".join(map(str, rep.errors)))
    out = design.run(vi, refs, mdb, rep)
    return vi, rep, out, refs


def rec(out, cid):
    return next(r for r in out["records"] if r.calc_id == cid)
