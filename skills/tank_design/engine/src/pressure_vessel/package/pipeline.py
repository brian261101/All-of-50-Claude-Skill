"""Pipeline: input -> validation -> calculation -> verification -> files.

Package layout (only files that were actually produced are listed in the
manifest):

    <out>/00_INPUT/        input copy, validation report, design basis, questions
    <out>/01_CALCULATION/  calculation_results.json, design_geometry.json,
                           verification.json, verification_report.md, PDF report
    <out>/02_CAD_3D/       FCStd, STEP, cad_check.json (FreeCAD stage)
    <out>/03_DRAWINGS_2D/  GA / fabrication DXF + PDF, drawing_check.json
    <out>/04_BOM/          BOM.csv, BOM.xlsx
    <out>/05_QA/           test_results.txt, consistency.json, engineering_review.md, manifest.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..codes.asme_viii_1 import design as asme_design
from ..codes.asme_viii_1.design import release_gate
from ..codes.api_650 import design as api_design
from ..inputs import read_input, validate_vessel
from ..inputs.tank_schema import validate_tank
from ..materials import MaterialDatabase
from ..references import ReferenceRegister
from ..verification.runner import run_verification, verification_markdown

DIRS = ["00_INPUT", "01_CALCULATION", "02_CAD_3D", "03_DRAWINGS_2D", "04_BOM", "05_QA"]


class InputRejected(RuntimeError):
    def __init__(self, report, path):
        super().__init__(f"input rejected with {len(report.errors)} error(s); see {path}")
        self.report = report


def _dump(path: Path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def questions_markdown(results_or_report, title="Open questions for the user") -> str:
    qs = results_or_report if isinstance(results_or_report, list) else results_or_report.get("questions", [])
    lines = [f"# {title}", "", "Answer these in the input file; nothing below is assumed by the software.", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(qs, 1)] or ["(none)"]
    return "\n".join(lines) + "\n"


def design_basis_markdown(vi) -> str:
    p, g = vi.process, vi.geometry
    rows = [("Project", f"{vi.project.project_id} / {vi.project.equipment_tag} rev {vi.project.revision}"),
            ("Description", vi.project.description), ("Design code", f"{vi.project.design_code} {vi.project.code_edition}"),
            ("Data status", vi.project.data_status),
            ("Design basis locked", f"{vi.design_basis.locked} (by {vi.design_basis.confirmed_by}, {vi.design_basis.confirmed_on})"),
            ("Fluid", f"{p.fluid} ({p.fluid_phase})"), ("Design pressure", f"{p.design_pressure:g} MPa(g)"),
            ("External pressure", "none" if not p.external_pressure else f"{p.external_pressure:g} MPa"),
            ("Design temperature", f"{p.design_temperature:g} degC"), ("MDMT", f"{p.mdmt:g} degC"),
            ("Corrosion allowance", f"{p.corrosion_allowance:g} mm"),
            ("Geometry", f"{g.orientation}, ID {g.inside_diameter:g} mm, T/T {g.tangent_to_tangent:g} mm"),
            ("Test", f"{p.test_type}, basis {p.test_basis}, {p.test_temperature:g} degC, {p.test_position}")]
    out = ["# Design basis", "", "| Item | Value |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    out += ["", "## Notes", ""] + [f"- {n}" for n in vi.design_basis.notes]
    return "\n".join(out) + "\n"


def calculate(input_path, out_dir, *, pv_elite_csv=None, material_db=None) -> dict:
    input_path, out = Path(input_path), Path(out_dir)
    for d in DIRS:
        (out / d).mkdir(parents=True, exist_ok=True)
    raw = read_input(input_path)
    shutil.copy2(input_path, out / "00_INPUT" / input_path.name)
    refs = ReferenceRegister.load()
    schema = raw.get("schema", "")
    if schema == "pv-design/tank@1":
        ti, rep = validate_tank(raw, source_path=str(input_path))
        _dump(out / "00_INPUT" / "validation_report.json", rep.to_dict())
        if not rep.ok:
            raise InputRejected(rep, out / "00_INPUT" / "validation_report.json")
        res = api_design.run(ti, refs, rep)
        results, geometry = res["results"], None
    else:
        mdb = MaterialDatabase.load(material_db)
        vi, rep = validate_vessel(raw, mdb, source_path=str(input_path))
        _dump(out / "00_INPUT" / "validation_report.json", rep.to_dict())
        if not rep.ok:
            (out / "00_INPUT" / "questions.md").write_text(
                questions_markdown([str(e) for e in rep.errors] + [str(q) for q in rep.questions],
                                   "Input errors and questions"), encoding="utf-8")
            raise InputRejected(rep, out / "00_INPUT" / "validation_report.json")
        (out / "00_INPUT" / "design_basis.md").write_text(design_basis_markdown(vi), encoding="utf-8")
        res = asme_design.run(vi, refs, mdb, rep)
        results, geometry = res["results"], res["geometry"]
    ver = run_verification(results, geometry, pv_elite_csv)
    if schema != "pv-design/tank@1":
        results["gate"] = release_gate(vi, res["records"], refs, ver)
    else:
        results["gate"]["blockers"] = [b for b in results["gate"]["blockers"] if "verification" not in b] + \
            ([] if ver["passed"] else ["verification suite reported discrepancies"])
    results["verification_summary"] = {k: ver[k] for k in ("passed", "n_checks", "n_failed")} | {"pv_elite": ver["pv_elite"]["status"]}
    paths = {"results": _dump(out / "01_CALCULATION" / "calculation_results.json", results),
             "verification": _dump(out / "01_CALCULATION" / "verification.json", ver)}
    (out / "01_CALCULATION" / "verification_report.md").write_text(verification_markdown(ver), encoding="utf-8")
    paths["verification_md"] = out / "01_CALCULATION" / "verification_report.md"
    if geometry:
        paths["geometry"] = _dump(out / "01_CALCULATION" / "design_geometry.json", geometry)
    (out / "00_INPUT" / "questions.md").write_text(questions_markdown(results), encoding="utf-8")
    paths["questions"] = out / "00_INPUT" / "questions.md"
    return {"results": results, "geometry": geometry, "verification": ver, "paths": paths}
