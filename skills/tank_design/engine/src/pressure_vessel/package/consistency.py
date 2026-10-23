"""Cross-artifact consistency: calculation, geometry, CAD, drawings and BOM
must come from the same input and result set and agree on the numbers."""

from __future__ import annotations

import json
from pathlib import Path


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def check(package_dir) -> dict:
    pkg = Path(package_dir)
    res = _load(pkg / "01_CALCULATION" / "calculation_results.json")
    geo = _load(pkg / "01_CALCULATION" / "design_geometry.json")
    ver = _load(pkg / "01_CALCULATION" / "verification.json")
    cad = _load(pkg / "02_CAD_3D" / "cad_check.json")
    td = _load(pkg / "02_CAD_3D" / "techdraw_check.json")
    drw = _load(pkg / "03_DRAWINGS_2D" / "drawing_check.json")
    prj = _load(pkg / "03_DRAWINGS_2D" / "projections.json")
    bom = _load(pkg / "04_BOM" / "bom.json")
    items = []

    def item(name, ok, detail=None, applies=True):
        items.append({"check": name, "ok": bool(ok) if applies else None,
                      "status": ("OK" if ok else "MISMATCH") if applies else "NOT_APPLICABLE", "detail": detail})

    item("calculation results present", res is not None)
    if res is None:
        return {"ok": False, "items": items}
    ih, rh = res["input_hash"], res["results_hash"]
    family = res["code"]["design_code"]
    for name, doc in (("verification", ver), ("design geometry", geo), ("CAD check", cad), ("projections", prj),
                      ("drawing check", drw), ("BOM", bom)):
        if family != "ASME_VIII_1" and name != "verification":
            item(f"{name}: same input hash", True,
                 f"{family}: geometry, CAD, drawings and BOM not implemented in v0.1", applies=False)
            continue
        if doc is None:
            item(f"{name}: same input hash", False, "artifact missing")
            continue
        item(f"{name}: same input hash", doc.get("input_hash") == ih, {"artifact": doc.get("input_hash"), "results": ih})
        if name != "verification" or "results_hash" in doc:
            item(f"{name}: same results hash", doc.get("results_hash") == rh, {"artifact": doc.get("results_hash"), "results": rh})
    if geo:
        sel = res.get("selected_thickness_mm", {})
        mism = []
        for c in geo["components"]:
            key = c["tag"] if c["kind"] == "shell_course" else ({"HD-BOT": "bottom", "HD-TOP": "top"}.get(c["tag"]))
            if key and abs(sel.get(key, -1) - c["params"]["thickness"]) > 1e-9:
                mism.append(c["tag"])
        item("selected thickness = modelled thickness", not mism, mism)
        tags = {c["tag"] for c in geo["components"]}
        if cad:
            cad_tags = {v["tag"] for v in cad.get("volumes", [])}
            item("CAD components = design components", cad_tags == tags,
                 {"missing_in_cad": sorted(tags - cad_tags), "extra_in_cad": sorted(cad_tags - tags)})
            worst = max((v["rel_diff"] for v in cad.get("volumes", [])), default=1.0)
            item("CAD volume = analytic volume per component (<= 2e-3)", worst <= 2e-3, {"worst_rel_diff": worst})
            oh = geo["vessel"]["overall_height"]
            item("overall height: geometry = CAD", abs(cad["bbox"][5] - oh) < 0.5, {"cad": cad["bbox"][5], "geometry": oh})
            item("CAD checks passed", cad.get("ok"), [i["check"] for i in cad.get("items", []) if not i["ok"]])
        if bom:
            bom_tags = set()
            for r in bom["rows"]:
                if r["kind"] not in ("gasket", "bolting"):
                    bom_tags |= {t.strip() for t in r["component_tags"].split(",")}
            item("BOM components = design components", bom_tags == tags,
                 {"missing_in_bom": sorted(tags - bom_tags), "extra_in_bom": sorted(bom_tags - tags)})
            W = (res.get("weights_kg") or {}).get("empty")
            net = bom["totals"]["net_theoretical_kg"]
            item("BOM net weight = calculated empty weight", W is not None and abs(net - W) <= 1e-6 * W,
                 {"bom": net, "calculation": W})
        if drw:
            dims = {d["dimension"]: d for s in drw["sheets"] for d in s["dimensions"]}
            oh = geo["vessel"]["overall_height"]
            d = dims.get("overall height")
            item("overall height: geometry = drawing", d is not None and abs(d["drawn_mm"] - oh) < 0.5,
                 {"drawing": d and d["drawn_mm"], "geometry": oh})
            bad = [k for k, v in dims.items() if not v["ok"]]
            item("all drawing dimensions = design values", not bad, bad)
            shell_noz = [n for n in geo["nozzles"] if n["location"] == "shell"]
            missing = [n["tag"] for n in shell_noz if f"{n['tag']} elevation from BTL" not in dims]
            item("every shell nozzle elevation dimensioned", not missing, missing)
            missing_p = [n["tag"] for n in geo["nozzles"] if f"{n['tag']} projection" not in dims]
            item("every nozzle projection dimensioned", not missing_p, missing_p)
            if bom:
                n_bom = next((s.get("bom_items_on_sheet") for s in drw["sheets"] if s["sheet"] == "FAB"), None)
                item("BOM table on drawing = BOM file", n_bom == len(bom["rows"]), {"drawing": n_bom, "bom": len(bom["rows"])})
            item("drawing checks passed", drw.get("ok"))
    if td is not None:
        item("TechDraw page exported (PDF + DXF)", td.get("exported"), {k: td.get(k) for k in ("pdf_bytes", "dxf_bytes")})
    rev = {res["project"]["revision"]}
    if geo:
        rev.add(geo["revision"])
    if bom:
        rev.add(bom["revision"])
    item("same revision everywhere", len(rev) == 1, sorted(rev))
    ok = all(i["ok"] for i in items if i["ok"] is not None)
    out = {"schema": "pv-design/consistency@1", "input_hash": ih, "results_hash": rh, "ok": ok, "items": items}
    (pkg / "05_QA").mkdir(exist_ok=True)
    (pkg / "05_QA" / "consistency.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out
