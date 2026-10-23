"""Build data/materials/material_db.json (REPRESENTATIVE_EXAMPLE records).

Source: data/materials_sec_ii_d_representative.csv of
LaelaZorana/asme-viii-pressure-vessel (MIT), whose author states the values are
"representative of Section II-D Table 1A" and must be verified. The values are
converted psi -> MPa and degF -> degC here; nothing else is changed. The first
tabulated point (100 degF) stands for the Table 1A column "-20 to 100 degF", so a
point at -20 degF (-28.9 degC) with the same stress is added and noted.

These records are for demonstrations and tests only. They can never make a
check PASS: their status is REPRESENTATIVE_EXAMPLE.

    python -I tools/build_material_db.py vendor/asme-viii-pressure-vessel data/materials/material_db.json
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PSI_TO_MPA = 0.006894757293168361

# Spec metadata (product form, minimum tensile/yield from the material
# specification as commonly published). Representative, unverified.
META = {
    "SA-516-70": ("SA-516/SA-516M", "70", "plate", 485, 260, 7850),
    "SA-515-70": ("SA-515/SA-515M", "70", "plate", 485, 260, 7850),
    "SA-285-C": ("SA-285/SA-285M", "C", "plate", 380, 205, 7850),
    "SA-106-B": ("SA-106/SA-106M", "B", "seamless pipe", 415, 240, 7850),
    "SA-53-B": ("SA-53/SA-53M", "B", "pipe", 415, 240, 7850),
    "SA-105": ("SA-105/SA-105M", "-", "forging", 485, 250, 7850),
    "SA-350-LF2": ("SA-350/SA-350M", "LF2", "forging", 485, 250, 7850),
    "SA-240-304": ("SA-240/SA-240M", "304", "plate", 515, 205, 7900),
    "SA-240-316": ("SA-240/SA-240M", "316", "plate", 515, 205, 7950),
    "SA-182-F304": ("SA-182/SA-182M", "F304", "forging", 515, 205, 7900),
}


def git_commit(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(vendor: Path, out: Path) -> int:
    rows = defaultdict(list)
    with open(vendor / "data" / "materials_sec_ii_d_representative.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            rows[r["material"].strip()].append((float(r["temperature_f"]), float(r["stress_psi"])))
    commit = git_commit(vendor)
    records = []
    for name, pts in sorted(rows.items()):
        spec, grade, form, fu, fy, rho = META[name]
        pts.sort()
        temps_c = [round((-20.0 - 32.0) * 5 / 9, 1)] + [round((t - 32.0) * 5 / 9, 1) for t, _ in pts]
        stress = [round(pts[0][1] * PSI_TO_MPA, 1)] + [round(s * PSI_TO_MPA, 1) for _, s in pts]
        records.append({
            "id": f"{name}_{form.split()[-1].upper()}_REP",
            "spec": spec, "grade": grade, "product_form": form,
            "allowable_stress": {"temperature_degC": temps_c, "S_MPa": stress},
            "interpolation": "linear between tabulated temperatures",
            "temperature_limits_degC": {"min": temps_c[0], "max": temps_c[-1]},
            "min_tensile_MPa": fu, "min_yield_MPa": fy, "density_kg_m3": rho,
            "source_document": ("LaelaZorana/asme-viii-pressure-vessel data/materials_sec_ii_d_"
                                f"representative.csv @ {commit[:12]} (MIT), converted psi->MPa, degF->degC"),
            "table_reference": "ASME BPVC II-D Table 1A (representative only, NOT checked)",
            "edition": "2023 basis as claimed by the source",
            "verified_on": None, "verified_by": None,
            "verification_status": "REPRESENTATIVE_EXAMPLE",
            "notes": ["first point -28.9 degC repeats the 37.8 degC value (Table 1A column '-20 to 100 F')",
                      "tensile/yield/density are representative values, not from a licensed source"],
        })
    db = {"db_name": "pv-design material database", "db_version": "0.1.0-representative",
          "status_note": "All records REPRESENTATIVE_EXAMPLE. Replace with VERIFIED_OFFICIAL or "
                         "USER_SUPPLIED_VERIFIED records before any design release.",
          "records": records}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(db, indent=1), encoding="utf-8")
    print(f"wrote {len(records)} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
