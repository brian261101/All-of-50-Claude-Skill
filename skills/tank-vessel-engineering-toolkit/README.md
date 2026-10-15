# Tank/Vessel Engineering Toolkit for Claude Code

A staged engineering workflow toolkit for:
- Pressure vessels: ASME BPVC Section VIII, Division 1 (only implemented modules may calculate).
- Atmospheric storage tanks: API 650 (only implemented modules may calculate).
- FreeCAD parametric 3D, TechDraw 2D drawings, Excel calculation package, GA, BOM and QA handover.
- Claude Code orchestration through a reviewed FreeCAD MCP server.

## Important status

This is a **workflow and software scaffold**, not a validated ASME/API design program. The calculation modules in this initial package are deliberately fail-closed: they validate inputs and report `BLOCKED` unless a verified, licensed-code implementation is added. Do not use generated results for construction or certification.

## Install into a project

Copy `skills/tank-vessel-design/` to the target project's `.claude/skills/tank-vessel-design/` folder. Copy `config/` and `src/` as appropriate to the project root. See `docs/INSTALL_WINDOWS.md`.

Expected structure:

```text
your-project/
  .claude/
    skills/tank-vessel-design/SKILL.md
  config/
    mcp-config.example.json
  project/
    design-inputs.yaml
    calculation-register.csv
  src/tankvessel/
  tests/
  output/
```

## Recommended implementation sequence

1. Install FreeCAD and confirm its Python / executable environment.
2. Install and review a FreeCAD MCP server; use its documented configuration rather than assuming tool names.
3. Run the workflow in `PRELIMINARY` mode and build the input/geometry pipeline.
4. Implement one calculation module at a time, with a code-edition record, permitted source references, independent reference cases, unit tests and regression tests.
5. Only mark a calculation `VERIFIED` after documented independent verification.
6. Generate 3D and 2D outputs from the same source-of-truth design data.
7. Review all deliverables with a qualified engineer.

## Files

- `skills/tank-vessel-design/SKILL.md`: primary orchestration rules.
- `skills/tank-vessel-design/references/`: gate checklists, code-family separation, QA and deliverable rules.
- `skills/tank-vessel-design/templates/`: input and calculation register templates.
- `src/tankvessel/`: fail-closed calculation and CAD orchestration scaffolds.
- `tests/`: unit tests for input validation and blocked-module behavior.
- `config/mcp-config.example.json`: example shape only; configure using the actual server's documentation.
- `docs/`: Windows install and acceptance tests.

## No false completion

The workflow must not claim that a file was generated unless it exists, is non-empty, and has passed its relevant checks. It must not claim code compliance based only on an AI response or an unvalidated calculation.
