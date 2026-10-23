"""Input validation for API 650 storage tanks (pv-design/tank@1).

Kept separate from the ASME VIII-1 schema on purpose: a tank input can never
be routed to the pressure-vessel formulas or the other way round.
Code-dependent constants (minimum shell thickness table, bottom minimum,
scope limits, Sd/St) are inputs confirmed by the user from the licensed
edition; none is hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import units
from ..status import DataStatus
from .schema import Issue, ValidationReport, _Ctx, input_hash

SCHEMA_ID = "pv-design/tank@1"


@dataclass
class TankCourse:
    id: str
    height: float          # mm
    material: str
    nominal_thickness: float | None


@dataclass
class TankMaterial:
    key: str
    spec: str
    Fy: float | None
    Fu: float | None
    Sd: float | None
    St: float | None
    density: float
    source: str
    status: str


@dataclass
class TankInput:
    project: dict
    design_basis: dict
    G: float
    G_test: float
    H: float                       # design liquid level, mm
    internal_pressure: float       # MPa
    external_pressure: float       # MPa
    dmt: float
    max_temp: float
    ca_shell: float
    ca_bottom: float
    D: float                       # nominal diameter, mm
    shell_height: float
    courses: list[TankCourse]
    bottom_thickness: float | None
    bottom_material: str
    roof: str
    materials: dict[str, TankMaterial]
    rules: dict
    rules_status: str
    scope_limits: dict
    plate_thicknesses: list[float]
    loads: dict
    input_hash: str
    source_path: str
    raw: dict = field(repr=False, default_factory=dict)


def validate_tank(raw: dict, *, source_path: str = "") -> tuple[TankInput | None, ValidationReport]:
    rep = ValidationReport()
    c = _Ctx(rep)
    if raw.get("schema") != SCHEMA_ID:
        c.err("schema", f"expected {SCHEMA_ID!r}")
    pr = raw.get("project", {}) or {}
    if pr.get("design_code") != "API_650":
        c.err("project.design_code", "a tank input must state design_code: API_650 (ASME VIII-1 vessels use "
              "pv-design/vessel@1)")
    for k in ("project_id", "equipment_tag", "code_edition", "revision"):
        if not pr.get(k):
            c.err(f"project.{k}", "required")
    L, PR, T = units.LENGTH, units.PRESSURE, units.TEMPERATURE
    p = raw.get("process", {}) or {}
    G = c.number(p, "design_specific_gravity", "process", lo=0.1, hi=3.0)
    Gt = c.number(p, "test_specific_gravity", "process", lo=0.5, hi=3.0)
    H = c.value(p, "design_liquid_level", "process", L, positive=True)
    Pi = c.value(p, "internal_pressure", "process", PR, non_negative=True)
    Pe = c.value(p, "external_pressure", "process", PR, non_negative=True)
    dmt = c.value(p, "design_metal_temperature", "process", T)
    tmax = c.value(p, "max_design_temperature", "process", T)
    cas = c.value(p, "corrosion_allowance_shell", "process", L, non_negative=True)
    cab = c.value(p, "corrosion_allowance_bottom", "process", L, non_negative=True)
    g = raw.get("geometry", {}) or {}
    D = c.value(g, "nominal_diameter", "geometry", L, positive=True)
    Hs = c.value(g, "shell_height", "geometry", L, positive=True)
    courses = []
    for i, cd in enumerate(g.get("courses") or []):
        cp = f"geometry.courses[{i}]"
        nt = cd.get("nominal_thickness")
        nom = None if isinstance(nt, str) and nt.strip().lower() == "auto" else c.value(cd, "nominal_thickness", cp, L, positive=True)
        courses.append(TankCourse(str(cd.get("id", i + 1)), c.value(cd, "height", cp, L, positive=True) or 0.0,
                                  c.text(cd, "material", cp) or "", nom))
    if not courses:
        c.err("geometry.courses", "at least one course is required")
    if Hs and courses and abs(sum(cc.height for cc in courses) - Hs) > 0.5:
        c.err("geometry.courses", "course heights do not add up to shell_height")
    if H and Hs and H > Hs:
        c.err("process.design_liquid_level", "design liquid level above the shell height")
    mats = {}
    for key, m in (raw.get("materials") or {}).items():
        mp = f"materials.{key}"
        st = str(m.get("verification_status", "UNVERIFIED"))
        if st not in DataStatus.__members__:
            c.err(f"{mp}.verification_status", f"unknown status {st!r}")
        mats[key] = TankMaterial(key, str(m.get("spec", "")),
                                 c.value(m, "Fy", mp, PR, required=False, positive=True),
                                 c.value(m, "Fu", mp, PR, required=False, positive=True),
                                 c.value(m, "Sd", mp, PR, required=False, positive=True,
                                         question="give the product design stress Sd (Table 5-2 of the licensed edition)"),
                                 c.value(m, "St", mp, PR, required=False, positive=True,
                                         question="give the hydrostatic test stress St (Table 5-2)"),
                                 c.value(m, "density", mp, units.DENSITY, positive=True) or 0.0,
                                 str(m.get("source", "")), st)
    for cc in courses:
        if cc.material not in mats:
            c.err("geometry.courses", f"course {cc.id}: material {cc.material!r} not defined")
    rules = raw.get("api650_rules", {}) or {}
    table = []
    for i, row in enumerate(rules.get("min_shell_thickness") or []):
        mx = row.get("max_diameter")
        dmax = float("inf") if str(mx).strip().lower() in ("inf", "none") else c.value(row, "max_diameter", f"api650_rules.min_shell_thickness[{i}]", L, positive=True)
        table.append((dmax, c.value(row, "thickness", f"api650_rules.min_shell_thickness[{i}]", L, positive=True)))
    if not table:
        c.ask("api650_rules.min_shell_thickness", "give the minimum nominal shell thickness table (5.6.1.1) from the licensed edition")
    rules_n = {"min_shell_thickness": table,
               "bottom_min_thickness": c.value(rules, "bottom_min_thickness", "api650_rules", L, required=False, positive=True,
                                               question="give the bottom plate minimum thickness (5.4.1)"),
               "one_foot_max_diameter": c.value(rules, "one_foot_method_max_diameter", "api650_rules", L, required=False,
                                                positive=True, question="give the diameter limit of the 1-foot method (5.6.3)")}
    sl = raw.get("scope_limits", {}) or {}
    scope = {"max_internal_pressure": c.value(sl, "max_internal_pressure", "scope_limits", PR, required=False,
                                              non_negative=True,
                                              question="state the internal-pressure limit of the API 650 part used "
                                                       "(basic design or Annex F) from the licensed edition"),
             "max_external_pressure": c.value(sl, "max_external_pressure", "scope_limits", PR, required=False, non_negative=True,
                                              question="state the external-pressure (vacuum) limit used"),
             "max_temperature": c.value(sl, "max_design_temperature", "scope_limits", T, required=False,
                                        question="state the maximum design temperature of the part used (basic or Annex M)"),
             "basis": str(sl.get("basis", ""))}
    fab = raw.get("fabrication", {}) or {}
    pt = fab.get("plate_thicknesses")
    plates = []
    if isinstance(pt, dict) and "values" in pt:
        plates = sorted(units.convert(float(v), str(pt["unit"]), expect=L).value for v in pt["values"])
    if rep.errors:
        return None, rep
    return TankInput(project=pr, design_basis=raw.get("design_basis", {}) or {}, G=G, G_test=Gt, H=H,
                     internal_pressure=Pi, external_pressure=Pe, dmt=dmt, max_temp=tmax, ca_shell=cas,
                     ca_bottom=cab, D=D, shell_height=Hs, courses=courses,
                     bottom_thickness=c.value(g, "bottom_plate_thickness", "geometry", L, required=False, positive=True),
                     bottom_material=str(g.get("bottom_material", courses[0].material)),
                     roof=str(g.get("roof", "not stated")), materials=mats, rules=rules_n,
                     rules_status=str(rules.get("status", "UNVERIFIED")), scope_limits=scope,
                     plate_thicknesses=plates, loads=raw.get("loads", {}) or {}, input_hash=input_hash(raw),
                     source_path=source_path, raw=raw), rep
