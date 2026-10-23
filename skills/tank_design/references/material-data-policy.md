# Material data policy

## Statuses
| Status | Meaning | Can give PASS? |
|---|---|---|
| VERIFIED_OFFICIAL | checked against the licensed source (II-D edition, table, line) | yes |
| USER_SUPPLIED_VERIFIED | supplied and signed off by the user (verified_by, verified_on, source) | yes |
| USER_SUPPLIED_UNVERIFIED | supplied without sign-off | no → NEEDS_ENGINEERING_REVIEW |
| REPRESENTATIVE_EXAMPLE | demo/teaching values (the bundled database) | no |
| UNVERIFIED | unknown provenance | no |

A record claiming a release-eligible status without `verified_by`,
`verified_on` and `source_document` is rejected on load.

## Bundled database
`pv_design/data/materials/material_db.json` (v0.1.0-representative): ten
grades converted from the MIT-licensed representative table of
LaelaZorana/asme-viii-pressure-vessel (psi → MPa, °F → °C) by
`pv_design/tools/build_material_db.py`. **All REPRESENTATIVE_EXAMPLE.** Data
from ASME-PVDE (GPL, transcriptions of II-D) is not imported.

## Adding a verified record (in the project input)
```yaml
materials:
  PLATE:
    record:
      id: SA-516-70_PLATE_2023
      spec: SA-516/SA-516M
      grade: "70"
      product_form: plate
      allowable_stress: {temperature_degC: [-29, 40, 100, 150], S_MPa: [..., ..., ..., ...]}
      interpolation: linear between tabulated temperatures   # only if the edition permits
      min_tensile_MPa: ...
      min_yield_MPa: ...
      density_kg_m3: ...
      source_document: "ASME BPVC II-D 2023 (metric) Table 1A, page/line ..."
      table_reference: "II-D Table 1A"
      edition: "2023"
      verified_by: "<name>"
      verified_on: "YYYY-MM-DD"
      verification_status: USER_SUPPLIED_VERIFIED
```

## Lookup rules
- exact tabulated temperature → value; between points → linear only if the
  record states it; outside the range → error (no extrapolation)
- the first point of II-D style tables covers "−29 to 40 °C"; store it as a
  point at the lower limit to avoid any implicit extension
- allowable stress at design and test temperature both appear in MAT-* records

## Other data held to the same rule
Pipe dimensions (`data/pipe/pipe_dimensions.json`, UNVERIFIED), flange ratings
and dimensions (input, with `rating_status` / `dimensions_status`), external
pressure chart readings (`external_pressure_data.*.status`), API 650 constants
(`api650_rules.status`), assessments (`assessments.*.status`).
