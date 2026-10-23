"""2D drawing package: GA sheet and fabrication-detail sheet (DXF + PDF).

Sheets are drawn in paper millimetres (A1, 841 x 594). Views are the HLR
projections of the exported STEP (drawings/hlr.py) scaled by 1/s; every
dimension is a real DXF DIMENSION entity whose DIMLFAC = s, so it displays
the true model length. drawing_check.json lists each dimension with the
design value from design_geometry.json and the value the DIMENSION entity
measures, and the drawing fails its check if any differ by more than 0.5 mm.

Not drawn because the design input does not define them: weld sizes,
bevels, fit-up, general tolerances. The sheets say so in their notes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

A1 = (841.0, 594.0)
STD_SCALES = (5, 10, 15, 20, 25, 30, 40, 50)


class Sheet:
    def __init__(self, title):
        self.doc = ezdxf.new("R2018", setup=True)
        self.doc.units = ezdxf.units.MM
        self.msp = self.doc.modelspace()
        self.title = title
        self.dims = []      # (name, design value, entity, dimlfac)
        L = self.doc.layers
        for name, color, lt, lw in (("OUTLINE", 7, "CONTINUOUS", 35), ("HIDDEN", 8, "DASHED", 18),
                                    ("CENTER", 1, "CENTER", 18), ("DIM", 4, "CONTINUOUS", 18),
                                    ("TEXT", 7, "CONTINUOUS", 25), ("HATCH", 8, "CONTINUOUS", 13),
                                    ("FRAME", 7, "CONTINUOUS", 50), ("TABLE", 7, "CONTINUOUS", 25),
                                    ("SMOOTH", 8, "CONTINUOUS", 13), ("STAMP", 1, "CONTINUOUS", 35)):
            if name not in L:
                L.add(name, color=color, linetype=lt, lineweight=lw)
        self.doc.header["$LTSCALE"] = 1.0
        st = self.doc.dimstyles.new("PV")
        st.dxf.dimtxt = 2.2
        st.dxf.dimasz = 2.0
        st.dxf.dimexe = 1.0
        st.dxf.dimexo = 0.8
        st.dxf.dimgap = 0.6
        st.dxf.dimdec = 0
        st.dxf.dimtad = 1
        st.dxf.dimclrd = 4
        st.dxf.dimclre = 4

    # primitives -----------------------------------------------------------------
    def line(self, a, b, layer="OUTLINE"):
        self.msp.add_line(a, b, dxfattribs={"layer": layer})

    def pline(self, pts, layer="OUTLINE", closed=False):
        if len(pts) >= 2:
            self.msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})

    def text(self, s, p, h=2.5, layer="TEXT", align=TextEntityAlignment.BOTTOM_LEFT, rot=0.0):
        t = self.msp.add_text(str(s), height=h, rotation=rot, dxfattribs={"layer": layer, "style": "OpenSans"})
        t.set_placement(p, align=align)
        return t

    def rect(self, x0, y0, x1, y1, layer="TABLE"):
        self.pline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, closed=True)

    def circle(self, c, r, layer="OUTLINE"):
        self.msp.add_circle(c, r, dxfattribs={"layer": layer})

    def table(self, x, y_top, widths, rows, h=2.0, row_h=4.6, header=True):
        """Rows of strings; returns the bottom y."""
        y = y_top
        W = sum(widths)
        for i, r in enumerate(rows):
            self.rect(x, y - row_h, x + W, y)
            cx = x
            for w, cell in zip(widths, r):
                self.line((cx, y), (cx, y - row_h), "TABLE")
                s = str(cell)
                maxc = max(int(w / (h * 0.62)), 3)
                if len(s) > maxc:
                    s = s[:maxc - 1] + "~"
                self.text(s, (cx + 0.8, y - row_h + 1.2), h * (1.05 if header and i == 0 else 1.0))
                cx += w
            y -= row_h
        return y

    def dim(self, name, design, p1, p2, base, s, angle=0.0, decimals=0):
        d = self.msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="PV",
                                    override={"dimlfac": float(s), "dimdec": decimals},
                                    dxfattribs={"layer": "DIM"})
        d.render()
        self.dims.append((name, design, d.dimension, float(s)))

    def frame(self, number, rev, scale_txt, status, sheet_no, sheets, project, units="mm",
              projection="Third angle; views labelled with viewing direction"):
        W, H = A1
        self.rect(0, 0, W, H, "FRAME")
        self.rect(20, 10, W - 10, H - 10, "FRAME")
        x0, y0 = W - 10 - 190, 10
        rows = [["Project", project], ["Title", self.title], ["Drawing no.", number],
                ["Revision", rev], ["Scale", scale_txt], ["Units", units], ["Projection", projection],
                ["Sheet", f"{sheet_no} of {sheets}"], ["Status", status]]
        y = y0 + 9 * 5.6
        self.table(x0, y, [34, 156], rows, h=2.4, row_h=5.6, header=False)
        self.rect(x0, y, x0 + 190, y + 12, "STAMP")
        self.text("PRELIMINARY - NOT FOR FABRICATION", (x0 + 95, y + 6), 5.0, "STAMP",
                  TextEntityAlignment.MIDDLE_CENTER)
        return x0, y + 12

    # views ------------------------------------------------------------------------
    def view(self, data, origin, s, label, show_hidden=True, hatch=False, label_gap=9.0):
        ox, oy = origin
        tr = (lambda p: (ox + p[0] / s, oy + p[1] / s))
        for pl in data.get("visible", []):
            self.pline([tr(p) for p in pl], "OUTLINE")
        for pl in data.get("smooth", []):
            self.pline([tr(p) for p in pl], "SMOOTH")
        if show_hidden:
            for pl in data.get("hidden", []):
                self.pline([tr(p) for p in pl], "HIDDEN")
        if hatch:
            for lp in data.get("cut_loops", []):
                if len(lp) < 3:
                    continue
                h = self.msp.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
                h.set_pattern_fill("ANSI31", scale=0.35)
                h.paths.add_polyline_path([tr(p) for p in lp], is_closed=True)
        xs = [tr(p)[0] for pl in data.get("visible", []) for p in pl]
        ys = [tr(p)[1] for pl in data.get("visible", []) for p in pl]
        if xs:
            self.text(label, ((min(xs) + max(xs)) / 2, min(ys) - label_gap), 3.5, align=TextEntityAlignment.MIDDLE_CENTER)
        return tr

    # output -----------------------------------------------------------------------
    def check_dims(self):
        out = []
        for name, design, ent, s in self.dims:
            drawn = ent.get_measurement() * s
            out.append({"dimension": name, "design_mm": round(design, 3), "drawn_mm": round(drawn, 3),
                        "ok": abs(drawn - design) <= 0.5})
        return out

    def save(self, dxf_path, pdf_path):
        self.doc.saveas(dxf_path)
        pdf_ok, err = render_pdf(self.doc, pdf_path)
        return {"dxf": str(dxf_path), "pdf": str(pdf_path) if pdf_ok else None, "pdf_error": err}


def render_pdf(doc, pdf_path):
    try:
        from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf
        backend = pymupdf.PyMuPdfBackend()
        cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                                   color_policy=config.ColorPolicy.BLACK,
                                   lineweight_policy=config.LineweightPolicy.ABSOLUTE,
                                   lineweight_scaling=1.0, hatch_policy=config.HatchPolicy.NORMAL)
        Frontend(RenderContext(doc), backend, config=cfg).draw_layout(doc.modelspace())
        page = layout.Page(A1[0], A1[1], layout.Units.mm, margins=layout.Margins.all(0))
        Path(pdf_path).write_bytes(backend.get_pdf_bytes(page, settings=layout.Settings(fit_page=True)))
        return True, None
    except Exception as exc:  # noqa: BLE001 - report, the DXF is still valid
        return False, f"{type(exc).__name__}: {exc}"


def _pick_scale(extent_mm, avail_mm):
    return next((s for s in STD_SCALES if extent_mm / s <= avail_mm), STD_SCALES[-1])


# ---------------------------------------------------------------------------------
# GA sheet
# ---------------------------------------------------------------------------------

def ga_sheet(geo, proj, results, bom, number):
    v = geo["vessel"]
    H = v["overall_height"]
    s = _pick_scale(H, 330.0)
    sh = Sheet(f"General arrangement - {geo['equipment_tag']}")
    a = v["inside_diameter"] / 2
    t1 = geo["courses"][next(iter(geo["courses"]))]["thickness"]
    Ro = a + t1
    btl, ttl = v["bottom_tangent_elevation"], v["top_tangent_elevation"]
    gy = 150.0                      # paper y of grade
    fx, sx, cx = 120.0, 290.0, 455.0
    views = proj["views"]
    tf = sh.view(views["front"], (fx, gy), s, "FRONT VIEW (looking north, from 180 deg)")
    ts = sh.view(views["side"], (sx, gy), s, "SIDE VIEW (looking west, from 90 deg)")
    tc = sh.view(views["section_AA"], (cx, gy), s, "SECTION A-A (plane through 90/270 deg, looking north)",
                 show_hidden=False, hatch=True)
    # centre lines
    for x0 in (fx, sx, cx):
        sh.line((x0, gy - 5), (x0, gy + H / s + 8), "CENTER")
    # --- front view dimensions --------------------------------------------------
    xl = tf((-v["max_radius"], 0))[0] - 12
    sh.dim("overall height", H, tf((0, 0)), tf((0, H)), (xl - 24, gy), s, angle=90)
    sh.dim("bottom tangent elevation", btl, tf((0, 0)), tf((0, btl)), (xl - 12, gy), s, angle=90)
    sh.dim("tangent to tangent", ttl - btl, tf((0, btl)), tf((0, ttl)), (xl - 12, gy), s, angle=90)
    nz = {n["tag"]: n for n in geo["nozzles"]}
    right_off = tf((v["max_radius"], 0))[0] + 10
    k = 0
    for n in geo["nozzles"]:
        if n["location"] != "shell":
            continue
        th = n["orientation"]
        ux = math.sin(math.radians(th))
        if abs(ux) > 0.99:          # profile in the front view (90 / 270 deg)
            side = 1 if ux > 0 else -1
            xb = right_off + 9 * k if side > 0 else xl + 2 - 9 * k
            sh.dim(f"{n['tag']} elevation from BTL", n["elevation_from_btl"], tf((side * Ro, btl)),
                   tf((side * Ro, n["z"])), (xb, gy), s, angle=90)
            sh.dim(f"{n['tag']} projection", n["projection"], tf((side * Ro, n["z"])),
                   tf((side * n["face_distance_from_axis"], n["z"])),
                   (0, tf((0, n["z"]))[1] + 14 + 4 * k), s)
            k += 1
    for n in geo["nozzles"]:
        if n["location"] == "top_head":
            z_out = geo["heads"]["top"]["outer_extreme"]
            sh.dim(f"{n['tag']} projection", n["projection"], tf((0, z_out)), tf((0, n["z"])),
                   (tf((n["neck_od"] / 2, 0))[0] + 8, 0), s, angle=90)
        if n["location"] == "bottom_head":
            z_out = geo["heads"]["bottom"]["outer_extreme"]
            sh.dim(f"{n['tag']} projection", n["projection"], tf((0, n["z"])), tf((0, z_out)),
                   (tf((n["neck_od"] / 2, 0))[0] + 8, 0), s, angle=90)
    lugs = [c for c in geo["components"] if c["kind"] == "lifting_lug"]
    if lugs:
        zc = lugs[0]["params"]["z_center"]
        sh.dim("lifting lug elevation from BTL", zc - btl, tf((Ro, btl)), tf((Ro, zc)), (right_off + 9 * k, gy), s, angle=90)
        k += 1
    legs = [c for c in geo["components"] if c["kind"] == "leg"]
    if legs:
        z1 = legs[0]["params"]["z1"]
        sh.dim("leg top elevation", z1, tf((0, 0)), tf((0, z1)), (right_off + 9 * k, gy), s, angle=90)
    # --- side view: nozzles at 0 / 180 deg in profile -----------------------------
    k = 0
    for n in geo["nozzles"]:
        if n["location"] != "shell":
            continue
        uy = math.cos(math.radians(n["orientation"]))
        if abs(uy) > 0.99:
            side = 1 if uy > 0 else -1
            xb = ts((side * (v["max_radius"] + 10), 0))[0] + side * 9 * k
            sh.dim(f"{n['tag']} elevation from BTL", n["elevation_from_btl"], ts((side * Ro, btl)),
                   ts((side * Ro, n["z"])), (xb, gy), s, angle=90)
            sh.dim(f"{n['tag']} projection", n["projection"], ts((side * Ro, n["z"])),
                   ts((side * n["face_distance_from_axis"], n["z"])), (0, ts((0, n["z"]))[1] + 14), s)
            k += 1
    # --- section: diameters, head depth, straight flange ----------------------------
    zm = (btl + ttl) / 2
    sh.dim("inside diameter", 2 * a, tc((-a, zm)), tc((a, zm)), (0, tc((0, zm))[1] + 6), s)
    sh.dim("outside diameter (bottom course)", 2 * Ro, tc((-Ro, zm - 300)), tc((Ro, zm - 300)),
           (0, tc((0, zm - 300))[1] - 6), s)
    hd = geo["heads"]["top"]["inside_depth"]
    sh.dim("top head inside depth", hd, tc((-a, ttl)), tc((-a * 0.0 - 0.01, ttl + hd)),
           (tc((-Ro, 0))[0] - 10, 0), s, angle=90)
    sf = geo["heads"]["top"]["sf"]
    if sf > 0:
        sh.dim("top head straight flange", sf, tc((Ro, ttl - sf)), tc((Ro, ttl)), (tc((Ro, 0))[0] + 8, 0), s, angle=90)
    for c in geo["components"]:
        if c["kind"] == "shell_course":
            p = c["params"]
            ym = tc((0, (p["z0"] + p["z1"]) / 2))[1]
            sh.text(f"{c['tag']}: t = {p['thickness']:g} ({c['material_label']})", (tc((Ro, 0))[0] + 3, ym), 2.0)
    # --- plan view with orientation ---------------------------------------------------
    pc = (741.0, 235.0)
    sp = _pick_scale(2 * v["max_radius"], 95.0)
    tp = sh.view(views["top"], pc, sp, f"PLAN VIEW (from above), scale 1:{sp}", show_hidden=False, label_gap=16.0)
    R = v["max_radius"] / sp
    sh.line((pc[0], pc[1] - R - 6), (pc[0], pc[1] + R + 10), "CENTER")
    sh.line((pc[0] - R - 6, pc[1]), (pc[0] + R + 6, pc[1]), "CENTER")
    sh.text("0 deg (N)", (pc[0], pc[1] + R + 12), 2.5, align=TextEntityAlignment.BOTTOM_CENTER)
    orient = []
    for n in geo["nozzles"]:
        if n["location"] == "shell":
            orient.append((n["tag"], n["orientation"]))
    for c in geo["components"]:
        if c["kind"] in ("leg", "lifting_lug"):
            orient.append((c["tag"], c["params"]["orientation"]))
    grouped = {}
    for tag, th in orient:
        grouped.setdefault(round(th, 3), []).append(tag)
    for th, tags in sorted(grouped.items()):
        tag = ", ".join(tags)
        u = (math.sin(math.radians(th)), math.cos(math.radians(th)))
        p_in = (pc[0] + u[0] * (Ro / sp) * 0.25, pc[1] + u[1] * (Ro / sp) * 0.25)
        p_out = (pc[0] + u[0] * (R + 4), pc[1] + u[1] * (R + 4))
        sh.line(p_in, p_out, "CENTER")
        sh.text(f"{tag} {th:g} deg", (p_out[0] + u[0] * 1.5, p_out[1] + u[1] * 1.5), 2.0,
                align=TextEntityAlignment.MIDDLE_LEFT if u[0] >= -0.1 else TextEntityAlignment.MIDDLE_RIGHT)
    if legs:
        r_leg = legs[0]["params"]["radius"]
        th0 = math.radians(legs[0]["params"]["orientation"])
        p1 = (r_leg * math.sin(th0), r_leg * math.cos(th0))
        p2 = (-p1[0], -p1[1])
        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
        sh.dim("leg circle diameter", 2 * r_leg, tp(p1), tp(p2), tp((p1[0] * 1.3, p1[1] * 0.0)), sp, angle=ang)
    # --- tables -----------------------------------------------------------------------
    x_t = 651.0
    rows = [["Mark", "Service", "NPS", "Sch/t", "Rating", "Orient.", "Elev.*", "Proj.", "Pad t x OD"]]
    for n in geo["nozzles"]:
        rows.append([n["tag"], n["service"], n.get("nps") or "-", n.get("schedule") or f"{n['neck_wall']:g}",
                     f"Cl{n.get('flange_class') or '-'} {n.get('facing') or ''} {n.get('flange_type') or ''}",
                     "-" if n.get("orientation") is None else f"{n['orientation']:g}",
                     "-" if n.get("elevation_from_btl") is None else f"{n['elevation_from_btl']:g}",
                     f"{n['projection']:g}", "-" if not n.get("pad") else f"{n['pad']['thickness']:g} x {n['pad']['od']:g}"])
    sh.text("NOZZLE SCHEDULE", (x_t, 574), 3.0)
    y = sh.table(x_t, 572, [12, 34, 10, 12, 30, 14, 14, 13, 21], rows, h=1.9, row_h=4.4)
    sh.text("* elevation of nozzle centreline above the bottom tangent line (BTL); head nozzles on the head centreline",
            (x_t, y - 3.5), 1.7)
    p = {r["calc_id"]: r for r in results["records"]}
    mawp = results.get("mawp_MPa")
    gov = next((tv["value"] for tv in p.get("MAWP", {}).get("results", []) if tv["symbol"] == "governing"), "-")
    w = results.get("weights_kg") or {}
    proc = (results.get("_raw_process") or {})
    drows = [["Item", "Value"],
             ["Design code", f"{results['code']['design_code']} {results['code'].get('edition')}"],
             ["Design pressure (int./ext.)", f"{proc.get('design_pressure', '-')} / {proc.get('external_pressure', '-')}"],
             ["MAWP (corroded, hot)", f"{mawp:.3f} MPa(g), governed by {gov}" if mawp else "-"],
             ["Design temperature / MDMT", f"{proc.get('design_temperature', '-')} / {proc.get('mdmt', '-')}"],
             ["Corrosion allowance", str(proc.get("corrosion_allowance", "-"))],
             ["Hydrotest pressure (top)", f"{results.get('test_pressure_top_MPa') or 0:.3f} MPa(g), {proc.get('test_position', '')}"],
             ["Joint efficiency A / B", f"{results['joint_efficiencies'].get('shell_longitudinal')} / {results['joint_efficiencies'].get('shell_circumferential')}"],
             ["Internal volume", f"{geo['vessel']['internal_volume_mm3'] / 1e9:.3f} m3"],
             ["Weight empty / test", f"{w.get('empty', 0):.0f} / {w.get('test', 0):.0f} kg (net theoretical)"],
             ["Shell / head material", f"{_mat(geo, 'shell_course')} / {_mat(geo, 'head')}"],
             ["Package stage", results["gate"]["stage"]],
             ["Calc. results", results["results_hash"][:16]]]
    sh.text("DESIGN DATA", (x_t, y - 10), 3.0)
    y = sh.table(x_t, y - 12, [44, 116], drows, h=1.9, row_h=4.4)
    notes = ["NOTES",
             "1. All dimensions in mm. Elevations from grade = underside of base plates unless noted.",
             "2. Orientation: 0 deg = plant north, clockwise seen from above.",
             "3. Weld sizes, bevels and fit-up are NOT defined in the design input and are not shown",
             "   (UG-41 / UW-16 not evaluated). General tolerances: not specified by the project.",
             "4. Flange dimensions are representative values to be verified against ASME B16.5.",
             "5. Material data and code references are not verified: see calculation report.",
             "6. Views from the FreeCAD model STEP, polygonal hidden-line removal."]
    yy = y - 8
    for i, line in enumerate(notes):
        sh.text(line, (x_t, yy - 4.2 * i), 2.6 if i == 0 else 1.9)
    proj_label = f"1:{s} (plan 1:{sp})"
    sh.frame(number, geo["revision"], proj_label, results["gate"]["stage"], 1, 2,
             f"{geo['project_id']} - {geo['equipment_tag']}")
    return sh, s


def _mat(geo, kind):
    c = next((c for c in geo["components"] if c["kind"] == kind), None)
    return c["material_label"].split(" (")[0] if c else "-"


# ---------------------------------------------------------------------------------
# fabrication sheet
# ---------------------------------------------------------------------------------

def fab_sheet(geo, results, bom, number):
    sh = Sheet(f"Fabrication details - {geo['equipment_tag']}")
    v = geo["vessel"]
    a = v["inside_diameter"] / 2
    btl = v["bottom_tangent_elevation"]
    courses = [c for c in geo["components"] if c["kind"] == "shell_course"]
    # --- shell development (plate layout) --------------------------------------------
    Lmax = max(math.pi * (2 * a + c["params"]["thickness"]) for c in courses)
    s = _pick_scale(Lmax, 300.0)
    x0, y0 = 40.0, 300.0
    sh.text(f"SHELL DEVELOPMENT (mean diameter, seen from outside), scale 1:{s}", (x0, y0 + sum(c['params']['length'] for c in courses) / s + 12), 3.0)
    y = y0
    for c in courses:
        p = c["params"]
        Ld = math.pi * (2 * a + p["thickness"])
        h = p["length"]
        sh.rect(x0, y, x0 + Ld / s, y + h / s, "OUTLINE")
        sh.text(f"{c['tag']}  {Ld:.0f} x {h:.0f} x t{p['thickness']:g}  ({c['material_label']})",
                (x0 + 2, y + 6), 2.2)
        seam = p.get("long_seam_orientation") or 0.0
        pos = (lambda th, seam=seam, Ld=Ld: ((th - seam) % 360.0) / 360.0 * Ld)   # from the seam, clockwise
        sh.text(f"plate edges = long seam at {seam:g} deg", (x0 + 1, y + 2), 1.8)
        for ref in (0, 90, 180, 270):
            xr = x0 + pos(ref) / s
            sh.line((xr, y), (xr, y + h / s), "CENTER")
            sh.text(f"{ref} deg", (xr + 0.8, y + h / s - 9), 1.8)
        sh.dim(f"{c['tag']} developed length", Ld, (x0, y), (x0 + Ld / s, y), (0, y - 6), s)
        sh.dim(f"{c['tag']} height", h, (x0 + Ld / s, y), (x0 + Ld / s, y + h / s), (x0 + Ld / s + 8, 0), s, angle=90)
        for n in geo["nozzles"]:
            if n.get("parent") != c["tag"]:
                continue
            xn = x0 + pos(n["orientation"]) / s
            yn = y + (n["z"] - p["z0"]) / s
            r_open = (n["neck_od"] if n["attachment"] == "set_in" else n["neck_id"]) / 2
            sh.circle((xn, yn), r_open / s)
            if n.get("pad"):
                sh.circle((xn, yn), n["pad"]["od"] / 2 / s, "HIDDEN")
            sh.text(f"{n['tag']} D{2 * r_open:.0f}", (xn + r_open / s + 1, yn + 1), 1.8)
            sh.dim(f"{n['tag']} position from long seam (developed)", pos(n["orientation"]), (x0, yn), (xn, yn),
                   (0, yn + 3 + r_open / s), s)
            sh.dim(f"{n['tag']} centre from course bottom", n["z"] - p["z0"], (xn, y), (xn, yn),
                   (xn + r_open / s + 6, 0), s, angle=90)
        for lg in (c2 for c2 in geo["components"] if c2["kind"] == "lifting_lug" and c2["params"]["parent"] == c["tag"]):
            q = lg["params"]
            xl_ = x0 + pos(q["orientation"]) / s
            yl_ = y + (q["z_center"] - p["z0"]) / s
            sh.rect(xl_ - q["thickness"] / 2 / s, yl_ - q["height"] / 2 / s, xl_ + q["thickness"] / 2 / s,
                    yl_ + q["height"] / 2 / s, "OUTLINE")
            sh.text(lg["tag"], (xl_ + 2, yl_), 1.8)
        y += h / s + 14
    # --- head detail ---------------------------------------------------------------------
    hd = next(c for c in geo["components"] if c["kind"] == "head")
    hp = hd["params"]
    from ..geometry.profiles import HeadProfile
    prof = HeadProfile(hp["type"], a, hp.get("aspect_ratio") or 2.0, hp.get("crown_radius") or 0.0, hp.get("knuckle_radius") or 0.0)
    sh_ = _pick_scale(a + hp["thickness"], 120.0)
    ox, oy = 470.0, 330.0
    t = hp["thickness"]
    inner = [(ox + x / sh_, oy + y / sh_) for x, y in prof.samples(0.0, 120)]
    outer = [(ox + x / sh_, oy + y / sh_) for x, y in prof.samples(t, 120)]
    sh.pline(inner)
    sh.pline(outer)
    sfp = hp["straight_flange"]
    sh.pline([(ox + a / sh_, oy), (ox + a / sh_, oy - sfp / sh_)])
    sh.pline([(ox + (a + t) / sh_, oy), (ox + (a + t) / sh_, oy - sfp / sh_)])
    sh.line((ox + a / sh_, oy - sfp / sh_), (ox + (a + t) / sh_, oy - sfp / sh_))
    sh.line((ox, oy - sfp / sh_ - 4), (ox, oy + (prof.depth + t) / sh_ + 6), "CENTER")
    sh.line((ox - 4, oy), (ox + (a + t) / sh_ + 6, oy), "CENTER")
    sh.text("TL", (ox + (a + t) / sh_ + 7, oy - 1), 2.0)
    sh.text(f"HEAD DETAIL ({hp['type']}{' %g:1' % hp['aspect_ratio'] if hp['type'] == 'ellipsoidal' else ''}), "
            f"scale 1:{sh_}", (ox, oy + (prof.depth + t) / sh_ + 12), 3.0)
    sh.dim("head inside radius", a, (ox, oy - sfp / sh_ - 2), (ox + a / sh_, oy - sfp / sh_ - 2),
           (0, oy - sfp / sh_ - 10), sh_)
    sh.dim("head inside depth", prof.depth, (ox, oy), (ox, oy + prof.depth / sh_), (ox - 10, 0), sh_, angle=90)
    sh.dim("straight flange", sfp, (ox + (a + t) / sh_, oy - sfp / sh_), (ox + (a + t) / sh_, oy),
           (ox + (a + t) / sh_ + 10, 0), sh_, angle=90)
    sh.text(f"t nominal {t:g} mm, minimum after forming {hp.get('min_thickness_after_forming')} mm "
            f"({hd['material_label']}); blank size and forming by the head maker", (ox, oy - sfp / sh_ - 18), 2.0)
    # --- leg + base plate and lug details ------------------------------------------------
    legs = [c for c in geo["components"] if c["kind"] == "leg"]
    bps = [c for c in geo["components"] if c["kind"] == "base_plate"]
    if legs and bps:
        bp = bps[0]["params"]
        lg = legs[0]["params"]
        sb = 5
        cxy = (470.0, 190.0)
        Lb, Wb = bp["length"] / sb, bp["width"] / sb
        sh.rect(cxy[0] - Wb / 2, cxy[1] - Lb / 2, cxy[0] + Wb / 2, cxy[1] + Lb / 2, "OUTLINE")
        sh.circle(cxy, lg["od"] / 2 / sb)
        sh.circle(cxy, (lg["od"] / 2 - lg["wall"]) / sb)
        for kk in range(bp["anchor_holes"]):
            off = (kk - (bp["anchor_holes"] - 1) / 2) * bp["anchor_spacing"] / sb
            sh.circle((cxy[0], cxy[1] + off), bp["anchor_hole_diameter"] / 2 / sb)
        sh.text(f"LEG BASE PLATE (plan; radial direction up), scale 1:{sb}", (cxy[0] - Wb / 2, cxy[1] + Lb / 2 + 8), 3.0)
        sh.dim("base plate width", bp["width"], (cxy[0] - Wb / 2, cxy[1] - Lb / 2), (cxy[0] + Wb / 2, cxy[1] - Lb / 2),
               (0, cxy[1] - Lb / 2 - 7), sb)
        sh.dim("base plate length", bp["length"], (cxy[0] + Wb / 2, cxy[1] - Lb / 2), (cxy[0] + Wb / 2, cxy[1] + Lb / 2),
               (cxy[0] + Wb / 2 + 8, 0), sb, angle=90)
        if bp["anchor_holes"] > 1:
            sh.dim("anchor hole spacing", bp["anchor_spacing"], (cxy[0], cxy[1] - bp["anchor_spacing"] / 2 / sb),
                   (cxy[0], cxy[1] + bp["anchor_spacing"] / 2 / sb), (cxy[0] - Wb / 2 - 8, 0), sb, angle=90)
        sh.text(f"t = {bp['thickness']:g}, {bp['anchor_holes']} holes D{bp['anchor_hole_diameter']:g} for {bp['anchor_bolt']}; "
                f"leg {lg['section']}, length {lg['z1'] - lg['z0']:.0f}", (cxy[0] - Wb / 2, cxy[1] - Lb / 2 - 16), 2.0)
    lugs = [c for c in geo["components"] if c["kind"] == "lifting_lug"]
    if lugs:
        q = lugs[0]["params"]
        sl = 5
        ox, oy = 560.0, 150.0
        Hh, P = q["height"] / sl, q["projection"] / sl
        sh.rect(ox, oy, ox + P, oy + Hh, "OUTLINE")
        hc = (ox + (q["projection"] - (q["parent_outer_radius"] + q["projection"] - q["hole_center_radius"])) / sl, oy + Hh / 2)
        sh.circle(hc, q["hole_diameter"] / 2 / sl)
        sh.line((ox, oy - 4), (ox, oy + Hh + 4), "CENTER")
        sh.text("shell OD", (ox - 1, oy + Hh + 5), 1.8, align=TextEntityAlignment.BOTTOM_RIGHT)
        sh.text(f"LIFTING LUG (side), scale 1:{sl}", (ox, oy + Hh + 12), 3.0)
        sh.dim("lug height", q["height"], (ox + P, oy), (ox + P, oy + Hh), (ox + P + 8, 0), sl, angle=90)
        sh.dim("lug projection", q["projection"], (ox, oy), (ox + P, oy), (0, oy - 7), sl)
        sh.dim("lug hole edge distance", q["parent_outer_radius"] + q["projection"] - q["hole_center_radius"],
               (hc[0], oy + Hh + 2), (ox + P, oy + Hh + 2), (0, oy + Hh + 5), sl)
        sh.text(f"t = {q['thickness']:g}, hole D{q['hole_diameter']:g}; weld to shell: size TBD", (ox, oy - 15), 2.0)
    # --- nozzle detail table ----------------------------------------------------------------
    rows = [["Mark", "Neck OD x t", "Neck type", "Length*", "Flange OD/thk/hub", "BC / holes", "Pad t x OD", "Parent"]]
    comp = {c["tag"]: c for c in geo["components"]}
    for n in geo["nozzles"]:
        fl = n.get("flange") or {}
        neck = comp.get(f"{n['tag']}-NECK", {}).get("params", {})
        rows.append([n["tag"], f"{n['neck_od']:.1f} x {n['neck_wall']:.2f}",
                     f"{n['neck_type']} {n.get('nps') or ''} {n.get('schedule') or ''}", f"{neck.get('length_at_axis', 0):.0f}",
                     f"{fl.get('od', 0):g}/{fl.get('thickness', 0):g}/{fl.get('length_through_hub') or '-'}",
                     f"{fl.get('bolt_circle', 0):g} / {fl.get('bolt_holes', '-')}xD{fl.get('bolt_hole_diameter', 0):g}",
                     "-" if not n.get("pad") else f"{n['pad']['thickness']:g} x {n['pad']['od']:g}", n.get("parent", "")])
    sh.text("NOZZLE DETAILS", (40, 140), 3.0)
    y = sh.table(40, 138, [12, 26, 30, 16, 34, 34, 22, 16], rows, h=1.9, row_h=4.4)
    sh.text("* neck length along the axis from the shell/head inner surface to the flange weld end", (40, y - 3.5), 1.7)
    # --- BOM ------------------------------------------------------------------------------------
    x_t = 651.0
    brow = [["Item", "Part no.", "Description", "Material", "Qty", "Net kg"]]
    for r in bom["rows"]:
        brow.append([r["item"], r["part_number"], r["description"], f"{r['material_spec']} {r['grade']}".strip(),
                     r["quantity"], "" if r["total_net_kg"] is None else f"{r['total_net_kg']:.1f}"])
    brow.append(["", "", "TOTAL net theoretical", "", "", f"{bom['totals']['net_theoretical_kg']:.1f}"])
    sh.text("BILL OF MATERIALS (see BOM.csv / BOM.xlsx for all columns)", (x_t, 574), 3.0)
    y = sh.table(x_t, 572, [9, 24, 54, 50, 9, 14], brow, h=1.7, row_h=4.0)
    notes = ["NOTES",
             "1. Weld details (sizes, bevels, fit-up, backing) are not defined in the design input and",
             "   are not shown; to be added from the approved WPS and UW-16 / UG-41 evaluation.",
             "2. NDE, PWHT and impact testing: not determined (see calculation report).",
             "3. General tolerances: not specified by the project.",
             "4. Gaskets and bolting are listed but not modelled; stud lengths TBD.",
             "5. Each development starts at the course long seam; positions are measured along the",
             "   mean circumference clockwise seen from above (view from outside)."]
    for i, line in enumerate(notes):
        sh.text(line, (x_t, y - 8 - 4.2 * i), 2.6 if i == 0 else 1.9)
    sh.frame(number, geo["revision"], "as noted", results["gate"]["stage"], 2, 2,
             f"{geo['project_id']} - {geo['equipment_tag']}")
    return sh


# ---------------------------------------------------------------------------------

def generate(package_dir) -> dict:
    pkg = Path(package_dir)
    geo = json.loads((pkg / "01_CALCULATION" / "design_geometry.json").read_text(encoding="utf-8"))
    res = json.loads((pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))
    proj = json.loads((pkg / "03_DRAWINGS_2D" / "projections.json").read_text(encoding="utf-8"))
    bom = json.loads((pkg / "04_BOM" / "bom.json").read_text(encoding="utf-8"))
    inp = next((pkg / "00_INPUT").glob("*.yaml"), None)
    if inp:
        from ..inputs import read_input
        res["_raw_process"] = read_input(inp).get("process", {})
    tag = f"{geo['project_id']}-{geo['equipment_tag'].replace('-', '')}"
    out = {"input_hash": geo["input_hash"], "results_hash": geo.get("results_hash"),
           "projection_source": proj.get("source_step"), "sheets": []}
    ga, s = ga_sheet(geo, proj, res, bom, f"{tag}-GA-001")
    files = ga.save(pkg / "03_DRAWINGS_2D" / "GA.dxf", pkg / "03_DRAWINGS_2D" / "GA.pdf")
    out["sheets"].append({"sheet": "GA", "number": f"{tag}-GA-001", "scale": f"1:{s}", **files,
                          "dimensions": ga.check_dims()})
    fb = fab_sheet(geo, res, bom, f"{tag}-FD-001")
    files = fb.save(pkg / "03_DRAWINGS_2D" / "fabrication_details.dxf", pkg / "03_DRAWINGS_2D" / "fabrication_drawings.pdf")
    out["sheets"].append({"sheet": "FAB", "number": f"{tag}-FD-001", "scale": "as noted", **files,
                          "dimensions": fb.check_dims(), "bom_items_on_sheet": len(bom["rows"])})
    # audit the DXF files by re-reading them
    for sh_ in out["sheets"]:
        d = ezdxf.readfile(sh_["dxf"])
        auditor = d.audit()
        sh_["dxf_audit_errors"] = len(auditor.errors)
        sh_["dxf_dimension_entities"] = len(d.modelspace().query("DIMENSION"))
        sh_["dims_ok"] = all(x["ok"] for x in sh_["dimensions"])
    out["ok"] = all(s_["dims_ok"] and s_["pdf"] and s_["dxf_audit_errors"] == 0 for s_ in out["sheets"])
    (pkg / "03_DRAWINGS_2D" / "drawing_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
