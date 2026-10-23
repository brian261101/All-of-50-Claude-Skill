"""Exact head profiles and numerical volume integrals (no CAD kernel).

These integrals are the analytic side of the CAD volume cross-check: the
FreeCAD model computes volumes with OpenCASCADE, this module computes the same
volumes by quadrature from the same definitions.

Head local coordinates: rho = radial distance from the axis, y = axial
distance from the tangent line towards the closed end. All mm.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass


def simpson(f, a, b, n=200):
    if b <= a:
        return 0.0
    n += n % 2
    h = (b - a) / n
    s = f(a) + f(b)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * f(a + i * h)
    return s * h / 3.0


@dataclass
class HeadProfile:
    """Inner surface of a formed head and its outward normal offset."""

    kind: str
    a: float                 # inside radius at the tangent line, D/2
    ar: float = 2.0          # ellipsoidal D/2h
    L: float = 0.0           # torispherical inside crown radius
    r: float = 0.0           # torispherical inside knuckle radius

    def __post_init__(self):
        if self.kind == "ellipsoidal":
            self.b = self.a / self.ar
        elif self.kind == "hemispherical":
            self.b = self.a
        elif self.kind == "torispherical":
            if self.L < self.a or self.r <= 0 or self.r >= self.a:
                raise ValueError("torispherical head needs L >= D/2 and 0 < r < D/2")
            self.yc = -math.sqrt((self.L - self.r) ** 2 - (self.a - self.r) ** 2)
            self.beta = math.acos((self.a - self.r) / (self.L - self.r))
            self.b = self.yc + self.L
        else:
            raise ValueError(f"unknown head kind {self.kind}")

    @property
    def depth(self) -> float:
        """Inside depth from tangent line to crown (excluding straight flange)."""
        return self.b

    def point(self, u: float, t: float = 0.0) -> tuple[float, float]:
        """Point on the surface offset by t along the outward normal; u in
        [0, 1] runs from the tangent line (u=0) to the crown on the axis (u=1)."""
        if self.kind == "ellipsoidal":
            th = u * math.pi / 2
            x, y = self.a * math.cos(th), self.b * math.sin(th)
            nx, ny = self.b * math.cos(th), self.a * math.sin(th)
            m = math.hypot(nx, ny)
            return x + t * nx / m, y + t * ny / m
        if self.kind == "hemispherical":
            th = u * math.pi / 2
            return (self.a + t) * math.cos(th), (self.a + t) * math.sin(th)
        th = u * math.pi / 2
        if th <= self.beta:   # knuckle
            return (self.a - self.r) + (self.r + t) * math.cos(th), (self.r + t) * math.sin(th)
        return (self.L + t) * math.cos(th), self.yc + (self.L + t) * math.sin(th)

    def samples(self, t: float = 0.0, n: int = 2000):
        """Dense (rho, y) points from the tangent line to the axis, plus the
        u-breakpoint of the torispherical knuckle so quadrature stays exact."""
        us = [i / n for i in range(n + 1)]
        if self.kind == "torispherical":
            ub = self.beta / (math.pi / 2)
            us = sorted(set(us + [ub]))
        return [self.point(u, t) for u in us]

    def solid_volume(self, t: float = 0.0) -> tuple[float, float]:
        """(volume, first moment about y=0) of the solid of revolution bounded
        by the offset surface and the tangent plane."""
        pts = self.samples(t)
        V = M = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dy = y1 - y0
            # exact for a linear segment: integral of pi*rho(y)^2 dy
            seg = math.pi * dy * (x0 * x0 + x0 * x1 + x1 * x1) / 3.0
            V += seg
            M += seg * (y0 + y1) / 2.0
        return V, M

    def y_of_rho(self, t: float = 0.0):
        """Return a function y(rho) for the offset surface (monotonic)."""
        pts = list(reversed(self.samples(t)))      # rho ascending from the axis
        rhos = [p[0] for p in pts]
        ys = [p[1] for p in pts]

        def f(rho):
            if rho <= rhos[0]:
                return ys[0]
            i = min(max(bisect_left(rhos, rho), 1), len(rhos) - 1)
            r0, r1 = rhos[i - 1], rhos[i]
            return ys[i - 1] + (ys[i] - ys[i - 1]) * (rho - r0) / (r1 - r0 or 1.0)
        return f


def head_metal(profile: HeadProfile, t: float, sf: float):
    """Metal volume and centroid (y) of a head including its straight flange
    (the straight flange occupies y in [-sf, 0])."""
    Vo, Mo = profile.solid_volume(t)
    Vi, Mi = profile.solid_volume(0.0)
    a = profile.a
    v_sf = math.pi * ((a + t) ** 2 - a ** 2) * sf
    V = Vo - Vi + v_sf
    M = Mo - Mi + v_sf * (-sf / 2.0)
    return V, M / V


def head_capacity(profile: HeadProfile, sf: float) -> float:
    """Inside volume of a head including its straight flange."""
    return profile.solid_volume(0.0)[0] + math.pi * profile.a ** 2 * sf


def polar_integral(f, r0, r1, nr=48, nphi=96):
    """Integral over an annulus r0 <= r <= r1 of f(r, phi) dA."""
    if r1 <= r0:
        return 0.0

    def ring(r):
        return simpson(lambda ph: f(r, ph), 0.0, 2 * math.pi, nphi) * r
    return simpson(ring, r0, r1, nr)


def _sq(R, v):
    d = R * R - v * v
    if d < 0:
        raise ValueError("cross-section wider than the cylinder")
    return math.sqrt(d)


def shell_nozzle_integrals(Ri, Ro, rn_in, rn_out, s_end, attach="set_in", h_in=0.0,
                           r_hole=None, pad=None):
    """Volumes and first moments (along the nozzle axis, from the vessel axis)
    of a radial nozzle in a cylinder.

    neck: annulus rn_in..rn_out from the inner (set_in) or outer (set_on)
    shell surface (minus inward projection h_in) to s_end; hole: material
    removed from the shell; pad: (te, Dp) saddle plate on the outside."""
    start = (lambda v: _sq(Ri, v) - h_in) if attach == "set_in" else (lambda v: _sq(Ro, v))

    def neck_len(r, ph):
        return s_end - start(r * math.sin(ph))

    def neck_mom(r, ph):
        s0 = start(r * math.sin(ph))
        return (s_end ** 2 - s0 ** 2) / 2.0

    out = {"neck_V": polar_integral(neck_len, rn_in, rn_out),
           "neck_M": polar_integral(neck_mom, rn_in, rn_out)}
    rh = rn_out if r_hole is None else r_hole
    out["hole_V"] = polar_integral(lambda r, ph: _sq(Ro, r * math.sin(ph)) - _sq(Ri, r * math.sin(ph)), 0.0, rh)
    out["hole_M"] = polar_integral(lambda r, ph: (Ro ** 2 - Ri ** 2) / 2.0, 0.0, rh)
    if pad:
        te, Dp = pad
        Rp = Ro + te
        out["pad_V"] = polar_integral(lambda r, ph: _sq(Rp, r * math.sin(ph)) - _sq(Ro, r * math.sin(ph)),
                                      rn_out, Dp / 2.0)
        out["pad_M"] = polar_integral(lambda r, ph: (Rp ** 2 - Ro ** 2) / 2.0, rn_out, Dp / 2.0)
    return out


def head_nozzle_integrals(profile: HeadProfile, t: float, rn_in, rn_out, y_end, attach="set_in",
                          r_hole=None):
    """Central nozzle in a head (axis = head axis). Volumes/moments along y."""
    yi, yo = profile.y_of_rho(0.0), profile.y_of_rho(t)
    start = yi if attach == "set_in" else yo
    out = {"neck_V": simpson(lambda r: 2 * math.pi * r * (y_end - start(r)), rn_in, rn_out, 200),
           "neck_M": simpson(lambda r: 2 * math.pi * r * (y_end ** 2 - start(r) ** 2) / 2.0, rn_in, rn_out, 200)}
    rh = rn_out if r_hole is None else r_hole
    out["hole_V"] = simpson(lambda r: 2 * math.pi * r * (yo(r) - yi(r)), 0.0, rh, 200)
    out["hole_M"] = simpson(lambda r: 2 * math.pi * r * (yo(r) ** 2 - yi(r) ** 2) / 2.0, 0.0, rh, 200)
    return out


def flange_volume(fl: dict, neck_od: float, neck_id: float, blind=False):
    """Simplified weld-neck (or blind) flange: ring of thickness (tf - rf_h),
    raised face disc, conical hub from hub_od to the neck OD over (Y - tf),
    bore = neck ID, bolt holes through the ring. Returns (V, centroid
    distance from the flange face)."""
    tf, rf_h = fl["thickness"], fl.get("raised_face_height") or 0.0
    od, rf_od = fl["od"], fl.get("raised_face_od") or 0.0
    ring_t = tf - rf_h
    bore = 0.0 if blind else neck_id
    parts = []  # (volume, centroid from face)
    parts.append((math.pi / 4 * (rf_od ** 2 - bore ** 2) * rf_h, rf_h / 2))
    parts.append((math.pi / 4 * (od ** 2 - bore ** 2) * ring_t, rf_h + ring_t / 2))
    parts.append((-fl["bolt_holes"] * math.pi / 4 * fl["bolt_hole_diameter"] ** 2 * ring_t, rf_h + ring_t / 2))
    if not blind and fl.get("hub_od") and fl.get("length_through_hub"):
        hl = fl["length_through_hub"] - tf
        R1, R2 = fl["hub_od"] / 2, neck_od / 2
        v_cone = math.pi * hl / 3 * (R1 * R1 + R1 * R2 + R2 * R2)
        zc = hl * (R1 * R1 + 2 * R1 * R2 + 3 * R2 * R2) / (4 * (R1 * R1 + R1 * R2 + R2 * R2))
        parts.append((v_cone, tf + zc))
        parts.append((-math.pi / 4 * bore ** 2 * hl, tf + hl / 2))
    V = sum(p[0] for p in parts)
    return V, sum(p[0] * p[1] for p in parts) / V
