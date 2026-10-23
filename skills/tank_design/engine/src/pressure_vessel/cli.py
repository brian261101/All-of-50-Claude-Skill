"""Command line: python -m pressure_vessel <command> ...

    validate INPUT                    validate only, print errors/warnings/questions
    calc INPUT --out DIR [--pv-elite CSV]   validation + calculations + verification
    report DIR                        calculation report (HTML + PDF)
    cad DIR [--headless]              print the MCP execute_code snippets, or run freecadcmd
    cad-status DIR                    read cad_check.json / techdraw_check.json
    drawings DIR                      HLR projections of the STEP + GA / fabrication DXF/PDF
    bom DIR                           BOM.csv / BOM.xlsx / bom.json
    package DIR [--no-tests]          consistency checks, tests, review file, manifest, README
    all INPUT --out DIR [--headless]  every stage; CAD by freecadcmd with --headless,
                                      otherwise stops after printing the MCP snippets

Exit status is non-zero when a stage fails; a PRELIMINARY design is not a
failure of the tool, it is reported as such.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print(obj):
    sys.stdout.write(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n")


def cmd_validate(a):
    from .inputs import read_input, validate_vessel
    from .inputs.tank_schema import validate_tank
    from .materials import MaterialDatabase
    raw = read_input(a.input)
    if raw.get("schema") == "pv-design/tank@1":
        _, rep = validate_tank(raw, source_path=str(a.input))
    else:
        _, rep = validate_vessel(raw, MaterialDatabase.load(), source_path=str(a.input))
    _print(rep.to_dict())
    return 0 if rep.ok else 2


def cmd_calc(a):
    from .package.pipeline import InputRejected, calculate
    try:
        r = calculate(a.input, a.out, pv_elite_csv=a.pv_elite)
    except InputRejected as exc:
        _print({"rejected": str(exc), "errors": [str(e) for e in exc.report.errors]})
        return 2
    res = r["results"]
    _print({"stage": res["gate"]["stage"], "counts": res["summary"]["counts"], "mawp_MPa": res.get("mawp_MPa"),
            "verification": res["verification_summary"], "blockers": res["gate"]["blockers"],
            "questions": len(res["questions"]), "files": {k: str(v) for k, v in r["paths"].items()}})
    return 0 if r["verification"]["passed"] else 3


def cmd_report(a):
    from .inputs import read_input
    from .reporting import generate_report
    inp = next((Path(a.dir) / "00_INPUT").glob("*.y*ml"), None) or next((Path(a.dir) / "00_INPUT").glob("*.json"), None)
    r = generate_report(a.dir, raw_input=read_input(inp) if inp else None)
    _print({"pdf": r["pdf"], "html": r["html"], "pages": r["pages"], "check": r["check"]})
    return 0 if r["check"]["ok"] else 4


def cmd_cad(a):
    from .cad.adapter import FreeCADMCPAdapter, run_headless
    if a.headless:
        r = run_headless(a.dir)
        _print({k: r.get(k) for k in ("ok", "mode", "error", "components_built")} |
               {"failed": [i["check"] for i in r.get("items", []) if not i["ok"]]})
        return 0 if r.get("ok") else 5
    ad = FreeCADMCPAdapter(a.dir)
    sys.stdout.write("# Send each block with the FreeCAD MCP tool execute_code (GUI must be running).\n"
                     "# 1) build + checks + FCStd + STEP\n" + ad.build_snippet() +
                     "\n# 2) TechDraw page (may outlast the MCP call; completion = 02_CAD_3D/techdraw_check.json)\n"
                     + ad.techdraw_create_snippet() + "\n# 3) TechDraw PDF/DXF export\n" + ad.techdraw_export_snippet())
    return 0


def cmd_cad_status(a):
    from .cad.adapter import FreeCADMCPAdapter
    st = FreeCADMCPAdapter(a.dir).status()
    c = st["cad_check"] or {}
    _print({"cad_ok": c.get("ok"), "failed": [i["check"] for i in c.get("items", []) if not i["ok"]],
            "techdraw": st["techdraw_check"] and {k: st["techdraw_check"].get(k) for k in ("views_complete", "exported")},
            "fcstd": st["fcstd"], "step": st["step"]})
    return 0 if c.get("ok") else 5


def cmd_drawings(a):
    from .drawings import ga, hlr
    hlr.run(a.dir)
    r = ga.generate(a.dir)
    _print({"ok": r["ok"], "sheets": [{k: s[k] for k in ("sheet", "dxf", "pdf", "dims_ok", "dxf_dimension_entities",
                                                           "dxf_audit_errors")} for s in r["sheets"]]})
    return 0 if r["ok"] else 6


def cmd_bom(a):
    from .bom.bom import build_bom, write_bom
    from .inputs import read_input
    pkg = Path(a.dir)
    geo = json.loads((pkg / "01_CALCULATION" / "design_geometry.json").read_text(encoding="utf-8"))
    res = json.loads((pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))
    inp = next((pkg / "00_INPUT").glob("*.y*ml"), None)
    b = build_bom(geo, res, read_input(inp) if inp else None)
    _print({"files": write_bom(b, pkg / "04_BOM"), "totals": b["totals"]})
    return 0


def cmd_package(a):
    from .package import consistency, manifest
    c = consistency.check(a.dir)
    tests = None if a.no_tests else manifest.run_tests(Path(a.dir))
    m = manifest.write_manifest(a.dir, tests=tests)
    _print({"consistency_ok": c["ok"], "mismatches": [i["check"] for i in c["items"] if i["ok"] is False],
            "tests": tests, "files": len(m["files"]), "stage": m["calculation_status"]["stage"]})
    return 0 if c["ok"] and (tests is None or tests["passed"]) else 7


def cmd_all(a):
    rc = cmd_calc(argparse.Namespace(input=a.input, out=a.out, pv_elite=a.pv_elite))
    if rc not in (0,):
        return rc
    d = argparse.Namespace(dir=a.out, headless=a.headless, no_tests=a.no_tests)
    if cmd_report(d):
        return 9
    code = json.loads((Path(a.out) / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))["code"]
    if code["design_code"] != "ASME_VIII_1":
        sys.stdout.write("geometry, CAD, drawings and BOM: not implemented for this code family in v0.1\n")
        return cmd_package(d)
    if cmd_bom(d):
        return 9
    if not a.headless and not (Path(a.out) / "02_CAD_3D" / "cad_check.json").is_file():
        cmd_cad(d)
        sys.stdout.write("\nCAD stage pending: run the snippets above through the FreeCAD MCP, then\n"
                         f"  python -m pressure_vessel drawings {a.out}\n  python -m pressure_vessel package {a.out}\n")
        return 0
    if a.headless and cmd_cad(d):
        return 5
    if cmd_drawings(d):
        return 6
    return cmd_package(d)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pressure_vessel", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate"); p.add_argument("input", type=Path); p.set_defaults(f=cmd_validate)   # noqa: E702
    p = sub.add_parser("calc"); p.add_argument("input", type=Path); p.add_argument("--out", required=True, type=Path)   # noqa: E702
    p.add_argument("--pv-elite", type=Path); p.set_defaults(f=cmd_calc)   # noqa: E702
    for name, f in (("report", cmd_report), ("cad-status", cmd_cad_status), ("drawings", cmd_drawings), ("bom", cmd_bom)):
        p = sub.add_parser(name); p.add_argument("dir", type=Path); p.set_defaults(f=f)   # noqa: E702
    p = sub.add_parser("cad"); p.add_argument("dir", type=Path); p.add_argument("--headless", action="store_true")   # noqa: E702
    p.set_defaults(f=cmd_cad)
    p = sub.add_parser("package"); p.add_argument("dir", type=Path); p.add_argument("--no-tests", action="store_true")   # noqa: E702
    p.set_defaults(f=cmd_package)
    p = sub.add_parser("all"); p.add_argument("input", type=Path); p.add_argument("--out", required=True, type=Path)   # noqa: E702
    p.add_argument("--headless", action="store_true"); p.add_argument("--no-tests", action="store_true")   # noqa: E702
    p.add_argument("--pv-elite", type=Path); p.set_defaults(f=cmd_all)   # noqa: E702
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
