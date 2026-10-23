# pv_design — traceable pressure vessel / tank design

Library, CLI and Claude Code skill `tank-vessel-design` (`.claude/skills/tank_design`, command `/tank_design`)
that take a unit-checked design input to:

1. validation with a question list (nothing safety-relevant is defaulted),
2. ASME BPVC VIII-1 calculations (shell, heads, nozzles UG-45/UG-37 with
   opening MAWP, external pressure with user chart data, MAWP UG-98, test
   pressure, weights/volume/CG, support and lug loads) or API 650 shell
   courses (1-foot method), each with inputs, formula, substitution, code
   reference, intermediates, result and a five-state status,
3. independent verification (different formulations + hand/cross benchmarks +
   PV Elite comparison harness) and a release gate,
4. a calculation report PDF/HTML,
5. a FreeCAD model (FCStd + STEP) built through the FreeCAD MCP or freecadcmd,
6. dimensioned 2D GA and fabrication sheets (DXF + PDF) and a TechDraw page,
7. a BOM (CSV/XLSX/JSON), cross-artifact consistency checks and a manifest.

> **Engineering-review tool. Results are PRELIMINARY and NOT FOR FABRICATION**
> until the material data and the code references are verified against the
> licensed editions and a qualified engineer has reviewed and signed the
> package. The software never sets a stage above `CALCULATION_VERIFIED`.

## Quick start

```bash
python pv_design/pv.py validate pv_design/examples/PV-DEMO-001/vessel_input.yaml
python pv_design/pv.py all pv_design/examples/PV-DEMO-001/vessel_input.yaml --out pv_design/output/PV-DEMO-001 --headless
python -m unittest discover -s pv_design/tests -t pv_design
```

Without `--headless`, `all` stops after printing the three FreeCAD MCP code
blocks (build, TechDraw page, TechDraw export); send them with the MCP tool
`execute_code`, then run `drawings` and `package`. See
`.claude/skills/tank_design/references/mcp-freecad-guide.md`.

Commands: `validate`, `calc`, `report`, `cad [--headless]`, `cad-status`,
`drawings`, `bom`, `package`, `handoff`, `resume`, `all` (`python pv_design/pv.py -h`).

## Web calculator and handoff

`web/` builds a static page (`python pv_design/web/build.py` → `web/dist/`, published at
https://brian261101.github.io/tank-vessel-design-web/) that runs this engine in the browser with
Pyodide: the design request form, validation, calculation, verification, release gate and a
calculation PDF (pdfmake), plus a handoff zip (`HANDOFF.json`, `README_FOR_CLAUDE.md`,
`00_INPUT/`, `01_CALCULATION/`). Nothing is reimplemented in JavaScript; the bundle is the files
listed by `handoff.engine_files()` with their fingerprint.

`pv.py resume <zip> --out <dir>` unpacks a handoff, checks the file hashes, recomputes locally and
compares every result (floats within 1e-9 relative, because WebAssembly and the local C library can
round the last digit differently), then the package continues with `report`, `bom`, `cad`,
`drawings`, `package`. `pv.py handoff <dir> --zip <file>` makes the same zip from a local package.

## Requirements

Python ≥ 3.11. Calculation core: standard library only. Optional: PyYAML
(YAML input), PyMuPDF (PDF), openpyxl (XLSX), ezdxf + cadquery-ocp (drawings),
FreeCAD 1.1 (model). All were present on the development machine; nothing was
installed for this project.

## Statuses

`PASS` (criterion met on verified data) · `FAIL` · `NOT_EVALUATED` (data
missing) · `OUT_OF_SCOPE` (beyond the implemented rule) ·
`NEEDS_ENGINEERING_REVIEW` (met on unverified data / indicative method) ·
`COMPUTED` (value without criterion). The bundled material data are
REPRESENTATIVE_EXAMPLE and every code reference ships UNVERIFIED, so the demo
reaches `NEEDS_ENGINEERING_REVIEW` at best — by design.

## Demo packages (generated 2026-10-23)

| Package | Content | Stage |
|---|---|---|
| `output/PV-DEMO-001` | V-101 vertical air receiver, ID 1200, T/T 3000, 1.0 MPa(g) / 80 °C, 2:1 heads, 6 nozzles, 4 legs, 2 lugs: report (53 p.), FCStd/STEP (MCP), TechDraw page, GA + fabrication DXF/PDF, BOM, QA | PRELIMINARY |
| `output/TK-DEMO-001` | T-201 API 650 water tank D 10 m: report, QA (no CAD in v0.1) | PRELIMINARY |

Both use invented demonstration data and must not be used for anything real.

## Layout

```
pv.py                     CLI launcher
src/pressure_vessel/      library (see docs/ARCHITECTURE.md)
data/                     code reference register, material DB, pipe table, benchmarks
examples/                 demo inputs, PV Elite CSV template
tests/                    unittest suite (84 tests, incl. end-to-end with freecadcmd)
tools/                    audit and data-build tools
docs/                     SOURCE_AUDIT, ARCHITECTURE, ACCEPTANCE_TESTS, KNOWN_LIMITATIONS
web/                      web calculator source (build.py, calc.js); dist/ is git-ignored
output/<PROJECT>/         generated packages
vendor/                   audited third-party repos (git-ignored, unmodified)
```

Licences and reused material: `NOTICE.md`.
