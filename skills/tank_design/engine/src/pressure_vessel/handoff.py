"""Handoff between the web calculator and Claude Code.

The web tool (pv_design/web) runs this same engine in the browser for
workflow steps 1-8 and packs the result into one zip:

    HANDOFF.json            what was done, with hashes (schema pv-design/handoff@1)
    README_FOR_CLAUDE.md    plain instructions for the tank-vessel-design skill
    00_INPUT/...            input file, source register, validation report
    01_CALCULATION/...      results, geometry, verification, report HTML + PDF

`resume()` unpacks it into a package folder, checks every file hash,
recomputes with the local engine and compares the input hash and every
calculation result, so steps 9-12 (CAD, drawings, BOM, package) start from results that
are proven identical, never from numbers taken on trust.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from . import __version__
from .paths import DATA_DIR, PACKAGE_DIR

SCHEMA = "pv-design/handoff@1"
SKILL = "tank-vessel-design"
COMMAND = "/tank_design"
STEPS_DONE = [(1, "Request"), (2, "Data collection"), (3, "Input validation"), (4, "Design basis"),
              (5, "Calculation"), (6, "Verification"), (7, "Review gate"), (8, "Calculation PDF")]
STEPS_NEXT = [(9, "3D model through the FreeCAD MCP"), (10, "2D drawings and BOM"),
              (11, "Consistency check"), (12, "Output package with manifest")]
# engine parts that do not take part in steps 1-8 and are not shipped to the browser
_EXCLUDED_DIRS = {"cad", "drawings", "bom", "__pycache__"}
_EXCLUDED_FILES = {"cli.py", "__main__.py", "package/consistency.py", "package/manifest.py"}
CARRIED = ("00_INPUT", "01_CALCULATION")


def engine_files(src_pkg: Path = PACKAGE_DIR, data_dir: Path = DATA_DIR) -> list[tuple[str, Path]]:
    """(bundle path, file) for every engine file used by steps 1-8, sorted."""
    out = []
    for p in sorted(src_pkg.rglob("*.py")):
        rel = p.relative_to(src_pkg).as_posix()
        if set(PurePosixPath(rel).parts[:-1]) & _EXCLUDED_DIRS or rel in _EXCLUDED_FILES:
            continue
        out.append((f"src/pressure_vessel/{rel}", p))
    for p in sorted(data_dir.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".csv"):
            out.append((f"data/{p.relative_to(data_dir).as_posix()}", p))
    return out


def _norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def engine_fingerprint(files=None) -> str:
    """SHA-256 over bundle paths and LF-normalised contents of the engine files.
    Identical on this machine and in the browser bundle when the code is the same."""
    h = hashlib.sha256()
    for rel, p in (files if files is not None else engine_files()):
        h.update(rel.encode() + b"\0" + _norm(Path(p).read_bytes()) + b"\0")
    return h.hexdigest()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# Pyodide's libm (WebAssembly) and the local C runtime may round pow/exp/log one
# unit differently in the last place, which changes the bitwise results hash
# without changing any result. Records are then compared value by value: every
# string, status and count exactly, floats within this relative tolerance.
RTOL = 1e-9
_PATH_KEYS = {("input_file",), ("results_hash",), ("material_db", "path")}


def compare_results(web: dict, local: dict, rtol: float = RTOL) -> dict:
    """Value-by-value comparison of two calculation_results.json documents."""
    diffs, floats, worst = [], 0, 0.0

    def walk(a, b, path):
        nonlocal floats, worst
        if path in _PATH_KEYS:
            return
        if isinstance(a, bool) or isinstance(b, bool) or not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            if type(a) is not type(b):
                diffs.append(".".join(map(str, path)))
            elif isinstance(a, dict):
                for k in sorted(set(a) | set(b), key=str):
                    if k not in a or k not in b:
                        diffs.append(".".join(map(str, path + (k,))))
                    else:
                        walk(a[k], b[k], path + (k,))
            elif isinstance(a, list):
                if len(a) != len(b):
                    diffs.append(".".join(map(str, path)) + " (length)")
                for i, (x, y) in enumerate(zip(a, b)):
                    walk(x, y, path + (i,))
            elif a != b:
                diffs.append(".".join(map(str, path)))
            return
        if a == b:
            return
        rel = abs(a - b) / max(abs(a), abs(b))
        if rel > rtol:
            diffs.append(".".join(map(str, path)))
        else:
            floats += 1
            worst = max(worst, rel)

    walk(web, local, ())
    return {"equal": not diffs, "differences": diffs[:50], "float_rounding_differences": floats,
            "max_relative_difference": worst, "rtol": rtol}


def make_handoff(package_dir, zip_path, *, tool: str = "pv_design", pdf_renderer: str = "",
                 fingerprint: str | None = None) -> dict:
    """Pack 00_INPUT and 01_CALCULATION of a calculated package into a handoff zip."""
    pkg = Path(package_dir)
    res = json.loads((pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))
    ver = json.loads((pkg / "01_CALCULATION" / "verification.json").read_text(encoding="utf-8"))
    pj = res["project"]
    inp = next(p for p in sorted((pkg / "00_INPUT").iterdir())
               if p.suffix in (".json", ".yaml", ".yml") and p.name != "validation_report.json")
    files = []
    for d in CARRIED:
        for p in sorted((pkg / d).rglob("*")):
            if p.is_file():
                files.append({"path": p.relative_to(pkg).as_posix(), "bytes": p.stat().st_size,
                              "sha256": _sha(p.read_bytes())})
    h = {
        "handoff": SCHEMA, "skill": SKILL, "command": COMMAND,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"), "created_by": tool,
        "engine": {"name": "pressure_vessel", "version": __version__,
                   "fingerprint": fingerprint or engine_fingerprint()},
        "project_id": pj.get("project_id"), "equipment_tag": pj.get("equipment_tag"),
        "revision": pj.get("revision"), "design_code": res["code"]["design_code"],
        "input_file": inp.relative_to(pkg).as_posix(),
        "input_hash": res["input_hash"], "results_hash": res["results_hash"],
        "stage": res["gate"]["stage"], "blockers": res["gate"]["blockers"],
        "counts": res["summary"]["counts"], "mawp_MPa": res.get("mawp_MPa"),
        "verification": {"passed": ver["passed"], "n_checks": ver["n_checks"], "n_failed": ver["n_failed"]},
        "pdf_renderer": pdf_renderer,
        "steps_done": [{"step": n, "name": s} for n, s in STEPS_DONE],
        "steps_next": [{"step": n, "name": s} for n, s in STEPS_NEXT],
        "files": files,
        "fabrication_release": res["gate"]["fabrication_release"],
    }
    readme = "\n".join([
        f"# Handoff: {pj.get('project_id')} / {pj.get('equipment_tag')} rev {pj.get('revision')}",
        "",
        f"This zip was produced by the tank-vessel-design web calculator ({tool}). Steps 1-8 are done:",
        "input, validation, design basis, calculation, verification, review gate and the calculation PDF.",
        f"Stage: **{h['stage']}** — not for fabrication.",
        "",
        "## For Claude Code",
        "",
        f"Use the **tank-vessel-design** skill (`{COMMAND}`). Do not recalculate by hand. Run:",
        "",
        "```bash",
        f"python pv_design/pv.py resume <this zip> --out pv_design/output/{pj.get('project_id')}",
        "```",
        "",
        "`resume` checks every file hash, recomputes with the local engine and compares the input hash",
        "and every calculation result. Only when they match, continue with step 9 (FreeCAD model through the MCP),",
        "step 10 (drawings and BOM), step 11 (consistency) and step 12 (package), exactly as SKILL.md says.",
        "",
        "## Open items at handoff",
        "",
    ] + [f"- {b}" for b in h["blockers"]]) + "\n"
    zp = Path(zip_path)
    zp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("HANDOFF.json", json.dumps(h, indent=1, ensure_ascii=False))
        z.writestr("README_FOR_CLAUDE.md", readme)
        for f in files:
            z.write(pkg / f["path"], f["path"])
    return h


def _safe_members(z: zipfile.ZipFile) -> list[str]:
    names = []
    for n in z.namelist():
        p = PurePosixPath(n)
        if p.is_absolute() or ".." in p.parts or n.startswith(("/", "\\")) or ":" in p.parts[0]:
            raise ValueError(f"unsafe path in handoff zip: {n!r}")
        if n.endswith("/"):
            continue
        if not (n in ("HANDOFF.json", "README_FOR_CLAUDE.md") or p.parts[0] in CARRIED):
            raise ValueError(f"unexpected file in handoff zip: {n!r}")
        names.append(n)
    return names


def read_handoff(zip_path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        h = json.loads(z.read("HANDOFF.json"))
    if h.get("handoff") != SCHEMA or h.get("skill") != SKILL:
        raise ValueError("not a tank-vessel-design handoff (HANDOFF.json schema/skill mismatch)")
    return h


def resume(zip_path, out_dir) -> dict:
    """Unpack, verify file hashes, recompute with the local engine and compare.

    Writes the package folder (00_INPUT, 01_CALCULATION recomputed locally;
    the browser PDF kept as *_web.pdf) and 05_QA/handoff_check.json."""
    from .package.pipeline import calculate

    zip_path, out = Path(zip_path), Path(out_dir)
    h = read_handoff(zip_path)
    check = {"handoff_file": str(zip_path), "project_id": h["project_id"], "items": []}

    def item(name, ok, detail=None):
        check["items"].append({"check": name, "ok": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory(prefix="pv_handoff_") as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(zip_path) as z:
            names = _safe_members(z)
            for n in names:
                dest = tmp / "web" / n
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(n))
        web = tmp / "web"
        bad = [f["path"] for f in h["files"] if not (web / f["path"]).is_file()
               or _sha((web / f["path"]).read_bytes()) != f["sha256"]]
        item("file hashes match HANDOFF.json", not bad, bad)
        local_fp = engine_fingerprint()
        same_engine = local_fp == h["engine"]["fingerprint"]
        item("same engine code as the web tool", same_engine,
             {"web": h["engine"]["fingerprint"][:16], "local": local_fp[:16], "web_version": h["engine"]["version"],
              "local_version": __version__})
        r = calculate(web / h["input_file"], tmp / "recalc")
        res = r["results"]
        item("input hash identical", res["input_hash"] == h["input_hash"],
             {"web": h["input_hash"][:16], "local": res["input_hash"][:16]})
        same_hash = res["results_hash"] == h["results_hash"]
        web_res = json.loads((web / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))
        cmp = compare_results(web_res, json.loads((tmp / "recalc" / "01_CALCULATION" / "calculation_results.json")
                                                  .read_text(encoding="utf-8")))
        # always value by value: results_hash covers the records only, not MAWP, gate or summary
        item("calculation results reproduced (all records, gate, MAWP)", cmp["equal"],
             {"results_hash_identical": same_hash, "web": h["results_hash"][:16], "local": res["results_hash"][:16]} | cmp)
        item("local verification passed", r["verification"]["passed"],
             {"checks": r["verification"]["n_checks"], "failed": r["verification"]["n_failed"]})
        identical = all(i["ok"] for i in check["items"] if i["check"] != "same engine code as the web tool")
        # assemble the package: local results are authoritative; keep the web files that the
        # local run does not produce (source register, the browser-rendered PDF)
        for d in CARRIED:
            (out / d).mkdir(parents=True, exist_ok=True)
        for p in (tmp / "recalc").rglob("*"):
            if p.is_file() and p.parts[-2] in CARRIED:
                shutil.copy2(p, out / p.parts[-2] / p.name)
        for f in h["files"]:
            src = web / f["path"]
            dest = out / f["path"]
            if dest.exists():
                continue
            if src.suffix.lower() == ".pdf":
                dest = dest.with_name(dest.stem + "_web.pdf")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        shutil.copy2(zip_path, out / "00_INPUT" / zip_path.name)
    check["identical"] = identical
    check["stage"] = res["gate"]["stage"]
    check["blockers"] = res["gate"]["blockers"]
    if not identical:
        check["next"] = ["STOP: the web results are not reproduced by the local engine — report the "
                         "mismatching items to the user; do not continue to CAD or drawings"]
    elif h["design_code"] == "ASME_VIII_1":
        check["next"] = [f"python pv_design/pv.py report {out}",
                         f"python pv_design/pv.py bom {out}",
                         f"python pv_design/pv.py cad {out}   (FreeCAD MCP route; or --headless)",
                         f"python pv_design/pv.py drawings {out}",
                         f"python pv_design/pv.py package {out}"]
    else:   # same split as `pv.py all`
        check["next"] = [f"python pv_design/pv.py report {out}",
                         f"python pv_design/pv.py package {out}",
                         f"geometry, CAD, drawings and BOM are not implemented for {h['design_code']} in "
                         f"v{__version__}: tell the user; do not model or draw it outside the engine"]
    (out / "05_QA").mkdir(parents=True, exist_ok=True)
    (out / "05_QA" / "handoff_check.json").write_text(json.dumps(check, indent=1, default=str), encoding="utf-8")
    return check
