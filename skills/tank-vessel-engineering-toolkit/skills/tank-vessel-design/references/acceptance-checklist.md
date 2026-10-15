# Acceptance checklist

## A. Inputs and design basis
- [ ] Equipment category and code family explicitly selected.
- [ ] Code edition/addenda and jurisdiction recorded.
- [ ] Units explicit; unit conversions tested.
- [ ] Every input labeled user-provided / derived / assumption.
- [ ] Missing critical values listed as blockers.
- [ ] Materials and properties have traceable sources and revisions.
- [ ] Nozzle schedule and design load cases reviewed.

## B. Calculations
- [ ] Calculation register created and maintained.
- [ ] Each module has method ID, code reference, limits and units.
- [ ] Unit tests cover normal, boundary, invalid and unsupported cases.
- [ ] Regression cases have independent verification evidence.
- [ ] Intermediate results and source traceability are recorded.
- [ ] Unsupported checks remain BLOCKED.
- [ ] Independent engineer review recorded before VERIFIED status.

## C. 3D CAD
- [ ] Model generated from source-of-truth input/result data.
- [ ] Units, datum and orientation documented.
- [ ] Native FCStd exists and opens.
- [ ] STEP export exists and imports successfully, if requested.
- [ ] Solid validity checks pass.
- [ ] Critical dimensions and nozzle locations agree with input.
- [ ] Components and material assumptions are labeled.

## D. Drawings
- [ ] GA contains overall dimensions, datums, support and nozzle orientation.
- [ ] Required detail sheets identified and generated.
- [ ] BOM reconciles to model.
- [ ] Drawing units, scale/NTS, projection, revision and status are present.
- [ ] PDF opens and page count is as expected.
- [ ] DXF/DWG naming matches actual file format.
- [ ] Fabrication notes are sourced / approved, not invented.

## E. Workbook / reports
- [ ] Workbook exists and opens.
- [ ] Inputs, formulas/results, units, sources and status are distinguishable.
- [ ] Blocked checks and limitations visible.
- [ ] PDF report matches workbook revision and design input.
- [ ] No unverified module represented as code-compliant.

## F. Release
- [ ] Automated tests pass.
- [ ] QA report exists and all failures are visible.
- [ ] Deliverable manifest lists actual files only.
- [ ] All open issues and assumptions listed.
- [ ] Qualified engineering review is required and recorded.
- [ ] No AI-assigned READY_FOR_CONSTRUCTION status.
