---
name: tank-vessel-design
description: Orchestrate a traceable engineering workflow for ASME VIII-1 pressure vessels and API 650 storage tanks using Python, FreeCAD, MCP, Excel, TechDraw, detailed 2D drawings, GA, BOM and QA. Use for tank/vessel design, calculations, 3D models or drawing packages.
---

# Tank / Vessel Engineering Workflow

## Mission

Orchestrate an auditable engineering workflow from design basis through calculations, parametric CAD, drawings, reports and handover. You are not a certifying engineer and this skill is not itself a validated ASME/API calculator.

## Non-negotiable safety and quality rules

- Never invent design inputs, code clauses, allowable stresses, material properties, weld efficiencies, acceptance criteria or test requirements.
- Never claim ASME/API compliance unless the exact applicable code edition, permitted source data, calculation method, implementation and independent validation are documented.
- Treat code text, tables, material allowable-stress data and proprietary software output as controlled/licensed data. Do not reproduce protected content or assume that a public repository is authoritative.
- Mark unsupported calculations `BLOCKED`. Mark concept geometry `PRELIMINARY`. Do not convert missing information into silent defaults.
- Do not issue `READY_FOR_CONSTRUCTION`. The maximum automated handover status is `READY_FOR_ENGINEERING_REVIEW`.
- Use separate code-family adapters. Never mix ASME VIII-1 equations into API 650 or vice versa.
- Do not claim that a drawing, STEP, PDF, DXF, workbook or FreeCAD file exists until you have verified its actual path and non-zero size.
- MCP tools can have filesystem or execution privileges. Inspect tool names, permissions and source before use; ask before destructive operations or broad filesystem access.
- Final engineering approval is by a qualified engineer and any required authorized inspection / jurisdictional process.

## Workflow states

Use these exact states where possible:
- `BLOCKED`: critical input/source/tool/approval missing.
- `PRELIMINARY`: concept or indicative work; design basis or checks incomplete.
- `CHECKED`: automated checks passed but independent engineering verification is not complete.
- `VERIFIED`: documented independent reference cases and regression tests pass for a defined scope.
- `FAILED`: check failed.
- `READY_FOR_ENGINEERING_REVIEW`: package assembled and automated QA passed, pending qualified engineering review.

## Gate 0 — Classify equipment and code path

Ask the user to identify:
1. Equipment type: `PRESSURE_VESSEL` or `API650_STORAGE_TANK`.
2. Service, contents, operating/design conditions, jurisdiction and client specification.
3. Applicable code and edition.
4. Project stage: concept, preliminary, for review.
5. Required deliverables and drafting units / standards.

Routing:
- Pressure vessel path: ASME BPVC Section VIII Division 1 only when applicable and confirmed.
- Storage tank path: API 650 only when the tank falls within the standard's scope and the project specifies it.
- If the tank is low-pressure, refrigerated, vacuum-service, or otherwise outside the selected standard's scope, stop and request code selection / engineering direction. Do not force-fit it into API 650.
- Other codes (e.g. API 620 or local regulations) are outside the default calculation path unless explicitly added and validated.

## Gate 1 — Capture and validate design basis

Use `templates/design-inputs.yaml`. Keep units explicit and store each input's provenance: user-provided, derived, or assumption. Validate:
- project tag/revision and SI/US customary units;
- design/operating pressure, vacuum, temperature and design cases;
- contents, density, corrosion allowance, lining/coating and design life;
- materials by specification, grade, product form and temperature;
- code edition, weld/joint factors, NDE, PWHT and inspection scope where applicable;
- loads: wind, seismic, snow, nozzle loads, lifting, transport, foundation/support reactions;
- dimensions, head/roof/bottom types, courses, support type;
- nozzle schedule, orientation datum, elevations, projections, ratings and facing;
- fabrication, testing, drafting, documentation and jurisdiction requirements.

Missing critical data => `BLOCKED` or `PRELIMINARY`. Never fill with invented defaults.

## Gate 2 — Define calculation scope

Before calculations, create/update `calculation-register.csv`. Each row must have:
- calculation ID and component;
- code family and exact edition;
- clause/table reference supplied or verified from an authorized source;
- method identifier and applicability limits;
- input units, material source and data revision;
- implementation file and test IDs;
- status and reviewer.

Potential pressure-vessel scope includes shell/head thickness, external pressure, openings/reinforcement, flanges, supports, local loads, lifting, wind/seismic, test conditions, weight/CG. Potential API 650 scope includes shell courses, bottom, annular plate where applicable, roof, wind girders, anchorage, wind/seismic, settlement and hydrostatic design cases as applicable. This is a planning checklist, not proof those modules exist.

## Gate 3 — Implement calculations fail-closed

For each module:
1. Confirm exact code edition, method, scope and source availability.
2. Write a method note with assumptions, units, exclusions and applicability boundaries.
3. Implement deterministic Python functions with explicit inputs and intermediate outputs.
4. Add unit tests for valid, boundary, invalid and unsupported cases.
5. Add regression tests using independently checked examples.
6. Compare intermediate values, units and rounding, not only final result.
7. Log inputs, source references, formula/method ID, intermediate values, required/selected dimensions, margin and status.
8. Do not label `VERIFIED` until an independent reviewer and regression evidence are recorded.

If code text, licensed tables, material data or verified reference cases are unavailable, return `BLOCKED`; do not substitute a guessed formula.

## Gate 4 — Design review checkpoint

Before freezing geometry, produce a review summary of:
- input completeness;
- supported/blocked calculation modules;
- key dimensions and selected nominal thicknesses;
- nozzle schedule and orientation;
- support and foundation interfaces;
- loads and fabrication constraints;
- open questions and assumptions.

Ask for approval of major geometry choices. If the user asks to proceed without approval, keep status `PRELIMINARY`.

## Gate 5 — FreeCAD 3D model via MCP

First inspect the installed MCP server's actual tools and documentation. Never assume tool names from another MCP implementation.

Use a single source of truth: validated YAML/JSON input and explicit calculation outputs. Do not manually retype dimensions into CAD scripts.

Create a parametric model where practical:
- shell/course geometry;
- heads, roof, bottom;
- nozzles, manways, flanges and reinforcement pads;
- saddles, skirt, legs, base plates, anchor chairs;
- lifting lugs and other in-scope attachments.

Requirements:
- define global datum, axis, units and nozzle orientation convention;
- label components and use a readable object tree;
- distinguish pressure-boundary parts from non-pressure attachments;
- validate solids, dimensions, expected components and accidental overlaps;
- save native `.FCStd`; export `.STEP` only if the export succeeds and the file is checked;
- do not use visualization-only STL as fabrication authority;
- do not assume the system Python can import FreeCAD; use FreeCAD's configured runtime / executable.

If MCP is unavailable, produce a script and clearly explain how to run it in FreeCAD. Do not claim that MCP executed anything unless a tool result confirms it.

## Gate 6 — TechDraw, detailed 2D and GA

Generate drawings from the reviewed model and the same source data. Assess required sheets:
- GA: overall dimensions, datum/elevations, support locations, orientation, nozzle orientation, equipment tag, design conditions, notes, revision and title block;
- nozzle schedule and details;
- shell courses / plate development;
- head / roof / bottom details;
- support, saddle, skirt, leg, base ring and anchor details;
- BOM and weld map if within scope;
- lifting/transport and foundation interface where required.

Include units, scale or NTS, projection method, drawing number, revision, drawing status and model revision. Do not invent weld sizes, tolerances, NDE, PWHT, pressure-test or fabrication notes.

Export PDF and native drawing sources if verified. Export DXF only if the configured route is tested. Do not call DXF a DWG.

## Gate 7 — Calculation workbook and report

Create Excel using `openpyxl` with:
- `Cover`, `Design_Basis`, `Material_Data`, `Calculation_Register`;
- one sheet per implemented calculation;
- `Nozzle_Schedule`, `Loads_Weight`, `BOM` where supported;
- `Checks_Warnings`, `Revision_History`, `Limitations`.

Show input units, source, method ID, intermediate values, results and status. Do not hide blocked checks. Do not hardcode a result where a formula is intended. Where formula recalculation is unavailable, disclose that cached values may not be populated.

Calculation PDF must match workbook revision and input set.

## Gate 8 — QA and consistency

Run automated checks for:
- input schema, required fields and units;
- unit tests and regression tests;
- code/source/material traceability;
- dimensions and corrosion allowance consistency across calculation, model, BOM and drawings;
- nozzle tag/size/orientation/projection/elevation consistency;
- solid validity and model completeness;
- drawing title block, dimensions, units and revision;
- file existence/non-zero size;
- source and deliverable manifest/hash where practical.

Create `output/qa/qa-report.md` with expected/actual/status/evidence. Any critical failure blocks `READY_FOR_ENGINEERING_REVIEW`.

## Gate 9 — Handover

Use `references/acceptance-checklist.md`. State:
- actual generated files and exact paths;
- equipment type, code/edition and revision;
- module status counts: verified, checked, preliminary, blocked, failed;
- tests run and results;
- QA issues and unresolved inputs;
- review/approval requirements.

## Suggested workspace

```text
project/
  design-inputs.yaml
  calculation-register.csv
  requirements/
  src/tankvessel/calculations/
  src/tankvessel/cad/
  src/tankvessel/drawings/
  src/tankvessel/reports/
  tests/unit/
  tests/regression/
  output/calculations/
  output/model/
  output/drawings/
  output/reports/
  output/qa/
```
