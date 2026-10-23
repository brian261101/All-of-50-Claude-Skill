"""Shared calculation context: input, data registers, record list, lookups."""

from __future__ import annotations

from dataclasses import dataclass, field

from ...inputs.models import VesselInput
from ...materials import MaterialDatabase, MaterialError
from ...references import ReferenceRegister
from ...trace import CalcRecord
from ...units import G0

# Table UW-12 maximum allowable joint efficiencies (register: ASME8-1:TableUW-12)
TABLE_UW12 = {
    1: {"full": 1.00, "spot": 0.85, "none": 0.70},
    2: {"full": 0.90, "spot": 0.80, "none": 0.65},
    3: {"none": 0.60},
    4: {"none": 0.55},
    5: {"none": 0.50},
    6: {"none": 0.45},
}


def hydrostatic(height_mm: float, density_kg_m3: float) -> float:
    """rho g h in MPa: kg/m3 -> kg/mm3 (1e-9), times g in mm/s2 and h in mm
    gives kg/(mm s2) = 1e-3 N/mm2."""
    return density_kg_m3 * 1e-9 * G0 * height_mm * 1e-3


@dataclass
class Ctx:
    vi: VesselInput
    refs: ReferenceRegister
    matdb: MaterialDatabase
    records: list[CalcRecord] = field(default_factory=list)
    selected: dict[str, float] = field(default_factory=dict)       # nominal thickness by component
    available: dict[str, float] = field(default_factory=dict)      # corroded available thickness
    required: dict[str, float] = field(default_factory=dict)       # required t at E=1 (for UG-45 tb1)
    mawp_parts: dict[str, float] = field(default_factory=dict)     # MAWP at the top, per part
    mawp_notes: list[str] = field(default_factory=list)
    joint_E: dict[str, float] = field(default_factory=dict)
    geometry: dict | None = None

    def add(self, rec: CalcRecord) -> CalcRecord:
        if any(r.calc_id == rec.calc_id for r in self.records):
            raise ValueError(f"duplicate calc id {rec.calc_id}")
        self.records.append(rec)
        return rec

    # --- data quality -------------------------------------------------------
    def unverified(self, refs=(), materials=(), extra=()) -> list[str]:
        out = list(self.refs.unverified(refs))
        for m in materials:
            ma = self.vi.materials.get(m)
            if ma is None:
                out.append(f"material {m} undefined")
            elif not ma.record:
                if ma.status not in ("VERIFIED_OFFICIAL", "USER_SUPPLIED_VERIFIED"):
                    out.append(f"material {m} ({ma.label}) data {ma.status}")
            elif not ma.record.status.release_eligible:
                out.append(f"material {m} ({ma.record.id}) data {ma.record.status}")
        out.extend(extra)
        return out

    # --- material lookups -----------------------------------------------------
    def S(self, mat_key: str, T: float) -> tuple[float | None, str]:
        ma = self.vi.materials[mat_key]
        if ma.record is None:
            return None, f"{mat_key} is a non-pressure material without allowable stresses"
        try:
            return ma.record.allowable_stress(T)
        except MaterialError as exc:
            return None, str(exc)

    # --- pressure at an elevation -------------------------------------------
    def static_head(self, z_abs: float) -> float:
        """Liquid static head (MPa) at absolute elevation z (operating case)."""
        p = self.vi.process
        if p.liquid_level is None or p.liquid_density is None:
            return 0.0
        z_liq = self.vi.geometry.bottom_tangent_elevation + p.liquid_level
        return hydrostatic(max(0.0, z_liq - z_abs), p.liquid_density)

    def P_at(self, z_abs: float) -> float:
        return self.vi.process.design_pressure + self.static_head(z_abs)

    def joint(self, name: str):
        return self.vi.fabrication.joints.get(name)
