# FreeCAD through the MCP — procedure and pitfalls

Verified 2026-10-23 on this machine: FreeCAD 1.1.4 (Python 3.11), FreeCAD MCP
addon 0.1.25 (`uvx freecad-mcp`, configured in the Claude desktop config), RPC
port 9875. Probe script: `pv_design/src/pressure_vessel/cad/freecad_probe.py`
(Part, Sketcher, PartDesign Body, Spreadsheet expressions, TechDraw page,
`TechDraw.projectEx`, STEP export/re-import, TechDraw DXF/PDF export, FCStd save
— all passed).

## Tools that exist (use no others)
`get_rpc_status`, `execute_code`, `execute_code_async`, `get_async_status`,
`execute_code_headless`, `create_document`, `create_object`, `edit_object`,
`delete_object`, `get_object`, `get_objects`, `get_view`, `list_documents`,
`reload_document`, `get_parts_list`, `insert_part_from_library`,
`run_fem_analysis`. The pipeline needs only `get_rpc_status` and `execute_code`.

## Procedure
1. `get_rpc_status`. If it errors, FreeCAD is not running: start
   `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` (PowerShell
   `Start-Process (Join-Path $env:ProgramFiles 'FreeCAD 1.1\bin\freecad.exe')`),
   wait ~30 s, retry.
2. `python pv_design/pv.py cad <package>` prints three blocks. Send each with
   `execute_code` (`include_screenshot: false` except to show the model):
   - build (≈ 3–5 s): solids, metadata, Params spreadsheet, checks, FCStd, STEP → `cad_check.json`
   - TechDraw create (≈ 60–100 s): page + 4 views (CoarseView) → `techdraw_check.json`
   - TechDraw export (≈ 35 s): DXF, then PDF (page window opened first)
3. `python pv_design/pv.py cad-status <package>` — the only source of truth.

## Pitfalls seen here
- The MCP reply "Request timed out" arrives after about a minute even with a
  larger `timeout`; FreeCAD keeps working. Check the files, never assume.
- **Exact hidden-line removal stalls** on the revolved B-spline head surfaces
  (`TechDraw.projectEx` ran > 15 min; OCP `HLRBRep_Algo` likewise). Use
  polygonal HLR: TechDraw `CoarseView = True`; the drawing stage uses OCP
  `HLRBRep_PolyAlgo` on the STEP (≈ 1 s/view). If FreeCAD hangs in such a call,
  stop the process (the FCStd/STEP were saved before projections).
- `TechDrawGui.exportPageAsPdf` writes nothing unless the page is open in its
  GUI window (`page.ViewObject.doubleClicked()` first).
- Removing a TechDraw page removes its views: collect names, then re-check
  each object exists before removing it.
- TechDraw templates carry sample values (names, "ISO 2768-m", materials):
  every field is overwritten or blanked by the script; approval fields stay blank.
- `freecadcmd` runs a script with `__name__` ≠ "__main__": the build script
  also starts on `PV_PACKAGE` in the environment (headless route).
- Set `doc.UnitSystem = "Metric small parts & CNC (mm, mm/min)"` so long
  lengths display in mm.
- `doc.save()` over an existing file leaves `*.FCBak` (excluded from the manifest).

## What the build checks (cad_check.json)
all components built · solids valid · OCC volume vs analytic volume (≤ 2e-3) ·
overall height = design · grade at z = 0 · plan envelope ≤ design · nozzle
orientation and elevation (flange centre of mass on the design axis) · no
pairwise overlap > 1 mm³ · STEP re-import solid count and volume (≤ 1e-4).

## Model conventions
Origin on the vessel axis at grade (underside of base plates), +Z up; plan
angle clockwise from +Y = 0° (north) seen from above; nozzle elevations from
the bottom tangent line; projection = outside surface to flange face. Objects
carry `Tag, Component, Material, MaterialStatus, CalcRef, Description,
AnalyticVolume_mm3, PressurePart` (group "PV_Design"); groups by BOM group;
`Params` spreadsheet holds the hashes and key dimensions. The model is
regenerated from `design_geometry.json` (not a feature-tree parametric model).
