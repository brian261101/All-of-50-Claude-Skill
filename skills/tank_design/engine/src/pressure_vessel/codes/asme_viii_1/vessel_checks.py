"""Vessel-level records: MAWP (UG-98), pressure test (UG-99/UG-100), weights,
volume, centre of gravity, support and lifting loads, load cases that are not
implemented, MDMT, PWHT and fatigue status."""

from __future__ import annotations

import math

from ...geometry.profiles import HeadProfile
from ...geometry.vessel import centre_of_gravity
from ...status import RecordKind
from ...trace import CalcRecord
from .context import Ctx, hydrostatic

MM, MPA, KG, N = "mm", "MPa", "kg", "N"


def mawp_record(ctx: Ctx):
    p = ctx.vi.process
    rec = CalcRecord("MAWP", "Vessel", "Maximum allowable working pressure (UG-98)",
                     method="lowest part MAWP referred to the top of the vessel (corroded, hot)",
                     references=["ASME8-1:UG-98"], criterion="MAWP >= design pressure")
    for k, v in sorted(ctx.mawp_parts.items(), key=lambda kv: kv[1]):
        rec.mid(f"MAWP[{k}]", v, MPA)
    missing = [r.component for r in ctx.records
               if r.calc_id.endswith("-FLG") and r.criterion_met is None]
    if not ctx.mawp_parts:
        ctx.add(rec.finalize(not_evaluated_reason="no component MAWP available"))
        return None
    gov = min(ctx.mawp_parts, key=ctx.mawp_parts.get)
    mawp = rec.res("MAWP", ctx.mawp_parts[gov], MPA, f"governed by {gov}")
    rec.res("governing", gov)
    rec.inp("P_design", p.design_pressure, MPA)
    rec.criterion_met = mawp >= p.design_pressure - 1e-12
    extra = []
    if missing:
        extra.append("flange ratings missing for " + ", ".join(sorted(set(missing))) + " (MAWP may be lower)")
    no_pmax = [r.component for r in ctx.records if r.calc_id.endswith("-UG37") and
               not any(tv.symbol == "P_max_opening" for tv in r.results)]
    if no_pmax:
        extra.append("opening MAWP not computed for " + ", ".join(no_pmax))
    extra += ctx.mawp_notes
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, [], extra)))
    return mawp


def test_records(ctx: Ctx, mawp):
    p, vi = ctx.vi.process, ctx.vi
    factor = 1.3 if p.test_type == "hydrostatic" else 1.1
    ref = "ASME8-1:UG-99(b)" if p.test_type == "hydrostatic" else "ASME8-1:UG-100"
    rec = CalcRecord("TEST-P", "Vessel", f"{p.test_type.capitalize()} test pressure",
                     kind=RecordKind.COMPUTATION, method=f"{factor} x basis pressure x LSR", references=[ref])
    ratios = {}
    for key, ma in vi.materials.items():
        if ma.record is None:
            continue
        used = any(key in r.materials for r in ctx.records if r.code_family == "ASME_VIII_1" and not r.calc_id.startswith("MAT-"))
        if not used:
            continue
        Sd, _ = ctx.S(key, p.design_temperature)
        St, _ = ctx.S(key, p.test_temperature)
        if Sd and St:
            ratios[key] = St / Sd
            rec.mid(f"S_test/S_design[{key}]", St / Sd, "-")
    if not ratios:
        ctx.add(rec.finalize())
        return None
    lsr = rec.mid("LSR", min(ratios.values()), "-", "lowest stress ratio of the pressure-part materials")
    basis = mawp if p.test_basis == "MAWP" else p.design_pressure
    if basis is None:
        rec.warnings.append("MAWP not available; test pressure not computed")
        ctx.add(rec.finalize())
        return None
    rec.inp("basis", p.test_basis)
    rec.inp("P_basis", basis, MPA)
    Pt = rec.res("P_test_top", factor * basis * lsr, MPA, "minimum test pressure at the top of the vessel")
    rec.eq(f"P_test = {factor} x P_basis x LSR", f"{factor} x {basis:.4f} x {lsr:.4f} = {Pt:.4f} MPa")
    if p.test_basis == "design_pressure":
        rec.warnings.append("design-pressure basis is permitted by the UG-99(b) footnote only when the MAWP "
                            "is not calculated; confirm with the Inspector")
    H = ctx.geometry["vessel"]["inside_height"]
    if p.test_type == "hydrostatic":
        dh = hydrostatic(H if p.test_position == "vertical" else ctx.vi.geometry.inside_diameter, p.test_fluid_density)
        rec.mid("test_head", dh, MPA, f"water head over {('inside height' if p.test_position == 'vertical' else 'diameter')}")
        rec.res("P_test_bottom", Pt + dh, MPA, f"at the lowest point, test in {p.test_position} position")
    ctx.add(rec.finalize())

    # informational membrane stress during the test (not a VIII-1 acceptance rule here)
    s = CalcRecord("TEST-STRESS", "Vessel", "Shell membrane stress during the test (informational)",
                   method="sigma = P (R + 0.6 t)/(E t) at the lowest course vs 0.9 x min. yield (room temperature)",
                   references=["ASME2D:TableY1", ref], mandatory=False,
                   criterion="sigma_test <= 0.9 Sy (screening limit; confirm the governing limit with the Inspector)")
    c0 = vi.geometry.shell_courses[0]
    ma = vi.materials[c0.material]
    t = ctx.available.get(c0.id)
    Pb = Pt + (hydrostatic(H, p.test_fluid_density) if p.test_type == "hydrostatic" and p.test_position == "vertical" else 0.0)
    E = ctx.joint_E.get("shell_longitudinal")
    Sy = ma.record.min_yield if ma.record else None
    if t is None or E is None or not Sy:
        ctx.add(s.finalize(not_evaluated_reason="thickness, E or yield not available"))
        return Pt
    R = vi.geometry.inside_diameter / 2 + p.corrosion_allowance
    sig = s.res("sigma_test", Pb * (R + 0.6 * t) / (E * t), MPA)
    s.inp("Sy", Sy, MPA, "minimum yield (material record; room temperature)", source=f"MAT-{c0.material}")
    s.res("ratio", sig / (0.9 * Sy), "-")
    s.criterion_met = sig <= 0.9 * Sy
    ctx.add(s.finalize(unverified=["screening limit is not a verified VIII-1 acceptance criterion"]
                       + ctx.unverified(s.references, [c0.material])))
    return Pt


def weight_records(ctx: Ctx):
    geo, p = ctx.geometry, ctx.vi.process
    rec = CalcRecord("WT", "Vessel", "Weights, volume and centre of gravity", kind=RecordKind.COMPUTATION,
                     method="exact profiles + quadrature per component (geometry/profiles.py); rho from material records",
                     references=["GEN:mechanics"])
    W_empty, cg = centre_of_gravity(geo)
    for grp in sorted({c["bom_group"] for c in geo["components"]}):
        rec.mid(f"mass[{grp}]", sum(c["mass_kg"] or 0 for c in geo["components"] if c["bom_group"] == grp), KG)
    missing = [c["tag"] for c in geo["components"] if c["mass_kg"] is None]
    if missing:
        rec.warnings.append("no density for " + ", ".join(missing) + ": excluded from weights")
    V = geo["vessel"]["internal_volume_mm3"]
    rec.res("W_empty", W_empty, KG, "net theoretical, fabricated (no internals, no insulation, no bolting/gaskets)")
    rec.res("CG_empty_z", cg[2], MM, "above grade")
    rec.res("V_internal", V / 1e9, "m3")
    contents = 0.0
    if p.liquid_level is not None and p.liquid_density is not None:
        g = ctx.vi.geometry
        a = g.inside_diameter / 2
        h = p.liquid_level
        if h > g.tangent_to_tangent:
            rec.warnings.append("liquid level above the top tangent line: liquid in the top head not included")
            h = g.tangent_to_tangent
        hb = g.heads["bottom"]
        prof = HeadProfile(hb.type, a, hb.aspect_ratio or 2.0, hb.crown_radius or 0.0, hb.knuckle_radius or 0.0)
        V_liq = rec.mid("V_liquid", (prof.solid_volume(0.0)[0] + math.pi * a * a * h) / 1e9, "m3",
                        "bottom head below BTL + cylinder up to the liquid level")
        contents = V_liq * p.liquid_density
    elif p.fluid_phase == "gas":
        rec.warnings.append("gas contents mass not included (no gas density in the design basis)")
    W_op = rec.res("W_operating", W_empty + contents, KG)
    W_test = rec.res("W_test", W_empty + V * (p.test_fluid_density or 0) * 1e-9, KG,
                     f"vessel full of test fluid ({p.test_fluid_density or 0:g} kg/m3)")
    ctx.add(rec.finalize())
    if p.required_volume:
        v = CalcRecord("VOL-REQ", "Vessel", "Internal volume vs required volume", code_family="PROJECT",
                       method="internal volume from exact head profiles", references=["PROJECT:requirement"],
                       criterion="V_internal >= V_required")
        v.inp("V_required", p.required_volume / 1e9, "m3")
        v.res("V_internal", V / 1e9, "m3")
        v.criterion_met = V >= p.required_volume
        ctx.add(v.finalize(unverified=ctx.unverified(v.references)))
    return {"empty": W_empty, "operating": W_op, "test": W_test, "cg_empty": cg}


def support_records(ctx: Ctx, w):
    legs = ctx.vi.geometry.legs
    loads = ctx.vi.loads
    if legs is None:
        return
    rec = CalcRecord("SUP-REACT", "Supports", f"Leg reactions, {legs.count} legs", kind=RecordKind.COMPUTATION,
                     method="vertical: W/n per leg; overturning: 4M/(n Dbc) when a base moment is given",
                     references=["GEN:mechanics"])
    g0 = 9.80665
    n = legs.count
    leg_c = next(c for c in ctx.geometry["components"] if c["kind"] == "leg")
    Dbc = rec.mid("D_bc", 2 * leg_c["params"]["radius"], MM, "leg circle diameter")
    for case in ("empty", "operating", "test"):
        rec.res(f"F_vert_{case}", w[case] * g0 / n, N, f"{case} weight / {n}")
    for lk in ("wind", "seismic"):
        li = loads.get(lk)
        if li and li.provided and "base_moment" in li.values:
            M = li.values["base_moment"]
            rec.res(f"dF_{lk}", 4 * M / (n * Dbc), N, f"4 M/(n Dbc), M = {M / 1e6:.1f} kN.m ({li.basis})")
    ctx.add(rec.finalize())
    s = CalcRecord("SUP-STRUCT", "Supports", "Leg, base plate and leg-to-shell attachment strength",
                   method="structural design of legs (column buckling, base plate, local shell stress)",
                   references=["GEN:mechanics"], criterion="member and local stresses within the project's structural code")
    s.questions.append("state the structural code (e.g. AISC 360 / TCVN 5575) and complete wind/seismic loads; "
                       "leg buckling, base plate and local shell stresses (WRC 537) are not implemented")
    ctx.add(s.finalize(out_of_scope="support structural design is not implemented in v0.1"))


def lug_records(ctx: Ctx, w):
    lugs = ctx.vi.geometry.lugs
    if lugs is None:
        return
    li = ctx.vi.loads.get("lifting")
    rec = CalcRecord("LUG-LOAD", "Lifting lugs", "Lifting load per lug", kind=RecordKind.COMPUTATION,
                     method="F = W_empty g x impact factor / n, vertical slings", references=["GEN:mechanics"])
    if not li or not li.provided or "impact_factor" not in li.values:
        rec.warnings.append("impact factor not given: lug load not computed")
        ctx.add(rec.finalize())
        return
    k = rec.inp("impact_factor", li.values["impact_factor"], "-", li.basis)
    F = rec.res("F_lug", w["empty"] * 9.80665 * k / lugs.count, N)
    rec.warnings.append("vertical slings assumed (spreader beam); a sling angle increases the lug load")
    ctx.add(rec.finalize())
    c = CalcRecord("LUG-CHECK", "Lifting lugs", "Lifting lug plate (basic strength of materials)",
                   code_family="GENERAL", method="net-section tension (W - dh) t and double-plane tear-out above the hole",
                   references=["GEN:lug-basic"], materials=[lugs.material],
                   criterion="sigma_t <= allowable tension and tau <= allowable shear (user-supplied)")
    al = lugs.allowables
    if not al:
        c.questions.append("give the lug allowable stresses and their basis (e.g. ASME BTH-1 design category)")
        ctx.add(c.finalize(not_evaluated_reason="allowable stresses not supplied"))
    else:
        t, Wd, dh = lugs.thickness, lugs.projection, lugs.hole_diameter
        st = c.res("sigma_t", F / ((Wd - dh) * t), MPA)
        a = lugs.height / 2 - dh / 2
        tau = c.res("tau", F / (2 * a * t), MPA)
        c.criterion_met = st <= al["tension"] and tau <= al["shear"]
        ctx.add(c.finalize(unverified=["indicative method, not ASME BTH-1"] + ctx.unverified(c.references, [lugs.material])))
    for cid, title in (("LUG-WELD", "Lug-to-shell weld"), ("LUG-LOCAL", "Local shell stress at the lugs (WRC 537)")):
        r = CalcRecord(cid, "Lifting lugs", title, method="not implemented", references=["GEN:lug-basic"])
        ctx.add(r.finalize(out_of_scope="not implemented in v0.1"))


def load_status_records(ctx: Ctx):
    vi = ctx.vi
    for key, title in (("wind", "Wind load"), ("seismic", "Seismic load"), ("piping_loads", "Nozzle piping loads"),
                       ("transport", "Transport loads"), ("snow", "Snow load"), ("thermal", "Thermal loads")):
        li = vi.loads.get(key)
        rec = CalcRecord(f"LOAD-{key.upper()}", "Loads", f"{title} (UG-22)",
                         method="combined primary stresses under the load (UG-22, UG-23)",
                         references=["ASME8-1:UG-22"], mandatory=key in ("wind", "seismic", "piping_loads"))
        if li and li.not_applicable_reason:
            rec.mandatory = False
            rec.status_reasons.append(f"declared not applicable: {li.not_applicable_reason}")
            ctx.add(rec.finalize(not_evaluated_reason=f"declared not applicable: {li.not_applicable_reason}"))
        elif li and li.provided:
            ctx.add(rec.finalize(out_of_scope="loads received, but the combined-stress check (UG-23(b) compressive "
                                              "allowable needs factor B) is not implemented in v0.1"))
        else:
            rec.questions.append({"wind": "give the wind base shear and base moment with the standard used "
                                          "(e.g. ASCE 7 / TCVN 2737), or declare not_applicable with a reason",
                                  "seismic": "give the seismic base shear and moment (standard, site class), or "
                                             "declare not_applicable with a reason",
                                  "piping_loads": "give the nozzle piping loads, or declare not_applicable"}.get(
                key, f"{title.lower()}: give values with their basis, or declare not_applicable"))
            ctx.add(rec.finalize(not_evaluated_reason="not provided"))
    p, fab = vi.process, vi.fabrication
    m = CalcRecord("MDMT", "Materials", f"MDMT {p.mdmt:g} degC: impact test exemption (UCS-66)",
                   method="UCS-66 curve / UCS-66.1 reduction for each pressure part", references=["ASME8-1:UCS-66"],
                   criterion="each pressure part exempt at the MDMT or impact tested")
    if fab.mdmt_assessment:
        a = fab.mdmt_assessment
        m.inp("assessment", a["result"], source=f"USER ({a['by']}: {a['basis']})")
        ok = str(a["result"]).lower() in ("exempt", "impact_tested", "pass")
        m.criterion_met = ok
        ctx.add(m.finalize(unverified=["user-supplied MDMT assessment"]))
    else:
        m.questions.append(f"give the UCS-66 assessment of every pressure part at MDMT {p.mdmt:g} degC "
                           "(curve, governing thickness, exemption or impact test)")
        ctx.add(m.finalize(not_evaluated_reason="UCS-66 curves not available to the software"))
    w = CalcRecord("PWHT", "Fabrication", "Postweld heat treatment requirement (UCS-56)",
                   method="UCS-56 by P-No. and governing thickness; service requirements", references=["ASME8-1:UCS-56"],
                   criterion="PWHT requirement determined")
    if fab.pwht_assessment:
        w.inp("assessment", fab.pwht_assessment["result"], source=f"USER ({fab.pwht_assessment['by']})")
        w.criterion_met = True
        ctx.add(w.finalize(unverified=["user-supplied PWHT assessment"]))
    else:
        w.questions.append("give the PWHT determination (UCS-56 / service requirements)")
        ctx.add(w.finalize(not_evaluated_reason="not determined"))
    f = CalcRecord("FATIGUE", "Vessel", "Fatigue / cyclic service screening", method="UG-22 cyclic loading",
                   references=["ASME8-1:UG-22"])
    if p.cyclic_service is False:
        f.mandatory = False
        ctx.add(f.finalize(not_evaluated_reason="not required: design basis states non-cyclic service"))
    elif p.cyclic_service is True:
        ctx.add(f.finalize(out_of_scope="cyclic service: fatigue analysis not implemented"))
    else:
        f.questions.append("state whether the vessel is in cyclic service")
        ctx.add(f.finalize(not_evaluated_reason="service type not stated"))
