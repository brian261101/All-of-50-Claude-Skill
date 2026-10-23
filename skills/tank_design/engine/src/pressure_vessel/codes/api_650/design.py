"""API 650 storage tank calculations (separate code family).

Implemented: scope gate against project-stated limits, shell course
thickness by the 1-foot method (design and hydrostatic test cases), minimum
nominal thickness from the user-confirmed table, Sd/St cross-check against
the stated derivation rule, bottom minimum thickness, weights and capacity.
Everything else (variable-design-point method, roof, wind girders,
anchorage, Annex E seismic, settlement, nozzles) is listed as NOT_EVALUATED
or OUT_OF_SCOPE.

SI form of the 1-foot method: D in m, H in m, S in MPa, t in mm:
    td = 4.9 D (H - 0.3) G / Sd + CA        tt = 4.9 D (H - 0.3) / St
"""

from __future__ import annotations

import hashlib
import json
import math

from ... import __version__
from ...inputs.tank_schema import TankInput
from ...references import ReferenceRegister
from ...status import RecordKind, Status
from ...trace import CalcRecord

MM, MPA = "mm", "MPa"


def _unver(refs, ids, extra=()):
    return list(refs.unverified(ids)) + list(extra)


def one_foot_td(D_m, H_m, G, Sd, CA):
    return 4.9 * D_m * (H_m - 0.3) * G / Sd + CA


def one_foot_tt(D_m, H_m, St):
    return 4.9 * D_m * (H_m - 0.3) / St


def run(ti: TankInput, refs: ReferenceRegister, validation=None) -> dict:
    recs: list[CalcRecord] = []
    rules_unv = [] if ti.rules_status in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED") else \
        [f"API 650 constants (min thickness table, bottom minimum) {ti.rules_status}"]

    sc = CalcRecord("API-SCOPE", "Tank", "API 650 applicability", code_family="API_650",
                    method="design conditions vs project-stated limits of the API 650 part used",
                    references=["API650:1.1"], criterion="internal/external pressure and temperature within the stated limits")
    lim = ti.scope_limits
    sc.inp("P_internal", ti.internal_pressure, MPA)
    sc.inp("P_external", ti.external_pressure, MPA)
    sc.inp("T_max", ti.max_temp, "degC")
    for k, v in lim.items():
        sc.inp(k, v, "", lim.get("basis", ""))
    if None in (lim["max_internal_pressure"], lim["max_external_pressure"], lim["max_temperature"]):
        sc.questions.append("state the scope limits of the API 650 part used, from the licensed edition")
        recs.append(sc.finalize(not_evaluated_reason="scope limits not stated"))
        in_scope = None
    else:
        in_scope = (ti.internal_pressure <= lim["max_internal_pressure"] and
                    ti.external_pressure <= lim["max_external_pressure"] and ti.max_temp <= lim["max_temperature"])
        if not in_scope:
            recs.append(sc.finalize(out_of_scope="design conditions outside the stated API 650 limits: select another "
                                                 "code (e.g. API 620, ASME VIII) — no API 650 result is produced"))
        else:
            sc.criterion_met = True
            recs.append(sc.finalize(unverified=_unver(refs, sc.references, ["scope limits stated by the user"])))
    if in_scope is False:
        return _assemble(ti, refs, recs, validation)

    D_m = ti.D / 1000.0
    tmin_tab = next((t for dmax, t in ti.rules["min_shell_thickness"] if ti.D <= dmax), None)
    one_ft_max = ti.rules["one_foot_max_diameter"]
    z = 0.0
    selected = {}
    for cc in ti.courses:          # bottom to top
        m = ti.materials[cc.material]
        rec = CalcRecord(f"API-SH-{cc.id}", f"Shell course {cc.id}", f"Shell course {cc.id}, 1-foot method",
                         code_family="API_650", method="5.6.3 1-foot method, design and hydrostatic test",
                         references=["API650:5.6.3", "API650:5.6.1.1", "API650:5.6.2.1"],
                         criterion="t_nom >= max(td, tt, t_min)")
        H_m = rec.inp("H", (ti.H - z) / 1000.0, "m", "design liquid level above the bottom of this course")
        rec.inp("D", D_m, "m")
        rec.inp("G", ti.G, "-")
        rec.inp("CA", ti.ca_shell, MM)
        Sd = rec.inp("Sd", m.Sd, MPA, m.source, source=f"MATERIAL {m.status}")
        St = rec.inp("St", m.St, MPA, m.source, source=f"MATERIAL {m.status}")
        z += cc.height
        if one_ft_max is None:
            rec.questions.append("1-foot method diameter limit not stated")
            recs.append(rec.finalize(not_evaluated_reason="method limit not stated"))
            continue
        if ti.D > one_ft_max:
            recs.append(rec.finalize(out_of_scope="diameter above the 1-foot method limit: variable-design-point "
                                                  "method not implemented"))
            continue
        if Sd is None or St is None or tmin_tab is None:
            rec.questions.append("Sd, St and the minimum thickness table are needed")
            recs.append(rec.finalize(not_evaluated_reason="Sd/St/minimum thickness missing"))
            continue
        if H_m <= 0.3:
            td = tt = 0.0
        else:
            td = rec.mid("td", one_foot_td(D_m, H_m, ti.G, Sd, ti.ca_shell), MM)
            tt = rec.mid("tt", one_foot_tt(D_m, H_m, St) if ti.G_test == 1.0 else one_foot_tt(D_m, H_m, St) * ti.G_test, MM)
            rec.eq("td = 4.9 D (H - 0.3) G / Sd + CA", f"4.9 x {D_m:.3f} x ({H_m:.3f} - 0.3) x {ti.G:g} / {Sd:.1f} + {ti.ca_shell:g} = {td:.3f} mm")
            rec.eq("tt = 4.9 D (H - 0.3) / St", f"4.9 x {D_m:.3f} x ({H_m:.3f} - 0.3) / {St:.1f} = {tt:.3f} mm")
        rec.mid("t_min_table", tmin_tab, MM, "5.6.1.1 (user-confirmed table)")
        need = rec.mid("t_required", max(td, tt, tmin_tab), MM)
        extra = list(rules_unv)
        if m.Fy and m.Fu:
            sd_rule = min(2 / 3 * m.Fy, 2 / 5 * m.Fu)
            st_rule = min(3 / 4 * m.Fy, 3 / 7 * m.Fu)
            rec.mid("Sd_rule", sd_rule, MPA, "min(2/3 Fy, 2/5 Fu) cross-check")
            rec.mid("St_rule", st_rule, MPA, "min(3/4 Fy, 3/7 Fu) cross-check")
            if Sd > sd_rule + 0.5 or St > st_rule + 0.5:
                rec.warnings.append("stated Sd/St exceed the derivation rule: verify against Table 5-2")
                extra.append("Sd/St inconsistent with the derivation rule")
        if cc.nominal_thickness is None:
            t_nom = next((t for t in ti.plate_thicknesses if t >= need - 1e-9), None)
            if t_nom is None:
                rec.criterion_met = False
                recs.append(rec.finalize())
                continue
        else:
            t_nom = cc.nominal_thickness
        rec.res("t_nom", t_nom, MM)
        rec.res("margin", t_nom - need, MM)
        rec.criterion_met = t_nom >= need - 1e-9
        selected[cc.id] = t_nom
        if m.status not in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED"):
            extra.append(f"material {m.key} {m.status}")
        recs.append(rec.finalize(unverified=_unver(refs, rec.references, extra)))

    b = CalcRecord("API-BOTTOM", "Bottom", "Bottom plate minimum thickness", code_family="API_650",
                   method="5.4.1 minimum + corrosion allowance", references=["API650:5.4.1"],
                   criterion="t_bottom >= t_min + CA")
    tbm = ti.rules["bottom_min_thickness"]
    if ti.bottom_thickness is None or tbm is None:
        recs.append(b.finalize(not_evaluated_reason="bottom thickness or rule value missing"))
    else:
        b.inp("t_bottom", ti.bottom_thickness, MM)
        b.mid("t_min", tbm + ti.ca_bottom, MM)
        b.criterion_met = ti.bottom_thickness >= tbm + ti.ca_bottom - 1e-9
        bm = ti.materials.get(ti.bottom_material)
        recs.append(b.finalize(unverified=_unver(refs, b.references, rules_unv +
                                                 ([f"material {bm.key} {bm.status}"] if bm and bm.status not in
                                                  ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED") else []))))

    w = CalcRecord("API-WT", "Tank", "Shell and bottom weights, capacity", code_family="API_650",
                   kind=RecordKind.COMPUTATION, method="plate volumes x density", references=["GEN:mechanics"])
    Ws = 0.0
    for cc in ti.courses:
        if cc.id in selected:
            m = ti.materials[cc.material]
            Ws += math.pi * (ti.D + selected[cc.id]) * selected[cc.id] * cc.height * m.density * 1e-9
    w.res("W_shell", Ws, "kg", "shell courses at mean diameter")
    if ti.bottom_thickness:
        bm = ti.materials.get(ti.bottom_material)
        w.res("W_bottom", math.pi / 4 * ti.D ** 2 * ti.bottom_thickness * (bm.density if bm else 0) * 1e-9, "kg",
              "flat bottom to the shell diameter (projection and lap not included)")
    w.res("V_design", math.pi / 4 * ti.D ** 2 * ti.H / 1e9, "m3", "to the design liquid level")
    w.res("W_test_water", math.pi / 4 * ti.D ** 2 * ti.H * 1000 * ti.G_test * 1e-9, "kg")
    recs.append(w.finalize())

    for cid, title in (("API-ROOF", f"Roof ({ti.roof})"), ("API-WIND-GIRDER", "Top angle / wind girders (5.9)"),
                       ("API-WIND", "Wind overturning and sliding (5.11)"), ("API-SEISMIC", "Seismic design (Annex E)"),
                       ("API-ANCHOR", "Anchorage (5.12)"), ("API-NOZZLES", "Shell openings and reinforcement (5.7)"),
                       ("API-ANNULAR", "Annular bottom plates (5.5)"), ("API-SETTLEMENT", "Foundation / settlement")):
        r = CalcRecord(cid, "Tank", title, code_family="API_650", method="not implemented in v0.1",
                       references=["API650:1.1"])
        recs.append(r.finalize(out_of_scope="not implemented in v0.1"))
    return _assemble(ti, refs, recs, validation, selected)


def _assemble(ti, refs, recs, validation, selected=None):
    used = sorted({r for rec in recs for r in rec.references})
    counts = {s.value: 0 for s in Status} | {"COMPUTED": 0}
    for r in recs:
        counts["COMPUTED" if r.kind == RecordKind.COMPUTATION else r.status.value] += 1
    rd = [r.to_dict() for r in recs]
    blockers = []
    if any(r.status == Status.FAIL for r in recs):
        blockers.append("FAIL present")
    if any(r.mandatory and r.kind == RecordKind.CHECK and r.status != Status.PASS for r in recs):
        blockers.append("mandatory checks not PASS")
    if refs.summary(used)["unverified_ids"]:
        blockers.append("code references not verified")
    blockers.append("verification suite not run for this result set")
    questions = [f"{q.field}: {q.message}" for q in validation.questions] if validation else []
    questions += [f"{r.calc_id}: {q}" for r in recs for q in r.questions]
    return {"results": {
        "schema": "pv-design/results@1", "software": {"name": "pressure_vessel", "version": __version__},
        "project": ti.project, "input_hash": ti.input_hash, "input_file": ti.source_path,
        "code": {"design_code": "API_650", "edition": ti.project.get("code_edition")},
        "records": rd, "summary": {"counts": counts}, "selected_thickness_mm": selected or {},
        "reference_register": refs.summary(used), "questions": questions,
        "results_hash": hashlib.sha256(json.dumps(rd, sort_keys=True, default=str).encode()).hexdigest(),
        "gate": {"stage": "PRELIMINARY", "blockers": blockers,
                 "fabrication_release": "NOT RELEASED — engineering review and approval required"}},
        "records": recs, "geometry": None}
