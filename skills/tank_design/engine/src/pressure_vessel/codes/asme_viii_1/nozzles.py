"""Nozzle checks: UG-45 neck thickness, UG-36(b)(1) scope, UG-37 area
replacement with UG-40 limits, flange rating (UG-44), UG-41 status, UG-42
spacing, UW-14 openings near seams.

Area method scope: radial nozzle, F = 1 (longitudinal plane governs), in a
cylindrical shell or on the centreline of a formed head. Everything else is
OUT_OF_SCOPE rather than approximated.
"""

from __future__ import annotations

import math

from ... import pipes
from ...status import RecordKind
from ...trace import CalcRecord
from . import formulas as F
from .context import Ctx

MM, MPA, MM2 = "mm", "MPa", "mm2"
K1_2TO1 = 0.90   # Table UG-37 K1 for D/2h = 2.0 (register ASME8-1:TableUG-37)


def _parent(ctx: Ctx, ge: dict):
    """(parent tag, material key, kind, head object or None)."""
    g = ctx.vi.geometry
    if ge["location"] == "shell":
        cc = next(c for c in g.shell_courses if c.id == ge["parent"])
        return cc.id, cc.material, "shell", None
    pos = "top" if ge["location"] == "top_head" else "bottom"
    h = g.heads[pos]
    return f"HD-{pos.upper()[:3]}", h.material, "head", h


def _neck_E(ctx: Ctx, nz) -> tuple[float | None, str]:
    neck = nz.neck
    if neck.type == "plate":
        return neck.seam_E, "rolled-plate neck: stated long-seam joint efficiency"
    rec = ctx.vi.materials[neck.material].record
    if rec and "seamless" in rec.product_form.lower():
        return 1.0, "seamless pipe (material record product form)"
    return None, "pipe product form is not stated as seamless: give the neck joint efficiency"


def _neck_avail(ctx: Ctx, nz) -> tuple[float | None, str]:
    fab = ctx.vi.fabrication
    neck, CA = nz.neck, ctx.vi.process.corrosion_allowance
    if neck.type == "pipe":
        if fab.pipe_undertolerance is None:
            return None, "pipe undertolerance not stated (UG-16(d))"
        return neck.wall * (1 - fab.pipe_undertolerance) - CA, \
            f"t_n x (1 - {fab.pipe_undertolerance:.3f}) - CA (UG-16(d))"
    ded, why = F.plate_undertolerance_deduction(neck.wall, fab.plate_undertolerance)
    return neck.wall - ded - CA, f"t_n - u - CA; {why}"


def nozzle_records(ctx: Ctx):
    vi = ctx.vi
    p = vi.process
    CA, D = p.corrosion_allowance, vi.geometry.inside_diameter
    T = p.design_temperature
    geo = {n["tag"]: n for n in ctx.geometry["nozzles"]}
    for nz in vi.geometry.nozzles:
        ge = geo[nz.tag]
        ptag, pmat, pkind, head = _parent(ctx, ge)
        Pn = ctx.P_at(ge["z"]) if pkind == "shell" else ctx.P_at(
            vi.geometry.bottom_tangent_elevation if nz.location == "bottom_head" else ge["z"])
        Sn, how_n = ctx.S(nz.neck.material, T)
        Sv, how_v = ctx.S(pmat, T)
        t_par = ctx.available.get(ptag)
        tr_par = ctx.required.get(ptag)
        _ug45(ctx, nz, ge, Pn, Sn, how_n, tr_par, ptag, pmat)
        _ug37(ctx, nz, ge, Pn, Sn, Sv, how_n, how_v, t_par, ptag, pmat, pkind, head, CA, D)
        _flange(ctx, nz, Pn)
        w = CalcRecord(f"NZ-{nz.tag}-UG41", f"Nozzle {nz.tag}", f"Nozzle {nz.tag} attachment weld strength",
                       method="UG-41 weld load paths", references=["ASME8-1:UG-41"],
                       criterion="weld strength >= load carried (UG-41)")
        w.questions.append("define the attachment weld detail (Fig. UW-16.1 sketch, weld sizes) so the UG-41 "
                           "load paths, or the UG-41(b)(1) exemption, can be evaluated")
        ctx.add(w.finalize(not_evaluated_reason="weld details not defined"))
    _spacing(ctx)


def _ug45(ctx, nz, ge, Pn, Sn, how_n, tr_par, ptag, pmat):
    CA = ctx.vi.process.corrosion_allowance
    rec = CalcRecord(f"NZ-{nz.tag}-UG45", f"Nozzle {nz.tag}", f"Nozzle {nz.tag} neck minimum thickness",
                     method="UG-45: t_UG45 = max(ta, min(tb3, tb1)); access openings ta only",
                     references=["ASME8-1:UG-45", "ASME8-1:TableUG-45", "ASME8-1:UG-27(c)(1)",
                                 "ASME8-1:UG-16(b)", "ASME8-1:UG-16(d)", "ASME:B36.10M"],
                     materials=[nz.neck.material, pmat], criterion="t_neck_avail >= t_UG45")
    rec.inp("P", Pn, MPA)
    rec.inp("OD", nz.neck.od, MM)
    rec.inp("t_n", nz.neck.wall, MM, f"nominal wall ({nz.neck.data_source[:60]})", source=f"PIPE_DATA {nz.neck.data_status}")
    rec.inp("Sn", Sn, MPA, how_n, source=f"MAT-{nz.neck.material}")
    rec.inp("CA", CA, MM)
    En, why_E = _neck_E(ctx, nz)
    rec.inp("E_neck", En, "-", why_E)
    if Sn is None or En is None or tr_par is None:
        rec.questions.append("need the neck allowable stress, the neck joint efficiency and the parent "
                             "required thickness")
        ctx.add(rec.finalize(not_evaluated_reason="missing input for UG-45"))
        return
    Rn = rec.mid("Rn", (nz.neck.od - 2 * nz.neck.wall) / 2 + CA, MM, "corroded inside radius of neck")
    try:
        trn = rec.mid("t_rn", F.shell_t_circ(Pn, Rn, Sn, En), MM, "UG-27(c)(1) for the neck")
    except F.OutOfScope as exc:
        ctx.add(rec.finalize(out_of_scope=str(exc)))
        return
    ta = rec.mid("ta", trn + CA, MM, "t_rn + CA")
    rec.eq("ta = P Rn / (Sn E - 0.6 P) + CA", f"{Pn:.4f} x {Rn:.2f} / ({Sn:.1f} x {En:.2f} - 0.6 x {Pn:.4f}) + {CA:g} = {ta:.3f} mm")
    extra = []
    if nz.access_opening:
        t45 = rec.res("t_UG45", ta, MM, "access/inspection opening: ta only")
    else:
        tb1 = rec.mid("tb1", max(tr_par + CA, F.UG16B_MIN + CA), MM,
                      f"parent ({ptag}) required t at E = 1 plus CA, not less than 1.5 mm + CA")
        nps = nz.neck.nps
        if nps is None:
            rec.questions.append("give equivalent_nps of the plate neck for Table UG-45 (tb3)")
            ctx.add(rec.finalize(not_evaluated_reason="tb3 needs the nominal pipe size"))
            return
        tt, why = pipes.ug45_table_value(nps)
        tb3 = rec.mid("tb3", tt + CA, MM, f"Table UG-45 value + CA; {why}", source="CODE_TABLE (derived)")
        tb = rec.mid("tb", min(tb3, tb1), MM, "min(tb3, tb1) — internal pressure only")
        rec.eq("t_UG45 = max(ta, min(tb3, tb1))", f"max({ta:.3f}, min({tb3:.3f}, {tb1:.3f}))")
        t45 = rec.res("t_UG45", max(ta, tb), MM)
        extra.append("Table UG-45 values derived from the STD wall (unverified derivation)")
    if ctx.vi.process.external_pressure:
        extra.append("external-pressure parts of UG-45 (ta external, tb2) not evaluated")
    tav, why_av = _neck_avail(ctx, nz)
    if tav is None:
        rec.questions.append(why_av)
        ctx.add(rec.finalize(not_evaluated_reason=why_av))
        return
    rec.res("t_neck_avail", tav + CA, MM, why_av.replace(" - CA", ""))
    if tav > 0:
        Pneck = rec.res("MAWP_neck", Sn * En * tav / (Rn + 0.6 * tav), MPA, "UG-27(c)(1) of the corroded neck")
        ctx.mawp_parts[f"neck {nz.tag}"] = Pneck - (Pn - ctx.vi.process.design_pressure)
    rec.res("margin", tav + CA - t45, MM)
    rec.criterion_met = tav + CA >= t45 - 1e-9
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, rec.materials, extra)))


def _seam_E1(ctx, nz, ge, r_open):
    """UW-14 proximity: return (E1, note). E1 = 1 unless the opening passes
    through a seam, in which case the seam's efficiency applies (review)."""
    if ge["location"] != "shell":
        return 1.0, None
    g = ctx.geometry
    z, th = ge["z"], ge["orientation"]
    R = g["vessel"]["inside_diameter"] / 2
    for s in g["seams"]:
        if s["kind"] == "circumferential" and abs(s["z"] - z) < r_open:
            return ctx.joint_E.get("shell_circumferential") or 0.0, f"opening crosses circumferential seam {s['between']}"
        if s["kind"] == "longitudinal" and s["z0"] <= z <= s["z1"]:
            dth = abs((th - s["orientation"] + 180) % 360 - 180)
            if R * math.radians(dth) < r_open:
                return ctx.joint_E.get("shell_longitudinal") or 0.0, f"opening crosses longitudinal seam of {s['course']}"
    return 1.0, None


def _ug37(ctx, nz, ge, Pn, Sn, Sv, how_n, how_v, t, ptag, pmat, pkind, head, CA, D):
    refs = ["ASME8-1:UG-37", "ASME8-1:UG-40", "ASME8-1:UG-36(b)(1)", "ASME8-1:UG-16(d)", "ASME8-1:UW-14"]
    mats = [nz.neck.material, pmat] + ([nz.pad.material] if nz.pad else [])
    rec = CalcRecord(f"NZ-{nz.tag}-UG37", f"Nozzle {nz.tag}", f"Nozzle {nz.tag} reinforcement (area method)",
                     method="UG-37(c) area replacement, Fig. UG-37.1 areas, UG-40 limits; F = 1, radial nozzle",
                     references=refs, materials=mats, criterion="A1 + A2 + A3 + A41 + A42 + A43 + A5 >= A")
    if None in (Sn, Sv, t):
        ctx.add(rec.finalize(not_evaluated_reason="missing allowable stress or parent thickness"))
        return
    neck = nz.neck
    d = rec.mid("d", neck.od - 2 * neck.wall + 2 * CA, MM, "finished opening diameter, corroded")
    Rn = d / 2
    # UG-36(b)(1) scope gate
    if pkind == "shell":
        lim = min(D / 2, 508.0) if D <= 1520.0 else min(D / 3, 1000.0)
        rec.mid("d_limit_UG36", lim, MM, "UG-36(b)(1) limit for the area rules in cylindrical shells")
    else:
        lim = D / 2
        rec.mid("d_limit_scope", lim, MM, "implementation scope for central head openings (d <= D/2)")
    if d > lim:
        ctx.add(rec.finalize(out_of_scope=f"d = {d:.1f} mm exceeds {lim:.1f} mm: large-opening rules "
                                          "(Appendix 1-7) not implemented"))
        return
    P = rec.inp("P", Pn, MPA)
    rec.inp("attachment", nz.attachment, "", "set_in = nozzle wall inserted through the shell")
    rec.inp("Sv", Sv, MPA, how_v, source=f"MAT-{pmat}")
    rec.inp("Sn", Sn, MPA, how_n, source=f"MAT-{neck.material}")
    rec.inp("t", t, MM, f"parent {ptag} corroded available thickness", source=ptag)
    tn = rec.inp("tn", neck.wall - CA, MM, "nominal neck wall less CA (no undertolerance, UG-16(d))")
    # tr of the parent, seamless (E = 1)
    if pkind == "shell":
        R = D / 2 + CA
        tr_fn = lambda Pv: Pv * R / (Sv - 0.6 * Pv)          # noqa: E731
        tr = F.shell_t_circ(P, R, Sv, 1.0)
        rec.eq("tr = P R / (Sv - 0.6 P)  (E = 1)", f"{P:.4f} x {R:.2f} / ({Sv:.1f} - 0.6 x {P:.4f}) = {tr:.3f} mm")
    elif head.type == "ellipsoidal":
        if abs(head.aspect_ratio - 2.0) > 1e-9:
            ctx.add(rec.finalize(out_of_scope="K1 (Table UG-37) only held for 2:1 heads in v0.1"))
            return
        rec.references.append("ASME8-1:TableUG-37")
        Dc = D + 2 * CA
        tr_fn = lambda Pv: Pv * K1_2TO1 * Dc / (2 * Sv - 0.2 * Pv)   # noqa: E731
        tr = tr_fn(P)
        rec.eq("tr = P K1 D / (2 Sv - 0.2 P), K1 = 0.90 (opening inside the 80 % circle)",
               f"{P:.4f} x 0.90 x {Dc:.2f} / (2 x {Sv:.1f} - 0.2 x {P:.4f}) = {tr:.3f} mm")
    elif head.type == "hemispherical":
        L = (D + 2 * CA) / 2
        tr_fn = lambda Pv: Pv * L / (2 * Sv - 0.2 * Pv)      # noqa: E731
        tr = tr_fn(P)
        rec.eq("tr = P L / (2 Sv - 0.2 P)", f"= {tr:.3f} mm")
    else:
        L = head.crown_radius + CA
        tr_fn = lambda Pv: Pv * L / (2 * Sv - 0.2 * Pv)      # noqa: E731
        tr = tr_fn(P)
        rec.eq("tr = P L / (2 Sv - 0.2 P)  (spherical crown, M = 1)", f"= {tr:.3f} mm")
    tr = rec.mid("tr", tr, MM, "required parent thickness, seamless")
    En = 1.0
    trn = rec.mid("trn", F.shell_t_circ(P, Rn, Sn, En), MM, "required neck thickness, seamless (E = 1)")
    rec.eq("trn = P Rn / (Sn - 0.6 P)", f"{P:.4f} x {Rn:.2f} / ({Sn:.1f} - 0.6 x {P:.4f}) = {trn:.3f} mm")
    r_open = max(neck.od / 2, (nz.pad.od / 2) if nz.pad else 0.0)
    E1, seam_note = _seam_E1(ctx, nz, ge, r_open)
    extra = []
    if seam_note:
        rec.warnings.append(seam_note + " (UW-14): E1 = seam efficiency, review required")
        extra.append(seam_note)
    Fc = rec.mid("F", 1.0, "-", "correction factor, longitudinal plane (radial nozzle)")
    E1 = rec.mid("E1", E1, "-", "1.0: opening not in a seam" if not seam_note else seam_note)
    te = nz.pad.thickness if nz.pad else 0.0
    Dp = nz.pad.od if nz.pad else 0.0
    Sp = None
    if nz.pad:
        Sp, how_p = ctx.S(nz.pad.material, ctx.vi.process.design_temperature)
        rec.inp("Sp", Sp, MPA, how_p, source=f"MAT-{nz.pad.material}")
        rec.inp("te", te, MM, "pad thickness")
        rec.inp("Dp", Dp, MM, "pad outside diameter")
        if Dp <= neck.od:
            rec.criterion_met = False
            rec.status_reasons.append("pad OD does not clear the nozzle")
            ctx.add(rec.finalize())
            return
    legs = nz.weld_legs
    h_in = nz.inward_projection
    common = dict(d=d, t=t, tn=tn, Sv=Sv, Sn=Sn, Sp=Sp, te=te, Dp=Dp, F=Fc, E1=E1,
                  leg41=legs.get("nozzle_outer_leg") or 0.0, leg42=legs.get("pad_outer_leg") or 0.0,
                  leg43=legs.get("inner_leg") or 0.0, h=h_in, ti=tn - CA if h_in > 0 else 0.0,
                  inserted=nz.attachment == "set_in")
    ar = F.area_replacement(tr=tr, trn=trn, **common)
    fr1, fr2, fr3, fr4 = ar["fr1"], ar["fr2"], ar["fr3"], ar["fr4"]
    rec.mid("fr2", fr2, "-", "Sn/Sv (<= 1)")
    rec.mid("fr1", fr1, "-", "set-in: Sn/Sv; set-on: 1.0")
    if nz.pad:
        rec.mid("fr4", fr4, "-", "Sp/Sv (<= 1)")
        rec.mid("fr3", fr3, "-", "min(Sn, Sp)/Sv")
    lim_par = rec.mid("limit_parallel", ar["limit_parallel"], MM, "UG-40: max(d, Rn + tn + t)")
    lim_nor = rec.mid("limit_normal", ar["limit_normal"], MM, "UG-40: min(2.5 t, 2.5 tn + te)")
    te_eff, Dp_eff = ar["te_eff"], ar["Dp_eff"]
    if te > lim_nor:
        rec.warnings.append(f"pad thickness {te:g} mm > normal limit {lim_nor:.2f} mm: only the part within the limit counted")
    if Dp > 2 * lim_par:
        rec.warnings.append(f"pad OD {Dp:g} mm > 2 x parallel limit {2 * lim_par:.1f} mm: only {Dp_eff:.1f} mm counted")
    A = rec.res("A", ar["A"], MM2, "required area")
    rec.eq("A = d tr F + 2 tn tr F (1 - fr1)", f"{d:.2f} x {tr:.3f} + 2 x {tn:.2f} x {tr:.3f} x (1 - {fr1:.3f}) = {A:.1f} mm2")
    ex = ar["excess_shell"]
    A1 = rec.res("A1", ar["A1"], MM2, "excess in the shell: larger of the two Fig. UG-37.1 expressions")
    rec.eq("A1 = max[d (E1 t - F tr) - 2 tn (E1 t - F tr)(1 - fr1), 2 (t + tn)(E1 t - F tr) - 2 tn (E1 t - F tr)(1 - fr1)]",
           f"E1 t - F tr = {ex:.3f} mm -> A1 = {A1:.1f} mm2")
    sur = ar["surplus_nozzle"]
    A2 = rec.res("A2", ar["A2"], MM2, "excess in the nozzle wall outward")
    if nz.pad:
        rec.eq("A2 = min[5 (tn - trn) fr2 t, 2 (tn - trn)(2.5 tn + te) fr2]",
               f"min(5 x {sur:.3f} x {fr2:.3f} x {t:.3f}, 2 x {sur:.3f} x (2.5 x {tn:.3f} + {te_eff:.2f}) x {fr2:.3f}) = {A2:.1f} mm2")
    else:
        rec.eq("A2 = min[5 (tn - trn) fr2 t, 5 (tn - trn) fr2 tn]",
               f"min(5 x {sur:.3f} x {fr2:.3f} x {t:.3f}, 5 x {sur:.3f} x {fr2:.3f} x {tn:.3f}) = {A2:.1f} mm2")
    A3 = rec.res("A3", ar["A3"], MM2, "inward projection")
    A41 = rec.res("A41", ar["A41"], MM2, "outer nozzle weld (0 if not defined)")
    A42 = rec.res("A42", ar["A42"], MM2, "pad outer weld")
    A43 = rec.res("A43", ar["A43"], MM2, "inner weld")
    A5 = rec.res("A5", ar["A5"], MM2, "pad: (Dp - d - 2 tn) te fr4")
    if nz.pad:
        rec.eq("A5 = (Dp - d - 2 tn) te fr4",
               f"({Dp_eff:.1f} - {d:.2f} - 2 x {tn:.2f}) x {te_eff:.2f} x {fr4:.3f} = {A5:.1f} mm2")
    tot = rec.res("A_avail", ar["A_avail"], MM2)
    rec.eq("A_avail = A1 + A2 + A3 + A41 + A42 + A43 + A5",
           f"{A1:.1f} + {A2:.1f} + {A3:.1f} + {A41:.1f} + {A42:.1f} + {A43:.1f} + {A5:.1f} = {tot:.1f} mm2 vs A = {A:.1f} mm2")
    rec.res("margin", tot - A, MM2)
    if not nz.pad:
        need = A - (A1 + A2 + A3 + A41 + A43)
        if need > 0:
            rec.warnings.append(f"without a pad the opening is short by {need:.0f} mm2")
    if all(v is None for v in legs.values()):
        extra.append("weld areas taken as zero (no weld sizes): conservative for the area check")
    rec.criterion_met = tot >= A - 1e-9
    # largest pressure for which this opening's area check is met (margin falls as P rises)
    def margin(Pv):
        r = F.area_replacement(tr=tr_fn(Pv), trn=Pv * Rn / (Sn - 0.6 * Pv), **common)
        return r["A_avail"] - r["A"]
    P_hi = 0.385 * min(Sv, Sn) * 0.999
    if margin(P_hi) >= 0:
        P_max, how = P_hi, "area check met up to the UG-27 validity limit (0.385 S)"
    elif margin(1e-6) < 0:
        P_max, how = 0.0, "area check not met at any pressure"
    else:
        lo, hi = 1e-6, P_hi
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if margin(mid) >= 0 else (lo, mid)
        P_max, how = lo, "bisection on A_avail(P) = A(P)"
    rec.res("P_max_opening", P_max, MPA, how)
    ctx.mawp_parts[f"opening {nz.tag}"] = P_max - (Pn - ctx.vi.process.design_pressure)
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, mats, [e for e in extra if "conservative" not in e])))


def _flange(ctx, nz, Pn):
    if nz.flange is None:
        return
    fl = nz.flange
    rec = CalcRecord(f"NZ-{nz.tag}-FLG", f"Nozzle {nz.tag}",
                     f"Flange {nz.tag} pressure-temperature rating ({fl.standard} Class {fl.pressure_class})",
                     method="design pressure at the nozzle <= rating at design temperature",
                     references=["ASME8-1:UG-44", "ASME:B16.5"], criterion="P <= rating(T_design)")
    rec.inp("P", Pn, MPA, "design pressure + static head at the nozzle")
    rec.inp("T", ctx.vi.process.design_temperature, "degC")
    if fl.rating_at_design_temperature is None:
        rec.questions.append(f"give the {fl.standard} Class {fl.pressure_class} rating of the "
                             f"{fl.material} flange material group at {ctx.vi.process.design_temperature:g} degC")
        ctx.add(rec.finalize(not_evaluated_reason="flange rating not supplied"))
        return
    r = rec.inp("rating", fl.rating_at_design_temperature, MPA, fl.rating_source, source=f"USER ({fl.rating_status})")
    rec.res("margin", r - Pn, MPA)
    rec.criterion_met = r >= Pn - 1e-12
    extra = [] if fl.rating_status in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED") else \
        [f"flange rating {fl.rating_status}"]
    # the rating limits the pressure at the flange; refer it to the top (UG-98)
    ctx.mawp_parts[f"flange {nz.tag}"] = r - (Pn - ctx.vi.process.design_pressure)
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references, [], extra)))


def _spacing(ctx: Ctx):
    rec = CalcRecord("NZ-UG42", "Nozzles", "Spacing of openings (overlapping reinforcement limits)",
                     method="pairwise centre distance on the shell surface vs sum of UG-40 parallel limits",
                     references=["ASME8-1:UG-42", "ASME8-1:UG-40"],
                     criterion="no two openings have overlapping limits of reinforcement")
    limits = {r.calc_id.split("-")[1]: r.value("limit_parallel") for r in ctx.records
              if r.calc_id.endswith("-UG37") and any(tv.symbol == "limit_parallel" for tv in r.intermediates)}
    shell = [n for n in ctx.geometry["nozzles"] if n["location"] == "shell" and n["tag"] in limits]
    R = ctx.geometry["vessel"]["inside_diameter"] / 2
    overl = []
    for i, a in enumerate(shell):
        for b in shell[i + 1:]:
            dth = math.radians(abs((a["orientation"] - b["orientation"] + 180) % 360 - 180))
            dist = math.hypot(R * dth, a["z"] - b["z"])
            need = limits[a["tag"]] + limits[b["tag"]]
            rec.mid(f"{a['tag']}-{b['tag']}", round(dist, 1), MM, f"centre distance (limits sum {need:.1f} mm)")
            if dist < need:
                overl.append(f"{a['tag']}/{b['tag']}")
    if overl:
        ctx.add(rec.finalize(out_of_scope="overlapping limits " + ", ".join(overl) + ": UG-42 not implemented"))
        return
    rec.criterion_met = True
    ctx.add(rec.finalize(unverified=ctx.unverified(rec.references)))
