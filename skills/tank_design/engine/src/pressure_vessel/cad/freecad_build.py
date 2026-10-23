"""Build the vessel in FreeCAD from design_geometry.json (run INSIDE FreeCAD).

Works in the GUI through the FreeCAD MCP (execute_code) and in freecadcmd.
Every solid is built from the same definitions as the analytic weights in
geometry/profiles.py; the script then checks validity, counts, key
dimensions, nozzle orientation, pairwise collisions, and OCC volume versus
the analytic volume, saves .FCStd and .step, re-reads the STEP, and writes
projections.json (TechDraw.projectEx edges) for the 2D drawing stage plus
cad_check.json with every result.

Run (MCP execute_code):
    exec(compile(open(p, encoding="utf-8").read(), p, "exec"),
         {"__name__": "__main__", "PV_ARGS": {"package": r"<package dir>"}})
"""

import json
import math
import os
import sys
import time

import FreeCAD as App
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None


def _args():
    """PV_ARGS (MCP exec globals), else PV_PACKAGE / PV_SRC environment
    variables (freecadcmd), else the last command-line argument."""
    a = globals().get("PV_ARGS") or {}
    if not a and os.environ.get("PV_PACKAGE"):
        a = {"package": os.environ["PV_PACKAGE"], "src": os.environ.get("PV_SRC")}
    if not a and len(sys.argv) > 1:
        a = {"package": sys.argv[-1]}
    return a


def _import_profiles(src_dir):
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from pressure_vessel.geometry import profiles   # pure Python, same definitions as the weights
    return profiles


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def tube_z(ro, ri, z0, z1, cx=0.0, cy=0.0):
    o = Part.makeCylinder(ro, z1 - z0, V(cx, cy, z0), V(0, 0, 1))
    if ri <= 0:
        return o
    return o.cut(Part.makeCylinder(ri, z1 - z0, V(cx, cy, z0), V(0, 0, 1)))


def along(shape, theta_deg, z):
    """Local frame (radial = +Y, z = 0) -> plant frame at plan angle theta,
    clockwise from +Y, at elevation z."""
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(0, 0, 1), -theta_deg)
    s.translate(V(0, 0, z))
    return s


def radial_cyl(r, s0, s1):
    """Cylinder along local +Y (radial) from s0 to s1, centred on y axis at z=0."""
    return Part.makeCylinder(r, s1 - s0, V(0, s0, 0), V(0, 1, 0))


def head_profile_face(prof, t, profiles, inner_only=False):
    """Planar face in the XZ plane (x = rho, z = y) to be revolved about Z."""
    def pts(off, n=240):
        return [V(x, 0, y) for x, y in prof.samples(off, n)]

    def curve(off):
        if prof.kind == "hemispherical":
            p = pts(off, 2)
            mid = prof.point(0.5, off)
            return [Part.Arc(p[0], V(mid[0], 0, mid[1]), p[-1]).toShape()]
        if prof.kind == "torispherical":
            ub = prof.beta / (math.pi / 2)
            a0, am, a1 = prof.point(0.0, off), prof.point(ub / 2, off), prof.point(ub, off)
            c0, cm, c1 = prof.point(ub, off), prof.point((ub + 1) / 2, off), prof.point(1.0, off)
            return [Part.Arc(V(a0[0], 0, a0[1]), V(am[0], 0, am[1]), V(a1[0], 0, a1[1])).toShape(),
                    Part.Arc(V(c0[0], 0, c0[1]), V(cm[0], 0, cm[1]), V(c1[0], 0, c1[1])).toShape()]
        bs = Part.BSplineCurve()
        bs.interpolate(pts(off))
        return [bs.toShape()]

    a, b = prof.a, prof.depth
    inner = curve(0.0)
    if inner_only:
        edges = inner + [Part.LineSegment(V(0, 0, b), V(0, 0, 0)).toShape(),
                         Part.LineSegment(V(0, 0, 0), V(a, 0, 0)).toShape()]
    else:
        outer = curve(t)
        top = prof.point(1.0, t)
        edges = inner + [Part.LineSegment(V(0, 0, b), V(0, 0, top[1])).toShape()] + outer + \
            [Part.LineSegment(V(a + t, 0, 0), V(a, 0, 0)).toShape()]
    w = Part.Wire(Part.__sortEdges__(edges))
    return Part.Face(w)


def revolve(face):
    return face.revolve(V(0, 0, 0), V(0, 0, 1), 360)


def place_head(shape, z_tangent, sign):
    s = shape.copy()
    if sign < 0:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    s.translate(V(0, 0, z_tangent))
    return s


def flange_local(fl, s_face, neck_od, bore, blind=False):
    """Flange along local +Y with its gasket face at y = s_face. A weld-neck
    flange extends inward (towards the vessel); a blind extends outward."""
    tf, rfh = fl["thickness"], fl.get("raised_face_height") or 0.0
    od, rfod = fl["od"], fl.get("raised_face_od") or 0.0
    sgn = 1.0 if blind else -1.0
    y_rf_end = s_face + sgn * rfh
    y_back = s_face + sgn * tf
    parts = []
    if rfh > 0 and rfod > 0:
        parts.append(radial_cyl(rfod / 2, min(s_face, y_rf_end), max(s_face, y_rf_end)))
    ring = radial_cyl(od / 2, min(y_rf_end, y_back), max(y_rf_end, y_back))
    n, dh, bc = fl["bolt_holes"], fl["bolt_hole_diameter"], fl["bolt_circle"]
    for i in range(n):
        ang = math.radians((i + 0.5) * 360.0 / n)
        x, z = bc / 2 * math.cos(ang), bc / 2 * math.sin(ang)
        hole = Part.makeCylinder(dh / 2, tf + 2, V(x, min(y_rf_end, y_back) - 1, z), V(0, 1, 0))
        ring = ring.cut(hole)
    parts.append(ring)
    if not blind and fl.get("hub_od") and fl.get("length_through_hub"):
        y_end = s_face - fl["length_through_hub"]
        hl = y_back - y_end
        parts.append(Part.makeCone(neck_od / 2, fl["hub_od"] / 2, hl, V(0, y_end, 0), V(0, 1, 0)))
    s = parts[0]
    for p in parts[1:]:
        s = s.fuse(p)
    if not blind and bore > 0:
        y0 = s_face - (fl.get("length_through_hub") or tf) - 1
        s = s.cut(radial_cyl(bore / 2, y0, s_face + 1))
    return s.removeSplitter()


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build(geo, profiles):
    comps = {c["tag"]: c for c in geo["components"]}
    a = geo["vessel"]["inside_diameter"] / 2.0
    shapes = {}
    noz = {n["tag"]: n for n in geo["nozzles"]}
    # heads
    for c in geo["components"]:
        if c["kind"] != "head":
            continue
        p = c["params"]
        prof = profiles.HeadProfile(p["type"], a, p.get("aspect_ratio") or 2.0, p.get("crown_radius") or 0.0,
                                    p.get("knuckle_radius") or 0.0)
        body = revolve(head_profile_face(prof, p["thickness"], profiles))
        if p["straight_flange"] > 0:
            body = body.fuse(tube_z(a + p["thickness"], a, -p["straight_flange"], 0.0)).removeSplitter()
        for tag in p.get("openings", []):
            n = noz[tag]
            rh = n["neck_od"] / 2 if n["attachment"] == "set_in" else n["neck_id"] / 2
            body = body.cut(Part.makeCylinder(rh, prof.depth + p["thickness"] + 50, V(0, 0, -1), V(0, 0, 1)))
        shapes[c["tag"]] = place_head(body, p["z_tangent"], p["direction"])
        c["_profile"] = prof
    # shell courses with holes
    for c in geo["components"]:
        if c["kind"] != "shell_course":
            continue
        p = c["params"]
        s = tube_z(a + p["thickness"], a, p["z0"], p["z1"])
        for tag in p.get("openings", []):
            n = noz[tag]
            rh = n["neck_od"] / 2 if n["attachment"] == "set_in" else n["neck_id"] / 2
            s = s.cut(along(radial_cyl(rh, 0.0, a + p["thickness"] + 50), n["orientation"], n["z"]))
        shapes[c["tag"]] = s
    # nozzles
    for n in geo["nozzles"]:
        tag = n["tag"]
        fl = n.get("flange")
        if n["location"] == "shell":
            Ri = a
            Ro = a + n["parent_thickness"]
            s_face, s_weld = n["face_distance_from_axis"], n["weld_distance_from_axis"]
            neck = radial_cyl(n["neck_od"] / 2, 0.0, s_weld).cut(radial_cyl(n["neck_id"] / 2, -1.0, s_weld + 1))
            r_cut = Ri - n.get("inward_projection", 0.0) if n["attachment"] == "set_in" else Ro
            core = Part.makeCylinder(r_cut, 4000, V(0, 0, -2000), V(0, 0, 1))
            shapes[f"{tag}-NECK"] = along(neck.cut(core), n["orientation"], n["z"])
            if n.get("pad"):
                te, Dp = n["pad"]["thickness"], n["pad"]["od"]
                band = Part.makeCylinder(Ro + te, 4000, V(0, 0, -2000), V(0, 0, 1)).cut(
                    Part.makeCylinder(Ro, 4000, V(0, 0, -2000), V(0, 0, 1)))
                pad = band.common(radial_cyl(Dp / 2, 0.0, Ro + te + 10)).cut(radial_cyl(n["neck_od"] / 2, 0.0, Ro + te + 10))
                shapes[f"{tag}-PAD"] = along(pad, n["orientation"], n["z"])
            if fl:
                shapes[f"{tag}-FLG"] = along(flange_local(fl, s_face, n["neck_od"], n["neck_id"]), n["orientation"], n["z"])
                if n.get("blind_cover"):
                    shapes[f"{tag}-BLD"] = along(flange_local(fl, s_face, n["neck_od"], 0.0, blind=True), n["orientation"], n["z"])
        else:
            hc = comps[n["parent"]]
            prof = hc["_profile"]
            p = hc["params"]
            y_face, y_weld = n["face_y_from_tangent"], n["weld_y_from_tangent"]
            neck = tube_z(n["neck_od"] / 2, n["neck_id"] / 2, 0.0, y_weld)
            if n["attachment"] == "set_in":
                inner = revolve(head_profile_face(prof, 0.0, profiles, inner_only=True))
                neck = neck.cut(inner)
            else:
                neck = neck.cut(revolve(head_profile_face(prof, p["thickness"], profiles, inner_only=False)).fuse(
                    revolve(head_profile_face(prof, 0.0, profiles, inner_only=True))))
            shapes[f"{tag}-NECK"] = place_head(neck, p["z_tangent"], p["direction"])
            if fl:
                f = flange_local(fl, y_face, n["neck_od"], n["neck_id"])
                f.rotate(V(0, 0, 0), V(1, 0, 0), 90)       # local +Y -> +Z
                shapes[f"{tag}-FLG"] = place_head(f, p["z_tangent"], p["direction"])
    # legs, base plates, lugs
    for c in geo["components"]:
        p = c["params"]
        if c["kind"] == "leg":
            shapes[c["tag"]] = tube_z(p["od"] / 2, p["od"] / 2 - p["wall"], p["z0"], p["z1"], *p["center"])
        elif c["kind"] == "base_plate":
            L, W, t = p["length"], p["width"], p["thickness"]
            r = math.hypot(*p["center"])
            box = Part.makeBox(W, L, t, V(-W / 2, r - L / 2, 0))
            for k in range(p.get("anchor_holes") or 0):
                off = (k - (p["anchor_holes"] - 1) / 2) * (p.get("anchor_spacing") or 0)
                box = box.cut(Part.makeCylinder(p["anchor_hole_diameter"] / 2, t + 2, V(0, r + off, -1), V(0, 0, 1)))
            shapes[c["tag"]] = along(box, p["orientation"], 0.0)
        elif c["kind"] == "lifting_lug":
            t, H, P, Ro = p["thickness"], p["height"], p["projection"], p["parent_outer_radius"]
            box = Part.makeBox(t, Ro + P, H, V(-t / 2, 0, -H / 2))
            box = box.cut(Part.makeCylinder(Ro, H + 2, V(0, 0, -H / 2 - 1), V(0, 0, 1)))
            box = box.cut(Part.makeCylinder(p["hole_diameter"] / 2, t + 2, V(-t / 2 - 1, p["hole_center_radius"], 0), V(1, 0, 0)))
            shapes[c["tag"]] = along(box, p["orientation"], p["z_center"])
    return shapes


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def checks(geo, shapes):
    out = {"components_expected": len(geo["components"]), "components_built": len(shapes), "items": []}

    def item(name, ok, detail):
        out["items"].append({"check": name, "ok": bool(ok), "detail": detail})

    missing = [c["tag"] for c in geo["components"] if c["tag"] not in shapes]
    item("all components built", not missing, {"missing": missing})
    vol = []
    for c in geo["components"]:
        s = shapes.get(c["tag"])
        if s is None:
            continue
        ok_valid = s.isValid() and len(s.Solids) >= 1
        occ = sum(x.Volume for x in s.Solids)
        rel = abs(occ - c["volume_mm3"]) / c["volume_mm3"]
        vol.append({"tag": c["tag"], "valid": ok_valid, "solids": len(s.Solids), "occ_volume": occ,
                    "analytic_volume": c["volume_mm3"], "rel_diff": rel})
    item("solids valid", all(v["valid"] for v in vol), [v["tag"] for v in vol if not v["valid"]])
    item("OCC volume = analytic volume (rel <= 2e-3)", all(v["rel_diff"] <= 2e-3 for v in vol),
         {"worst": max(vol, key=lambda v: v["rel_diff"]) if vol else None})
    out["volumes"] = vol
    # key dimensions
    bb = None
    for s in shapes.values():
        bb = s.BoundBox if bb is None else bb.united(s.BoundBox)
    oh = geo["vessel"]["overall_height"]
    item("overall height (bbox ZMax) = design", abs(bb.ZMax - oh) < 0.5, {"cad": bb.ZMax, "design": oh})
    item("grade at z = 0 (bbox ZMin)", abs(bb.ZMin) < 0.5, {"cad": bb.ZMin})
    rmax = max(abs(bb.XMin), abs(bb.XMax), abs(bb.YMin), abs(bb.YMax))
    item("max plan extent within design max radius", rmax <= geo["vessel"]["max_radius"] + 0.5,
         {"cad": rmax, "design": geo["vessel"]["max_radius"]})
    out["bbox"] = [bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax]
    # nozzle orientation and position (flange centre of mass on the design axis)
    noz = []
    for n in geo["nozzles"]:
        s = shapes.get(f"{n['tag']}-FLG") or shapes.get(f"{n['tag']}-NECK")
        cm = s.Solids[0].CenterOfMass
        if n["location"] == "shell":
            ang = math.degrees(math.atan2(cm.x, cm.y)) % 360
            d_ang = abs((ang - n["orientation"] + 180) % 360 - 180)
            ok = d_ang < 0.05 and abs(cm.z - n["z"]) < 0.05
            noz.append({"tag": n["tag"], "design_orientation": n["orientation"], "cad_orientation": ang,
                        "design_z": n["z"], "cad_z": cm.z, "ok": ok})
        else:
            ok = math.hypot(cm.x, cm.y) < 0.05 and (cm.z - n["axis_point"][2]) * n["axis_dir"][2] > 0
            noz.append({"tag": n["tag"], "design": "head centreline", "cad_xy": [cm.x, cm.y], "ok": ok})
    item("nozzle orientation / elevation", all(x["ok"] for x in noz), noz)
    # collisions: any pair sharing more than 1 mm3 of volume
    tags = list(shapes)
    hits, pairs = [], 0
    for i, ta in enumerate(tags):
        for tb in tags[i + 1:]:
            A, B = shapes[ta], shapes[tb]
            if not A.BoundBox.intersect(B.BoundBox):
                continue
            pairs += 1
            try:
                v = A.common(B).Volume
            except Exception as exc:   # noqa: BLE001 - record and continue
                hits.append({"a": ta, "b": tb, "error": str(exc)})
                continue
            if v > 1.0:
                hits.append({"a": ta, "b": tb, "volume_mm3": v})
    item("no unintended collisions (> 1 mm3)", not hits, {"pairs_tested": pairs, "hits": hits})
    out["ok"] = all(i["ok"] for i in out["items"])
    return out


# ---------------------------------------------------------------------------
# projections for the drawing stage
# ---------------------------------------------------------------------------

ROT = {   # rotations that bring each view direction onto +Z for projectEx
    "front": (V(1, 0, 0), -90.0),      # viewer at -Y (south): x = X, y = Z
    "top": (None, 0.0),                # viewer above: x = X, y = Y
}


def _edges_to_polylines(shape, defl=0.25):
    out = []
    for e in shape.Edges:
        try:
            pts = e.discretize(Deflection=defl)
        except Exception:  # noqa: BLE001
            continue
        if len(pts) >= 2:
            out.append([[round(p.x, 3), round(p.y, 3)] for p in pts])
    return out


def projections(shapes, geo):
    import TechDraw
    comp = Part.makeCompound(list(shapes.values()))
    views = {}
    for name in ("front", "top", "side"):
        s = comp.copy()
        if name == "front":
            s.rotate(V(0, 0, 0), V(1, 0, 0), -90)
        elif name == "side":                 # viewer at +X (east): x = Y, y = Z
            m = App.Matrix(0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1)
            s.transformShape(m)
        g = TechDraw.projectEx(s, V(0, 0, 1))
        views[name] = {"visible": _edges_to_polylines(g[0]) + _edges_to_polylines(g[1]) + _edges_to_polylines(g[3]),
                       "hidden": _edges_to_polylines(g[5]) + _edges_to_polylines(g[8])}
    # section A-A: plane Y = 0, keep Y >= 0, viewed from -Y
    big = 1e5
    keep = Part.makeBox(2 * big, big, 2 * big, V(-big, 0, -big))
    cut = comp.common(keep)
    s = cut.copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), -90)
    g = TechDraw.projectEx(s, V(0, 0, 1))
    hatch = []
    for w in comp.slice(V(0, 1, 0), 0.0):
        pts = w.discretize(Deflection=0.2)
        hatch.append([[round(p.x, 3), round(p.z, 3)] for p in pts])
    views["section_AA"] = {"visible": _edges_to_polylines(g[0]) + _edges_to_polylines(g[1]) + _edges_to_polylines(g[3]),
                           "hidden": [], "cut_faces": hatch}
    return views


# ---------------------------------------------------------------------------

def main():
    args = _args()
    pkg = args["package"]
    src = args.get("src") or (os.path.dirname(os.path.dirname(os.path.dirname(HERE))) if HERE else None)
    profiles = _import_profiles(src or os.path.join(os.path.dirname(pkg), "..", "src"))
    geo = json.load(open(os.path.join(pkg, "01_CALCULATION", "design_geometry.json"), encoding="utf-8"))
    outdir = os.path.join(pkg, "02_CAD_3D")
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    shapes = build(geo, profiles)
    t_build = time.time() - t0
    report = checks(geo, shapes)
    report["build_seconds"] = round(t_build, 2)

    name = f"{geo['equipment_tag'].replace('-', '_')}_rev{geo['revision']}"
    for d in list(App.listDocuments()):
        if d == name:
            App.closeDocument(d)
    doc = App.newDocument(name)
    try:
        doc.UnitSystem = "Metric small parts & CNC (mm, mm/min)"
    except Exception:  # noqa: BLE001 - older/newer FreeCAD
        pass
    groups = {}
    colours = {"shell": (0.72, 0.74, 0.78), "heads": (0.72, 0.74, 0.78), "nozzles": (0.55, 0.6, 0.7),
               "pads": (0.8, 0.6, 0.3), "flanges": (0.45, 0.5, 0.6), "supports": (0.35, 0.35, 0.35),
               "lugs": (0.85, 0.7, 0.1)}
    objs = []
    for c in geo["components"]:
        g = c["bom_group"] or "other"
        if g not in groups:
            groups[g] = doc.addObject("App::DocumentObjectGroup", g.capitalize())
        o = doc.addObject("Part::Feature", c["tag"].replace("-", "_"))
        o.Shape = shapes[c["tag"]]
        o.Label = f"{c['tag']} {c['description']}"
        for prop, val in (("Tag", c["tag"]), ("Component", c["kind"]), ("Material", c["material_label"]),
                          ("MaterialStatus", c["material_status"]), ("CalcRef", c["calc_ref"]),
                          ("Description", c["description"])):
            o.addProperty("App::PropertyString", prop, "PV_Design")
            setattr(o, prop, str(val))
        o.addProperty("App::PropertyFloat", "AnalyticVolume_mm3", "PV_Design")
        o.AnalyticVolume_mm3 = float(c["volume_mm3"])
        o.addProperty("App::PropertyBool", "PressurePart", "PV_Design")
        o.PressurePart = bool(c["pressure_part"])
        groups[g].addObject(o)
        if App.GuiUp:
            o.ViewObject.ShapeColor = colours.get(g, (0.7, 0.7, 0.7))
        objs.append(o)
    sh = doc.addObject("Spreadsheet::Sheet", "Params")
    rows = [("project_id", geo["project_id"]), ("equipment_tag", geo["equipment_tag"]), ("revision", geo["revision"]),
            ("input_hash", geo["input_hash"]), ("results_hash", geo.get("results_hash", "")),
            ("ID_mm", geo["vessel"]["inside_diameter"]), ("TT_mm", geo["vessel"]["tangent_to_tangent"]),
            ("BTL_mm", geo["vessel"]["bottom_tangent_elevation"]), ("overall_height_mm", geo["vessel"]["overall_height"]),
            ("status", "PRELIMINARY - NOT FOR FABRICATION")]
    for i, (k, v) in enumerate(rows, 1):
        sh.set(f"A{i}", k)
        sh.set(f"B{i}", f"'{v}" if isinstance(v, str) else str(v))
        if isinstance(v, (int, float)):
            sh.setAlias(f"B{i}", k)
    doc.recompute()
    fc = os.path.join(outdir, f"{name}.FCStd")
    doc.saveAs(fc)
    import Import
    step = os.path.join(outdir, f"{name}.step")
    Import.export(objs, step)
    rd = Part.read(step)
    occ_total = sum(s.Volume for s in Part.makeCompound(list(shapes.values())).Solids)
    report["step"] = {"file": step, "bytes": os.path.getsize(step), "solids_reimported": len(rd.Solids),
                      "solids_expected": sum(len(s.Solids) for s in shapes.values()),
                      "volume_reimported": rd.Volume, "volume_model": occ_total}
    report["step"]["volume_rel_diff"] = abs(rd.Volume - occ_total) / occ_total
    report["items"].append({"check": "STEP re-import: solid count and volume (rel <= 1e-4)", "ok":
                            report["step"]["solids_reimported"] == report["step"]["solids_expected"] and
                            report["step"]["volume_rel_diff"] <= 1e-4, "detail": report["step"]})
    report["fcstd"] = {"file": fc, "bytes": os.path.getsize(fc)}
    report["ok"] = all(i["ok"] for i in report["items"])
    report.update({"input_hash": geo["input_hash"], "results_hash": geo.get("results_hash"),
                   "freecad_version": ".".join(App.Version()[:3]), "document": name,
                   "mode": "GUI (MCP)" if App.GuiUp else "freecadcmd"})
    json.dump(report, open(os.path.join(outdir, "cad_check.json"), "w", encoding="utf-8"), indent=1, default=str)
    if args.get("projections", False):
        t1 = time.time()
        views = projections(shapes, geo)
        json.dump({"input_hash": geo["input_hash"], "results_hash": geo.get("results_hash"), "views": views,
                   "seconds": round(time.time() - t1, 2)},
                  open(os.path.join(outdir, "projections.json"), "w", encoding="utf-8"))
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.ActiveDocument.ActiveView.viewIsometric()
        Gui.SendMsgToActiveView("ViewFit")
    return report


# freecadcmd runs the file with __name__ set to the module name, so the
# environment variable marks a headless run as well
if __name__ == "__main__" or (os.environ.get("PV_PACKAGE") and "PV_ARGS" not in globals()):
    r = main()
    print(json.dumps({k: r[k] for k in ("ok", "components_expected", "components_built", "build_seconds")}, indent=1))
    for it in r["items"]:
        print(("OK  " if it["ok"] else "FAIL"), it["check"])
