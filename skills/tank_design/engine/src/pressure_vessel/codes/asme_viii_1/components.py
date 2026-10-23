"""Material, joint-efficiency, shell-course and head calculation records."""

from __future__ import annotations

from ...geometry.profiles import HeadProfile
from ...status import RecordKind
from ...trace import CalcRecord
from . import formulas as F
from .context import TABLE_UW12, Ctx

MM, MPA, C = "mm", "MPa", "degC"


def material_records(ctx: Ctx):
    p = ctx.vi.process
    for key, ma in ctx.vi.materials.items():
        if ma.record is None:
            rec = CalcRecord(f"MAT-{key}", f"Material {key}", f"Non-pressure material {ma.spec}",
                             kind=RecordKind.COMPUTATION, code_family="PROJECT", method="data record",
                             references=["PROJECT:requirement"])
            rec.res("density", ma.density, "kg/m3", source=f"INPUT ({ma.status})")
            if ma.min_yield:
                rec.res("Fy", ma.min_yield, MPA, "minimum yield (user input)", source=f"INPUT ({ma.status})")
            ctx.add(rec.finalize())
            continue
        r = ma.record
        rec = CalcRecord(f"MAT-{key}", f"Material {key}", f"Allowable stress, {r.name}",
                         method="material database lookup (exact or linear between tabulated temperatures)",
                         references=["ASME2D:Table1A"], materials=[key],
                         criterion="design and test temperatures within the record's tabulated range")
        rec.inp("record", r.id, source=f"MATERIAL_DB {ctx.matdb.version}")
        rec.inp("status", str(r.status))
        rec.inp("source", r.source_document)
        rec.inp("T_design", p.design_temperature, C)
        rec.inp("T_test", p.test_temperature, C)
        ok = True
        for sym, T in (("S_design", p.design_temperature), ("S_test", p.test_temperature)):
            S, how = ctx.S(key, T)
            if S is None:
                ok = False
                rec.warnings.append(how)
                rec.res(sym, None, MPA, how)
            else:
                rec.res(sym, S, MPA, how, source=f"MATERIAL:{r.id}")
        if p.external_design_temperature is not None:
            S, how = ctx.S(key, p.external_design_temperature)
            rec.res("S_ext_T", S, MPA, how, source=f"MATERIAL:{r.id}")
        rec.criterion_met = ok
        ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, [key])))


def _E_table(j) -> tuple[float | None, str]:
    row = TABLE_UW12.get(j.joint_type, {})
    if j.radiography not in row:
        return None, f"Table UW-12 has no entry for type {j.joint_type} with {j.radiography} radiography"
    return row[j.radiography], f"Table UW-12 type {j.joint_type}, {j.radiography} RT"


def joint_records(ctx: Ctx):
    fab = ctx.vi.fabrication
    for name, j in fab.joints.items():
        rec = CalcRecord(f"JE-{name}", "Weld joints", f"Joint efficiency, {name.replace('_', ' ')}",
                         kind=RecordKind.COMPUTATION, method="Table UW-12 lookup",
                         references=["ASME8-1:UW-3", "ASME8-1:UW-11", "ASME8-1:TableUW-12"])
        rec.inp("category", j.category)
        rec.inp("joint_type", j.joint_type)
        rec.inp("radiography", j.radiography)
        E, how = _E_table(j)
        rec.res("E", E, "-", how, source="CODE_TABLE:ASME8-1:TableUW-12")
        if E is None:
            rec.warnings.append(how)
        ctx.joint_E[name] = E
        ctx.add(rec.finalize())


def seamless_head_E(ctx: Ctx) -> tuple[float, str, list[str]]:
    """UW-12(d) for seamless heads: 1.0 when the UW-11(a)(5)(b) spot RT is met
    and the head-to-shell weld is Type 1 or 2; otherwise 0.85."""
    fab = ctx.vi.fabrication
    j = ctx.joint("head_to_shell")
    notes = []
    met = fab.spot_rt_uw11a5b
    if j is not None and j.radiography == "full":
        met = True if met is None else met
    if met is None:
        notes.append("UW-11(a)(5)(b) compliance not stated: E = 0.85 used (conservative); confirm")
        return 0.85, "UW-12(d): compliance not stated -> 0.85", notes
    if met and j is not None and j.joint_type in (1, 2):
        return 1.0, "UW-12(d): seamless head, UW-11(a)(5)(b) spot RT met -> 1.0", notes
    return 0.85, "UW-12(d): seamless head, spot RT not met or Type 3-6 joint -> 0.85", notes


def _select_plate(ctx: Ctx, t_design: float, und) -> tuple[float | None, float, str]:
    for t in ctx.vi.fabrication.plate_thicknesses:
        ded, _ = F.plate_undertolerance_deduction(t, und)
        if t - ded >= t_design - 1e-9:
            return t, ded, f"smallest listed plate with t - undertolerance >= {t_design:.3f} mm"
    return None, 0.0, "no listed plate thickness is sufficient"


def shell_records(ctx: Ctx):
    vi, p, g = ctx.vi, ctx.vi.process, ctx.vi.geometry
    CA = p.corrosion_allowance
    D = g.inside_diameter
    E_long = ctx.joint_E.get("shell_longitudinal")
    E_circ = ctx.joint_E.get("shell_circumferential")
    und = vi.fabrication.plate_undertolerance
    z = g.bottom_tangent_elevation + g.heads["bottom"].straight_flange
    for cc in g.shell_courses:
        z_bottom = z
        z += cc.length
        rec = CalcRecord(f"SH-{cc.id}", f"Shell course {cc.id}",
                         f"Cylindrical shell {cc.id} under internal pressure",
                         method="UG-27(c)(1) circumferential and UG-27(c)(2) longitudinal stress; "
                                "UG-16(b) minimum; UG-16(c) plate undertolerance; UG-25 corrosion",
                         references=["ASME8-1:UG-27(c)(1)", "ASME8-1:UG-27(c)(2)", "ASME8-1:UG-16(b)",
                                     "ASME8-1:UG-16(c)", "ASME8-1:UG-25"],
                         materials=[cc.material],
                         criterion="t_avail = t_nom - u - CA >= max(t_req, 1.5 mm)")
        Pc = rec.inp("P", ctx.P_at(z_bottom), MPA, "design pressure + static head at course bottom")
        rec.inp("D", D, MM, "inside diameter (new)")
        rec.inp("CA", CA, MM)
        S, how = ctx.S(cc.material, p.design_temperature)
        rec.inp("S", S, MPA, how, source=f"MAT-{cc.material}")
        rec.inp("E_long", E_long, "-", "Category A joint (circumferential stress)", source="JE-shell_longitudinal")
        rec.inp("E_circ", E_circ, "-", "Category B joint (longitudinal stress)", source="JE-shell_circumferential")
        rec.inp("u", und, MM, "plate mill undertolerance")
        if S is None or E_long is None or E_circ is None:
            rec.questions.append("allowable stress and both joint efficiencies are needed")
            ctx.add(rec.finalize(not_evaluated_reason="missing S or E"))
            continue
        R = rec.mid("R", D / 2 + CA, MM, "corroded inside radius D/2 + CA")
        try:
            tc = rec.mid("t_circ", F.shell_t_circ(Pc, R, S, E_long), MM)
            rec.eq("t_circ = P R / (S E_long - 0.6 P)",
                   f"{Pc:.4f} x {R:.2f} / ({S:.1f} x {E_long:.2f} - 0.6 x {Pc:.4f}) = {tc:.3f} mm")
            tl = rec.mid("t_long", F.shell_t_long(Pc, R, S, E_circ), MM)
            rec.eq("t_long = P R / (2 S E_circ + 0.4 P)",
                   f"{Pc:.4f} x {R:.2f} / (2 x {S:.1f} x {E_circ:.2f} + 0.4 x {Pc:.4f}) = {tl:.3f} mm")
        except F.OutOfScope as exc:
            ctx.add(rec.finalize(out_of_scope=str(exc)))
            continue
        t_req = rec.mid("t_req", max(tc, tl), MM, "governing: " + ("circumferential" if tc >= tl else "longitudinal"))
        t_min = rec.mid("t_min", max(t_req, F.UG16B_MIN), MM, "max(t_req, UG-16(b) 1.5 mm)")
        t_des = rec.mid("t_design", t_min + CA, MM, "t_min + CA")
        if cc.nominal_thickness is None:
            t_nom, ded, why = _select_plate(ctx, t_des, und)
            rec.mid("selection", why)
            if t_nom is None:
                rec.criterion_met = False
                ctx.add(rec.finalize())
                continue
        else:
            t_nom = cc.nominal_thickness
            ded, _ = F.plate_undertolerance_deduction(t_nom, und)
        _, why_u = F.plate_undertolerance_deduction(t_nom, und)
        rec.res("t_nom", t_nom, MM, "selected nominal plate" if cc.nominal_thickness is None else "specified nominal plate")
        rec.mid("u_deducted", ded, MM, why_u)
        t_av = rec.res("t_avail", t_nom - ded - CA, MM, "corroded available thickness")
        rec.eq("t_avail = t_nom - u_deducted - CA", f"{t_nom:g} - {ded:g} - {CA:g} = {t_av:.3f} mm")
        rec.res("margin", t_av - t_min, MM)
        rec.criterion_met = t_av >= t_min - 1e-9
        extra = ["plate undertolerance not stated"] if und is None else []
        ctx.selected[cc.id] = t_nom
        ctx.available[cc.id] = t_av
        ctx.required[cc.id] = F.shell_t_circ(Pc, R, S, 1.0)
        ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, [cc.material], extra)))

        m = CalcRecord(f"SH-{cc.id}-MAWP", f"Shell course {cc.id}", f"MAWP of shell course {cc.id}",
                       kind=RecordKind.COMPUTATION, method="UG-27 solved for P; static head deducted (UG-98)",
                       references=["ASME8-1:UG-27(c)(1)", "ASME8-1:UG-27(c)(2)", "ASME8-1:UG-98"],
                       materials=[cc.material])
        m.inp("t", t_av, MM, "corroded available thickness", source=f"SH-{cc.id}")
        m.inp("R", R, MM)
        try:
            pc = m.mid("P_circ", F.shell_mawp_circ(t_av, R, S, E_long), MPA)
            pl = m.mid("P_long", F.shell_mawp_long(t_av, R, S, E_circ), MPA)
            m.eq("P_circ = S E_long t / (R + 0.6 t)", f"{S:.1f} x {E_long:.2f} x {t_av:.3f} / ({R:.2f} + 0.6 x {t_av:.3f}) = {pc:.4f} MPa")
            m.eq("P_long = 2 S E_circ t / (R - 0.4 t)", f"2 x {S:.1f} x {E_circ:.2f} x {t_av:.3f} / ({R:.2f} - 0.4 x {t_av:.3f}) = {pl:.4f} MPa")
            sh = m.mid("static_head", ctx.static_head(z_bottom), MPA)
            mw = m.res("MAWP_top", min(pc, pl) - sh, MPA, "MAWP referred to the top of the vessel")
            ctx.mawp_parts[f"shell {cc.id}"] = mw
        except F.OutOfScope as exc:
            m.warnings.append(str(exc))
            ctx.mawp_notes.append(f"shell {cc.id}: MAWP not computed ({exc})")
        ctx.add(m.finalize())


def _head_formula(h, P, D, R, S, E, CA, t=None):
    """Return (t_req or MAWP, formula text, substitution, refs, extra mids)."""
    if h.type == "ellipsoidal":
        ar = h.aspect_ratio
        K = F.ellipsoidal_K(ar)
        refs = ["ASME8-1:App1-4(c)"] + (["ASME8-1:UG-32-ellipsoidal"] if abs(ar - 2.0) < 1e-9 else [])
        if t is None:
            v = F.ellipsoidal_t(P, D, S, E, ar)
            return v, "t = P D K / (2 S E - 0.2 P), K = (2 + (D/2h)^2)/6", \
                f"{P:.4f} x {D:.2f} x {K:.4f} / (2 x {S:.1f} x {E:.2f} - 0.2 x {P:.4f}) = {v:.3f} mm", refs, {"K": K}
        v = F.ellipsoidal_mawp(t, D, S, E, ar)
        return v, "P = 2 S E t / (K D + 0.2 t)", \
            f"2 x {S:.1f} x {E:.2f} x {t:.3f} / ({K:.4f} x {D:.2f} + 0.2 x {t:.3f}) = {v:.4f} MPa", refs, {"K": K}
    if h.type == "torispherical":
        L, r = h.crown_radius + CA, h.knuckle_radius + CA
        M = F.torispherical_M(L, r)
        refs = ["ASME8-1:App1-4(d)", "ASME8-1:UG-32-geometry"]
        if t is None:
            v = F.torispherical_t(P, L, r, S, E)
            return v, "t = P L M / (2 S E - 0.2 P), M = (3 + sqrt(L/r))/4", \
                f"{P:.4f} x {L:.2f} x {M:.4f} / (2 x {S:.1f} x {E:.2f} - 0.2 x {P:.4f}) = {v:.3f} mm", refs, {"L": L, "r": r, "M": M}
        v = F.torispherical_mawp(t, L, r, S, E)
        return v, "P = 2 S E t / (L M + 0.2 t)", \
            f"2 x {S:.1f} x {E:.2f} x {t:.3f} / ({L:.2f} x {M:.4f} + 0.2 x {t:.3f}) = {v:.4f} MPa", refs, {"L": L, "r": r, "M": M}
    L = R
    refs = ["ASME8-1:UG-32-hemispherical"]
    if t is None:
        v = F.hemispherical_t(P, L, S, E)
        return v, "t = P L / (2 S E - 0.2 P)", \
            f"{P:.4f} x {L:.2f} / (2 x {S:.1f} x {E:.2f} - 0.2 x {P:.4f}) = {v:.3f} mm", refs, {"L": L}
    v = F.hemispherical_mawp(t, L, S, E)
    return v, "P = 2 S E t / (L + 0.2 t)", f"2 x {S:.1f} x {E:.2f} x {t:.3f} / ({L:.2f} + 0.2 x {t:.3f}) = {v:.4f} MPa", refs, {"L": L}


def head_records(ctx: Ctx):
    vi, p, g = ctx.vi, ctx.vi.process, ctx.vi.geometry
    CA, D = p.corrosion_allowance, g.inside_diameter
    E_seam, E_why, E_notes = seamless_head_E(ctx)
    for pos in ("bottom", "top"):
        h = g.heads[pos]
        tag = f"HD-{pos.upper()[:3]}"
        depth = HeadProfile(h.type, D / 2, h.aspect_ratio or 2.0, h.crown_radius or 0.0,
                            h.knuckle_radius or 0.0).depth
        z_ref = g.bottom_tangent_elevation - depth if pos == "bottom" \
            else g.bottom_tangent_elevation + g.tangent_to_tangent
        rec = CalcRecord(tag, f"{pos.capitalize()} head", f"{h.type.capitalize()} head ({pos}) under internal pressure",
                         method="UG-32 / Appendix 1-4 with corroded dimensions; UG-16(b) minimum",
                         references=["ASME8-1:UG-16(b)", "ASME8-1:UG-25"], materials=[h.material],
                         criterion="t_min_formed - CA >= max(t_req, 1.5 mm)")
        P = rec.inp("P", ctx.P_at(z_ref), MPA, "design pressure + static head at the head's lowest point")
        rec.inp("D", D, MM)
        rec.inp("CA", CA, MM)
        S, how = ctx.S(h.material, p.design_temperature)
        rec.inp("S", S, MPA, how, source=f"MAT-{h.material}")
        if h.construction == "seamless":
            E = rec.inp("E", E_seam, "-", E_why, source="ASME8-1:UW-12(d)")
            rec.references.append("ASME8-1:UW-12(d)")
            rec.warnings.extend(E_notes)
        else:
            E = rec.inp("E", h.joint_efficiency_override, "-", "welded head: user-stated E of the welds within the head")
            rec.references.append("ASME8-1:TableUW-12")
        if S is None or E is None:
            ctx.add(rec.finalize(not_evaluated_reason="missing S or E"))
            continue
        Dc = rec.mid("D_c", D + 2 * CA, MM, "corroded inside diameter")
        Rc = Dc / 2
        try:
            t_req, f_txt, sub, refs, extra = _head_formula(h, P, Dc, Rc, S, E, CA)
        except F.OutOfScope as exc:
            ctx.add(rec.finalize(out_of_scope=str(exc)))
            continue
        rec.references.extend(refs)
        for k, v in extra.items():
            rec.mid(k, v, MM if k in ("L", "r") else "-")
        rec.eq(f_txt, sub)
        t_req = rec.mid("t_req", t_req, MM)
        t_min = rec.mid("t_min", max(t_req, F.UG16B_MIN), MM, "max(t_req, 1.5 mm)")
        unv_extra = []
        if h.nominal_thickness is None:          # automatic: needs the forming allowance
            need = t_min + CA + (h.forming_allowance or 0.0)
            t_nom = next((t for t in vi.fabrication.plate_thicknesses if t >= need - 1e-9), None)
            rec.mid("t_plate_needed", need, MM, "t_min + CA + forming allowance")
            if t_nom is None:
                rec.criterion_met = False
                ctx.add(rec.finalize())
                continue
            t_formed = t_nom - (h.forming_allowance or 0.0)
            unv_extra.append("minimum thickness after forming derived from the stated forming allowance")
        else:
            t_nom = h.nominal_thickness
            if h.min_thickness_after_forming is not None:
                t_formed = h.min_thickness_after_forming
            else:
                t_formed = t_nom - h.forming_allowance
                unv_extra.append("minimum thickness after forming derived from the stated forming allowance")
        rec.res("t_nom", t_nom, MM, "nominal plate")
        rec.res("t_min_formed", t_formed, MM, "minimum thickness after forming")
        Lc = F.head_crown_radius(h.type, Dc, h.aspect_ratio or 2.0, (h.crown_radius or 0) + CA)
        if Lc:
            rec.mid("ts/L", t_formed / Lc, "-", "applicability ts/L >= 0.002 (Appendix 1-4(f) otherwise)")
            rec.references.append("ASME8-1:App1-4(f)")
            try:
                F.thin_head_scope(t_formed, Lc)
            except F.OutOfScope as exc:
                ctx.add(rec.finalize(out_of_scope=str(exc)))
                continue
        t_av = rec.res("t_avail", t_formed - CA, MM, "corroded available thickness")
        rec.res("margin", t_av - t_min, MM)
        if h.type == "torispherical":
            Do_skirt = D + 2 * t_nom
            issues = F.torispherical_geometry_issues(h.crown_radius, h.knuckle_radius, Do_skirt, t_formed)
            rec.mid("geometry_issues", "; ".join(issues) or "none")
            if issues:
                rec.criterion_met = False
                rec.status_reasons.append("head geometry limits not met: " + "; ".join(issues))
                ctx.add(rec.finalize())
                continue
        rec.criterion_met = t_av >= t_min - 1e-9
        ctx.selected[pos] = t_nom
        ctx.available[tag] = t_av
        # required thickness at E = 1 for UG-45 tb1 / UG-37 tr of head nozzles
        ctx.required[tag] = _head_formula(h, P, Dc, Rc, S, 1.0, CA)[0]
        ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, [h.material], unv_extra + (
            [] if h.construction == "welded" else [n for n in E_notes]))))

        m = CalcRecord(f"{tag}-MAWP", f"{pos.capitalize()} head", f"MAWP of {pos} head",
                       kind=RecordKind.COMPUTATION, method="head formula solved for P; static head deducted",
                       references=list(dict.fromkeys(rec.references + ["ASME8-1:UG-98"])), materials=[h.material])
        m.inp("t", t_av, MM, source=tag)
        try:
            mw, f_txt, sub, _, _ = _head_formula(h, P, Dc, Rc, S, E, CA, t=t_av)
            m.eq(f_txt, sub)
            sh = m.mid("static_head", ctx.static_head(z_ref), MPA)
            v = m.res("MAWP_top", mw - sh, MPA, "referred to the top of the vessel")
            ctx.mawp_parts[f"{pos} head"] = v
        except F.OutOfScope as exc:
            m.warnings.append(str(exc))
        ctx.add(m.finalize())

        # straight flange checked as a cylinder (UG-27) with the head thickness
        if h.straight_flange > 0:
            sf = CalcRecord(f"{tag}-SF", f"{pos.capitalize()} head", f"Straight flange of {pos} head as a cylinder",
                            method="UG-27(c)(1)/(c)(2) with the head's minimum formed thickness",
                            references=["ASME8-1:UG-27(c)(1)", "ASME8-1:UG-27(c)(2)", "ASME8-1:UW-12(d)"],
                            materials=[h.material], criterion="t_avail >= t_req (straight flange)")
            Ec = E_seam if h.construction == "seamless" else h.joint_efficiency_override
            El = ctx.joint_E.get("head_to_shell")
            sf.inp("E_circ_stress", Ec, "-", "seamless section, UW-12(d)")
            sf.inp("E_long_stress", El, "-", "Category B head-to-shell joint")
            try:
                t1 = F.shell_t_circ(P, Rc, S, Ec)
                t2 = F.shell_t_long(P, Rc, S, El) if El else 0.0
                tr = sf.mid("t_req", max(t1, t2), MM)
                sf.eq("t = max(P R/(S E - 0.6P), P R/(2 S E + 0.4P))", f"max({t1:.3f}, {t2:.3f}) = {tr:.3f} mm")
                sf.res("t_avail", t_av, MM)
                sf.criterion_met = t_av >= tr - 1e-9
                ctx.add(sf.finalize(unverified=ctx.unverified(sf.references, [h.material], E_notes)))
            except F.OutOfScope as exc:
                ctx.add(sf.finalize(out_of_scope=str(exc)))
