"""External pressure: UG-28 (cylinders) and UG-33 (formed heads).

Factor A for cylinders (Fig. G) and factor B for every component (material
chart) must be supplied by the user from the licensed Section II-D, with the
source. Nothing is read from an approximation of those charts. Without the
data the checks are NOT_EVALUATED and the report prints the ratios the user
needs to enter the charts.
"""

from __future__ import annotations

from ...trace import CalcRecord
from .context import Ctx
from .formulas import OutOfScope

MM, MPA = "mm", "MPa"
K0_2TO1 = 0.90  # Table UG-33.1, D/2h = 2.0


def external_records(ctx: Ctx):
    p, g = ctx.vi.process, ctx.vi.geometry
    Pe = p.external_pressure
    data = ctx.vi.external_pressure_data
    if not Pe:
        rec = CalcRecord("EXT-NONE", "External pressure", "External pressure / vacuum",
                         method="design basis states no external pressure", references=["ASME8-1:UG-22"],
                         mandatory=False)
        rec.status_reasons.append("not required: no external pressure in the design basis (confirm no vacuum case)")
        ctx.add(rec.finalize(not_evaluated_reason="not required by the design basis"))
        return
    _shell(ctx, Pe, data.get("shell"))
    for pos in ("top", "bottom"):
        _head(ctx, pos, Pe, data.get("heads"))


def _shell(ctx: Ctx, Pe, chart):
    g, CA = ctx.vi.geometry, ctx.vi.process.corrosion_allowance
    rec = CalcRecord("EXT-SHELL", "Shell", "Cylindrical shell under external pressure",
                     method="UG-28(c)(1): Pa = 4B/(3 Do/t), or 2AE/(3 Do/t) left of the material line",
                     references=["ASME8-1:UG-28(c)(1)", "ASME8-1:UG-28(b)", "ASME2D:FigG", "ASME2D:MaterialCharts"],
                     materials=[g.shell_courses[0].material], criterion="Pa >= P_ext")
    rec.inp("P_ext", Pe, MPA)
    # governing course: the thinnest corroded course (same material assumed per course list)
    cid = min((c.id for c in g.shell_courses if c.id in ctx.available), key=lambda k: ctx.available[k], default=None)
    if cid is None:
        ctx.add(rec.finalize(not_evaluated_reason="shell thickness not established"))
        return
    t = rec.inp("t", ctx.available[cid], MM, f"corroded available thickness of {cid} (thinnest)", source=f"SH-{cid}")
    Do = rec.inp("Do", g.inside_diameter + 2 * ctx.selected[cid], MM, "outside diameter")
    hb = ctx.geometry["heads"]["bottom"]["inside_depth"]
    ht = ctx.geometry["heads"]["top"]["inside_depth"]
    L = rec.mid("L", g.tangent_to_tangent + (hb + ht) / 3, MM, "T/T + one third of each head depth, no stiffeners (UG-28(b))")
    LDo = rec.mid("L/Do", L / Do, "-")
    Dot = rec.mid("Do/t", Do / t, "-")
    if L / Do > 50:
        rec.mid("L/Do_used", 50.0, "-", "Fig. G entered at 50 for larger values")
    if Do / t < 10:
        ctx.add(rec.finalize(out_of_scope="Do/t < 10: UG-28(c)(2) not implemented"))
        return
    if not chart or ("B" not in chart and not (chart.get("left_of_material_line") and "A" in chart and "E" in chart)):
        rec.questions.append(f"read factor A from II-D Fig. G at L/Do = {min(LDo, 50):.3f} and Do/t = {Dot:.1f}, then "
                             f"factor B from the chart for the shell material at "
                             f"{ctx.vi.process.external_design_temperature:g} degC (or E if A is left of the line)")
        ctx.add(rec.finalize(not_evaluated_reason="chart factors A/B not supplied (never approximated)"))
        return
    rec.inp("A", chart.get("A"), "-", chart["source"], source=f"USER ({chart['status']})")
    if chart.get("left_of_material_line"):
        E = rec.inp("E", chart["E"], MPA, chart["source"], source=f"USER ({chart['status']})")
        Pa = rec.res("Pa", 2 * chart["A"] * E / (3 * Dot), MPA)
        rec.eq("Pa = 2 A E / (3 (Do/t))", f"2 x {chart['A']:.3e} x {E:.0f} / (3 x {Dot:.2f}) = {Pa:.4f} MPa")
    else:
        B = rec.inp("B", chart["B"], MPA, chart["source"], source=f"USER ({chart['status']})")
        Pa = rec.res("Pa", 4 * B / (3 * Dot), MPA)
        rec.eq("Pa = 4 B / (3 (Do/t))", f"4 x {B:.2f} / (3 x {Dot:.2f}) = {Pa:.4f} MPa")
    rec.res("margin", Pa - Pe, MPA)
    rec.criterion_met = Pa >= Pe - 1e-12
    extra = [] if chart["status"] in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED") else [f"chart readings {chart['status']}"]
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, rec.materials, extra)))


def _head(ctx: Ctx, pos, Pe, chart):
    g, CA = ctx.vi.geometry, ctx.vi.process.corrosion_allowance
    h = g.heads[pos]
    tag = f"HD-{pos.upper()[:3]}"
    if tag not in ctx.available:
        return
    t = ctx.available[tag]
    D = g.inside_diameter
    # part (a)(1): UG-32 thickness at 1.67 x external pressure, E = 1
    r1 = CalcRecord(f"EXT-{tag}-A1", f"{pos.capitalize()} head", f"{pos.capitalize()} head, external pressure UG-33(a)(1)",
                    method="UG-32 / App. 1-4 thickness with P = 1.67 P_ext and E = 1",
                    references=["ASME8-1:UG-33(a)(1)", "ASME8-1:App1-4(c)", "ASME8-1:App1-4(d)",
                                "ASME8-1:UG-32-hemispherical"], materials=[h.material],
                    criterion="t_avail >= t_req(1.67 P_ext)")
    from .components import _head_formula       # local import avoids a cycle
    S, how = ctx.S(h.material, ctx.vi.process.external_design_temperature)
    r1.inp("P_ext", Pe, MPA)
    r1.inp("S", S, MPA, how)
    if S is None:
        ctx.add(r1.finalize(not_evaluated_reason="allowable stress unavailable"))
    else:
        P = r1.mid("P_equiv", 1.67 * Pe, MPA, "1.67 x P_ext")
        Dc = D + 2 * CA
        try:
            treq, ftxt, sub, _, _ = _head_formula(h, P, Dc, Dc / 2, S, 1.0, CA)
            r1.eq(ftxt, sub)
            r1.mid("t_req", treq, MM)
            r1.res("t_avail", t, MM, source=tag)
            r1.criterion_met = t >= treq - 1e-9
            ctx.add(r1.finalize(unverified=ctx.unverified(r1.references, r1.materials)))
        except OutOfScope as exc:
            ctx.add(r1.finalize(out_of_scope=str(exc)))
    # part (a)(2): buckling with factor B
    r2 = CalcRecord(f"EXT-{tag}-A2", f"{pos.capitalize()} head", f"{pos.capitalize()} head, external pressure buckling",
                    method="UG-33: A = 0.125/(Ro/t); Pa = B/(Ro/t) or 0.0625 E/(Ro/t)^2",
                    references=["ASME8-1:UG-33(d)", "ASME2D:MaterialCharts"], materials=[h.material],
                    criterion="Pa >= P_ext")
    t_nom = ctx.selected[pos]
    Do = D + 2 * t_nom
    if h.type == "ellipsoidal":
        if abs(h.aspect_ratio - 2.0) > 1e-9:
            ctx.add(r2.finalize(out_of_scope="K0 (Table UG-33.1) only held for 2:1 heads in v0.1"))
            return
        r2.references.append("ASME8-1:TableUG-33.1")
        Ro = r2.mid("Ro", K0_2TO1 * Do, MM, "K0 Do, K0 = 0.90 (Table UG-33.1, 2:1)")
    elif h.type == "torispherical":
        Ro = r2.mid("Ro", h.crown_radius + t_nom, MM, "outside crown radius")
    else:
        Ro = r2.mid("Ro", Do / 2, MM, "outside radius")
    Rot = r2.mid("Ro/t", Ro / t, "-")
    A = r2.mid("A", 0.125 / Rot, "-", "A = 0.125/(Ro/t)")
    r2.eq("A = 0.125 / (Ro/t)", f"0.125 / {Rot:.2f} = {A:.4e}")
    if not chart or ("B" not in chart and not (chart.get("left_of_material_line") and "E" in chart)):
        r2.questions.append(f"read factor B for A = {A:.4e} from the {h.material} material chart at "
                            f"{ctx.vi.process.external_design_temperature:g} degC (or E if left of the line)")
        ctx.add(r2.finalize(not_evaluated_reason="chart factor B not supplied (never approximated)"))
        return
    if chart.get("left_of_material_line"):
        E = r2.inp("E", chart["E"], MPA, chart["source"], source=f"USER ({chart['status']})")
        Pa = r2.res("Pa", 0.0625 * E / Rot ** 2, MPA)
        r2.eq("Pa = 0.0625 E / (Ro/t)^2", f"= {Pa:.4f} MPa")
    else:
        B = r2.inp("B", chart["B"], MPA, chart["source"], source=f"USER ({chart['status']})")
        Pa = r2.res("Pa", B / Rot, MPA)
        r2.eq("Pa = B / (Ro/t)", f"{B:.2f} / {Rot:.2f} = {Pa:.4f} MPa")
    r2.criterion_met = Pa >= Pe - 1e-12
    extra = [] if chart["status"] in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED") else [f"chart readings {chart['status']}"]
    ctx.add(r2.finalize(unverified=ctx.unverified(r2.references, r2.materials, extra)))
