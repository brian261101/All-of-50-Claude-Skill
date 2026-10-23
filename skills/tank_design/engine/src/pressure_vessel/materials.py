"""Versioned material database with verification state.

Lookup policy (see references/material-data-policy.md):
* exact tabulated temperature -> tabulated value;
* between two tabulated temperatures -> linear interpolation, only if the
  record states ``interpolation: linear between tabulated temperatures`` (the
  convention of the Section II-D stress tables, to be confirmed by the user);
* outside the tabulated range -> refused (no extrapolation).
The result always carries the record's verification status, so a calculation
can tell whether its material data is release eligible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .paths import DATA_DIR
from .status import DataStatus


class MaterialError(ValueError):
    pass


@dataclass
class MaterialRecord:
    id: str
    spec: str
    grade: str
    product_form: str
    temperatures: list[float]          # degC, ascending
    stresses: list[float]              # MPa
    interpolation: str = ""
    t_min: float | None = None
    t_max: float | None = None
    min_tensile: float | None = None   # MPa
    min_yield: float | None = None     # MPa
    density: float | None = None       # kg/m3
    source_document: str = ""
    table_reference: str = ""
    edition: str = ""
    verified_on: str | None = None
    verified_by: str | None = None
    status: DataStatus = DataStatus.UNVERIFIED
    notes: list[str] = field(default_factory=list)
    yield_at_temperature: dict | None = None   # optional {"temperature_degC": [...], "Sy_MPa": [...]}

    @property
    def name(self) -> str:
        return f"{self.spec} Gr {self.grade} ({self.product_form})".replace(" Gr -", "")

    def allowable_stress(self, temperature: float) -> tuple[float, str]:
        """(S in MPa, how it was obtained)."""
        return _lookup(self.temperatures, self.stresses, temperature, self.interpolation, self.id,
                       self.t_min, self.t_max)

    def yield_strength(self, temperature: float) -> tuple[float | None, str]:
        if self.yield_at_temperature:
            t = self.yield_at_temperature["temperature_degC"]
            s = self.yield_at_temperature["Sy_MPa"]
            return _lookup(t, s, temperature, self.interpolation, self.id, t[0], t[-1])
        return None, "no yield-vs-temperature data in the record"

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "spec": self.spec, "grade": self.grade,
                "product_form": self.product_form, "status": str(self.status),
                "source_document": self.source_document, "table_reference": self.table_reference,
                "edition": self.edition, "verified_on": self.verified_on, "verified_by": self.verified_by,
                "density_kg_m3": self.density, "min_tensile_MPa": self.min_tensile,
                "min_yield_MPa": self.min_yield, "notes": self.notes}


def _lookup(ts, ss, T, interpolation, rid, t_min, t_max):
    if len(ts) != len(ss) or not ts:
        raise MaterialError(f"{rid}: temperature and stress lists differ in length or are empty")
    lo_lim = ts[0] if t_min is None else t_min
    hi_lim = ts[-1] if t_max is None else t_max
    if T < lo_lim - 1e-9 or T > hi_lim + 1e-9 or T < ts[0] - 1e-9 or T > ts[-1] + 1e-9:
        raise MaterialError(f"{rid}: {T:g} degC is outside the tabulated range "
                            f"{ts[0]:g}..{ts[-1]:g} degC; no extrapolation is performed")
    for t, s in zip(ts, ss):
        if abs(t - T) < 1e-9:
            return s, f"tabulated value at {t:g} degC"
    for (t0, s0), (t1, s1) in zip(zip(ts, ss), zip(ts[1:], ss[1:])):
        if t0 < T < t1:
            if "linear" not in (interpolation or "").lower():
                raise MaterialError(f"{rid}: {T:g} degC lies between tabulated points and the record "
                                    "does not permit interpolation")
            s = s0 + (s1 - s0) * (T - t0) / (t1 - t0)
            return s, f"linear interpolation between {t0:g} degC ({s0:g}) and {t1:g} degC ({s1:g})"
    raise MaterialError(f"{rid}: lookup failed at {T:g} degC")


def record_from_dict(d: dict) -> MaterialRecord:
    st = d.get("allowable_stress") or {}
    temps = [float(x) for x in st.get("temperature_degC", [])]
    stresses = [float(x) for x in st.get("S_MPa", [])]
    if temps != sorted(temps):
        raise MaterialError(f"{d.get('id')}: temperatures must be ascending")
    lim = d.get("temperature_limits_degC") or {}
    try:
        status = DataStatus(d.get("verification_status", "UNVERIFIED"))
    except ValueError:
        raise MaterialError(f"{d.get('id')}: unknown verification_status {d.get('verification_status')!r}") from None
    if status.release_eligible and not (d.get("verified_by") and d.get("verified_on") and d.get("source_document")):
        raise MaterialError(f"{d.get('id')}: status {status} needs verified_by, verified_on and source_document")
    return MaterialRecord(
        id=d["id"], spec=d["spec"], grade=str(d.get("grade", "-")), product_form=d.get("product_form", ""),
        temperatures=temps, stresses=stresses, interpolation=d.get("interpolation", ""),
        t_min=lim.get("min"), t_max=lim.get("max"), min_tensile=d.get("min_tensile_MPa"),
        min_yield=d.get("min_yield_MPa"), density=d.get("density_kg_m3"),
        source_document=d.get("source_document", ""), table_reference=d.get("table_reference", ""),
        edition=str(d.get("edition", "")), verified_on=d.get("verified_on"), verified_by=d.get("verified_by"),
        status=status, notes=list(d.get("notes", [])), yield_at_temperature=d.get("yield_at_temperature"))


class MaterialDatabase:
    def __init__(self, records: dict[str, MaterialRecord], version: str, path: str = ""):
        self.records, self.version, self.path = records, version, path

    @classmethod
    def load(cls, path: Path | None = None) -> "MaterialDatabase":
        p = Path(path or DATA_DIR / "materials" / "material_db.json")
        data = json.loads(p.read_text(encoding="utf-8"))
        recs = {}
        for d in data["records"]:
            r = record_from_dict(d)
            if r.id in recs:
                raise MaterialError(f"duplicate material id {r.id}")
            recs[r.id] = r
        return cls(recs, data.get("db_version", "?"), str(p))

    def add(self, rec: MaterialRecord, *, replace: bool = False):
        if rec.id in self.records and not replace:
            raise MaterialError(f"material id {rec.id} already exists")
        self.records[rec.id] = rec

    def get(self, mid: str) -> MaterialRecord:
        if mid not in self.records:
            raise MaterialError(f"material {mid!r} not found in database {self.version}; "
                                f"known ids: {sorted(self.records)}")
        return self.records[mid]
