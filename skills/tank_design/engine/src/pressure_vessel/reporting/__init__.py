"""Report generation (HTML always; PDF when PyMuPDF is available)."""

from __future__ import annotations

import json
from pathlib import Path

from .calc_report import build_html
from .pdf import check_pdf, html_to_pdf

REQUIRED_HEADINGS = ["Design Calculation", "Design code and edition", "Calculations by component", "MAWP",
                     "Nozzle reinforcement", "Verification results", "Warnings and unresolved items",
                     "Engineering review and sign-off", "NOT FOR FABRICATION"]


def generate_report(package_dir, *, raw_input: dict | None = None) -> dict:
    pkg = Path(package_dir)
    calc = pkg / "01_CALCULATION"
    results = json.loads((calc / "calculation_results.json").read_text(encoding="utf-8"))
    geometry = json.loads((calc / "design_geometry.json").read_text(encoding="utf-8")) \
        if (calc / "design_geometry.json").is_file() else None
    ver = json.loads((calc / "verification.json").read_text(encoding="utf-8")) \
        if (calc / "verification.json").is_file() else None
    if raw_input:
        results["_raw_process"] = raw_input.get("process", {})
    pj = results["project"]
    stem = f"{pj['project_id']}_{pj['equipment_tag']}_Design_Calculation_Rev{pj['revision']}"
    html = build_html(results, geometry, ver)
    html_path = calc / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = calc / f"{stem}.pdf"
    header = f"{pj['project_id']} / {pj['equipment_tag']} — Design Calculation Rev {pj['revision']} — {results['gate']['stage']}"
    footer = f"NOT FOR FABRICATION. Results {results['results_hash'][:12]}, input {results['input_hash'][:12]}"
    n = html_to_pdf(html, pdf_path, header, footer)
    chk = check_pdf(pdf_path, REQUIRED_HEADINGS + [r["calc_id"] for r in results["records"]])
    (calc / "report_check.json").write_text(json.dumps(chk, indent=1), encoding="utf-8")
    return {"html": str(html_path), "pdf": str(pdf_path), "pages": n, "check": chk}
