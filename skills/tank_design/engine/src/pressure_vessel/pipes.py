"""Pipe outside diameters and walls (B36.10M subset, UNVERIFIED data)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .paths import DATA_DIR


@dataclass(frozen=True)
class PipeSize:
    nps: str
    schedule: str
    od: float        # mm
    wall: float      # mm, nominal
    std_wall: float  # mm, standard weight wall of this NPS
    source: str
    status: str


def _norm_nps(nps) -> str:
    s = str(nps).strip().replace('"', "").replace(" ", "-")
    aliases = {"0.5": "1/2", "0.75": "3/4", "1.5": "1-1/2", "1.0": "1"}
    if s in aliases:
        return aliases[s]
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return s


@lru_cache(maxsize=4)
def _table(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup(nps, schedule, path: Path | None = None) -> PipeSize:
    data = _table(str(path or DATA_DIR / "pipe" / "pipe_dimensions.json"))
    key = _norm_nps(nps)
    sch = str(schedule).strip().upper().replace("SCH", "").strip()
    for row in data["rows"]:
        if row["nps"] == key:
            walls = row["walls_in"]
            if sch not in walls:
                raise KeyError(f"NPS {key}: schedule {schedule!r} not in table (have {sorted(walls)})")
            return PipeSize(key, sch, row["od_in"] * 25.4, walls[sch] * 25.4, walls["STD"] * 25.4,
                            data["source_document"], data["verification_status"])
    raise KeyError(f"NPS {nps!r} not in pipe table")


def ug45_table_value(nps, path: Path | None = None) -> tuple[float, str]:
    """Table UG-45 thickness as derived from the standard-weight wall:
    0.875 x STD wall, with NPS 12 and larger capped at the NPS 12 STD value
    (STD wall is 0.375 in for all of them in the table, so the cap is implicit).
    The derivation must be confirmed against the licensed Table UG-45."""
    p = lookup(nps, "STD", path)
    return 0.875 * p.std_wall, f"0.875 x STD wall {p.std_wall:.2f} mm of NPS {p.nps} (derived; UNVERIFIED)"
