"""Add a TechDraw page to the vessel document and export it (run INSIDE the
FreeCAD GUI, after freecad_build.py, through the MCP).

Views use CoarseView (polygonal hidden-line removal): exact HLR stalled on
the revolved B-spline heads on this machine. The page is the native FreeCAD
drawing; the fully dimensioned GA/fabrication sheets are produced by the
ezdxf stage (drawings/ga.py) from the same STEP.
"""

import glob
import json
import os
import time

import FreeCAD as App


def _template():
    tdir = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "Templates")
    cands = sorted(glob.glob(os.path.join(tdir, "**", "*.svg"), recursive=True))
    for pref in ("A3_Landscape_ISO7200TD", "A3_Landscape", "A3", "A4_Landscape"):
        for c in cands:
            if pref.lower() in os.path.basename(c).lower():
                return c, cands
    return (cands[0] if cands else None), cands


def main():
    args = globals().get("PV_ARGS") or {}
    pkg = args["package"]
    geo = json.load(open(os.path.join(pkg, "01_CALCULATION", "design_geometry.json"), encoding="utf-8"))
    name = f"{geo['equipment_tag'].replace('-', '_')}_rev{geo['revision']}"
    fc = os.path.join(pkg, "02_CAD_3D", f"{name}.FCStd")
    doc = App.getDocument(name) if name in App.listDocuments() else App.openDocument(fc)
    # removing a page also removes its views: collect names first, then re-check
    for nm in [o.Name for o in doc.Objects if o.TypeId.startswith("TechDraw::")]:
        if doc.getObject(nm) is not None:
            doc.removeObject(nm)
    parts = [o for o in doc.Objects if o.TypeId == "Part::Feature"]
    page = doc.addObject("TechDraw::DrawPage", "GA_Page")
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
    path, cands = _template()
    tpl.Template = path
    page.Template = tpl
    H = geo["vessel"]["overall_height"]
    scale = next(s for s in (1 / 10, 1 / 15, 1 / 20, 1 / 25, 1 / 30, 1 / 40, 1 / 50) if H * s <= 200)
    specs = [("Front", App.Vector(0, -1, 0), App.Vector(1, 0, 0), (95, 150)),
             ("Side", App.Vector(1, 0, 0), App.Vector(0, 1, 0), (185, 150)),
             ("Top", App.Vector(0, 0, 1), App.Vector(1, 0, 0), (265, 215)),
             ("Iso", App.Vector(1, -1, 0.8), App.Vector(1, 1, 0), (365, 205))]
    views = []
    for nm, d, xd, (x, y) in specs:
        v = doc.addObject("TechDraw::DrawViewPart", f"View_{nm}")
        page.addView(v)
        v.Source = parts
        v.Direction = d
        v.XDirection = xd
        v.ScaleType = "Custom"
        v.Scale = scale * (0.45 if nm == "Iso" else 1.0)
        v.CoarseView = True
        v.HardHidden = False
        v.X, v.Y = x, y
        v.Label = f"{nm} view"
        views.append(v)
    # Every template field gets a deliberate value or is blanked, so no template
    # default (sample names, materials, tolerance classes) survives. Approval
    # fields are never filled by software.
    fill = {"title": f"{geo['equipment_tag']} GA - TechDraw views",
            "supplementary_title_1": "Dimensions: see GA.pdf",
            "supplementary_title_2": "PRELIMINARY - NOT FOR FABRICATION",
            "document_type": "General arrangement (views only)",
            "document_status": "PRELIMINARY - NOT FOR FABRICATION",
            "drawing_number": f"{geo['project_id']}-{geo['equipment_tag']}-TD-001",
            "revision_index": str(geo["revision"]), "scale": f"1:{round(1 / scale)}",
            "date_of_issue": time.strftime("%Y-%m-%d"), "creator": "pressure_vessel",
            "general_tolerances": "Not specified", "part_material": "See BOM / calculation report",
            "language_code": "EN", "sheet_number": "1/1"}
    texts = {k: fill.get(k, "") for k in tpl.EditableTexts}
    tpl.EditableTexts = texts
    doc.recompute()
    t0 = time.time()
    done = False
    if App.GuiUp:
        import FreeCADGui as Gui
        while time.time() - t0 < float(args.get("wait_s", 240)):
            Gui.updateGui()
            try:
                done = all(len(v.getVisibleEdges()) > 0 for v in views)
            except Exception:  # noqa: BLE001
                done = False
            if done:
                break
            time.sleep(0.25)
    out = {"template": path, "templates_found": len(cands), "scale": f"1:{round(1 / scale)}",
           "views": {v.Label: (len(v.getVisibleEdges()) if hasattr(v, "getVisibleEdges") else None) for v in views},
           "views_complete": done, "seconds": round(time.time() - t0, 1)}
    doc.save()
    out["fcstd"] = fc
    json.dump(out, open(os.path.join(pkg, "02_CAD_3D", "techdraw_check.json"), "w", encoding="utf-8"), indent=1)
    return out


def export():
    """Second step (separate MCP call): DXF, then PDF. The PDF exporter needs
    the page open in its GUI window, otherwise it writes nothing."""
    args = globals().get("PV_ARGS") or {}
    pkg = args["package"]
    geo = json.load(open(os.path.join(pkg, "01_CALCULATION", "design_geometry.json"), encoding="utf-8"))
    name = f"{geo['equipment_tag'].replace('-', '_')}_rev{geo['revision']}"
    doc = App.getDocument(name)
    page = doc.getObject("GA_Page")
    chk_path = os.path.join(pkg, "02_CAD_3D", "techdraw_check.json")
    out = json.load(open(chk_path, encoding="utf-8")) if os.path.exists(chk_path) else {}
    ddir = os.path.join(pkg, "03_DRAWINGS_2D")
    os.makedirs(ddir, exist_ok=True)
    import TechDraw
    dxf = os.path.join(ddir, f"{name}_TechDraw_views.dxf")
    TechDraw.writeDXFPage(page, dxf)
    out.update({"dxf": dxf, "dxf_bytes": os.path.getsize(dxf)})
    json.dump(out, open(chk_path, "w", encoding="utf-8"), indent=1)
    if App.GuiUp:
        import FreeCADGui as Gui
        import TechDrawGui
        page.ViewObject.doubleClicked()
        Gui.updateGui()
        pdf = os.path.join(ddir, f"{name}_TechDraw_views.pdf")
        if os.path.exists(pdf):
            os.remove(pdf)
        t0 = time.time()
        TechDrawGui.exportPageAsPdf(page, pdf)
        out.update({"pdf": pdf, "pdf_bytes": os.path.getsize(pdf) if os.path.exists(pdf) else 0,
                    "pdf_seconds": round(time.time() - t0, 1)})
    doc.save()
    out["exported"] = bool(out.get("pdf_bytes")) and bool(out.get("dxf_bytes"))
    json.dump(out, open(chk_path, "w", encoding="utf-8"), indent=1)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
    print(json.dumps(export(), indent=1))
