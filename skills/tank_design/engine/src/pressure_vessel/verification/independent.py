"""Independent formulations used to cross-check the calculation engine.

Nothing here calls the engine's formula functions. The checks use either a
different equation (outside-dimension forms of Mandatory Appendix 1-1/1-4,
which are algebraically equivalent when Ro = R + t), a different numerical
route (bisection on the stress equation instead of the closed form), or a
different geometric derivation (reinforcement areas from the limits of
reinforcement; head volumes from spherical-zone and torus formulas).
"""

from __future__ import annotations

import math


def bisect(f, lo, hi, tol=1e-12, it=300):
    flo = f(lo)
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# --- shells -----------------------------------------------------------------

def shell_circ_by_stress(P, R, S, E):
    """Thickness where the UG-27 circumferential stress P(R + 0.6t)/(Et) = S."""
    return bisect(lambda t: P * (R + 0.6 * t) / (E * t) - S, 1e-9, R)


def shell_long_by_stress(P, R, S, E):
    """Thickness where the longitudinal stress P(R - 0.4t)/(2Et) = S."""
    return bisect(lambda t: P * (R - 0.4 * t) / (2 * E * t) - S, 1e-9, R)


def shell_circ_outside_form(P, R, S, E):
    """Appendix 1-1 outside-radius form t = P Ro/(SE + 0.4P), Ro = R + t,
    solved by fixed-point iteration."""
    t = 0.0
    for _ in range(200):
        t = P * (R + t) / (S * E + 0.4 * P)
    return t


def shell_long_outside_form(P, R, S, E):
    t = 0.0
    for _ in range(200):
        t = P * (R + t) / (2 * S * E + 1.4 * P)
    return t


def lame_hoop_max(P, Ri, t):
    """Exact elastic hoop stress at the bore of a thick cylinder (information)."""
    Ro = Ri + t
    return P * (Ro ** 2 + Ri ** 2) / (Ro ** 2 - Ri ** 2)


# --- heads ------------------------------------------------------------------------

def ellipsoidal_outside_form(P, D, S, E, ar):
    K = (2 + ar * ar) / 6.0
    t = 0.0
    for _ in range(200):
        t = P * (D + 2 * t) * K / (2 * S * E + 2 * P * (K - 0.1))
    return t


def torispherical_outside_form(P, L, r, S, E):
    M = 0.25 * (3 + math.sqrt(L / r))
    t = 0.0
    for _ in range(200):
        t = P * (L + t) * M / (2 * S * E + P * (M - 0.2))
    return t


def hemispherical_outside_form(P, L, S, E):
    t = 0.0
    for _ in range(200):
        t = P * (L + t) / (2 * S * E + 0.8 * P)
    return t


def head_stress_at_mawp(kind, P, D, t, E, ar=2.0, L=None, r=None):
    """Membrane stress S implied by (P, t): should equal the allowable stress
    when P is the MAWP."""
    if kind == "ellipsoidal":
        K = (2 + ar * ar) / 6.0
        return P * (K * D + 0.2 * t) / (2 * E * t)
    if kind == "torispherical":
        M = 0.25 * (3 + math.sqrt(L / r))
        return P * (L * M + 0.2 * t) / (2 * E * t)
    return P * (D / 2 + 0.2 * t) / (2 * E * t)


# --- reinforcement (geometric derivation) -----------------------------------------

def area_geometric(d, t, tr, tn, trn, Sv, Sn, Sp=None, te=0.0, Dp=0.0, inserted=True):
    """Area bookkeeping derived from the reinforcement zone instead of the
    printed formulas: the zone is 2*Lp wide (parallel limit) and Ln high
    (normal limit) on each side of the wall; excess metal inside the zone,
    weighted by the strength ratio, is available. Welds are not counted."""
    f2 = min(Sn / Sv, 1.0)
    f1 = f2 if inserted else 1.0
    pad = te > 0 and Dp > 0
    f4 = min((Sp or Sv) / Sv, 1.0) if pad else 1.0
    Lp = max(d, d / 2 + tn + t)
    Ln = min(2.5 * t, 2.5 * tn + te)
    excess = t - tr
    shell_band = (2 * Lp - d) * excess                    # shell strip inside the zone minus the hole
    shell_band -= 2 * tn * excess * (1 - f1)             # nozzle wall replaces shell metal at fr1
    nozzle = 2 * Ln * (tn - trn) * f2 if tn > trn else 0.0
    pad_area = (min(Dp, 2 * Lp) - d - 2 * tn) * min(te, Ln) * f4 if pad else 0.0
    required = d * tr + 2 * tn * tr * (1 - f1)
    return {"A": required, "A1": max(shell_band, 0.0), "A2": nozzle, "A5": max(pad_area, 0.0),
            "A_avail": max(shell_band, 0.0) + nozzle + max(pad_area, 0.0)}


# --- volumes (closed forms) ---------------------------------------------------------

def hemisphere_metal(a, t):
    return 2.0 / 3.0 * math.pi * ((a + t) ** 3 - a ** 3)


def torispherical_solid(a, L, r):
    """Closed-form volume of the solid bounded by the torispherical surface
    and the tangent plane: torus-section knuckle (Pappus) + spherical crown
    segment + the cylinder under the crown base."""
    yc = -math.sqrt((L - r) ** 2 - (a - r) ** 2)
    beta = math.acos((a - r) / (L - r))
    # knuckle: region between rho = 0 and the arc for y in [0, r sin(beta)]
    yk = r * math.sin(beta)
    c = a - r
    # pi * integral_0^yk (c + sqrt(r^2 - y^2))^2 dy, in closed form
    root = math.sqrt(r * r - yk * yk)
    Vk = math.pi * ((c * c + r * r) * yk - yk ** 3 / 3.0 + c * (yk * root + r * r * math.asin(yk / r)))
    # crown: spherical cap above y = yk of the sphere centred at yc with radius L
    cap_h = (yc + L) - yk
    Vc = math.pi * cap_h ** 2 * (3 * L - cap_h) / 3.0
    return Vk + Vc


def ellipsoid_half(a, b):
    return 2.0 / 3.0 * math.pi * a * a * b
