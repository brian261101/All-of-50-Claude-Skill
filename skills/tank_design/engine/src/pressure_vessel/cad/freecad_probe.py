"""Capability probe, run INSIDE FreeCAD (MCP execute_code or freecadcmd).

Checks the operations the CAD stage depends on: new document, Part solids,
Sketcher, PartDesign Body, Spreadsheet, TechDraw page/view, STEP export and
re-import, TechDraw DXF export. Writes a JSON report next to the given path.

    exec(compile(open(p, encoding="utf-8").read(), p, "exec"),
         {"__name__": "__main__", "PROBE_OUT": r"<dir>"})
"""

import json
import os
import time
import traceback

import FreeCAD as App

OUT_DIR = globals().get("PROBE_OUT") or os.environ.get("PV_PROBE_OUT") or App.getUserAppDataDir()


def _try(results, name, fn):
    t0 = time.time()
    try:
        detail = fn()
        results[name] = {"ok": True, "detail": detail, "s": round(time.time() - t0, 2)}
    except Exception as exc:  # noqa: BLE001 - probe records every failure
        results[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                         "trace": traceback.format_exc(limit=2)}


def run(out_dir=OUT_DIR):
    import Part

    os.makedirs(out_dir, exist_ok=True)
    res = {"freecad_version": ".".join(App.Version()[:3]), "gui": App.GuiUp}
    doc = App.newDocument("PV_PROBE")
    state = {}

    def part():
        box = doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 100, 50, 25
        cyl = doc.addObject("Part::Feature", "Cyl")
        cyl.Shape = Part.makeCylinder(10, 40)
        doc.recompute()
        state["box"] = box
        return {"box_volume": round(box.Shape.Volume, 3), "valid": box.Shape.isValid()}

    def sketch():
        import Sketcher
        sk = doc.addObject("Sketcher::SketchObject", "Sketch")
        sk.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(50, 0, 0)))
        sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 50))
        doc.recompute()
        return {"geometry": len(sk.Geometry), "constraints": len(sk.Constraints)}

    def body():
        b = doc.addObject("PartDesign::Body", "Body")
        doc.recompute()
        return {"type": b.TypeId}

    def spreadsheet():
        sh = doc.addObject("Spreadsheet::Sheet", "Params")
        sh.set("A1", "ID")
        sh.set("B1", "1200")
        sh.setAlias("B1", "ID")
        state["box"].setExpression("Length", "Params.ID")
        doc.recompute()
        return {"box_length_from_sheet": state["box"].Length.Value}

    def techdraw():
        page = doc.addObject("TechDraw::DrawPage", "Page")
        tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
        tdir = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "Templates")
        cands = [f for f in os.listdir(tdir) if f.lower().endswith(".svg")] if os.path.isdir(tdir) else []
        if cands:
            tpl.Template = os.path.join(tdir, sorted(cands)[0])
        page.Template = tpl
        view = doc.addObject("TechDraw::DrawViewPart", "View")
        page.addView(view)
        view.Source = [state["box"]]
        view.Direction = App.Vector(0, -1, 0)
        doc.recompute()
        state["page"] = page
        return {"templates_found": len(cands), "view_ok": view.isValid() if hasattr(view, "isValid") else True}

    def step_roundtrip():
        import Import
        p = os.path.join(out_dir, "probe.step")
        Import.export([state["box"]], p)
        shp = Part.read(p)
        return {"bytes": os.path.getsize(p), "reimport_volume": round(shp.Volume, 3)}

    def projectex():
        import TechDraw
        out = TechDraw.projectEx(state["box"].Shape, App.Vector(0, -1, 0))
        return {"n_groups": len(out), "visible_edges": len(out[0].Edges)}

    def dxf_page():
        import TechDraw
        p = os.path.join(out_dir, "probe_page.dxf")
        TechDraw.writeDXFPage(state["page"], p)
        return {"bytes": os.path.getsize(p)}

    def pdf_page():
        if not App.GuiUp:
            raise RuntimeError("TechDrawGui PDF export needs the GUI")
        import TechDrawGui
        p = os.path.join(out_dir, "probe_page.pdf")
        TechDrawGui.exportPageAsPdf(state["page"], p)
        return {"bytes": os.path.getsize(p)}

    def save():
        p = os.path.join(out_dir, "probe.FCStd")
        doc.saveAs(p)
        return {"bytes": os.path.getsize(p)}

    for name, fn in [("part", part), ("sketcher", sketch), ("partdesign_body", body),
                     ("spreadsheet_expressions", spreadsheet), ("techdraw_page", techdraw),
                     ("step_export_reimport", step_roundtrip), ("techdraw_projectEx", projectex),
                     ("techdraw_dxf_page", dxf_page), ("techdraw_pdf_page", pdf_page),
                     ("save_fcstd", save)]:
        _try(res, name, fn)
    App.closeDocument(doc.Name)
    with open(os.path.join(out_dir, "freecad_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
