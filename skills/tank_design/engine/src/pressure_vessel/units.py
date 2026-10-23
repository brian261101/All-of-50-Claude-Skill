"""Explicit-unit quantities.

Every dimensional input must state its unit: ``"1.0 MPa"``, ``"8 mm"``,
``"-10 degC"`` or ``{value: 1.0, unit: MPa}``. A bare number for a dimensional
field is rejected, so MPa can never be mixed with psi, or mm with inch,
without an explicit conversion.

Internal (calculation) units: length mm, area mm^2, volume mm^3, pressure and
stress MPa (= N/mm^2), force N, moment N*mm, mass kg, density kg/m^3,
temperature degC, fractions as plain numbers (12.5 % -> 0.125).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

LENGTH, AREA, VOLUME, PRESSURE, TEMPERATURE = "length", "area", "volume", "pressure", "temperature"
DENSITY, MASS, FORCE, MOMENT, FRACTION, ACCEL = "density", "mass", "force", "moment", "fraction", "acceleration"

_PSI = 0.006894757293168361  # MPa per psi (exact from lbf and inch definitions)

# unit text (lower case, normalised) -> (dimension, factor to internal unit)
_LINEAR: dict[str, tuple[str, float]] = {
    "mm": (LENGTH, 1.0), "m": (LENGTH, 1000.0), "cm": (LENGTH, 10.0),
    "in": (LENGTH, 25.4), "inch": (LENGTH, 25.4), "ft": (LENGTH, 304.8),
    "mm2": (AREA, 1.0), "cm2": (AREA, 100.0), "m2": (AREA, 1.0e6), "in2": (AREA, 645.16),
    "mm3": (VOLUME, 1.0), "cm3": (VOLUME, 1.0e3), "m3": (VOLUME, 1.0e9), "l": (VOLUME, 1.0e6),
    "in3": (VOLUME, 16387.064), "ft3": (VOLUME, 28316846.592), "usgal": (VOLUME, 3785411.784),
    "mpa": (PRESSURE, 1.0), "n/mm2": (PRESSURE, 1.0), "kpa": (PRESSURE, 1.0e-3),
    "pa": (PRESSURE, 1.0e-6), "bar": (PRESSURE, 0.1), "psi": (PRESSURE, _PSI),
    "ksi": (PRESSURE, _PSI * 1000.0), "kgf/cm2": (PRESSURE, 0.0980665),
    "kg/m3": (DENSITY, 1.0), "g/cm3": (DENSITY, 1000.0), "lb/ft3": (DENSITY, 16.018463373960138),
    "kg": (MASS, 1.0), "t": (MASS, 1000.0), "lb": (MASS, 0.45359237),
    "n": (FORCE, 1.0), "kn": (FORCE, 1.0e3), "lbf": (FORCE, 4.4482216152605), "kgf": (FORCE, 9.80665),
    "n.mm": (MOMENT, 1.0), "n.m": (MOMENT, 1.0e3), "kn.m": (MOMENT, 1.0e6),
    "lbf.ft": (MOMENT, 1355.8179483314004), "lbf.in": (MOMENT, 112.98482902761670),
    "%": (FRACTION, 0.01), "fraction": (FRACTION, 1.0),
    "m/s2": (ACCEL, 1000.0), "mm/s2": (ACCEL, 1.0), "g0": (ACCEL, 9806.65),
}
_TEMPS = {"degc": "C", "c": "C", "°c": "C", "degf": "F", "f": "F", "°f": "F", "k": "K"}

# gauge / absolute suffixes on pressure units: "MPa(g)", "barg", "psig", "psia"
_GAUGE_RE = re.compile(r"^(?P<u>[a-z/0-9]+?)\s*(?:\((?P<p>[ga])\)|(?P<s>[ga]))$")

INTERNAL_UNIT = {LENGTH: "mm", AREA: "mm2", VOLUME: "mm3", PRESSURE: "MPa", TEMPERATURE: "degC",
                 DENSITY: "kg/m3", MASS: "kg", FORCE: "N", MOMENT: "N.mm", FRACTION: "-",
                 ACCEL: "mm/s2"}

G0 = 9806.65  # standard gravity, mm/s^2


class UnitError(ValueError):
    """Raised for a missing, unknown or dimensionally wrong unit."""


def _norm(unit: str) -> str:
    u = unit.strip().lower().replace(" ", "").replace("·", ".").replace("*", ".")
    u = u.replace("²", "2").replace("³", "3").replace("^", "")
    return {"n/m2": "pa", "mpa(g)": "mpa(g)", "litre": "l", "liter": "l"}.get(u, u)


@dataclass(frozen=True)
class Quantity:
    """A value converted to the internal unit of its dimension."""

    value: float
    dim: str
    text: str = ""          # the original input text, kept for the report
    pressure_ref: str = ""  # "g", "a" or "" for pressures

    @property
    def unit(self) -> str:
        return INTERNAL_UNIT[self.dim]

    def __float__(self) -> float:
        return self.value


def _split(text: str) -> tuple[float, str]:
    m = re.match(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)\s*$", text)
    if not m:
        raise UnitError(f"cannot read a number and unit from {text!r}")
    return float(m.group(1)), m.group(2)


def convert(value: float, unit: str, *, expect: str | None = None) -> Quantity:
    """Convert ``value`` given in ``unit`` to the internal unit."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise UnitError(f"value must be a finite number, got {value!r}")
    u = _norm(unit)
    text = f"{value:g} {unit}"
    if u in _TEMPS:
        kind = _TEMPS[u]
        c = value if kind == "C" else (value - 32.0) * 5.0 / 9.0 if kind == "F" else value - 273.15
        q = Quantity(c, TEMPERATURE, text)
    else:
        ref = ""
        if u not in _LINEAR:
            m = _GAUGE_RE.match(u)
            if m and m.group("u") in _LINEAR and _LINEAR[m.group("u")][0] == PRESSURE:
                ref = m.group("p") or m.group("s")
                u = m.group("u")
        if u not in _LINEAR:
            raise UnitError(f"unknown unit {unit!r}")
        dim, factor = _LINEAR[u]
        q = Quantity(value * factor, dim, text, ref)
    if expect is not None and q.dim != expect:
        raise UnitError(f"{text!r} is a {q.dim}, expected a {expect}")
    return q


def parse(raw, *, expect: str | None = None, field: str = "value") -> Quantity:
    """Parse ``"8 mm"`` or ``{value: 8, unit: mm}``. Bare numbers are rejected
    unless ``expect`` is None-dimensional (handled by callers)."""
    if isinstance(raw, Quantity):
        if expect and raw.dim != expect:
            raise UnitError(f"{field}: {raw.text!r} is a {raw.dim}, expected a {expect}")
        return raw
    if isinstance(raw, bool) or raw is None:
        raise UnitError(f"{field}: a quantity with a unit is required, got {raw!r}")
    if isinstance(raw, (int, float)):
        raise UnitError(f"{field}: {raw!r} has no unit; write it as e.g. '{raw} "
                        f"{INTERNAL_UNIT.get(expect or '', 'mm')}'")
    if isinstance(raw, dict):
        if set(raw) - {"value", "unit", "source", "note"} or "value" not in raw or "unit" not in raw:
            raise UnitError(f"{field}: a quantity mapping needs exactly 'value' and 'unit' "
                            f"(optional 'source', 'note'), got keys {sorted(raw)}")
        try:
            return convert(raw["value"], str(raw["unit"]), expect=expect)
        except UnitError as exc:
            raise UnitError(f"{field}: {exc}") from None
    if isinstance(raw, str):
        try:
            v, u = _split(raw)
            if not u:
                raise UnitError(f"{raw!r} has no unit")
            return convert(v, u, expect=expect)
        except UnitError as exc:
            raise UnitError(f"{field}: {exc}") from None
    raise UnitError(f"{field}: cannot interpret {raw!r} as a quantity")


def to(value: float, dim: str, unit: str) -> float:
    """Convert an internal value to a display unit (inverse of convert)."""
    u = _norm(unit)
    if dim == TEMPERATURE:
        kind = _TEMPS[u]
        return value if kind == "C" else value * 9.0 / 5.0 + 32.0 if kind == "F" else value + 273.15
    d, factor = _LINEAR[u]
    if d != dim:
        raise UnitError(f"cannot express a {dim} in {unit}")
    return value / factor


def fmt(value: float | None, digits: int = 3) -> str:
    """Engineering formatting used in reports: fixed decimals, no exponent for
    ordinary magnitudes."""
    if value is None:
        return "—"
    if value != 0 and (abs(value) >= 1e7 or abs(value) < 10 ** (-digits)):
        return f"{value:.{digits}e}"
    return f"{value:.{digits}f}"
