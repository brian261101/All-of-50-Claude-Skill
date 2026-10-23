"""Helpers for the skill-level tests: run the skill scripts as subprocesses
and read the files they produce."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
TEMPLATES = SKILL / "templates"
_CACHE: dict[str, Path] = {}


def run(script, *args, timeout=600):
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def calculated_package(template="vessel-input.yaml", mutate=None, key=None) -> Path:
    """Run run_calculations.py once per (template, key) and cache the folder."""
    k = key or template
    if k in _CACHE:
        return _CACHE[k]
    tmp = Path(tempfile.mkdtemp(prefix="pvskill_"))
    src = TEMPLATES / template
    if mutate:
        import yaml
        raw = yaml.safe_load(src.read_text(encoding="utf-8"))
        mutate(raw)
        src = tmp / template
        src.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    out = tmp / "pkg"
    rc, so, se = run("run_calculations.py", src, "--out", out)
    if rc not in (0,):
        raise AssertionError(f"run_calculations failed rc={rc}\n{so}\n{se}")
    _CACHE[k] = out
    return out


def results(pkg: Path) -> dict:
    return json.loads((pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))


def record(res: dict, cid: str) -> dict:
    return next(r for r in res["records"] if r["calc_id"] == cid)


def value(rec: dict, sym: str):
    for g in ("results", "intermediates", "inputs"):
        for tv in rec[g]:
            if tv["symbol"] == sym:
                return tv["value"]
    raise KeyError(sym)


def cleanup():
    for p in _CACHE.values():
        shutil.rmtree(p.parent, ignore_errors=True)
