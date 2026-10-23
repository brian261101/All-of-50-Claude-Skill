"""Package manifest, QA files and package README. Only files that exist are
listed; every listed file has its size and SHA-256."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

from .. import __version__
from ..paths import PROJECT_DIR


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _versions():
    out = {"pressure_vessel": __version__, "python": platform.python_version()}
    for mod in ("ezdxf", "pymupdf", "openpyxl", "yaml"):
        try:
            m = __import__(mod)
            out[mod] = getattr(m, "__version__", getattr(m, "VersionBind", "?"))
        except ImportError:
            out[mod] = None
    return out


def run_tests(pkg: Path) -> dict:
    """Run the library test suite and save the transcript to 05_QA."""
    proc = subprocess.run([sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                          cwd=PROJECT_DIR, capture_output=True, text=True, timeout=900)
    text = proc.stdout + proc.stderr
    (pkg / "05_QA" / "test_results.txt").write_text(
        f"pressure_vessel {__version__} — unittest run {_dt.datetime.now().isoformat(timespec='seconds')}\n"
        f"command: python -I -m unittest discover -s tests -t . (cwd {PROJECT_DIR})\n\n{text}", encoding="utf-8")
    last = [ln for ln in text.splitlines() if ln.startswith("Ran ")]
    return {"returncode": proc.returncode, "summary": last[-1] if last else "?",
            "passed": proc.returncode == 0 and "OK" in text.splitlines()[-1]}


def review_markdown(res: dict, cons: dict) -> str:
    g = res["gate"]
    lines = [f"# Engineering review — {res['project']['project_id']} / {res['project']['equipment_tag']} rev {res['project']['revision']}",
             "", f"Package stage: **{g['stage']}**. {g['fabrication_release']}", "",
             "## Automated blockers", ""] + [f"- {b}" for b in g["blockers"]] + [
             "", "## Open mandatory checks", ""] + [f"- {x}" for x in g.get("open_mandatory", [])] + [
             "", "## Consistency", "", f"Cross-artifact consistency: **{'OK' if cons['ok'] else 'MISMATCH'}**", ""] + [
             f"- [{i['status']}] {i['check']}" for i in cons["items"]] + [
             "", "## Reviewer checklist (to be completed by a qualified engineer)", "",
             "- [ ] Design basis confirmed with the client; inputs locked",
             "- [ ] Code edition/addenda confirmed; every code reference verified (code_reference_verification)",
             "- [ ] Material allowable stresses replaced by verified records",
             "- [ ] External-pressure chart readings, flange ratings, MDMT/PWHT assessments supplied",
             "- [ ] Wind, seismic, nozzle loads, supports and lifting evaluated",
             "- [ ] Weld details, NDE, PWHT, tolerances defined on drawings",
             "- [ ] Calculation report, model, drawings and BOM reviewed together (same hashes)",
             "", "## Sign-off (by hand — never filled by software)", "",
             "| Role | Name | Signature | Date |", "|---|---|---|---|",
             "| Prepared | | | |", "| Checked | | | |", "| Approved (engineer of record) | | | |",
             "| Authorized Inspector / third party | | | |"]
    return "\n".join(lines) + "\n"


def write_manifest(package_dir, *, tests: dict | None = None) -> dict:
    pkg = Path(package_dir)
    res = json.loads((pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))

    def _j(rel):
        p = pkg / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    cad, td, drw, bom = _j("02_CAD_3D/cad_check.json"), _j("02_CAD_3D/techdraw_check.json"), \
        _j("03_DRAWINGS_2D/drawing_check.json"), _j("04_BOM/bom.json")
    cons, ver = _j("05_QA/consistency.json"), _j("01_CALCULATION/verification.json")
    (pkg / "05_QA" / "engineering_review.md").write_text(review_markdown(res, cons or {"ok": False, "items": []}),
                                                         encoding="utf-8")
    files = []
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and p.suffix != ".FCBak":
            files.append({"path": p.relative_to(pkg).as_posix(), "bytes": p.stat().st_size, "sha256": _sha(p)})
    versions = _versions()
    if cad:
        versions["freecad"] = cad.get("freecad_version")
    man = {
        "schema": "pv-design/manifest@1",
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "project_id": res["project"]["project_id"], "equipment_tag": res["project"]["equipment_tag"],
        "revision": res["project"]["revision"], "input_file": res.get("input_file"), "input_hash": res["input_hash"],
        "results_hash": res["results_hash"], "design_code": res["code"],
        "material_data_version": (res.get("material_db") or {}).get("version"),
        "reference_register": res.get("reference_register"),
        "software": versions,
        "calculation_status": {"stage": res["gate"]["stage"], "counts": res["summary"]["counts"]},
        "verification_status": None if ver is None else {k: ver[k] for k in ("passed", "n_checks", "n_failed")}
        | {"pv_elite": ver["pv_elite"]["status"]},
        "test_status": tests,
        "cad_status": None if cad is None else {"ok": cad.get("ok"), "mode": cad.get("mode"),
                                                "failed": [i["check"] for i in cad["items"] if not i["ok"]]},
        "techdraw_status": None if td is None else {"exported": td.get("exported"), "views_complete": td.get("views_complete")},
        "drawing_status": None if drw is None else {"ok": drw.get("ok"),
                                                    "sheets": [{k: s[k] for k in ("sheet", "number", "scale", "dims_ok",
                                                                                  "dxf_dimension_entities", "dxf_audit_errors")}
                                                               for s in drw["sheets"]]},
        "bom_status": None if bom is None else {"rows": len(bom["rows"]), "net_kg": bom["totals"]["net_theoretical_kg"]},
        "consistency": None if cons is None else {"ok": cons["ok"]},
        "outstanding_issues": res["gate"]["blockers"] + [f"{len(res.get('questions', []))} open questions for the user"],
        "review_status": "NOT REVIEWED — no engineering sign-off recorded",
        "fabrication_release": res["gate"]["fabrication_release"],
        "files": files,
    }
    (pkg / "05_QA" / "manifest.json").write_text(json.dumps(man, indent=1, default=str), encoding="utf-8")
    (pkg / "README.md").write_text(package_readme(man), encoding="utf-8")
    return man


def package_readme(m: dict) -> str:
    lines = [f"# {m['project_id']} / {m['equipment_tag']} — design package rev {m['revision']}", "",
             f"**Stage: {m['calculation_status']['stage']} — NOT FOR FABRICATION.** {m['fabrication_release']}", "",
             f"Input hash `{m['input_hash'][:16]}`, results hash `{m['results_hash'][:16]}` — every file below was "
             "produced from this input and result set (see 05_QA/consistency.json).", "",
             "| Area | Status |", "|---|---|",
             f"| Calculation | {m['calculation_status']['counts']} |",
             f"| Verification | {m['verification_status']} |",
             f"| Tests | {m['test_status']} |",
             f"| CAD (FreeCAD) | {m['cad_status']} |",
             f"| TechDraw page | {m['techdraw_status']} |",
             f"| 2D drawings | {m['drawing_status'] and {'ok': m['drawing_status']['ok']}} |",
             f"| BOM | {m['bom_status']} |",
             f"| Consistency | {m['consistency']} |",
             f"| Review | {m['review_status']} |", "",
             "## Outstanding issues", ""] + [f"- {x}" for x in m["outstanding_issues"]] + ["", "## Files", ""] + \
        [f"- `{f['path']}` ({f['bytes']} bytes)" for f in m["files"]]
    return "\n".join(lines) + "\n"
