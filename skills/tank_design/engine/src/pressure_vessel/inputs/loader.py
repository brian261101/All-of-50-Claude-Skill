"""Read YAML or JSON input files. YAML needs PyYAML; JSON works with the
standard library alone."""

from __future__ import annotations

import json
from pathlib import Path


def read_input(path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError("YAML input needs PyYAML (pip install pyyaml); or supply JSON") from exc
        data = yaml.safe_load(text)
    elif p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"{p}: input must be .yaml, .yml or .json")
    if not isinstance(data, dict):
        raise ValueError(f"{p}: top level must be a mapping")
    return data
