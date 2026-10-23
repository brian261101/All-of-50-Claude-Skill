"""Hidden-line projections of the exported STEP with OpenCASCADE (OCP).

Runs in system Python (cadquery-ocp), reading the STEP written by the
FreeCAD stage, so the 2D views come from the same B-rep as the 3D model.
Views (model: Z up, plan 0 deg = +Y):
    front  viewer at -Y (south): u = X, v = Z
    side   viewer at +X (east):  u = Y, v = Z
    top    viewer above:         u = X, v = Y
    section_AA  plane Y = 0, material with Y >= 0 kept, viewed from -Y
Output polylines are in model millimetres.

    python -I -m pressure_vessel.drawings.hlr <package_dir>
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

VIEWS = {
    "front": {"N": (0, -1, 0), "Vx": (1, 0, 0)},
    "side": {"N": (1, 0, 0), "Vx": (0, 1, 0)},
    "top": {"N": (0, 0, 1), "Vx": (1, 0, 0)},
    "section_AA": {"N": (0, -1, 0), "Vx": (1, 0, 0), "keep_y_min": 0.0},
}


def _axes(v):
    n, x = v["N"], v["Vx"]
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    return n, x, y


def _proj(v, p):
    _, x, y = _axes(v)
    return (p[0] * x[0] + p[1] * x[1] + p[2] * x[2], p[0] * y[0] + p[1] * y[1] + p[2] * y[2])


def load_step(path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    r = STEPControl_Reader()
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"cannot read {path}")
    r.TransferRoots()
    shape = r.OneShape()
    out = []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        out.append(TopoDS.Solid_s(ex.Current()))
        ex.Next()
    return out


def _polylines(comp, defl=0.15):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    if comp is None or comp.IsNull():
        return out
    ex = TopExp_Explorer(comp, TopAbs_EDGE)
    while ex.More():
        c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
        d = GCPnts_QuasiUniformDeflection(c, defl)
        if d.IsDone() and d.NbPoints() >= 2:
            pts = [d.Value(k) for k in range(1, d.NbPoints() + 1)]
        else:
            a, b = c.FirstParameter(), c.LastParameter()
            pts = [c.Value(a + (b - a) * k / 8.0) for k in range(9)]
        out.append([[round(p.X(), 3), round(p.Y(), 3)] for p in pts])
        ex.Next()
    return out


def _rdp(pts, tol):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    best, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dy * (px - x0) - dx * (py - y0)) / L if L > 1e-12 else math.hypot(px - x0, py - y0)
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _rdp(pts[:idx + 1], tol)[:-1] + _rdp(pts[idx:], tol)


def chain(polys, snap=0.02, tol=0.05, min_len=0.5):
    """Join segments that share end points into polylines, simplify them
    (Ramer-Douglas-Peucker) and drop specks shorter than min_len."""
    from collections import defaultdict

    def key(p):
        return (round(p[0] / snap), round(p[1] / snap))
    ends = defaultdict(list)
    for i, pl in enumerate(polys):
        ends[key(pl[0])].append(i)
        ends[key(pl[-1])].append(i)
    used = [False] * len(polys)
    out = []
    for i in range(len(polys)):
        if used[i]:
            continue
        used[i] = True
        line = list(polys[i])
        for forward in (True, False):
            while True:
                k = key(line[-1] if forward else line[0])
                nxt = next((j for j in ends[k] if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                seg = polys[nxt]
                if forward:
                    seg = seg if key(seg[0]) == k else seg[::-1]
                    line += seg[1:]
                else:
                    seg = seg if key(seg[-1]) == k else seg[::-1]
                    line = seg[:-1] + line
        line = _rdp(line, tol)
        length = sum(math.dist(a, b) for a, b in zip(line, line[1:]))
        if length >= min_len:
            out.append([[round(x, 3), round(y, 3)] for x, y in line])
    return out


def _section_loops(solids, v):
    """Closed loops of the cut faces on the plane Y = 0 (view coordinates)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopTools import TopTools_HSequenceOfShape
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    loops = []
    pln = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0))
    for s in solids:
        sec = BRepAlgoAPI_Section(s, pln)
        sec.Build()
        if not sec.IsDone():
            continue
        edges = TopTools_HSequenceOfShape()
        ex = TopExp_Explorer(sec.Shape(), TopAbs_EDGE)
        while ex.More():
            edges.Append(ex.Current())
            ex.Next()
        if edges.Length() == 0:
            continue
        wires = TopTools_HSequenceOfShape()
        ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(edges, 1e-4, False, wires)
        for i in range(1, wires.Length() + 1):
            w = wires.Value(i)
            pts = []
            we = TopExp_Explorer(w, TopAbs_EDGE)
            while we.More():
                c = BRepAdaptor_Curve(TopoDS.Edge_s(we.Current()))
                d = GCPnts_QuasiUniformDeflection(c, 0.1)
                seg = [d.Value(k) for k in range(1, d.NbPoints() + 1)] if d.IsDone() else []
                seg = [_proj(v, (p.X(), p.Y(), p.Z())) for p in seg]
                if pts and seg and math.dist(pts[-1], seg[-1]) < math.dist(pts[-1], seg[0]):
                    seg.reverse()
                pts += seg
                we.Next()
            if len(pts) > 2:
                loops.append([[round(x, 3), round(y, 3)] for x, y in pts])
    return loops


def compute(solids, name, exact=False, mesh_defl=0.4):
    """Hidden-line projection. Default is the polygonal algorithm on a fine
    mesh (exact HLR stalls on the revolved B-spline head surfaces)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape, HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    v = VIEWS[name]
    t0 = time.time()
    use = solids
    if "keep_y_min" in v:
        box = BRepPrimAPI_MakeBox(gp_Pnt(-1e5, v["keep_y_min"], -1e5), gp_Pnt(1e5, 1e5, 1e5)).Shape()
        use = []
        for s in solids:
            c = BRepAlgoAPI_Common(s, box)
            c.Build()
            if c.IsDone() and not c.Shape().IsNull():
                use.append(c.Shape())
    n, x, _ = _axes(v)
    proj = HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*n), gp_Dir(*x)))
    if exact:
        algo = HLRBRep_Algo()
        for s in use:
            algo.Add(s)
        algo.Projector(proj)
        algo.Update()
        algo.Hide()
        hs = HLRBRep_HLRToShape(algo)
    else:
        algo = HLRBRep_PolyAlgo()
        for s in use:
            BRepMesh_IncrementalMesh(s, mesh_defl, False, 0.2, True)
            algo.Load(s)
        algo.Projector(proj)
        algo.Update()
        hs = HLRBRep_PolyHLRToShape()
        hs.Update(algo)
    res = {"visible": _polylines(hs.VCompound()) + _polylines(hs.OutLineVCompound()),
           "smooth": _polylines(hs.Rg1LineVCompound()),
           "hidden": [] if "keep_y_min" in v else _polylines(hs.HCompound()) + _polylines(hs.OutLineHCompound()),
           "algorithm": "HLRBRep_Algo (exact)" if exact else f"HLRBRep_PolyAlgo (mesh deflection {mesh_defl} mm)",
           "seconds": None}
    raw = {k: len(res[k]) for k in ("visible", "smooth", "hidden")}
    for k in ("visible", "smooth", "hidden"):
        res[k] = chain(res[k])
    res["raw_segments"] = raw
    if "keep_y_min" in v:
        res["cut_loops"] = _section_loops(solids, v)
    res["seconds"] = round(time.time() - t0, 2)
    return res


def run(package_dir, views=("front", "side", "top", "section_AA")) -> dict:
    pkg = Path(package_dir)
    cad = pkg / "02_CAD_3D"
    step = next(cad.glob("*.step"))
    chk = json.loads((cad / "cad_check.json").read_text(encoding="utf-8"))
    solids = load_step(step)
    out = {"source_step": step.name, "input_hash": chk.get("input_hash"), "results_hash": chk.get("results_hash"),
           "solids": len(solids), "views": {}}
    for nm in views:
        out["views"][nm] = compute(solids, nm)
        print(f"{nm:11s} visible={len(out['views'][nm]['visible']):4d} hidden={len(out['views'][nm]['hidden']):4d} "
              f"{out['views'][nm]['seconds']:.1f}s", flush=True)
    (pkg / "03_DRAWINGS_2D").mkdir(exist_ok=True)
    (pkg / "03_DRAWINGS_2D" / "projections.json").write_text(json.dumps(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    run(sys.argv[1])
