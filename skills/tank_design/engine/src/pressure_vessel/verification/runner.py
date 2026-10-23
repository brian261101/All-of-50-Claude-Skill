"""Verification runner: independent re-computation of the actual results,
benchmark suites, and the PV Elite comparison harness.

A discrepancy stops release (gate) and is reported; nothing is adjusted to
make results agree.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from ..codes.api_650.design import one_foot_td, one_foot_tt
from ..codes.asme_viii_1 import formulas as F
from ..codes.asme_viii_1.context import hydrostatic
from ..geometry import profiles as pf
from ..paths import DATA_DIR
from ..status import Status
from . import independent as I

PSI = 0.006894757293168361
IN = 25.4


def _close(a, b, rel=1e-6, abs_=1e-9):
    return a is not None and b is not None and abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


class _Log:
    def __init__(self):
        self.items = []

    def check(self, group, cid, quantity, engine, independent, rel=1e-6, note="", method=""):
        ok = _close(engine, independent, rel)
        self.items.append({"group": group, "id": cid, "quantity": quantity, "engine": engine,
                           "independent": independent, "rel_tol": rel, "ok": ok, "method": method, "note": note})
        return ok


def _tv(rec, sym):
    for grp in ("results", "intermediates", "inputs"):
        for tv in rec[grp]:
            if tv["symbol"] == sym:
                return tv["value"]
    return None


def verify_results(results: dict, geometry: dict | None, log: _Log):
    """Re-compute the engine's own results with independent formulations."""
    for r in results["records"]:
        cid = r["calc_id"]
        if cid.startswith("SH-") and not cid.endswith("MAWP") and _tv(r, "t_circ") is not None:
            P, R, S = _tv(r, "P"), _tv(r, "R"), _tv(r, "S")
            El, Ec = _tv(r, "E_long"), _tv(r, "E_circ")
            log.check("shell", cid, "t_circ", _tv(r, "t_circ"), I.shell_circ_by_stress(P, R, S, El), 1e-7,
                      method="bisection on P(R+0.6t)/(Et) = S")
            log.check("shell", cid, "t_circ", _tv(r, "t_circ"), I.shell_circ_outside_form(P, R, S, El), 1e-7,
                      method="Appendix 1-1 outside-radius form")
            log.check("shell", cid, "t_long", _tv(r, "t_long"), I.shell_long_by_stress(P, R, S, Ec), 1e-7,
                      method="bisection on P(R-0.4t)/(2Et) = S")
            log.check("shell", cid, "t_long", _tv(r, "t_long"), I.shell_long_outside_form(P, R, S, Ec), 1e-7,
                      method="Appendix 1-1 outside-radius form (longitudinal)")
        if cid.startswith("SH-") and cid.endswith("-MAWP") and _tv(r, "P_circ") is not None:
            base = next(x for x in results["records"] if x["calc_id"] == cid[:-5])
            S, El = _tv(base, "S"), _tv(base, "E_long")
            t, R = _tv(r, "t"), _tv(r, "R")
            sig = _tv(r, "P_circ") * (R + 0.6 * t) / (El * t)
            log.check("shell", cid, "stress at MAWP", sig, S, 1e-9, method="stress equation evaluated at MAWP")
        if cid.startswith("HD-") and cid.count("-") == 1 and _tv(r, "t_req") is not None:
            P, S, E, Dc = _tv(r, "P"), _tv(r, "S"), _tv(r, "E"), _tv(r, "D_c")
            if _tv(r, "K") is not None:
                K = _tv(r, "K")
                ar = math.sqrt(6 * K - 2)
                ind = I.ellipsoidal_outside_form(P, Dc, S, E, ar)
                m = "Appendix 1-4(c) outside-diameter form"
            elif _tv(r, "M") is not None:
                ind = I.torispherical_outside_form(P, _tv(r, "L"), _tv(r, "r"), S, E)
                m = "Appendix 1-4(d) outside-radius form"
            else:
                ind = I.hemispherical_outside_form(P, _tv(r, "L"), S, E)
                m = "outside-radius form (sphere)"
            log.check("head", cid, "t_req", _tv(r, "t_req"), ind, 1e-7, method=m)
        if cid.endswith("-UG37") and _tv(r, "A") is not None:
            ia = I.area_geometric(_tv(r, "d"), _tv(r, "t"), _tv(r, "tr"), _tv(r, "tn"), _tv(r, "trn"),
                                  _tv(r, "Sv"), _tv(r, "Sn"), _tv(r, "Sp"), _tv(r, "te") or 0.0,
                                  _tv(r, "Dp") or 0.0, inserted=_tv(r, "attachment") == "set_in")
            for q in ("A", "A1", "A2", "A5"):
                log.check("nozzle", cid, q, _tv(r, q), ia[q], 1e-9, method="reinforcement-zone derivation")
        if cid == "MAWP" and _tv(r, "MAWP") is not None:
            parts = [tv["value"] for tv in r["intermediates"] if tv["symbol"].startswith("MAWP[")]
            log.check("vessel", cid, "MAWP", _tv(r, "MAWP"), min(parts), 1e-12, method="minimum of part MAWPs")
        if cid == "TEST-P" and _tv(r, "P_test_top") is not None:
            f = 1.3 if "hydro" in r["title"].lower() else 1.1
            log.check("vessel", cid, "P_test_top", _tv(r, "P_test_top"), f * _tv(r, "P_basis") * _tv(r, "LSR"), 1e-12,
                      method="hand formula")
    if geometry:
        a = geometry["vessel"]["inside_diameter"] / 2
        for c in geometry["components"]:
            if c["kind"] == "shell_course" and not c["params"].get("openings"):
                t, L = c["params"]["thickness"], c["params"]["length"]
                log.check("geometry", c["tag"], "volume", c["volume_mm3"], math.pi * ((a + t) ** 2 - a * a) * L, 1e-9,
                          method="ring volume")
        log.check("geometry", "capacity", "internal volume", geometry["vessel"]["internal_volume_mm3"],
                  _capacity_closed_form(geometry), 1e-5, method="closed-form head volumes + cylinder")


def _capacity_closed_form(geometry):
    a = geometry["vessel"]["inside_diameter"] / 2
    total = math.pi * a * a * sum(c["params"]["length"] for c in geometry["components"] if c["kind"] == "shell_course")
    for c in geometry["components"]:
        if c["kind"] != "head":
            continue
        p = c["params"]
        if p["type"] == "ellipsoidal":
            total += I.ellipsoid_half(a, a / p["aspect_ratio"])
        elif p["type"] == "hemispherical":
            total += 2 / 3 * math.pi * a ** 3
        else:
            total += I.torispherical_solid(a, p["crown_radius"], p["knuckle_radius"])
        total += math.pi * a * a * p["straight_flange"]
    return total


# --- benchmark suites ---------------------------------------------------------------

def _call(fn, i):
    if fn == "area_replacement":
        return F.area_replacement(**i)
    if fn == "hydro":
        return i["factor"] * i["mawp"] * i["lsr"]
    if fn == "api650_td":
        return one_foot_td(i["D_m"], i["H_m"], i["G"], i["Sd"], i["CA"])
    if fn == "api650_tt":
        return one_foot_tt(i["D_m"], i["H_m"], i["St"])
    if fn == "hydrostatic":
        return hydrostatic(i["height_mm"], i["density_kg_m3"])
    if fn == "head_metal_volume":
        return pf.head_metal(pf.HeadProfile(i["kind"], i["a"]), i["t"], i["sf"])[0]
    if fn == "head_capacity":
        return pf.head_capacity(pf.HeadProfile(i["kind"], i["a"], i.get("ar", 2.0)), i["sf"])
    return getattr(F, fn)(**i)


def run_benchmarks(log: _Log, path: Path | None = None):
    bdir = Path(path or DATA_DIR / "benchmarks")
    hand = json.loads((bdir / "hand_calcs_si.json").read_text(encoding="utf-8"))
    for c in hand["cases"]:
        out = _call(c["function"], c["inputs"])
        for k, exp in c["expected"].items():
            got = out[k] if isinstance(out, dict) else out
            log.check("benchmark:hand", c["id"], f"{c['title']} [{k}]", got, exp, c["tolerance_rel"],
                      method=c["function"], note=c["arithmetic"][:160])
    lz = json.loads((bdir / "laela_zorana_us_units.json").read_text(encoding="utf-8"))
    for c in lz["cases"]:
        i = c["inputs_us"]
        fn = c["function"]
        if fn == "shell_t_circ":
            got = F.shell_t_circ(i["P_psi"] * PSI, i["R_in"] * IN, i["S_psi"] * PSI, i["E"]) / IN
        elif fn == "ellipsoidal_t":
            got = F.ellipsoidal_t(i["P_psi"] * PSI, i["D_in"] * IN, i["S_psi"] * PSI, i["E"]) / IN
        elif fn == "shell_mawp_circ":
            got = F.shell_mawp_circ(i["t_in"] * IN, i["R_in"] * IN, i["S_psi"] * PSI, i["E"]) / PSI
        elif fn == "torispherical_t":
            got = F.torispherical_t(i["P_psi"] * PSI, i["L_in"] * IN, i["r_in"] * IN, i["S_psi"] * PSI, i["E"]) / IN
        else:   # area_A_us with the reference library's convention, plus ours for the record
            P, R, S, Sn = i["P_psi"] * PSI, i["R_in"] * IN, i["S_psi"] * PSI, i["Sn_psi"] * PSI
            CA, tw, OD = i["CA_in"] * IN, i["tw_in"] * IN, i["OD_in"] * IN
            tr = F.shell_t_circ(P, R, S, 1.0)
            tn_ref = tw * (1 - i["mill_tol"]) - CA
            d_ref = OD - 2 * tn_ref
            trn = F.shell_t_circ(P, d_ref / 2, Sn, 1.0)
            got = F.area_replacement(d=d_ref, t=0.5 * IN, tr=tr, tn=tn_ref, trn=trn, Sv=S, Sn=Sn)["A"] / IN ** 2
            tn = tw - CA
            d = OD - 2 * tw + 2 * CA
            ours = F.area_replacement(d=d, t=0.5 * IN, tr=tr, tn=tn, trn=F.shell_t_circ(P, d / 2, Sn, 1.0),
                                      Sv=S, Sn=Sn)["A"] / IN ** 2
            log.items.append({"group": "benchmark:cross-implementation", "id": c["id"] + "-default-convention",
                              "quantity": "A with UG-16(d) convention (in2)", "engine": ours,
                              "independent": c["expected_us"]["value_in2"], "rel_tol": None, "ok": True,
                              "method": "information: known method difference", "note": c["method_difference"]})
        exp = next(iter(c["expected_us"].values()))
        log.check("benchmark:cross-implementation", c["id"], c["title"], got, exp, c["tolerance_rel"],
                  method=fn, note=c["method_difference"] or lz["source"][:120])


# --- PV Elite comparison --------------------------------------------------------------

def compare_pv_elite(results: dict, csv_path: Path | None, log: _Log) -> dict:
    """CSV columns: calc_id, symbol, value, unit, rel_tolerance. Values must be
    in the engine's units (mm, MPa, mm2). Returns a status block."""
    if not csv_path or not Path(csv_path).is_file():
        return {"status": "NOT_AVAILABLE", "note": "no PV Elite results supplied; harness ready "
                                                   "(examples/pv_elite_results_template.csv)"}
    recs = {r["calc_id"]: r for r in results["records"]}
    n = bad = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row.get("calc_id") or row["calc_id"].lstrip().startswith("#"):
                continue
            r = recs.get(row["calc_id"])
            eng = _tv(r, row["symbol"]) if r else None
            ok = log.check("pv_elite", row["calc_id"], row["symbol"], eng, float(row["value"]),
                           float(row.get("rel_tolerance") or 0.005), method="PV Elite (user-supplied)")
            n += 1
            bad += 0 if ok else 1
    return {"status": "COMPARED", "values": n, "deviations": bad, "file": str(csv_path)}


def run_verification(results: dict, geometry: dict | None, pv_elite_csv=None) -> dict:
    log = _Log()
    verify_results(results, geometry, log)
    run_benchmarks(log)
    pve = compare_pv_elite(results, pv_elite_csv, log)
    failed = [i for i in log.items if not i["ok"]]
    return {"schema": "pv-design/verification@1", "results_hash": results["results_hash"],
            "input_hash": results["input_hash"], "passed": not failed, "n_checks": len(log.items),
            "n_failed": len(failed), "items": log.items, "discrepancies": failed, "pv_elite": pve,
            "scope_note": "Verifies the implementation (arithmetic, algebra, geometry) against independent "
                          "formulations and benchmarks. It does not verify the Code formulas themselves; "
                          "that needs the licensed Code (reference register)."}


def verification_markdown(v: dict) -> str:
    lines = [f"# Verification report", "",
             f"- Result set: `{v['results_hash'][:16]}` (input `{v['input_hash'][:16]}`)",
             f"- Checks: {v['n_checks']}, failed: {v['n_failed']} -> **{'PASSED' if v['passed'] else 'DISCREPANCIES'}**",
             f"- PV Elite comparison: {v['pv_elite']['status']} — {v['pv_elite'].get('note', '')}",
             f"- Scope: {v['scope_note']}", "",
             "| Group | Id | Quantity | Engine | Independent | Rel. tol | OK | Method |", "|---|---|---|---|---|---|---|---|"]
    for i in v["items"]:
        e = i["engine"]
        x = i["independent"]
        fmt = (lambda z: f"{z:.6g}" if isinstance(z, (int, float)) else str(z))
        lines.append(f"| {i['group']} | {i['id']} | {i['quantity']} | {fmt(e)} | {fmt(x)} | "
                     f"{i['rel_tol'] if i['rel_tol'] is not None else 'info'} | {'yes' if i['ok'] else '**NO**'} | {i['method']} |")
    notes = [i for i in v["items"] if i.get("note") and "method" in str(i.get("method")) and "difference" in str(i.get("note"))]
    if notes:
        lines += ["", "## Known method differences (reported, not adjusted)", ""]
        lines += [f"- **{i['id']}**: {i['note']}" for i in notes]
    return "\n".join(lines) + "\n"
