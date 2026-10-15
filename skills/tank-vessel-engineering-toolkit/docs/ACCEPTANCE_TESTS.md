# Software / workflow acceptance tests

## Smoke tests
- [ ] Claude Code discovers the skill and can read the workflow.
- [ ] No MCP tool is assumed before tool discovery.
- [ ] Invalid or mismatched equipment/code pair is rejected.
- [ ] Missing code edition is rejected.
- [ ] Unimplemented ASME calculation returns `BLOCKED` with no numeric result.
- [ ] Unimplemented API 650 calculation returns `BLOCKED` with no numeric result.
- [ ] FreeCAD scratch test creates and saves a native file.
- [ ] STEP export is imported into a fresh document and inspected.
- [ ] TechDraw output PDF exists, opens and includes title/revision.
- [ ] Excel workbook opens and has input/source/status tabs.
- [ ] Cross-checks compare dimensions and nozzle schedule between input/model/drawings.
- [ ] QA report records actual test results and all blockers.
- [ ] No file is reported as created unless existence and size are checked.

## Calculation-module release gate
A module may move to `CHECKED` only after implementation and automated tests pass. It may move to `VERIFIED` only after:
- exact code edition and permitted reference documented;
- independent reference case(s) pass;
- reviewer and date recorded;
- limitations and excluded cases are explicit;
- regression tests pass in CI / repeatable local run.

## Handover gate
- [ ] Deliverables manifest matches files on disk.
- [ ] All blocked/failed items are shown.
- [ ] Final status does not exceed `READY_FOR_ENGINEERING_REVIEW`.
- [ ] Construction release is controlled by the project’s authorized engineering process.
