# Architecture

## Data flow

```
input YAML/JSON ──► inputs.schema (units, ranges, no defaults) ──► VesselInput
        │                                   └─► ValidationReport (errors / warnings / questions)
        ▼
codes.asme_viii_1.design.run ──► CalcRecords + selected thicknesses ──► geometry.vessel.build_geometry
   materials, joints, shells, heads ─┘          (single dimensional source: design_geometry.json)
   nozzles, external, MAWP, test, weights, supports, lugs, loads, MDMT/PWHT/fatigue, assessments
        ▼
verification.runner (independent formulations, benchmarks, PV Elite CSV) ──► release gate
        ▼
reporting (HTML ► PDF)   bom (CSV/XLSX/JSON)   cad (FreeCAD: MCP or freecadcmd) ──► FCStd, STEP, cad_check
                                                         └► TechDraw page (MCP) ──► PDF/DXF
                                               drawings.hlr (OCP polygonal HLR of the STEP)
                                               drawings.ga (ezdxf sheets, DIMENSION entities) ──► DXF/PDF
        ▼
package.consistency (hashes, components, weights, dimensions) ──► package.manifest (+ tests, review file, README)
```

API 650 tanks follow `inputs.tank_schema` → `codes.api_650.design` → report →
consistency/manifest (no geometry/CAD/drawings/BOM in v0.1).

## Modules (`src/pressure_vessel`)

| Module | Role |
|---|---|
| `status.py` | Status, RecordKind, DesignStage, DataStatus; `decide()`, `aggregate()` |
| `units.py` | explicit-unit parsing and conversion (mm, MPa(g), °C, kg, N) |
| `trace.py` | `CalcRecord` / `TraceValue`: the audit trail of every number |
| `references.py` | code reference register + project verification |
| `materials.py` | versioned material records, lookup policy, verification status |
| `pipes.py` | pipe dimensions, derived Table UG-45 values |
| `inputs/` | `schema.py` (vessel@1), `tank_schema.py` (tank@1), `models.py`, `loader.py` |
| `codes/asme_viii_1/` | `formulas.py` (pure functions, limits, area method), `components.py` (MAT, JE, SH, HD), `nozzles.py`, `external.py`, `vessel_checks.py`, `context.py`, `design.py` (orchestration, assessments, gate) |
| `codes/api_650/design.py` | scope gate, 1-foot method, bottom, weights |
| `geometry/` | `profiles.py` (exact head profiles, quadrature, nozzle/hole/pad integrals, flange volumes), `vessel.py` (design geometry, weights, CG) |
| `verification/` | `independent.py` (alternative formulations), `runner.py` (re-computation, benchmarks, PV Elite) |
| `reporting/` | `calc_report.py` (HTML), `pdf.py` (PyMuPDF Story + header/footer + PDF check) |
| `cad/` | `freecad_build.py`, `freecad_techdraw.py` (run inside FreeCAD), `freecad_probe.py`, `adapter.py` (MCP snippets, headless runner, status) |
| `drawings/` | `hlr.py` (OCP hidden-line removal of the STEP), `ga.py` (GA + fabrication sheets, dimension check) |
| `bom/bom.py` | BOM rows, net vs procurement weight, CSV/XLSX |
| `package/` | `pipeline.py`, `consistency.py`, `manifest.py` |
| `cli.py` | command line |

## Design rules encoded

- Records are data (JSON); every cited reference id must exist in the register.
- `finalize()` maps (criterion, data quality) → status; computations never get a status.
- Missing data never becomes a default; it becomes NOT_EVALUATED plus a question.
- The gate: no FAIL, no open mandatory check, all used references verified,
  all materials release-eligible, input USER_CONFIRMED, basis locked,
  verification passed → `CALCULATION_VERIFIED`; otherwise `PRELIMINARY`.
- Geometry is built once from validated input + selected thicknesses; CAD,
  drawings and BOM read it, and consistency checks compare them by hash and value.

## Skill structure

```
.claude/skills/tank_design/
  SKILL.md                 workflow, rules, stop conditions
  references/              code-matrix, calculation-methods, material-data-policy,
                           mcp-freecad-guide, report-requirements
  templates/               vessel-input.yaml, tank-input.yaml, project-config.yaml
  scripts/                 validate_input, run_calculations, generate_report,
                           run_verification, build_package (+ _common)
  tests/                   skill-level tests (scripts run as subprocesses)
```
