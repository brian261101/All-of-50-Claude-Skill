"""Locate the pressure_vessel library from the skill folder and import it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[2]          # <repo>/.claude/skills/<skill>


def config() -> dict:
    cfg = {"library_root": "pv_design", "output_root": "pv_design/output"}
    p = SKILL_DIR / "templates" / "project-config.yaml"
    try:
        import yaml
        cfg.update(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    except Exception:  # noqa: BLE001 - PyYAML missing: defaults are enough
        pass
    return cfg


def library_root() -> Path:
    """The project's pv_design/ if present, else the engine/ copy bundled in
    the published skill package."""
    for root in (REPO_ROOT / config()["library_root"], SKILL_DIR / "engine"):
        if (root / "src" / "pressure_vessel").is_dir():
            return root
    raise SystemExit(f"pressure_vessel library not found under {REPO_ROOT / config()['library_root']} "
                     f"or {SKILL_DIR / 'engine'}")


def bootstrap():
    src = str(library_root() / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def emit(obj):
    sys.stdout.write(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n")
