"""Input validation for the ASME VIII-1 vessel schema (pv-design/vessel@1).

The validator never fills a missing safety-relevant value. A missing required
field is an error; a missing optional field that a check needs becomes a
question for the user and, later, a NOT_EVALUATED check. Every dimensional
value needs an explicit unit (see units.py).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from .. import pipes, units
from ..materials import MaterialDatabase, MaterialError, record_from_dict
from ..status import DataStatus
from .models import (DesignBasis, Fabrication, Flange, FlangeDims, Geometry, Head, Joint, Legs,
                     LoadItem, Lugs, MaterialAssignment, Neck, Nozzle, Pad, Process, Project,
                     ShellCourse, VesselInput)

SCHEMA_ID = "pv-design/vessel@1"
NONE_TOKENS = {"none", "null", "n/a", "na", "", "-"}
UNSTATED_TOKENS = {"tbd", "not_stated", "unknown", "to be confirmed"}
DESIGN_CODES = {"ASME_VIII_1", "API_650", "API_620", "EN_13445", "ASME_VIII_2"}
HEAD_TYPES = {"ellipsoidal", "torispherical", "hemispherical"}
RT_LEVELS = {"full", "spot", "none"}
LOAD_KEYS = ["wind", "seismic", "piping_loads", "snow", "lifting", "transport", "thermal"]


@dataclass
class Issue:
    field: str
    message: str

    def __str__(self):
        return f"{self.field}: {self.message}"


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    questions: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": [vars(i) for i in self.errors],
                "warnings": [vars(i) for i in self.warnings],
                "questions": [vars(i) for i in self.questions]}


class _Missing:
    pass


MISSING = _Missing()


def _is_none(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in NONE_TOKENS)


def _is_unstated(v) -> bool:
    return isinstance(v, str) and v.strip().lower() in UNSTATED_TOKENS


class _Ctx:
    def __init__(self, rep: ValidationReport):
        self.rep = rep

    def err(self, path, msg):
        self.rep.errors.append(Issue(path, msg))

    def warn(self, path, msg):
        self.rep.warnings.append(Issue(path, msg))

    def ask(self, path, msg):
        self.rep.questions.append(Issue(path, msg))

    def get(self, d: dict, key: str):
        if not isinstance(d, dict):
            return MISSING
        return d.get(key, MISSING)

    def quantity(self, d, key, path, dim, *, required=True, question=None, positive=False,
                 non_negative=False):
        v = self.get(d, key)
        p = f"{path}.{key}"
        if v is MISSING or _is_none(v) or _is_unstated(v):
            if required:
                self.err(p, "required value missing" + (f" — {question}" if question else ""))
            elif question:
                self.ask(p, question)
            return None
        try:
            q = units.parse(v, expect=dim, field=p)
        except units.UnitError as exc:
            self.err(p, str(exc))
            return None
        if positive and not q.value > 0:
            self.err(p, f"must be positive, got {q.text}")
            return None
        if non_negative and q.value < 0:
            self.err(p, f"must not be negative, got {q.text}")
            return None
        return q

    def value(self, d, key, path, dim, **kw) -> float | None:
        q = self.quantity(d, key, path, dim, **kw)
        return None if q is None else q.value

    def angle(self, d, key, path, *, required=True) -> float | None:
        v = self.get(d, key)
        p = f"{path}.{key}"
        if v is MISSING or _is_none(v):
            if required:
                self.err(p, "required angle missing (write e.g. '90 deg')")
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            self.err(p, f"{v!r} has no unit; write it as '{v} deg'")
            return None
        s = str(v).strip().lower().replace("°", " deg")
        try:
            num, u = units._split(s)
        except units.UnitError as exc:
            self.err(p, str(exc))
            return None
        if u in ("deg", "degree", "degrees"):
            return num % 360.0
        if u == "rad":
            return math.degrees(num) % 360.0
        self.err(p, f"unknown angle unit {u!r}; use deg")
        return None

    def text(self, d, key, path, *, required=True, choices=None, question=None) -> str | None:
        v = self.get(d, key)
        p = f"{path}.{key}"
        if v is MISSING or _is_none(v):
            if required:
                self.err(p, "required text missing" + (f" — {question}" if question else ""))
            elif question:
                self.ask(p, question)
            return None
        s = str(v).strip()
        if choices and s not in choices:
            self.err(p, f"{s!r} is not one of {sorted(choices)}")
            return None
        return s

    def flag(self, d, key, path, *, required=False, question=None) -> bool | None:
        v = self.get(d, key)
        p = f"{path}.{key}"
        if v is MISSING or _is_none(v) or _is_unstated(v):
            if required:
                self.err(p, "required true/false missing")
            elif question:
                self.ask(p, question)
            return None
        if isinstance(v, bool):
            return v
        self.err(p, f"expected true or false, got {v!r}")
        return None

    def number(self, d, key, path, *, required=True, integer=False, lo=None, hi=None) -> float | None:
        v = self.get(d, key)
        p = f"{path}.{key}"
        if v is MISSING or _is_none(v):
            if required:
                self.err(p, "required number missing")
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            self.err(p, f"expected a plain number, got {v!r}")
            return None
        if integer and int(v) != v:
            self.err(p, f"expected an integer, got {v!r}")
            return None
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            self.err(p, f"{v!r} outside the allowed range [{lo}, {hi}]")
            return None
        return int(v) if integer else float(v)


def input_hash(raw: dict) -> str:
    blob = json.dumps(raw, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------

def validate_vessel(raw: dict, matdb: MaterialDatabase, *, source_path: str = ""
                    ) -> tuple[VesselInput | None, ValidationReport]:
    rep = ValidationReport()
    c = _Ctx(rep)
    if not isinstance(raw, dict):
        c.err("<root>", "input must be a mapping")
        return None, rep
    if raw.get("schema") != SCHEMA_ID:
        c.err("schema", f"expected {SCHEMA_ID!r}, got {raw.get('schema')!r}")

    pr = raw.get("project", {})
    project = Project(
        project_id=c.text(pr, "project_id", "project") or "",
        equipment_tag=c.text(pr, "equipment_tag", "project") or "",
        description=c.text(pr, "description", "project") or "",
        customer=c.text(pr, "customer", "project", required=False) or "",
        design_code=c.text(pr, "design_code", "project", choices=DESIGN_CODES) or "",
        code_edition=c.text(pr, "code_edition", "project",
                            question="state the code edition (year) and addenda the design is to") or "",
        addenda=c.text(pr, "addenda", "project", required=False) or "none stated",
        units_system=c.text(pr, "units_system", "project", choices={"SI", "US"}) or "SI",
        design_status=c.text(pr, "design_status", "project", required=False) or "PRELIMINARY",
        revision=str(pr.get("revision", "")) if pr.get("revision") is not None else (c.err("project.revision", "required") or ""),
        data_status=c.text(pr, "data_status", "project", choices={"DEMO_SAMPLE", "USER_CONFIRMED"}) or "DEMO_SAMPLE",
        jurisdiction=c.text(pr, "jurisdiction", "project", required=False,
                            question="state the installation country/jurisdiction and its inspection rules") or "not stated",
        prepared_by=c.text(pr, "prepared_by", "project", required=False) or "",
        date=str(pr.get("date", "")),
    )
    if project.design_code and project.design_code != "ASME_VIII_1":
        c.err("project.design_code", f"{project.design_code} input must use its own schema; this "
              "validator is for ASME_VIII_1 vessels (API 650 tanks use pv-design/tank@1)")

    db = raw.get("design_basis", {})
    basis = DesignBasis(locked=bool(db.get("locked", False)), confirmed_by=db.get("confirmed_by"),
                        confirmed_on=db.get("confirmed_on"), notes=list(db.get("notes", []) or []))
    if basis.locked and not (basis.confirmed_by and basis.confirmed_on):
        c.err("design_basis", "locked: true requires confirmed_by and confirmed_on")
    if basis.locked and project.data_status != "USER_CONFIRMED":
        c.err("design_basis", "a design basis built on DEMO_SAMPLE data cannot be locked")

    process = _process(c, raw.get("process", {}))
    materials = _materials(c, raw.get("materials", {}), matdb)
    fab = _fabrication(c, raw.get("fabrication", {}))
    geometry = _geometry(c, raw.get("geometry", {}), raw.get("flange_types", {}) or {}, materials,
                         process, fab)
    loads = _loads(c, raw.get("loads", {}), geometry)
    ext = _external_data(c, raw.get("external_pressure_data", {}) or {}, process)

    if process and process.operating_pressure is not None and process.operating_pressure > process.design_pressure:
        c.err("process.operating_pressure", "operating pressure exceeds design pressure")
    if process and process.operating_temperature is not None and process.operating_temperature > process.design_temperature:
        c.err("process.operating_temperature", "operating temperature exceeds design temperature")
    if process and process.mdmt > process.design_temperature:
        c.err("process.mdmt", "MDMT is above the design temperature")
    if process and process.design_pressure > 20.7:
        c.warn("process.design_pressure", "above 20.7 MPa (3000 psi): VIII-1 may require additional "
               "design rules; thick-wall cases are OUT_OF_SCOPE here")

    if rep.errors or process is None or geometry is None:
        return None, rep
    assessments = _assessments(c, raw.get("assessments") or {})
    if rep.errors:
        return None, rep
    vi = VesselInput(project=project, design_basis=basis, process=process, geometry=geometry,
                     materials=materials, fabrication=fab, loads=loads, external_pressure_data=ext,
                     assessments=assessments,
                     reference_verification=list((raw.get("code_reference_verification") or {}).get("verified", []) or []),
                     source_path=source_path, input_hash=input_hash(raw), raw=raw)
    return vi, rep


def _process(c: _Ctx, d: dict) -> Process | None:
    P = "process"
    L, PR, T = units.LENGTH, units.PRESSURE, units.TEMPERATURE
    dp = c.quantity(d, "design_pressure", P, PR, non_negative=True)
    if dp is not None and dp.pressure_ref == "a":
        c.err(f"{P}.design_pressure", "give the design pressure as gauge (e.g. 'MPa(g)', 'barg'); "
              "absolute values need an explicit atmospheric reference")
        dp = None
    ext_raw = c.get(d, "external_pressure")
    ext = None
    if not (ext_raw is MISSING or _is_none(ext_raw)):
        ext = c.value(d, "external_pressure", P, PR, non_negative=True)
    else:
        c.warn(f"{P}.external_pressure", "no external pressure / vacuum stated: external-pressure "
               "checks will be listed as not required — confirm that no vacuum case exists")
    fluid_phase = c.text(d, "fluid_phase", P, choices={"gas", "liquid", "two_phase"})
    level = c.value(d, "liquid_level", P, L, required=False, non_negative=True)
    rho = c.value(d, "liquid_density", P, units.DENSITY, required=False, positive=True)
    if fluid_phase in ("liquid", "two_phase") and (level is None or rho is None):
        c.ask(f"{P}.liquid_level", "liquid service: give the maximum liquid level above the bottom "
              "tangent line and the liquid density, so static head can be added (UG-22, UG-98)")
    test_type = c.text(d, "test_type", P, choices={"hydrostatic", "pneumatic"})
    test_basis = c.text(d, "test_basis", P, choices={"MAWP", "design_pressure"})
    pos = c.text(d, "test_position", P, choices={"vertical", "horizontal"}, required=False) or "vertical"
    trho = c.value(d, "test_fluid_density", P, units.DENSITY, required=test_type == "hydrostatic",
                   positive=True)
    vals = dict(
        fluid=c.text(d, "fluid", P) or "",
        fluid_phase=fluid_phase or "",
        lethal_service=c.flag(d, "lethal_service", P, question="state whether the service is lethal (UW-2)"),
        cyclic_service=c.flag(d, "cyclic_service", P, question="state whether the vessel is in cyclic "
                              "service (fatigue screening is required if so)"),
        operating_pressure=c.value(d, "operating_pressure", P, PR, required=False),
        design_pressure=None if dp is None else dp.value,
        operating_temperature=c.value(d, "operating_temperature", P, T, required=False),
        design_temperature=c.value(d, "design_temperature", P, T),
        mdmt=c.value(d, "mdmt", P, T),
        external_pressure=ext,
        external_design_temperature=c.value(d, "external_design_temperature", P, T,
                                            required=ext is not None and ext > 0),
        required_volume=c.value(d, "required_volume", P, units.VOLUME, required=False, positive=True),
        liquid_level=level, liquid_density=rho,
        corrosion_allowance=c.value(d, "corrosion_allowance", P, L, non_negative=True),
        test_type=test_type or "", test_basis=test_basis or "",
        test_temperature=c.value(d, "test_temperature", P, T),
        test_position=pos, test_fluid_density=trho,
    )
    if vals["corrosion_allowance"] is not None and vals["corrosion_allowance"] > 6.0:
        c.warn(f"{P}.corrosion_allowance", "corrosion allowance above 6 mm — confirm")
    if any(vals[k] is None for k in ("design_pressure", "design_temperature", "mdmt", "corrosion_allowance",
                                       "test_temperature")):
        return None
    return Process(**vals)


def _materials(c: _Ctx, d: dict, matdb: MaterialDatabase) -> dict[str, MaterialAssignment]:
    out = {}
    if not isinstance(d, dict) or not d:
        c.err("materials", "at least one material assignment is required")
        return out
    for key, m in d.items():
        p = f"materials.{key}"
        if not isinstance(m, dict):
            c.err(p, "must be a mapping")
            continue
        if m.get("non_pressure"):
            rho = c.value(m, "density", p, units.DENSITY, positive=True)
            st = str(m.get("verification_status", "UNVERIFIED"))
            if st not in DataStatus.__members__:
                c.err(f"{p}.verification_status", f"unknown status {st!r}")
            out[key] = MaterialAssignment(key, None, True, c.text(m, "spec", p) or "", rho, st,
                                          c.value(m, "min_yield", p, units.PRESSURE, required=False))
            continue
        if "db_id" in m:
            try:
                out[key] = MaterialAssignment(key, matdb.get(m["db_id"]))
            except MaterialError as exc:
                c.err(f"{p}.db_id", str(exc))
            continue
        if "record" in m:
            try:
                rec = record_from_dict(m["record"])
                matdb.add(rec, replace=False)
                out[key] = MaterialAssignment(key, rec)
            except (MaterialError, KeyError) as exc:
                c.err(f"{p}.record", f"invalid inline material record: {exc}")
            continue
        c.err(p, "give db_id (material database id), an inline 'record', or non_pressure: true")
    return out


def _joint(c: _Ctx, d, name) -> Joint | None:
    p = f"fabrication.joints.{name}"
    if not isinstance(d, dict):
        c.err(p, "joint definition missing: state category, joint_type (Table UW-12) and radiography "
              "(full/spot/none). No default joint efficiency is assumed.")
        return None
    cat = c.text(d, "category", p, choices={"A", "B", "C", "D"})
    jt = c.number(d, "joint_type", p, integer=True, lo=1, hi=6)
    rt = c.text(d, "radiography", p, choices=RT_LEVELS)
    if None in (cat, jt, rt):
        return None
    return Joint(name, cat, int(jt), rt)


def _fabrication(c: _Ctx, d: dict) -> Fabrication:
    p = "fabrication"
    jd = c.get(d, "joints")
    joints = {}
    for name in ("shell_longitudinal", "shell_circumferential", "head_to_shell"):
        j = _joint(c, (jd or {}).get(name) if isinstance(jd, dict) else None, name)
        if j:
            joints[name] = j
    pt = c.get(d, "plate_thicknesses")
    plates: list[float] = []
    if isinstance(pt, dict) and "values" in pt and "unit" in pt:
        try:
            plates = sorted(units.convert(float(v), str(pt["unit"]), expect=units.LENGTH).value
                            for v in pt["values"])
        except (units.UnitError, TypeError, ValueError) as exc:
            c.err(f"{p}.plate_thicknesses", str(exc))
    elif not (pt is MISSING or _is_none(pt)):
        c.err(f"{p}.plate_thicknesses", "write as {values: [6, 8, 10], unit: mm}")

    def fraction(key):
        q = c.quantity(d, key, p, units.FRACTION, required=False, non_negative=True)
        return None if q is None else q.value

    def assessment(key):
        v = c.get(d, key)
        if v is MISSING or _is_none(v):
            return None
        if not isinstance(v, dict) or not {"result", "basis", "by"} <= set(v):
            c.err(f"{p}.{key}", "an assessment needs result, basis and by")
            return None
        return v

    return Fabrication(
        joints=joints,
        spot_rt_uw11a5b=c.flag(d, "spot_rt_meets_uw11a5b", p,
                               question="state whether the spot radiography of UW-11(a)(5)(b) is met "
                                        "(controls E for seamless heads, UW-12(d))"),
        plate_thicknesses=plates,
        plate_undertolerance=c.value(d, "plate_undertolerance", p, units.LENGTH, required=False,
                                     non_negative=True,
                                     question="state the plate mill undertolerance (UG-16(c))"),
        pipe_undertolerance=fraction("pipe_undertolerance"),
        cutting_allowance=fraction("cutting_allowance"),
        scrap_allowance=fraction("scrap_allowance"),
        nde=str(d.get("nde", "not stated")), pwht=str(d.get("pwht", "not stated")),
        impact_testing=str(d.get("impact_testing", "not stated")),
        mdmt_assessment=assessment("mdmt_assessment"), pwht_assessment=assessment("pwht_assessment"),
        general_tolerances=str(d.get("general_tolerances", "not specified")),
    )


def _flange(c: _Ctx, d, path, types: dict, materials) -> Flange | None:
    if _is_none(d):
        return None
    if not isinstance(d, dict):
        c.err(path, "flange must be a mapping or none")
        return None
    ref = d.get("type_ref")
    base = {}
    if ref is not None:
        if ref not in types:
            c.err(f"{path}.type_ref", f"unknown flange type {ref!r}; define it under flange_types")
            return None
        base = dict(types[ref])
    merged = {**base, **{k: v for k, v in d.items() if k != "type_ref"}}
    mat = c.text(merged, "material", path)
    if mat and mat not in materials:
        c.err(f"{path}.material", f"material key {mat!r} not defined under materials")
    dims = None
    dd = merged.get("dimensions")
    if isinstance(dd, dict):
        L = units.LENGTH
        dp = f"{path}.dimensions"
        dims = FlangeDims(
            od=c.value(dd, "od", dp, L, positive=True) or 0.0,
            thickness=c.value(dd, "thickness", dp, L, positive=True) or 0.0,
            hub_od=c.value(dd, "hub_od", dp, L, required=False, positive=True),
            length_through_hub=c.value(dd, "length_through_hub", dp, L, required=False, positive=True),
            bolt_circle=c.value(dd, "bolt_circle", dp, L, positive=True) or 0.0,
            bolt_holes=int(c.number(dd, "bolt_holes", dp, integer=True, lo=4, hi=200) or 0),
            bolt_hole_diameter=c.value(dd, "bolt_hole_diameter", dp, L, positive=True) or 0.0,
            bolt_size=str(dd.get("bolt_size", "")),
            raised_face_od=c.value(dd, "raised_face_od", dp, L, required=False, positive=True),
            raised_face_height=c.value(dd, "raised_face_height", dp, L, required=False, non_negative=True),
            source=str(merged.get("dimensions_source", "not stated")),
            status=str(merged.get("dimensions_status", "UNVERIFIED")))
    else:
        c.ask(f"{path}.dimensions", "flange dimensions not given: the 3D model and drawings will show "
              "the flange only as a neck end")
    # a missing rating is asked for by the NZ-<tag>-FLG calculation record
    rating = c.value(merged, "rating_at_design_temperature", path, units.PRESSURE, required=False,
                     positive=True)
    return Flange(
        type_ref=str(ref or ""), standard=str(merged.get("standard", "")),
        pressure_class=str(merged.get("class", "")), flange_type=str(merged.get("type", "")),
        facing=str(merged.get("facing", "")), material=mat or "",
        rating_at_design_temperature=rating, rating_source=str(merged.get("rating_source", "")),
        rating_status=str(merged.get("rating_status", "UNVERIFIED")), dims=dims,
        blind_cover=bool(merged.get("blind_cover", False)),
        supply_bolting=bool(merged.get("supply_bolting", False)),
        gasket=str(merged.get("gasket", "not specified")), bolting=str(merged.get("bolting", "not specified")))


def _neck(c: _Ctx, d, path, materials) -> Neck | None:
    if not isinstance(d, dict):
        c.err(path, "neck definition missing")
        return None
    kind = c.text(d, "type", path, choices={"pipe", "plate"})
    mat = c.text(d, "material", path)
    if mat and mat not in materials:
        c.err(f"{path}.material", f"material key {mat!r} not defined under materials")
    if kind == "pipe":
        if "nps" in d:
            try:
                ps = pipes.lookup(d["nps"], d.get("schedule", ""))
            except KeyError as exc:
                c.err(f"{path}.nps", str(exc))
                return None
            return Neck("pipe", ps.od, ps.wall, mat or "", ps.nps, ps.schedule, ps.std_wall,
                        ps.source, ps.status)
        od = c.value(d, "od", path, units.LENGTH, positive=True)
        wall = c.value(d, "wall", path, units.LENGTH, positive=True)
        if od is None or wall is None:
            return None
        return Neck("pipe", od, wall, mat or "", None, None, None, "user input", "USER_SUPPLIED_UNVERIFIED")
    if kind == "plate":
        od = c.value(d, "od", path, units.LENGTH, positive=True)
        wall = c.value(d, "thickness", path, units.LENGTH, positive=True)
        seam_E = c.number(d, "seam_joint_efficiency", path, lo=0.45, hi=1.0)
        if od is None or wall is None:
            return None
        std = None
        if d.get("equivalent_nps") is not None:
            try:
                std = pipes.lookup(d["equivalent_nps"], "STD").std_wall
            except KeyError as exc:
                c.err(f"{path}.equivalent_nps", str(exc))
        return Neck("plate", od, wall, mat or "", str(d.get("equivalent_nps")) if d.get("equivalent_nps") else None,
                    None, std, "user input", "USER_SUPPLIED_UNVERIFIED", seam_E)
    return None


def _head(c: _Ctx, d, pos, materials) -> Head | None:
    p = f"geometry.heads.{pos}"
    if not isinstance(d, dict):
        c.err(p, "head definition missing")
        return None
    typ = c.text(d, "type", p, choices=HEAD_TYPES)
    L = units.LENGTH
    ar = kr = cr = None
    if typ == "ellipsoidal":
        ar = c.number(d, "aspect_ratio", p, lo=1.0, hi=3.0)
    if typ == "torispherical":
        cr = c.value(d, "crown_radius", p, L, positive=True)
        kr = c.value(d, "knuckle_radius", p, L, positive=True)
    mat = c.text(d, "material", p)
    if mat and mat not in materials:
        c.err(f"{p}.material", f"material key {mat!r} not defined")
    nom_raw = c.get(d, "nominal_thickness")
    nom = None
    if isinstance(nom_raw, str) and nom_raw.strip().lower() == "auto":
        fa = c.value(d, "forming_allowance", p, L, non_negative=True,
                     question="automatic head thickness needs the forming (thinning) allowance from the head maker")
        tmin = None
    else:
        nom = c.value(d, "nominal_thickness", p, L, positive=True)
        tmin = c.value(d, "min_thickness_after_forming", p, L, required=False, positive=True)
        fa = c.value(d, "forming_allowance", p, L, required=False, non_negative=True)
        if tmin is None and fa is None:
            c.err(p, "give min_thickness_after_forming or forming_allowance (UG-32 uses the minimum "
                  "thickness after forming; it is not assumed equal to the nominal plate)")
        if tmin is not None and nom is not None and tmin > nom:
            c.err(f"{p}.min_thickness_after_forming", "exceeds the nominal plate thickness")
    construction = c.text(d, "construction", p, choices={"seamless", "welded"})
    jeo = c.number(d, "joint_efficiency", p, required=construction == "welded", lo=0.3, hi=1.0)
    if typ is None or mat is None or construction is None:
        return None
    return Head(pos, typ, ar, cr, kr, c.value(d, "straight_flange", p, L, non_negative=True) or 0.0,
                mat, construction, nom, tmin, fa, jeo)


def _geometry(c: _Ctx, d: dict, flange_types: dict, materials, process, fab) -> Geometry | None:
    p = "geometry"
    L = units.LENGTH
    orient = c.text(d, "orientation", p, choices={"vertical", "horizontal"})
    if orient == "horizontal":
        c.err(f"{p}.orientation", "horizontal vessels (saddles, Zick analysis) are OUT_OF_SCOPE in "
              "v0.1; the calculation core is orientation independent but the geometry/CAD/support "
              "layers are vertical only")
    basis = c.text(d, "diameter_basis", p, choices={"ID"})
    D = c.value(d, "diameter", p, L, positive=True)
    tt = c.value(d, "tangent_to_tangent", p, L, positive=True)
    btl = c.value(d, "bottom_tangent_elevation", p, L, non_negative=True)
    courses = []
    for i, cd in enumerate(d.get("shell_courses") or []):
        cp = f"{p}.shell_courses[{i}]"
        mat = c.text(cd, "material", cp)
        if mat and mat not in materials:
            c.err(f"{cp}.material", f"material key {mat!r} not defined")
        nt = cd.get("nominal_thickness")
        nom = None if (isinstance(nt, str) and nt.strip().lower() == "auto") else \
            c.value(cd, "nominal_thickness", cp, L, positive=True)
        if nom is None and not fab.plate_thicknesses:
            c.err(f"{cp}.nominal_thickness", "auto selection needs fabrication.plate_thicknesses")
        courses.append(ShellCourse(c.text(cd, "id", cp) or f"C{i + 1}",
                                   c.value(cd, "length", cp, L, positive=True) or 0.0, mat or "", nom,
                                   c.angle(cd, "long_seam_orientation", cp, required=False)))
    if not courses:
        c.err(f"{p}.shell_courses", "at least one shell course is required")
    hd = d.get("heads") or {}
    heads = {}
    for pos in ("top", "bottom"):
        h = _head(c, hd.get(pos), pos, materials)
        if h:
            heads[pos] = h
    if tt and courses and len(heads) == 2:
        total = sum(cc.length for cc in courses) + sum(h.straight_flange for h in heads.values())
        if abs(total - tt) > 0.5:
            c.err(f"{p}.shell_courses", f"course lengths {sum(cc.length for cc in courses):g} mm + "
                  f"straight flanges {sum(h.straight_flange for h in heads.values()):g} mm = {total:g} mm "
                  f"does not equal the tangent-to-tangent length {tt:g} mm")
    nozzles = []
    tags = set()
    for i, nd in enumerate(d.get("nozzles") or []):
        np_ = f"{p}.nozzles[{i}]"
        tag = c.text(nd, "tag", np_)
        if tag in tags:
            c.err(f"{np_}.tag", f"duplicate nozzle tag {tag}")
        tags.add(tag)
        loc = c.text(nd, "location", np_, choices={"shell", "top_head", "bottom_head"})
        neck = _neck(c, nd.get("neck"), f"{np_}.neck", materials)
        pad = None
        pd = nd.get("pad")
        if not _is_none(pd):
            pp = f"{np_}.pad"
            te = c.value(pd, "thickness", pp, L, positive=True)
            dp_ = c.value(pd, "outside_diameter", pp, L, positive=True)
            pm = c.text(pd, "material", pp)
            if pm and pm not in materials:
                c.err(f"{pp}.material", f"material key {pm!r} not defined")
            if te and dp_ and pm:
                pad = Pad(te, dp_, pm)
        wl = nd.get("welds") or {}
        legs = {}
        for k in ("nozzle_outer_leg", "pad_outer_leg", "inner_leg"):
            legs[k] = c.value(wl, k, f"{np_}.welds", L, required=False, non_negative=True)
        if all(v is None for v in legs.values()):
            c.warn(f"{np_}.welds", "no weld sizes: weld areas A41-A43 are taken as zero (conservative) "
                   "and weld strength (UG-41) is NOT_EVALUATED")
        elev = c.value(nd, "elevation", np_, L, required=loc == "shell")
        offset = c.value(nd, "offset", np_, L, required=False, non_negative=True) or 0.0
        if loc != "shell" and offset > 0:
            c.err(f"{np_}.offset", "off-centre head nozzles (hillside/radial in the knuckle) are "
                  "OUT_OF_SCOPE in v0.1; place head nozzles on the head centreline")
        att = c.text(nd, "attachment", np_, choices={"set_in", "set_on"})
        if neck and tag and loc and att:
            nozzles.append(Nozzle(
                tag=tag, service=c.text(nd, "service", np_, required=False) or "", location=loc,
                elevation=elev, orientation=c.angle(nd, "orientation", np_, required=loc == "shell") or 0.0,
                offset=offset, projection=c.value(nd, "projection", np_, L, positive=True) or 0.0,
                neck=neck, attachment=att,
                inward_projection=c.value(nd, "inward_projection", np_, L, required=False, non_negative=True) or 0.0,
                flange=_flange(c, nd.get("flange"), f"{np_}.flange", flange_types, materials),
                pad=pad, weld_legs=legs, access_opening=bool(nd.get("access_opening", False))))
    legs = None
    sd = d.get("supports")
    if isinstance(sd, dict) and sd.get("type") == "legs":
        sp = f"{p}.supports"
        lg = sd.get("leg", {})
        legs = Legs(count=int(c.number(sd, "count", sp, integer=True, lo=3, hi=12) or 0),
                    orientation_start=c.angle(sd, "orientation_start", sp) or 0.0,
                    section=str(lg.get("section", "")),
                    od=c.value(lg, "od", f"{sp}.leg", L, positive=True) or 0.0,
                    wall=c.value(lg, "wall", f"{sp}.leg", L, positive=True) or 0.0,
                    material=c.text(lg, "material", f"{sp}.leg") or "",
                    top_elevation=c.value(sd, "top_elevation", sp, L, positive=True) or 0.0,
                    base_plate=_base_plate(c, sd.get("base_plate") or {}, f"{sp}.base_plate"))
    elif sd is not None and not _is_none(sd):
        c.err(f"{p}.supports", "only supports.type: legs is implemented in v0.1 (skirt and saddles are OUT_OF_SCOPE)")
    else:
        c.ask(f"{p}.supports", "no supports defined: support loads and the support model will be absent")
    lugs = None
    ld = d.get("lifting_lugs")
    if isinstance(ld, dict):
        lp = f"{p}.lifting_lugs"
        al = ld.get("allowables")
        allow = None
        if isinstance(al, dict):
            allow = {k: c.value(al, k, f"{lp}.allowables", units.PRESSURE, positive=True)
                     for k in ("tension", "shear", "bearing")}
            if None in allow.values():
                allow = None
        lugs = Lugs(count=int(c.number(ld, "count", lp, integer=True, lo=1, hi=8) or 0),
                    orientation_start=c.angle(ld, "orientation_start", lp) or 0.0,
                    elevation=c.value(ld, "elevation", lp, L, positive=True) or 0.0,
                    thickness=c.value(ld, "thickness", lp, L, positive=True) or 0.0,
                    height=c.value(ld, "height", lp, L, positive=True) or 0.0,
                    projection=c.value(ld, "projection", lp, L, positive=True) or 0.0,
                    hole_diameter=c.value(ld, "hole_diameter", lp, L, positive=True) or 0.0,
                    hole_edge_distance=c.value(ld, "hole_edge_distance", lp, L, positive=True) or 0.0,
                    material=c.text(ld, "material", lp) or "", allowables=allow)
    if None in (orient, basis, D, tt, btl) or orient == "horizontal" or len(heads) != 2:
        return None
    return Geometry(orient, basis, D, tt, btl, courses, heads, nozzles, legs, lugs,
                    str(d.get("insulation", "none")))


def _base_plate(c: _Ctx, d: dict, path: str) -> dict:
    L = units.LENGTH
    out = {k: c.value(d, k, path, L, positive=True) for k in ("length", "width", "thickness")}
    out["anchor_holes"] = int(c.number(d, "anchor_holes", path, required=False, integer=True, lo=0, hi=8) or 0)
    out["anchor_hole_diameter"] = c.value(d, "anchor_hole_diameter", path, L, required=out["anchor_holes"] > 0,
                                          positive=True)
    out["anchor_spacing"] = c.value(d, "anchor_spacing", path, L, required=out["anchor_holes"] > 1, positive=True)
    out["anchor_bolt"] = str(d.get("anchor_bolt", ""))
    out["material"] = c.text(d, "material", path) or ""
    return out


def _loads(c: _Ctx, d: dict, geometry) -> dict[str, LoadItem]:
    out = {}
    for key in LOAD_KEYS:
        v = (d or {}).get(key)
        p = f"loads.{key}"
        if isinstance(v, dict) and "not_applicable" in v:
            reason = str(v["not_applicable"]).strip()
            if not reason:
                c.err(p, "not_applicable needs a reason")
            out[key] = LoadItem(key, False, reason, {}, "")
            continue
        if isinstance(v, str) and v.strip().lower() == "not_applicable":
            c.err(p, "write not_applicable as {not_applicable: '<reason>'}")
            continue
        if isinstance(v, dict) and v:
            vals = {}
            for k, raw in v.items():
                if k in ("basis", "note"):
                    continue
                if k == "impact_factor":
                    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw >= 1.0:
                        vals[k] = float(raw)
                    else:
                        c.err(f"{p}.impact_factor", "must be a plain number >= 1.0")
                    continue
                dim = units.MOMENT if "moment" in k else units.FORCE
                try:
                    vals[k] = units.parse(raw, expect=dim, field=f"{p}.{k}").value
                except units.UnitError as exc:
                    c.err(f"{p}.{k}", str(exc))
            out[key] = LoadItem(key, True, None, vals, str(v.get("basis", "not stated")))
            if not v.get("basis"):
                c.warn(p, "load values given without a basis (standard, edition, calculation reference)")
            continue
        out[key] = LoadItem(key, False, None, {}, "")
        if key == "lifting":
            c.ask(p, "give the lifting impact factor (dynamic factor) and lifting method")
    return out


ASSESSMENT_OK = {"pass", "exempt", "acceptable", "impact_tested"}


def _assessments(c: _Ctx, d: dict) -> dict[str, dict]:
    """External engineering assessments for checks the software does not
    implement (e.g. UG-41 weld strength, support structure). Keyed by calc id."""
    out = {}
    if not isinstance(d, dict):
        c.err("assessments", "must map calc ids to assessment records")
        return out
    for cid, a in d.items():
        p = f"assessments.{cid}"
        if not isinstance(a, dict) or not {"result", "basis", "by", "status"} <= set(a):
            c.err(p, "an assessment needs result, basis, by and status")
            continue
        if str(a["status"]) not in DataStatus.__members__:
            c.err(f"{p}.status", f"unknown status {a['status']!r}")
            continue
        out[str(cid)] = {k: str(v) for k, v in a.items()}
    return out


def _external_data(c: _Ctx, d: dict, process) -> dict:
    out = {"shell": None, "heads": None}
    for key in ("shell", "heads"):
        v = d.get(key)
        p = f"external_pressure_data.{key}"
        if _is_none(v):
            continue          # the EXT-* records ask for the chart data with the ratios to enter
        if not isinstance(v, dict) or "source" not in v:
            c.err(p, "chart data needs at least 'source' plus A/B (and E for the elastic path)")
            continue
        rec = {"source": str(v["source"]), "status": str(v.get("status", "USER_SUPPLIED_UNVERIFIED"))}
        for k in ("A",):
            if k in v and v[k] is not None:
                rec[k] = float(v[k])
        for k in ("B", "E"):
            if k in v and v[k] is not None:
                rec[k] = units.parse(v[k], expect=units.PRESSURE, field=f"{p}.{k}").value
        rec["left_of_material_line"] = bool(v.get("left_of_material_line", False))
        out[key] = rec
    return out
