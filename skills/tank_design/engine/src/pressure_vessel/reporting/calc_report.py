"""Calculation report: HTML (always) and PDF (PyMuPDF, if installed).

Every calculation is printed as Input -> Formula/Method -> Code reference ->
Intermediate values -> Result -> Acceptance status. Statuses are printed as
words; no colour suggests that an unevaluated item passed (no green is used
anywhere, PASS is plain black text).
"""

from __future__ import annotations

import datetime as _dt
from html import escape

from .. import DISCLAIMER, __version__

STATUS_CSS = {
    "PASS": "st-pass", "FAIL": "st-fail", "NOT_EVALUATED": "st-ne", "OUT_OF_SCOPE": "st-oos",
    "NEEDS_ENGINEERING_REVIEW": "st-rev", "COMPUTED": "st-comp", "None": "st-comp",
}

CSS = """
body { font-family: sans-serif; font-size: 8.6pt; line-height: 1.25; }
h1 { font-size: 17pt; margin: 0 0 6pt 0; }
h2 { font-size: 12pt; margin: 12pt 0 4pt 0; border-bottom: 1px solid #000; }
h3 { font-size: 9.6pt; margin: 9pt 0 3pt 0; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0 6pt 0; }
th, td { border: 0.6px solid #444; padding: 1.5pt 3pt; vertical-align: top; text-align: left; }
th { background-color: #e6e6e6; }
td.num { text-align: right; }
.small { font-size: 7.4pt; }
.mono { font-family: monospace; font-size: 7.8pt; }
.banner { border: 2px solid #000; padding: 6pt; font-weight: bold; font-size: 11pt; text-align: center; margin: 10pt 0; }
.st-pass { font-weight: bold; }
.st-fail { font-weight: bold; color: #b00000; }
.st-ne { font-style: italic; color: #555555; }
.st-oos { font-style: italic; color: #555555; }
.st-rev { font-weight: bold; color: #8a5a00; }
.st-comp { color: #333333; }
.box { border: 1px solid #000; height: 34pt; }
.calc { border: 0.8px solid #888; padding: 4pt; margin: 6pt 0; }
"""


def _st(s):
    s = "COMPUTED" if s in (None, "None") else str(s)
    return f'<span class="{STATUS_CSS.get(s, "st-comp")}">{escape(s)}</span>'


def _num(v, d=3):
    if isinstance(v, bool) or v is None:
        return escape(str(v))
    if isinstance(v, (int, float)):
        if v != 0 and (abs(v) >= 1e7 or abs(v) < 1e-3):
            return f"{v:.4e}"
        return f"{v:.{d}f}"
    return escape(str(v))


def _table(head, rows, cls=""):
    h = "".join(f"<th>{escape(str(x))}</th>" for x in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><tr>{h}</tr>{body}</table>'


def _tv_rows(tvs):
    return [[escape(tv["symbol"]), _num(tv["value"]), escape(tv["unit"]), escape(tv["description"]),
             f'<span class="small">{escape(tv["source"])}</span>'] for tv in tvs]


def _record_html(r, refs_by_id):
    ref_rows = []
    for rid in r["references"]:
        ref = refs_by_id.get(rid, {})
        ref_rows.append([escape(rid), escape(ref.get("clause", "")), escape(ref.get("title", ""))[:140],
                         escape(ref.get("verification_status", "?"))])
    parts = [f'<div class="calc"><h3>{escape(r["calc_id"])} — {escape(r["title"])} &nbsp; [{_st(r["status"])}]</h3>',
             f'<p><b>Component:</b> {escape(r["component"])} &nbsp; <b>Kind:</b> {escape(r["kind"])} &nbsp; '
             f'<b>Code family:</b> {escape(r["code_family"])} &nbsp; <b>Mandatory:</b> {r["mandatory"]}</p>',
             f'<p><b>Method:</b> {escape(r["method"])}</p>']
    if ref_rows:
        parts.append("<p><b>Code references</b></p>" + _table(["Register id", "Clause", "Title", "Verification"], ref_rows, "small"))
    if r["inputs"]:
        parts.append("<p><b>Input</b></p>" + _table(["Symbol", "Value", "Unit", "Description", "Source"], _tv_rows(r["inputs"])))
    if r["formula"]:
        rows = [[f'<span class="mono">{escape(f)}</span>', f'<span class="mono">{escape(s)}</span>']
                for f, s in zip(r["formula"], r["substitution"])]
        parts.append("<p><b>Formula / substitution</b></p>" + _table(["Formula", "Substituted values"], rows))
    if r["intermediates"]:
        parts.append("<p><b>Intermediate values</b></p>" + _table(["Symbol", "Value", "Unit", "Description", "Source"],
                                                                 _tv_rows(r["intermediates"])))
    if r["results"]:
        parts.append("<p><b>Result</b></p>" + _table(["Symbol", "Value", "Unit", "Description", "Source"], _tv_rows(r["results"])))
    acc = f'<p><b>Acceptance criterion:</b> {escape(r["criterion"] or "— (computation, no criterion)")}' \
          f' &nbsp; <b>Criterion met:</b> {escape(str(r["criterion_met"]))} &nbsp; <b>Status:</b> {_st(r["status"])}</p>'
    parts.append(acc)
    for k, label in (("status_reasons", "Status basis"), ("warnings", "Warnings"), ("questions", "Data required")):
        if r[k]:
            parts.append(f"<p><b>{label}:</b></p><ul>" + "".join(f"<li>{escape(x)}</li>" for x in r[k]) + "</ul>")
    parts.append("</div>")
    return "".join(parts)


def build_html(results: dict, geometry: dict | None, verification: dict | None, *, revision_history=None,
               bom_summary=None) -> str:
    pj = results["project"]
    gate = results["gate"]
    refs_by_id = {r["id"]: r for r in results.get("references_used", [])}
    recs = results["records"]
    by = {r["calc_id"]: r for r in recs}
    now = _dt.date.today().isoformat()
    title = f"{pj.get('project_id')} {pj.get('equipment_tag')} — Design Calculation Rev {pj.get('revision')}"
    H = [f"<html><head><meta charset='utf-8'><title>{escape(title)}</title></head><body>"]

    # 1 cover
    H.append(f"<h1>Design Calculation</h1><p style='font-size:13pt'><b>{escape(pj.get('equipment_tag', ''))}</b> — "
             f"{escape(pj.get('description', ''))}</p>")
    H.append(_table(["Item", "Value"], [
        ["Project", escape(f"{pj.get('project_id')} — {pj.get('customer', '')}")],
        ["Document", escape(f"{pj.get('project_id')}_{pj.get('equipment_tag')}_Design_Calculation_Rev{pj.get('revision')}")],
        ["Revision", escape(str(pj.get("revision")))], ["Date generated", now],
        ["Design code", escape(f"{results['code']['design_code']} edition {results['code'].get('edition')}")],
        ["Package stage", f"<b>{escape(gate['stage'])}</b>"],
        ["Input data status", escape(str(pj.get("data_status")))],
        ["Input hash", f"<span class='mono'>{results['input_hash']}</span>"],
        ["Results hash", f"<span class='mono'>{results['results_hash']}</span>"],
        ["Software", escape(f"pressure_vessel {__version__}")]]))
    H.append(f"<div class='banner'>{escape(gate['stage'])} — NOT FOR FABRICATION<br/>"
             f"<span style='font-size:8.5pt;font-weight:normal'>{escape(gate['fabrication_release'])}</span></div>")
    H.append(f"<p class='small'>{escape(DISCLAIMER)}</p>")
    counts = results["summary"]["counts"]
    H.append("<h3>Result summary</h3>" + _table(["PASS", "FAIL", "NOT_EVALUATED", "OUT_OF_SCOPE", "NEEDS_ENGINEERING_REVIEW", "COMPUTED"],
                                                 [[str(counts.get(k, 0)) for k in ("PASS", "FAIL", "NOT_EVALUATED", "OUT_OF_SCOPE",
                                                                                   "NEEDS_ENGINEERING_REVIEW", "COMPUTED")]]))
    H.append("<h3>Release blockers</h3><ul>" + "".join(f"<li>{escape(b)}</li>" for b in gate["blockers"]) + "</ul>"
             if gate["blockers"] else "<p>No automated blockers (engineering review still required).</p>")

    # contents
    sections = ["Project information", "Equipment data", "Design code and edition", "Design basis",
                "Material specifications", "Geometry", "Input data and units", "Calculation assumptions",
                "Calculations by component", "Required thickness", "Selected nominal thickness",
                "Corrosion allowance and mill tolerance", "MAWP", "Nozzle reinforcement", "External pressure",
                "Supports and loads", "Test pressure", "Weight and volume", "Verification results",
                "Warnings and unresolved items", "Material database sources", "Revision history",
                "Engineering review and sign-off"]
    H.append("<h2 style='page-break-before: always'>Contents</h2><ol start='2'>" +
             "".join(f"<li>{escape(s)}</li>" for s in sections) + "</ol>")

    def sec(n, name):
        H.append(f"<h2>{n}. {escape(name)}</h2>")

    sec(2, "Project information")
    H.append(_table(["Field", "Value"], [[escape(k), escape(str(v))] for k, v in pj.items()]))
    sec(3, "Equipment data")
    if geometry:
        v = geometry["vessel"]
        H.append(_table(["Item", "Value"], [
            ["Orientation", escape(v["orientation"])], ["Inside diameter", f"{v['inside_diameter']:.1f} mm"],
            ["Tangent to tangent", f"{v['tangent_to_tangent']:.1f} mm"],
            ["Bottom / top tangent elevation", f"{v['bottom_tangent_elevation']:.1f} / {v['top_tangent_elevation']:.1f} mm"],
            ["Overall height", f"{v['overall_height']:.1f} mm"], ["Internal volume", f"{v['internal_volume_mm3'] / 1e9:.4f} m3"],
            ["Conventions", escape("; ".join(f"{k}: {x}" for k, x in geometry["conventions"].items()))]]))
    else:
        H.append("<p>See section 7 / calculation records (no vessel geometry for this code family in v0.1).</p>")
    sec(4, "Design code and edition")
    rr = results["reference_register"]
    H.append(f"<p>Design code: <b>{escape(results['code']['design_code'])}</b>, edition "
             f"<b>{escape(str(results['code'].get('edition')))}</b>, addenda {escape(str(results['code'].get('addenda', '-')))}. "
             f"Reference register v{escape(rr['register_version'])}: {rr['used']} references used, "
             f"<b>{rr['verified']} verified</b> against the licensed edition.</p>")
    H.append(_table(["Register id", "Document", "Clause", "Verification", "Verified by / on"],
                    [[escape(r["id"]), escape(r["document"]), escape(r["clause"]), escape(r["verification_status"]),
                      escape(f"{r.get('verified_by') or '-'} / {r.get('verified_on') or '-'}")] for r in results.get("references_used", [])], "small"))
    sec(5, "Design basis")
    db = results.get("design_basis") or {}
    H.append(f"<p>Design basis locked: <b>{escape(str(db.get('locked')))}</b> (confirmed by {escape(str(db.get('confirmed_by')))}, "
             f"{escape(str(db.get('confirmed_on')))}).</p>")
    if "process" in (results.get("validation") or {}) or True:
        proc = (results.get("_raw_process") or {})
        if proc:
            H.append(_table(["Process item", "Input"], [[escape(k), escape(str(v))] for k, v in proc.items()]))
    sec(6, "Material specifications")
    mats = (results.get("material_db") or {}).get("used", {})
    H.append(_table(["Key", "Material", "Status", "Density kg/m3", "Source", "Table reference"],
                    [[escape(k), escape(m.get("name", "")), f"<b>{escape(str(m.get('status')))}</b>", _num(m.get("density_kg_m3"), 0),
                      f"<span class='small'>{escape(str(m.get('source_document', '')))}</span>", escape(str(m.get("table_reference", "")))]
                     for k, m in mats.items()]))
    sec(7, "Geometry")
    if geometry:
        rows = []
        for c in geometry["components"]:
            if c["kind"] in ("shell_course", "head"):
                p = c["params"]
                rows.append([escape(c["tag"]), escape(c["description"]), _num(p.get("thickness"), 1),
                             _num(p.get("z0", p.get("z_tangent")), 1), _num(p.get("z1"), 1) if "z1" in p else "-",
                             escape(c["material_label"])])
        H.append(_table(["Tag", "Component", "t nominal mm", "z0 / tangent mm", "z1 mm", "Material"], rows))
        nrows = []
        for n in geometry["nozzles"]:
            fl = n.get("flange") or {}
            nrows.append([escape(n["tag"]), escape(n["service"]), escape(n["location"]),
                          "-" if n.get("elevation_from_btl") is None else f"{n['elevation_from_btl']:.0f}",
                          "-" if n.get("orientation") is None else f"{n['orientation']:.0f}",
                          f"{n['projection']:.0f}", escape(f"{n.get('nps') or '-'} / {n.get('schedule') or n['neck_type']}"),
                          f"{n['neck_od']:.1f} x {n['neck_wall']:.2f}",
                          escape(f"{n.get('flange_standard') or ''} Cl {n.get('flange_class') or ''} {n.get('flange_type') or ''} {n.get('facing') or ''}"),
                          escape("-" if not n.get("pad") else f"{n['pad']['thickness']:g} x {n['pad']['od']:g}")])
        H.append("<h3>Nozzle schedule</h3>" + _table(["Tag", "Service", "Location", "Elev. from BTL mm", "Orient. deg",
                                                      "Projection mm", "NPS / Sch", "Neck OD x t mm", "Flange", "Pad t x OD mm"], nrows, "small"))
    sec(8, "Input data and units")
    H.append(f"<p>Input file: <span class='mono'>{escape(str(results.get('input_file')))}</span>. All values were entered "
             "with explicit units and converted to mm, MPa (gauge), degC, kg. The complete validated input is "
             "reproduced in 00_INPUT of the package; the input hash on the cover identifies it.</p>")
    val = results.get("validation") or {}
    if val:
        H.append(_table(["Validation", "Count"], [["errors", str(len(val.get("errors", [])))],
                                                 ["warnings", str(len(val.get("warnings", [])))],
                                                 ["questions", str(len(val.get("questions", [])))]]))
    sec(9, "Calculation assumptions")
    assumptions = [
        "Corroded dimensions everywhere (UG-25): inside radius R = D/2 + CA, thickness less CA.",
        "Plate undertolerance per UG-16(c); pipe undertolerance taken in UG-45 neck checks, not in UG-37/UG-40 areas (UG-16(d)).",
        "Reinforcement: radial nozzles, F = 1, longitudinal plane; weld areas counted only when weld sizes are given.",
        "Head openings only on the head centreline; tr of 2:1 heads with K1 = 0.90 (80 % circle).",
        "External pressure chart factors are never approximated; without user chart data the check is NOT_EVALUATED.",
        "Weights are net theoretical values from exact profiles; bolting, gaskets, internals, paint and insulation are excluded.",
        "Material allowable stresses are used exactly as held in the material records, with their verification status.",
    ]
    for r in recs:
        assumptions += [f"{r['calc_id']}: {w}" for w in r["warnings"]]
    H.append("<ul>" + "".join(f"<li>{escape(a)}</li>" for a in assumptions) + "</ul>")

    sec(10, "Calculations by component")
    H.append("<p>Each block reads: Input -> Formula/Method -> Code reference -> Intermediate values -> Result -> Acceptance status.</p>")
    for r in recs:
        H.append(_record_html(r, refs_by_id))

    def val_of(r, sym):
        for g in ("results", "intermediates", "inputs"):
            for tv in r[g]:
                if tv["symbol"] == sym:
                    return tv["value"]
        return None

    thick = [r for r in recs if (r["calc_id"].startswith(("SH-", "HD-", "API-SH-")) and val_of(r, "t_nom") is not None)]
    sec(11, "Required thickness")
    H.append(_table(["Calc", "Component", "t required (corroded) mm", "t min incl. UG-16(b) mm", "Status"],
                    [[escape(r["calc_id"]), escape(r["component"]), _num(val_of(r, "t_req") or val_of(r, "t_required")),
                      _num(val_of(r, "t_min")), _st(r["status"])] for r in thick]))
    sec(12, "Selected nominal thickness")
    H.append(_table(["Calc", "Component", "t nominal mm", "t min after forming mm", "t available (corroded) mm", "Margin mm"],
                    [[escape(r["calc_id"]), escape(r["component"]), _num(val_of(r, "t_nom"), 2), _num(val_of(r, "t_min_formed"), 2),
                      _num(val_of(r, "t_avail")), _num(val_of(r, "margin"))] for r in thick]))
    sec(13, "Corrosion allowance and mill tolerance")
    H.append("<p>CA is added to required thicknesses and removed from available ones; plate undertolerance follows UG-16(c) "
             "(ignored only when not more than the smaller of 0.25 mm or 6 %); pipe undertolerance is deducted for neck "
             "thickness checks. Values used are shown in each record's input table.</p>")
    sec(14, "MAWP")
    m = by.get("MAWP")
    if m:
        H.append(_table(["Part", "MAWP at top of vessel (MPa)"], [[escape(tv["symbol"][5:-1]), _num(tv["value"], 4)]
                                                                for tv in m["intermediates"] if tv["symbol"].startswith("MAWP[")]))
        H.append(f"<p>Vessel MAWP = <b>{_num(val_of(m, 'MAWP'), 4)} MPa</b>, governed by {escape(str(val_of(m, 'governing')))}; status {_st(m['status'])}.</p>")
    sec(15, "Nozzle reinforcement")
    nz = [r for r in recs if r["calc_id"].endswith("-UG37")]
    H.append(_table(["Calc", "d mm", "A req mm2", "A avail mm2", "P max opening MPa", "Status"],
                    [[escape(r["calc_id"]), _num(val_of(r, "d"), 2), _num(val_of(r, "A"), 1), _num(val_of(r, "A_avail"), 1),
                      _num(val_of(r, "P_max_opening"), 4), _st(r["status"])] for r in nz]))
    nz45 = [r for r in recs if r["calc_id"].endswith("-UG45")]
    H.append(_table(["Calc", "t UG-45 mm", "t neck available mm", "Status"],
                    [[escape(r["calc_id"]), _num(val_of(r, "t_UG45")), _num(val_of(r, "t_neck_avail")), _st(r["status"])] for r in nz45]))
    sec(16, "External pressure")
    ext = [r for r in recs if r["calc_id"].startswith("EXT")]
    H.append(_table(["Calc", "Title", "Status", "Data required"], [[escape(r["calc_id"]), escape(r["title"]), _st(r["status"]),
                                                                    escape("; ".join(r["questions"]))] for r in ext]))
    sec(17, "Supports and loads")
    sl = [r for r in recs if r["calc_id"].startswith(("SUP", "LUG", "LOAD"))]
    H.append(_table(["Calc", "Title", "Key results", "Status"],
                    [[escape(r["calc_id"]), escape(r["title"]), escape(", ".join(f"{tv['symbol']}={_num(tv['value'], 1)}" for tv in r["results"])),
                      _st(r["status"])] for r in sl]))
    sec(18, "Test pressure")
    tp = by.get("TEST-P")
    if tp:
        H.append(_table(["Symbol", "Value", "Unit", "Description"], [[escape(tv["symbol"]), _num(tv["value"], 4), escape(tv["unit"]),
                                                                       escape(tv["description"])] for tv in tp["intermediates"] + tp["results"]]))
    sec(19, "Weight and volume")
    wt = by.get("WT") or by.get("API-WT")
    if wt:
        H.append(_table(["Symbol", "Value", "Unit", "Description"], [[escape(tv["symbol"]), _num(tv["value"], 2), escape(tv["unit"]),
                                                                       escape(tv["description"])] for tv in wt["intermediates"] + wt["results"]]))
    if bom_summary:
        H.append(f"<p>{escape(bom_summary)}</p>")
    sec(20, "Verification results")
    if verification:
        H.append(f"<p>Independent checks: <b>{verification['n_checks']}</b>, discrepancies: <b>{verification['n_failed']}</b> "
                 f"-> <b>{'PASSED' if verification['passed'] else 'DISCREPANCIES — release stopped'}</b>. PV Elite comparison: "
                 f"{escape(verification['pv_elite']['status'])}.</p><p class='small'>{escape(verification['scope_note'])}</p>")
        H.append(_table(["Group", "Id", "Quantity", "Engine", "Independent", "OK", "Method"],
                        [[escape(i["group"]), escape(i["id"]), escape(str(i["quantity"]))[:70], _num(i["engine"], 5),
                          _num(i["independent"], 5), "yes" if i["ok"] else "<b>NO</b>", escape(i["method"])]
                         for i in verification["items"]], "small"))
    else:
        H.append("<p><b>Verification not run for this result set.</b></p>")
    sec(21, "Warnings and unresolved items")
    H.append("<h3>Open mandatory checks</h3><ul>" + "".join(f"<li>{escape(x)}</li>" for x in gate.get("open_mandatory", [])) + "</ul>")
    H.append("<h3>Data required from the user</h3><ol>" + "".join(f"<li>{escape(q)}</li>" for q in results.get("questions", [])) + "</ol>")
    sec(22, "Material database sources")
    md = results.get("material_db") or {}
    H.append(f"<p>Database version <b>{escape(str(md.get('version')))}</b> ({escape(str(md.get('path')))}). Records used and their "
             "verification state are listed in section 6. REPRESENTATIVE_EXAMPLE or UNVERIFIED data can never produce PASS.</p>")
    sec(23, "Revision history")
    hist = revision_history or [{"rev": pj.get("revision"), "date": now, "description": "Generated by pressure_vessel",
                                 "by": pj.get("prepared_by", "")}]
    H.append(_table(["Rev", "Date", "Description", "By"], [[escape(str(h.get(k, ""))) for k in ("rev", "date", "description", "by")] for h in hist]))
    sec(24, "Engineering review and sign-off")
    H.append("<p>To be completed by hand by qualified persons. The software never fills these fields.</p>")
    H.append(_table(["Role", "Name", "Signature", "Date", "Remarks"],
                    [[r, "", "<div class='box'></div>", "", ""] for r in ("Prepared", "Checked", "Approved (engineer of record)",
                                                                           "Authorized Inspector / third party")]))
    H.append("</body></html>")
    return "".join(H)
