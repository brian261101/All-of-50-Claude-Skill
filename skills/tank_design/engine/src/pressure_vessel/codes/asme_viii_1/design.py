"""ASME VIII-1 vessel calculation orchestrator and release gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from ... import __version__
from ...geometry.vessel import build_geometry
from ...inputs.models import VesselInput
from ...materials import MaterialDatabase
from ...references import ReferenceRegister
from ...status import DesignStage, RecordKind, Status, aggregate
from . import components, external, nozzles, vessel_checks
from .context import Ctx


def run(vi: VesselInput, refs: ReferenceRegister, matdb: MaterialDatabase, validation=None) -> dict:
    if vi.reference_verification:
        problems = refs.apply_verification(vi.reference_verification)
        if problems:
            raise ValueError("code_reference_verification: " + "; ".join(problems))
    ctx = Ctx(vi, refs, matdb)
    components.material_records(ctx)
    components.joint_records(ctx)
    components.shell_records(ctx)
    components.head_records(ctx)
    missing = [k for k in [c.id for c in vi.geometry.shell_courses] + ["top", "bottom"] if k not in ctx.selected]
    geometry = None
    if not missing:
        ctx.geometry = geometry = build_geometry(vi, ctx.selected)
        nozzles.nozzle_records(ctx)
        external.external_records(ctx)
    mawp = vessel_checks.mawp_record(ctx)
    weights = None
    test_p = None
    if geometry:
        test_p = vessel_checks.test_records(ctx, mawp)
        weights = vessel_checks.weight_records(ctx)
        vessel_checks.support_records(ctx, weights)
        vessel_checks.lug_records(ctx, weights)
    vessel_checks.load_status_records(ctx)
    apply_assessments(ctx)
    for r in ctx.records:
        for rid in r.references:
            refs.get(rid)          # every cited id must exist in the register
    results = assemble(vi, refs, matdb, ctx, mawp, test_p, weights, validation)
    if geometry:
        geometry["results_hash"] = results["results_hash"]
    return {"results": results, "geometry": geometry, "records": ctx.records}


def apply_assessments(ctx: Ctx):
    """Replace NOT_EVALUATED / OUT_OF_SCOPE status of a check by a recorded
    external engineering assessment. The record keeps the original method
    text and states that the result comes from outside the software."""
    from ...inputs.schema import ASSESSMENT_OK
    from ...status import DataStatus
    by_id = {r.calc_id: r for r in ctx.records}
    for cid, a in ctx.vi.assessments.items():
        r = by_id.get(cid)
        if r is None:
            raise ValueError(f"assessment for unknown calc id {cid!r}")
        if r.kind != RecordKind.CHECK or r.status not in (Status.NOT_EVALUATED, Status.OUT_OF_SCOPE):
            raise ValueError(f"assessment for {cid}: only NOT_EVALUATED/OUT_OF_SCOPE checks can take one "
                             f"(current status {r.status_text})")
        r.method = f"EXTERNAL ASSESSMENT ({a['basis']}) — software scope: {r.method}"
        r.inp("assessment", a["result"], source=f"USER {a['status']} by {a['by']} {a.get('date', '')}".strip())
        r.status_reasons = [f"evaluated outside the software: {a['basis']}"]
        r.questions = []
        r.criterion_met = a["result"].strip().lower() in ASSESSMENT_OK
        unv = [] if DataStatus(a["status"]).release_eligible else [f"assessment {a['status']}"]
        r.finalize(unverified=ctx.unverified(r.references, r.materials, unv))


def _counts(records):
    out = {s.value: 0 for s in Status}
    out["COMPUTED"] = 0
    for r in records:
        out["COMPUTED" if r.kind == RecordKind.COMPUTATION else r.status.value] += 1
    return out


def release_gate(vi: VesselInput, records, refs: ReferenceRegister, verification: dict | None = None) -> dict:
    checks = [r for r in records if r.kind == RecordKind.CHECK]
    blockers = []
    fails = [r.calc_id for r in checks if r.status == Status.FAIL]
    if fails:
        blockers.append(f"FAIL: {', '.join(fails)}")
    open_ = [f"{r.calc_id} ({r.status})" for r in checks
             if r.mandatory and r.status in (Status.NOT_EVALUATED, Status.OUT_OF_SCOPE, Status.NEEDS_ENGINEERING_REVIEW)]
    if open_:
        blockers.append(f"mandatory checks not PASS: {len(open_)}")
    used = sorted({rid for r in records for rid in r.references})
    unref = refs.summary(used)["unverified_ids"]
    if unref:
        blockers.append(f"code references not verified against the licensed edition: {len(unref)} of {len(used)}")
    unmat = sorted({f"{k} ({m.data_status})" for k, m in vi.materials.items()
                    if m.data_status not in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED")})
    if unmat:
        blockers.append("material data not release eligible: " + ", ".join(unmat))
    if vi.project.data_status != "USER_CONFIRMED":
        blockers.append(f"input data status is {vi.project.data_status}")
    if not vi.design_basis.locked:
        blockers.append("design basis not locked (inputs not confirmed by the user)")
    if verification is None:
        blockers.append("verification suite not run for this result set")
    elif not verification.get("passed"):
        blockers.append("verification suite reported discrepancies")
    stage = DesignStage.PRELIMINARY if blockers else DesignStage.CALCULATION_VERIFIED
    return {"stage": str(stage), "blockers": blockers, "open_mandatory": open_, "fails": fails,
            "fabrication_release": "NOT RELEASED — requires CALCULATION_VERIFIED plus signed engineering "
                                   "review and approval by a qualified engineer (never set by software)"}


def assemble(vi, refs, matdb, ctx: Ctx, mawp, test_p, weights, validation) -> dict:
    recs = [r.to_dict() for r in ctx.records]
    used = sorted({rid for r in ctx.records for rid in r.references})
    by_comp = {}
    for r in ctx.records:
        if r.kind == RecordKind.CHECK:
            by_comp.setdefault(r.component, []).append(r.status)
    questions = []
    if validation is not None:
        questions += [f"{q.field}: {q.message}" for q in validation.questions]
    for r in ctx.records:
        questions += [f"{r.calc_id}: {q}" for q in r.questions]
    body = {
        "schema": "pv-design/results@1",
        "software": {"name": "pressure_vessel", "version": __version__},
        "project": asdict(vi.project), "design_basis": asdict(vi.design_basis),
        "input_file": vi.source_path, "input_hash": vi.input_hash,
        "code": {"design_code": vi.project.design_code, "edition": vi.project.code_edition,
                 "addenda": vi.project.addenda},
        "material_db": {"version": matdb.version, "path": matdb.path,
                        "used": {k: (m.record.to_dict() if m.record else
                                     {"id": k, "name": m.spec, "status": m.status, "density_kg_m3": m.density,
                                      "source_document": "project input (non-pressure)"})
                                 for k, m in vi.materials.items()}},
        "reference_register": refs.summary(used),
        "references_used": [asdict(refs.get(r)) for r in used],
        "records": recs,
        "summary": {"counts": _counts(ctx.records),
                    "by_component": {k: str(aggregate(v)) for k, v in by_comp.items()}},
        "selected_thickness_mm": ctx.selected, "available_thickness_mm": ctx.available,
        "joint_efficiencies": ctx.joint_E,
        "mawp_MPa": mawp, "mawp_parts_MPa": ctx.mawp_parts, "test_pressure_top_MPa": test_p,
        "weights_kg": None if weights is None else {k: v for k, v in weights.items() if k != "cg_empty"},
        "cg_empty_mm": None if weights is None else list(weights["cg_empty"]),
        "questions": questions,
        "validation": None if validation is None else validation.to_dict(),
    }
    body["results_hash"] = hashlib.sha256(json.dumps(recs, sort_keys=True, default=str).encode()).hexdigest()
    body["gate"] = release_gate(vi, ctx.records, refs, None)
    return body
