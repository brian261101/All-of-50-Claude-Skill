"""Bill of materials from the design geometry (the same data the CAD uses).

Weights: "net" = theoretical finished weight from exact geometry; "blank" =
stock blank (plate rectangle, pipe length) where a rule is defined;
procurement = blank x (1 + cutting allowance) x (1 + scrap allowance), with
both allowances taken from the input. Where no blank rule exists (formed
heads, standard flanges) the procurement weight is left empty and the reason
is stated; nothing is guessed.
"""

from __future__ import annotations

import csv
import json
import math
from collections import OrderedDict
from pathlib import Path

COLUMNS = ["item", "part_number", "description", "component_tags", "material_spec", "grade", "quantity", "unit",
           "thickness_mm", "diameter_mm", "length_mm", "unit_net_kg", "total_net_kg", "blank_kg_each",
           "procurement_kg_total", "standard", "manufacturing_notes", "source_ref"]

GROUP_CODE = {"shell": "SH", "heads": "HD", "nozzles": "NZ", "pads": "RP", "flanges": "FL", "supports": "SP",
              "lugs": "LG"}


def _spec_grade(results, key, label):
    m = (results.get("material_db") or {}).get("used", {}).get(key) or {}
    if m.get("spec"):
        return m["spec"], m.get("grade", "")
    return label, ""


def build_bom(geometry: dict, results: dict, raw_input: dict | None = None) -> dict:
    fab = (raw_input or {}).get("fabrication", {}) or {}

    def pct(key):
        v = fab.get(key)
        if isinstance(v, str) and v.strip().endswith("%"):
            return float(v.strip()[:-1]) / 100.0
        return None
    cut, scrap = pct("cutting_allowance"), pct("scrap_allowance")
    factor = None if cut is None or scrap is None else (1 + cut) * (1 + scrap)
    eq = geometry["equipment_tag"].replace("-", "")
    lines: "OrderedDict[str, dict]" = OrderedDict()
    noz = {n["tag"]: n for n in geometry["nozzles"]}

    for c in geometry["components"]:
        p, k = c["params"], c["kind"]
        spec, grade = _spec_grade(results, c["material"], c["material_label"])
        rho = c["density_kg_m3"]
        t = d = L = None
        blank = None
        std, notes = "", ""
        if k == "shell_course":
            t, d, L = p["thickness"], p["inside_diameter"], p["length"]
            blank = math.pi * (d + t) * L * t * rho * 1e-9
            notes = f"rolled plate, developed length {math.pi * (d + t):.0f} mm (mean diameter) x {L:.0f} mm; long seam at {p.get('long_seam_orientation')} deg"
        elif k == "head":
            t, d = p["thickness"], p["inside_diameter"]
            L = p["straight_flange"]
            notes = (f"formed {p['type']} head{' %g:1' % p['aspect_ratio'] if p['type'] == 'ellipsoidal' else ''}, "
                     f"SF {L:g} mm, min. thickness after forming {p.get('min_thickness_after_forming')} mm; blank size by head maker")
        elif k == "nozzle_neck":
            n = noz[p["nozzle"]]
            t, d, L = p["wall"], p["od"], p["length_at_axis"]
            blank = math.pi / 4 * (d ** 2 - (d - 2 * t) ** 2) * (L + 2 * t) * rho * 1e-9 if rho else None
            if n["neck_type"] == "pipe":
                std = "ASME B36.10M"
                notes = f"pipe NPS {n['nps']} Sch {n['schedule']}, cut length ~{L + 2 * t:.0f} mm (profiled end)"
            else:
                notes = f"rolled plate neck OD {d:.0f} x {t:g} mm, length ~{L + 2 * t:.0f} mm"
        elif k == "pad":
            t, d = p["thickness"], p["od"]
            blank = d * d * t * rho * 1e-9
            notes = f"reinforcing pad, rolled to the shell OD; telltale hole per project practice (TBD); square blank {d:.0f} mm"
        elif k in ("flange", "blind"):
            t, d = p["thickness"], p["od"]
            n = noz[p["nozzle"]]
            std = n.get("flange_standard") or ""
            notes = (f"{'blind' if k == 'blind' else n.get('flange_type')} Cl {n.get('flange_class')} {n.get('facing')}, "
                     "standard purchased item; weight from simplified model, use the supplier catalogue weight")
        elif k == "leg":
            t, d, L = p["wall"], p["od"], p["z1"] - p["z0"]
            blank = math.pi / 4 * (d ** 2 - (d - 2 * t) ** 2) * L * rho * 1e-9
            notes = f"{p['section']}"
        elif k == "base_plate":
            t, L = p["thickness"], p["length"]
            d = p["width"]
            blank = p["length"] * p["width"] * t * rho * 1e-9
            notes = f"{p['length']:g} x {p['width']:g} x {t:g}, {p['anchor_holes']} holes D{p['anchor_hole_diameter']:g} for {p['anchor_bolt']}"
        elif k == "lifting_lug":
            t, L = p["thickness"], p["height"]
            pen = p["parent_outer_radius"] - math.sqrt(p["parent_outer_radius"] ** 2 - (t / 2) ** 2)
            blank = (p["projection"] + pen) * p["height"] * t * rho * 1e-9
            notes = f"plate lug, hole D{p['hole_diameter']:g}; profiled to shell OD"
        key = (k, spec, grade, round(t or 0, 3), round(d or 0, 3), round(L or 0, 1), c["material"])
        key = "|".join(map(str, key)) if k in ("leg", "base_plate", "lifting_lug") else c["tag"]
        if key in lines:
            ln = lines[key]
            ln["quantity"] += 1
            ln["component_tags"] += f", {c['tag']}"
            continue
        generic = {"leg": f"Support leg, {p.get('section', '')}", "base_plate": "Leg base plate",
                   "lifting_lug": "Lifting lug"}
        lines[key] = {"group": c["bom_group"], "kind": k, "description": generic.get(k, c["description"]),
                      "component_tags": c["tag"], "material_spec": spec, "grade": grade, "quantity": 1, "unit": "pc",
                      "thickness_mm": t, "diameter_mm": d, "length_mm": L, "unit_net_kg": c["mass_kg"],
                      "blank_kg_each": blank, "standard": std, "manufacturing_notes": notes,
                      "source_ref": c["calc_ref"] or "design_geometry", "material_status": c["material_status"]}
    # accessories that are not modelled: gaskets and bolting for joints supplied with the vessel
    acc = []
    nz_in = {n["tag"]: n for n in ((raw_input or {}).get("geometry", {}) or {}).get("nozzles", [])}
    for n in geometry["nozzles"]:
        fl = n.get("flange")
        src = (nz_in.get(n["tag"]) or {}).get("flange") or {}
        if not fl or not src.get("supply_bolting"):
            continue
        acc.append({"group": "accessories", "kind": "gasket", "description": f"Gasket {n['tag']}",
                    "component_tags": f"{n['tag']}-GSK", "material_spec": src.get("gasket", "TBD"), "grade": "",
                    "quantity": 1, "unit": "pc", "thickness_mm": None, "diameter_mm": fl.get("raised_face_od"),
                    "length_mm": None, "unit_net_kg": None, "blank_kg_each": None, "standard": "ASME B16.20 / B16.21",
                    "manufacturing_notes": "not modelled; type, material and dimensions to be specified",
                    "source_ref": f"NZ-{n['tag']}-FLG", "material_status": "NOT SPECIFIED"})
        acc.append({"group": "accessories", "kind": "bolting", "description": f"Stud bolts {n['tag']}, {fl['bolt_size']}",
                    "component_tags": f"{n['tag']}-BLT", "material_spec": src.get("bolting", "TBD"), "grade": "",
                    "quantity": fl["bolt_holes"], "unit": "set (1 stud + 2 nuts)", "thickness_mm": None,
                    "diameter_mm": None, "length_mm": None, "unit_net_kg": None, "blank_kg_each": None,
                    "standard": "ASME B16.5 / B18.2.1 / B18.2.2",
                    "manufacturing_notes": "stud length not computed (to be set per B16.5 / PCC-1)",
                    "source_ref": f"NZ-{n['tag']}-FLG", "material_status": "NOT SPECIFIED"})
    rows = []
    for i, ln in enumerate(list(lines.values()) + acc, 1):
        ln["item"] = i
        ln["part_number"] = f"{eq}-{GROUP_CODE.get(ln['group'], 'AC')}-{i:02d}"
        ln["total_net_kg"] = None if ln["unit_net_kg"] is None else ln["unit_net_kg"] * ln["quantity"]
        ln["procurement_kg_total"] = None if (ln["blank_kg_each"] is None or factor is None) else \
            ln["blank_kg_each"] * ln["quantity"] * factor
        rows.append(ln)
    net = sum(r["total_net_kg"] or 0 for r in rows)
    proc = sum(r["procurement_kg_total"] or 0 for r in rows)
    no_proc = [r["part_number"] for r in rows if r["procurement_kg_total"] is None and r["unit_net_kg"] is not None]
    return {"schema": "pv-design/bom@1", "project_id": geometry["project_id"], "equipment_tag": geometry["equipment_tag"],
            "revision": geometry["revision"], "input_hash": geometry["input_hash"],
            "results_hash": geometry.get("results_hash"), "rows": rows,
            "totals": {"net_theoretical_kg": net, "procurement_estimate_kg": proc,
                       "procurement_excludes": no_proc, "cutting_allowance": cut, "scrap_allowance": scrap},
            "weight_basis": "net = exact geometry x density (material records); procurement = blank x (1 + cutting) "
                            "x (1 + scrap) where a blank rule exists; gaskets and bolting not weighed"}


def _fmt(v, d=2):
    return "" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def write_bom(bom: dict, out_dir) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bom.json").write_text(json.dumps(bom, indent=1, default=str), encoding="utf-8")
    with open(out / "BOM.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"# {bom['project_id']} {bom['equipment_tag']} rev {bom['revision']} — BOM, PRELIMINARY, NOT FOR FABRICATION"])
        w.writerow([f"# input {bom['input_hash'][:16]} results {str(bom['results_hash'])[:16]}; {bom['weight_basis']}"])
        w.writerow(COLUMNS)
        for r in bom["rows"]:
            w.writerow([_fmt(r.get(c), 3 if c.endswith("_mm") else 2) for c in COLUMNS])
        t = bom["totals"]
        w.writerow([])
        w.writerow(["", "", "TOTAL net theoretical (kg)", "", "", "", "", "", "", "", "", "", _fmt(t["net_theoretical_kg"])])
        w.writerow(["", "", "TOTAL procurement estimate (kg)", "", "", "", "", "", "", "", "", "", "", "",
                    _fmt(t["procurement_estimate_kg"]), "", "excludes: " + ", ".join(t["procurement_excludes"])])
    paths = {"csv": str(out / "BOM.csv"), "json": str(out / "bom.json")}
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM"
        ws.append([f"{bom['project_id']} {bom['equipment_tag']} rev {bom['revision']} — Bill of materials (PRELIMINARY, NOT FOR FABRICATION)"])
        ws.append([f"input {bom['input_hash']}  results {bom['results_hash']}"])
        ws.append([bom["weight_basis"]])
        ws.append(COLUMNS)
        for c in ws[4]:
            c.font = Font(bold=True)
        for r in bom["rows"]:
            ws.append([r.get(c) for c in COLUMNS])
        t = bom["totals"]
        ws.append([])
        ws.append(["", "", "TOTAL net theoretical (kg)"] + [""] * 9 + [t["net_theoretical_kg"]])
        ws.append(["", "", "TOTAL procurement estimate (kg)"] + [""] * 11 + [t["procurement_estimate_kg"]])
        for col, wdt in zip("ABCDEFGHIJKLMNOPQR", (5, 16, 38, 22, 26, 8, 8, 10, 10, 10, 10, 11, 11, 11, 13, 22, 60, 16)):
            ws.column_dimensions[col].width = wdt
        wb.save(out / "BOM.xlsx")
        paths["xlsx"] = str(out / "BOM.xlsx")
    except ImportError:
        paths["xlsx"] = None
    return paths
