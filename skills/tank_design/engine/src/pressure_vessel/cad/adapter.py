"""FreeCAD adapter.

Python cannot call MCP tools itself: the MCP client (Claude Code) does. So
the adapter's MCP side produces the exact code snippets to send with the
FreeCAD MCP tool ``execute_code`` and then verifies the outcome from the
files FreeCAD writes (cad_check.json, techdraw_check.json). A headless
fallback runs the same build script with ``freecadcmd`` as a subprocess.

Each MCP step is kept short: the MCP call returns "Request timed out" after
roughly a minute even when FreeCAD finishes the work, so long steps are split
(build | TechDraw create | TechDraw export) and completion is read from the
check files, never assumed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

CAD_DIR = Path(__file__).resolve().parent
SRC_DIR = CAD_DIR.parents[1]


class FreeCADMCPAdapter:
    """Prepare MCP execute_code snippets and verify their results."""

    def __init__(self, package_dir):
        self.pkg = Path(package_dir).resolve()

    def _snippet(self, script, call, extra=""):
        args = {"package": str(self.pkg), "src": str(SRC_DIR)}
        return (f"import json\np = r\"{CAD_DIR / script}\"\n"
                f"g = {{\"__name__\": \"pv\", \"__file__\": p, \"PV_ARGS\": {json.dumps(args)}{extra}}}\n"
                "exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), g)\n"
                f"r = g[\"{call}\"]()\n"
                "print(json.dumps({k: r.get(k) for k in ('ok', 'components_built', 'views_complete', 'exported', 'pdf_bytes') if k in r}))\n")

    def build_snippet(self):
        return self._snippet("freecad_build.py", "main")

    def techdraw_create_snippet(self):
        return self._snippet("freecad_techdraw.py", "main")

    def techdraw_export_snippet(self):
        return self._snippet("freecad_techdraw.py", "export")

    def probe_snippet(self, out_dir):
        p = CAD_DIR / "freecad_probe.py"
        return (f"p = r\"{p}\"\ng = {{\"__name__\": \"probe\", \"PROBE_OUT\": r\"{out_dir}\"}}\n"
                "exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), g)\nprint(g['run'](g['PROBE_OUT']))\n")

    def wait_for(self, name, newer_than: float, timeout_s=300.0):
        """Wait for a check file written after ``newer_than`` (epoch s)."""
        f = self.pkg / "02_CAD_3D" / name
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            if f.is_file() and f.stat().st_mtime >= newer_than:
                return json.loads(f.read_text(encoding="utf-8"))
            time.sleep(2.0)
        return None

    def status(self) -> dict:
        cad = self.pkg / "02_CAD_3D"
        out = {"cad_check": None, "techdraw_check": None}
        for k in out:
            f = cad / f"{k}.json"
            if f.is_file():
                out[k] = json.loads(f.read_text(encoding="utf-8"))
        out["fcstd"] = [str(p) for p in cad.glob("*.FCStd")]
        out["step"] = [str(p) for p in cad.glob("*.step")]
        return out


def find_freecadcmd() -> str | None:
    cands = [shutil.which("freecadcmd"), shutil.which("FreeCADCmd")]
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    for ver in ("FreeCAD 1.1", "FreeCAD 1.0", "FreeCAD 0.21"):
        cands.append(os.path.join(pf, ver, "bin", "freecadcmd.exe"))
    return next((c for c in cands if c and os.path.isfile(c)), None)


def run_headless(package_dir, timeout_s=900) -> dict:
    """Run freecad_build.py in freecadcmd (no GUI: no colours, no TechDraw
    PDF). Returns the parsed cad_check.json or an error record."""
    exe = find_freecadcmd()
    if not exe:
        return {"ok": False, "error": "freecadcmd not found"}
    env = dict(os.environ, PV_PACKAGE=str(Path(package_dir).resolve()), PV_SRC=str(SRC_DIR))
    t0 = time.time()
    proc = subprocess.run([exe, str(CAD_DIR / "freecad_build.py")], env=env, capture_output=True, text=True,
                          timeout=timeout_s)
    chk = Path(package_dir) / "02_CAD_3D" / "cad_check.json"
    if chk.is_file() and chk.stat().st_mtime >= t0:
        r = json.loads(chk.read_text(encoding="utf-8"))
        r["headless_stdout_tail"] = proc.stdout[-1500:]
        return r
    return {"ok": False, "error": "freecadcmd finished without writing cad_check.json",
            "returncode": proc.returncode, "stdout": proc.stdout[-3000:], "stderr": proc.stderr[-3000:]}
