"""Typed, unit-normalised design input (output of the validator).

All lengths mm, pressures MPa (gauge), temperatures degC, angles degrees,
fractions plain numbers. ``None`` means "not provided"; the calculation layer
turns that into NOT_EVALUATED, never into a default value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..materials import MaterialRecord


@dataclass
class Project:
    project_id: str
    equipment_tag: str
    description: str
    customer: str
    design_code: str
    code_edition: str
    addenda: str
    units_system: str
    design_status: str
    revision: str
    data_status: str
    jurisdiction: str
    prepared_by: str
    date: str


@dataclass
class DesignBasis:
    locked: bool
    confirmed_by: str | None
    confirmed_on: str | None
    notes: list[str] = field(default_factory=list)


@dataclass
class Process:
    fluid: str
    fluid_phase: str
    lethal_service: bool | None
    cyclic_service: bool | None
    operating_pressure: float | None
    design_pressure: float
    operating_temperature: float | None
    design_temperature: float
    mdmt: float
    external_pressure: float | None
    external_design_temperature: float | None
    required_volume: float | None
    liquid_level: float | None
    liquid_density: float | None
    corrosion_allowance: float
    test_type: str
    test_basis: str
    test_temperature: float
    test_position: str
    test_fluid_density: float | None


@dataclass
class Joint:
    name: str
    category: str
    joint_type: int
    radiography: str


@dataclass
class MaterialAssignment:
    key: str
    record: MaterialRecord | None        # pressure-part material with allowable stresses
    non_pressure: bool = False
    spec: str = ""
    density: float | None = None         # kg/m3
    status: str = "UNVERIFIED"
    min_yield: float | None = None       # MPa (non-pressure parts, user-supplied)

    @property
    def label(self) -> str:
        return self.record.name if self.record else self.spec

    @property
    def rho(self) -> float | None:
        return self.record.density if self.record else self.density

    @property
    def data_status(self) -> str:
        return str(self.record.status) if self.record else self.status


@dataclass
class ShellCourse:
    id: str
    length: float
    material: str
    nominal_thickness: float | None          # None = select automatically
    long_seam_orientation: float | None


@dataclass
class Head:
    position: str                 # top/bottom (vertical) or left/right (horizontal)
    type: str                     # ellipsoidal | torispherical | hemispherical
    aspect_ratio: float | None    # D/2h, ellipsoidal
    crown_radius: float | None    # inside L, torispherical
    knuckle_radius: float | None  # inside r, torispherical
    straight_flange: float
    material: str
    construction: str             # seamless | welded
    nominal_thickness: float | None
    min_thickness_after_forming: float | None
    forming_allowance: float | None
    joint_efficiency_override: float | None = None


@dataclass
class FlangeDims:
    od: float
    thickness: float
    hub_od: float | None
    length_through_hub: float | None
    bolt_circle: float
    bolt_holes: int
    bolt_hole_diameter: float
    bolt_size: str
    raised_face_od: float | None
    raised_face_height: float | None
    source: str
    status: str


@dataclass
class Flange:
    type_ref: str
    standard: str
    pressure_class: str
    flange_type: str
    facing: str
    material: str
    rating_at_design_temperature: float | None
    rating_source: str
    rating_status: str
    dims: FlangeDims | None
    blind_cover: bool
    supply_bolting: bool
    gasket: str
    bolting: str


@dataclass
class Neck:
    type: str            # pipe | plate
    od: float
    wall: float          # nominal
    material: str
    nps: str | None = None
    schedule: str | None = None
    std_wall: float | None = None
    data_source: str = ""
    data_status: str = ""
    seam_E: float | None = None      # joint efficiency of a rolled-plate neck's long seam


@dataclass
class Pad:
    thickness: float
    od: float
    material: str


@dataclass
class Nozzle:
    tag: str
    service: str
    location: str            # shell | top_head | bottom_head (vertical)
    elevation: float | None  # from bottom tangent line, shell nozzles
    orientation: float       # degrees, plan angle
    offset: float            # mm from head centre, head nozzles
    projection: float        # outside surface to flange face
    neck: Neck
    attachment: str          # set_in | set_on
    inward_projection: float
    flange: Flange | None
    pad: Pad | None
    weld_legs: dict[str, float | None]
    access_opening: bool


@dataclass
class Legs:
    count: int
    orientation_start: float
    section: str
    od: float
    wall: float
    material: str
    top_elevation: float          # above BTL
    base_plate: dict[str, Any]


@dataclass
class Lugs:
    count: int
    orientation_start: float
    elevation: float              # lug centre above BTL
    thickness: float
    height: float
    projection: float
    hole_diameter: float
    hole_edge_distance: float
    material: str
    allowables: dict[str, float] | None   # user-supplied allowable stresses for the basic check


@dataclass
class Geometry:
    orientation: str
    diameter_basis: str
    inside_diameter: float
    tangent_to_tangent: float
    bottom_tangent_elevation: float
    shell_courses: list[ShellCourse]
    heads: dict[str, Head]
    nozzles: list[Nozzle]
    legs: Legs | None
    lugs: Lugs | None
    insulation: str


@dataclass
class Fabrication:
    joints: dict[str, Joint]
    spot_rt_uw11a5b: bool | None
    plate_thicknesses: list[float]
    plate_undertolerance: float | None
    pipe_undertolerance: float | None
    cutting_allowance: float | None
    scrap_allowance: float | None
    nde: str
    pwht: str
    impact_testing: str
    mdmt_assessment: dict | None
    pwht_assessment: dict | None
    general_tolerances: str


@dataclass
class LoadItem:
    key: str
    provided: bool
    not_applicable_reason: str | None
    values: dict[str, float]
    basis: str


@dataclass
class VesselInput:
    project: Project
    design_basis: DesignBasis
    process: Process
    geometry: Geometry
    materials: dict[str, MaterialAssignment]
    fabrication: Fabrication
    loads: dict[str, LoadItem]
    external_pressure_data: dict[str, dict | None]
    reference_verification: list[dict]
    assessments: dict[str, dict]
    source_path: str
    input_hash: str
    raw: dict
