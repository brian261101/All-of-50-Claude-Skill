"""ASME VIII-1 internal-pressure formulas as plain functions (SI: mm, MPa).

Each function states its rule, applicability limits and raises
``OutOfScope`` instead of returning a number outside those limits. Symbols:
P pressure, R/D/L/r corroded inside radius/diameter/crown/knuckle radius,
S allowable stress, E joint efficiency, t thickness (corroded, exclusive of
corrosion allowance). Register ids of the references are in ``REF``.
"""

from __future__ import annotations

import math


class OutOfScope(ValueError):
    """The formula's stated applicability limits are exceeded."""


REF = {
    "shell_circ": "ASME8-1:UG-27(c)(1)", "shell_long": "ASME8-1:UG-27(c)(2)",
    "ellipsoidal": "ASME8-1:App1-4(c)", "ellipsoidal_2to1": "ASME8-1:UG-32-ellipsoidal",
    "torispherical": "ASME8-1:App1-4(d)", "torispherical_std": "ASME8-1:UG-32-torispherical",
    "hemispherical": "ASME8-1:UG-32-hemispherical", "head_geometry": "ASME8-1:UG-32-geometry",
    "thin_head": "ASME8-1:App1-4(f)", "thick_shell": "ASME8-1:App1-2",
}

UG16B_MIN = 1.5  # mm, UG-16(b) minimum for shells and heads exclusive of CA


def _pos(**kw):
    for k, v in kw.items():
        if v is None or not v > 0:
            raise ValueError(f"{k} must be positive, got {v}")


def _eff(E):
    if not 0 < E <= 1:
        raise ValueError(f"joint efficiency must satisfy 0 < E <= 1, got {E}")


# --- cylindrical shells, UG-27 ------------------------------------------------

def shell_t_circ(P, R, S, E):
    """UG-27(c)(1): t = PR/(SE - 0.6P); valid for P <= 0.385SE and t <= R/2."""
    _pos(P=P, R=R, S=S), _eff(E)
    if P > 0.385 * S * E:
        raise OutOfScope(f"P = {P:g} MPa > 0.385SE = {0.385 * S * E:.3f} MPa: thick-wall rules "
                         "(Appendix 1-2) apply and are not implemented")
    t = P * R / (S * E - 0.6 * P)
    if t > R / 2:
        raise OutOfScope("t > R/2: Appendix 1-2 applies")
    return t


def shell_t_long(P, R, S, E):
    """UG-27(c)(2): t = PR/(2SE + 0.4P); valid for P <= 1.25SE and t <= R/2."""
    _pos(P=P, R=R, S=S), _eff(E)
    if P > 1.25 * S * E:
        raise OutOfScope(f"P > 1.25SE = {1.25 * S * E:.3f} MPa: Appendix 1-2 applies")
    t = P * R / (2 * S * E + 0.4 * P)
    if t > R / 2:
        raise OutOfScope("t > R/2: Appendix 1-2 applies")
    return t


def shell_mawp_circ(t, R, S, E):
    """UG-27(c)(1) solved for P: P = SEt/(R + 0.6t)."""
    _pos(t=t, R=R, S=S), _eff(E)
    if t > R / 2:
        raise OutOfScope("t > R/2: Appendix 1-2 applies")
    P = S * E * t / (R + 0.6 * t)
    if P > 0.385 * S * E:
        raise OutOfScope("resulting P exceeds 0.385SE")
    return P


def shell_mawp_long(t, R, S, E):
    """UG-27(c)(2) solved for P: P = 2SEt/(R - 0.4t)."""
    _pos(t=t, R=R, S=S), _eff(E)
    if t > R / 2:
        raise OutOfScope("t > R/2: Appendix 1-2 applies")
    return 2 * S * E * t / (R - 0.4 * t)


# --- formed heads, UG-32 / Appendix 1-4 ----------------------------------------

def ellipsoidal_K(ar):
    """Appendix 1-4(c): K = (2 + (D/2h)^2)/6, for 1.0 <= D/2h <= 3.0."""
    if not 1.0 <= ar <= 3.0:
        raise OutOfScope(f"D/2h = {ar:g} outside 1.0..3.0")
    return (2.0 + ar * ar) / 6.0


def ellipsoidal_t(P, D, S, E, ar=2.0):
    """t = PDK/(2SE - 0.2P) (K = 1 for 2:1 heads, the UG-32 form). The
    ts/L >= 0.002 applicability limit concerns the head's specified thickness,
    see ``thin_head_scope``."""
    _pos(P=P, D=D, S=S), _eff(E)
    K = ellipsoidal_K(ar)
    den = 2 * S * E - 0.2 * P
    if den <= 0:
        raise OutOfScope("2SE - 0.2P <= 0")
    return P * D * K / den


def head_crown_radius(kind, D, ar=2.0, L=None):
    """Inside crown radius used for the ts/L limit: torispherical L; for an
    ellipsoidal head the exact crown radius a^2/b = D*ar/2 (larger than the
    0.9D equivalent for 2:1 heads, so the limit is applied conservatively)."""
    if kind == "torispherical":
        return L
    if kind == "ellipsoidal":
        return D * ar / 2.0
    return None


def thin_head_scope(ts, L):
    """Formed-head rules apply for ts/L >= 0.002 (ts = specified minimum
    thickness after forming); thinner heads need Appendix 1-4(f)."""
    if L and ts / L < 0.002:
        raise OutOfScope(f"ts/L = {ts / L:.5f} < 0.002: Appendix 1-4(f) applies (not implemented)")


def ellipsoidal_mawp(t, D, S, E, ar=2.0):
    """P = 2SEt/(KD + 0.2t)."""
    _pos(t=t, D=D, S=S), _eff(E)
    return 2 * S * E * t / (ellipsoidal_K(ar) * D + 0.2 * t)


def torispherical_M(L, r):
    """Appendix 1-4(d): M = (3 + sqrt(L/r))/4, L/r <= 16 2/3."""
    _pos(L=L, r=r)
    if L / r > 50.0 / 3.0 + 1e-9:
        raise OutOfScope(f"L/r = {L / r:.3f} > 16 2/3")
    return 0.25 * (3.0 + math.sqrt(L / r))


def torispherical_t(P, L, r, S, E):
    """Appendix 1-4(d): t = PLM/(2SE - 0.2P)."""
    _pos(P=P, L=L, r=r, S=S), _eff(E)
    den = 2 * S * E - 0.2 * P
    if den <= 0:
        raise OutOfScope("2SE - 0.2P <= 0")
    return P * L * torispherical_M(L, r) / den


def torispherical_mawp(t, L, r, S, E):
    """P = 2SEt/(LM + 0.2t)."""
    _pos(t=t, L=L, r=r, S=S), _eff(E)
    return 2 * S * E * t / (L * torispherical_M(L, r) + 0.2 * t)


def torispherical_geometry_issues(L, r, Do_skirt, t):
    """Head geometry rules (crown radius <= skirt OD; knuckle >= 6 % skirt OD
    and >= 3t). Returns a list of violated conditions (empty = acceptable)."""
    issues = []
    if L > Do_skirt + 1e-9:
        issues.append(f"crown radius L = {L:.1f} mm exceeds skirt OD {Do_skirt:.1f} mm")
    if r < 0.06 * Do_skirt - 1e-9:
        issues.append(f"knuckle radius r = {r:.1f} mm < 6 % of skirt OD = {0.06 * Do_skirt:.1f} mm")
    if r < 3 * t - 1e-9:
        issues.append(f"knuckle radius r = {r:.1f} mm < 3t = {3 * t:.1f} mm")
    return issues


def hemispherical_t(P, L, S, E):
    """UG-32 hemispherical: t = PL/(2SE - 0.2P), P <= 0.665SE, t <= 0.356L."""
    _pos(P=P, L=L, S=S), _eff(E)
    if P > 0.665 * S * E:
        raise OutOfScope("P > 0.665SE: Appendix 1-3 applies (not implemented)")
    t = P * L / (2 * S * E - 0.2 * P)
    if t > 0.356 * L:
        raise OutOfScope("t > 0.356L: Appendix 1-3 applies (not implemented)")
    return t


def hemispherical_mawp(t, L, S, E):
    """P = 2SEt/(L + 0.2t)."""
    _pos(t=t, L=L, S=S), _eff(E)
    return 2 * S * E * t / (L + 0.2 * t)


# --- opening reinforcement, UG-37(c) / Fig. UG-37.1 / UG-40 --------------------

def area_replacement(*, d, t, tr, tn, trn, Sv, Sn, Sp=None, te=0.0, Dp=0.0, F=1.0, E1=1.0,
                     leg41=0.0, leg42=0.0, leg43=0.0, h=0.0, ti=0.0, inserted=True):
    """Area replacement for one opening; all thicknesses corroded.

    Returns every intermediate the report prints. Pad thickness and diameter
    beyond the UG-40 limits are not counted. Weld legs of 0 mean "not
    counted" (conservative when weld sizes are unknown)."""
    fr2 = min(Sn / Sv, 1.0)
    fr1 = fr2 if inserted else 1.0
    pad = te > 0 and Dp > 0
    fr4 = min((Sp if Sp is not None else Sv) / Sv, 1.0) if pad else 1.0
    fr3 = min(fr2, fr4) if pad else fr2
    Rn = d / 2.0
    lim_par = max(d, Rn + tn + t)
    lim_nor = min(2.5 * t, 2.5 * tn + te)
    te_eff = min(te, lim_nor) if pad else 0.0
    Dp_eff = min(Dp, 2.0 * lim_par) if pad else 0.0
    A = d * tr * F + 2.0 * tn * tr * F * (1.0 - fr1)
    ex = E1 * t - F * tr
    A1 = max(d * ex - 2.0 * tn * ex * (1.0 - fr1), 2.0 * (t + tn) * ex - 2.0 * tn * ex * (1.0 - fr1), 0.0)
    sur = max(tn - trn, 0.0)
    if pad:
        A2 = min(5.0 * sur * fr2 * t, 2.0 * sur * (2.5 * tn + te_eff) * fr2)
    else:
        A2 = min(5.0 * sur * fr2 * t, 5.0 * sur * fr2 * tn)
    A3 = min(5.0 * t * ti * fr2, 5.0 * ti * ti * fr2, 2.0 * h * ti * fr2) if h > 0 and ti > 0 else 0.0
    A41 = leg41 ** 2 * (fr3 if pad else fr2)
    A42 = leg42 ** 2 * fr4 if pad else 0.0
    A43 = leg43 ** 2 * fr2 if h > 0 else 0.0
    A5 = max(Dp_eff - d - 2.0 * tn, 0.0) * te_eff * fr4 if pad else 0.0
    total = A1 + A2 + A3 + A41 + A42 + A43 + A5
    return {"fr1": fr1, "fr2": fr2, "fr3": fr3, "fr4": fr4, "limit_parallel": lim_par,
            "limit_normal": lim_nor, "te_eff": te_eff, "Dp_eff": Dp_eff, "excess_shell": ex,
            "surplus_nozzle": sur, "A": A, "A1": A1, "A2": A2, "A3": A3, "A41": A41, "A42": A42,
            "A43": A43, "A5": A5, "A_avail": total, "adequate": total >= A - 1e-9}


# --- plate undertolerance, UG-16(c) -------------------------------------------

def plate_undertolerance_deduction(t_nominal, undertolerance):
    """UG-16(c): an undertolerance not exceeding the smaller of 0.25 mm or 6 %
    of the ordered thickness may be ignored; a larger one is deducted."""
    if undertolerance is None:
        return 0.0, "undertolerance not stated: taken as 0 (needs review)"
    limit = min(0.25, 0.06 * t_nominal)
    if undertolerance <= limit + 1e-12:
        return 0.0, f"undertolerance {undertolerance:g} mm <= min(0.25 mm, 6 %) = {limit:.3f} mm: ignored"
    return undertolerance, f"undertolerance {undertolerance:g} mm > {limit:.3f} mm: deducted"
