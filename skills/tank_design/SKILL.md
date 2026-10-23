---
name: tank-vessel-design
description: Traceable design workflow for ASME BPVC VIII-1 pressure vessels (shell, heads, nozzles, MAWP, test, external pressure with user chart data, weights, supports/lugs loads) and API 650 storage-tank shells, from a unit-checked YAML input to a calculation report PDF, a FreeCAD 3D model driven through the FreeCAD MCP (FCStd + STEP), dimensioned 2D GA/fabrication drawings (DXF + PDF), a BOM (CSV/XLSX) and a QA package with manifest. Use whenever the user asks to design, size, check or document a pressure vessel, air receiver, separator, drum, column shell or storage tank, gives vessel design data (pressure, temperature, diameter, nozzles), asks for a "calculation report", "MAWP", "hydrotest", "nozzle reinforcement", "bình chịu áp lực", "bồn chứa", "tính chiều dày", "bản vẽ GA/BOM bình", or wants a vessel modelled in FreeCAD — even if they do not name the skill.
---

# Pressure vessel / tank design (ASME VIII-1, API 650)

The engine lives in `pv_design/` (library `pv_design/src/pressure_vessel`, CLI
`python pv_design/pv.py`). When the project has no `pv_design/` folder (skill
installed from the published package), the same engine is bundled in this
skill folder as `engine/`: use `python <this skill folder>/engine/pv.py` in
place of `python pv_design/pv.py` and write packages to a project folder such
as `./pv_output/<ID>`. This skill tells you how to drive it. It is an
engineering-review tool: it produces drafts and traceable calculations, never
an approved design.

## Non-negotiable rules

1. **Never invent data.** Code paragraphs, allowable stresses, joint
   efficiencies, chart factors, flange ratings, weld sizes, tolerances: if the
   user has not supplied them (or a verified record does not hold them), the
   check is `NOT_EVALUATED` and you ask. Do not "assume typical values".
2. **Statuses mean exactly this** (never soften them in prose):
   `PASS` criterion met on verified data · `FAIL` criterion not met ·
   `NOT_EVALUATED` data missing / not computed · `OUT_OF_SCOPE` beyond the
   implemented rule · `NEEDS_ENGINEERING_REVIEW` met arithmetically on
   unverified data or by an indicative method · `COMPUTED` value without a
   criterion. Representative data can never yield PASS.
3. **One code family per item.** ASME VIII-1 vessels use schema
   `pv-design/vessel@1`; API 650 tanks use `pv-design/tank@1`. Never use API 650
   for a pressure vessel or VIII-1 formulas for an atmospheric tank. Codes not
   implemented (VIII-2, EN 13445, API 620, PED category) → say so, stop.
4. **No claim of compliance or fabrication readiness.** The highest automatic
   stage is `CALCULATION_VERIFIED`; `ENGINEERING_REVIEW` and
   `APPROVED_FOR_FABRICATION` exist only with signatures by qualified people.
   Drawings and report carry "PRELIMINARY — NOT FOR FABRICATION" until then.
5. **A CAD model is not proof of strength; passing unit tests is not proof of
   code compliance.** Say so when summarising.
6. **Report only what exists.** Before saying a file was made, check it exists
   and is non-empty (the pipeline's check files do this; read them).
7. **Do not modify** `pv_design/vendor/` (third-party sources, audit only),
   `data/code_references.json` statuses, or material records' verification
   fields on the user's behalf. Verification is recorded by the user in the
   project input (`code_reference_verification`, material `record` with
   `verified_by/verified_on`).

## Workflow

Work in the user's language for conversation; files stay in English unless asked.

1. **Classify the request.** Equipment type, service, code + edition, stage
   (concept / preliminary / for review), deliverables. If the code is not
   ASME VIII-1 or API 650, or the service is outside the module scope
   (horizontal vessel on saddles, skirt, jacket, thick wall P > 0.385SE, lethal,
   cyclic → fatigue), state the limitation (see `references/code-matrix.md`).
2. **Collect the input.** Copy `templates/vessel-input.yaml` (or
   `tank-input.yaml`) into the project folder, e.g.
   `pv_design/projects/<ID>/vessel_input.yaml`, and fill it from the user's data.
   Every dimensional value needs a unit (`"1.0 MPa(g)"`, `"8 mm"`). Put
   anything the user did not give as `none` — never a guess. Mark
   `data_status: DEMO_SAMPLE` unless the user confirms the values.
3. **Validate:** `python pv_design/pv.py validate <input>`. Fix errors; turn
   warnings and questions into a short, specific question list for the user
   (one message, grouped). Stop and ask when an answer changes safety
   (pressure, temperature, material, CA, joint efficiency, loads).
4. **Lock the design basis** only when the user confirms the inputs
   (`design_basis.locked: true`, `confirmed_by`, `confirmed_on`,
   `data_status: USER_CONFIRMED`). Otherwise proceed as PRELIMINARY and say so.
5. **Calculate + verify:**
   `python pv_design/pv.py calc <input> --out pv_design/output/<ID>`
   (add `--pv-elite results.csv` if the user has licensed PV Elite results —
   see `references/calculation-methods.md`). Read
   `01_CALCULATION/calculation_results.json`: gate stage, FAILs, open mandatory
   checks, questions. A FAIL is a design result: propose the fix (thicker plate,
   pad, schedule) and re-run — do not edit numbers.
6. **Verification gate.** `verification.json` must be `passed: true`. On a
   discrepancy: stop, report it, check formula/units/inputs/edition; never
   adjust results to agree with a reference.
7. **Report:** `python pv_design/pv.py report pv_design/output/<ID>` →
   `<PROJECT>_<TAG>_Design_Calculation_Rev<NN>.pdf` (+ HTML). Confirm
   `report_check.json` is ok. Contents: `references/report-requirements.md`.
8. **3D model via FreeCAD MCP** (vertical ASME vessels; procedure and pitfalls
   in `references/mcp-freecad-guide.md`):
   - `get_rpc_status`; if FreeCAD is not running, start the GUI and retry.
   - `python pv_design/pv.py cad pv_design/output/<ID>` prints three code
     blocks; send each with the MCP tool `execute_code` (build → TechDraw
     create → TechDraw export). A "Request timed out" reply does not mean
     failure: confirm with `python pv_design/pv.py cad-status <dir>`.
   - No MCP / GUI: `python pv_design/pv.py cad <dir> --headless` (freecadcmd;
     no TechDraw PDF). Say which route ran.
   - `cad_check.json` must be ok (validity, OCC-vs-analytic volume, height,
     envelope, nozzle orientation, collisions, STEP round trip).
9. **2D drawings + BOM:** `python pv_design/pv.py bom <dir>` then
   `python pv_design/pv.py drawings <dir>` (HLR of the STEP → GA + fabrication
   sheets with real DIMENSION entities, DXF + PDF). `drawing_check.json` lists
   every dimension against the design value. Weld sizes, tolerances and other
   undefined fabrication data are written as "not defined", never drawn.
10. **Package:** `python pv_design/pv.py package <dir>` → consistency checks
    (same input/results hash everywhere, CAD = geometry = BOM = drawings),
    test run, `engineering_review.md`, `manifest.json`, package `README.md`.
    Or run everything: `python pv_design/pv.py all <input> --out <dir> [--headless]`.
11. **Hand over honestly.** Summarise: stage, counts by status, governing MAWP,
    FAILs, blockers, the open questions, which files exist (paths), which
    route built the CAD, what is not implemented. Recommend the verification
    steps the user must do (reference register, material records, chart data).

## Stop conditions

Stop and ask (do not continue to drawings as if final) when: validation has
errors; design code/edition is unknown; a FAIL needs a design decision the
user should make; verification reports a discrepancy; CAD checks fail; the
user asks for a release status the gate does not allow.

## Files

- `references/code-matrix.md` — codes, scope of each module, what is OUT_OF_SCOPE
- `references/calculation-methods.md` — every implemented formula, limit, register id, verification method
- `references/material-data-policy.md` — data statuses, adding verified records, interpolation policy
- `references/mcp-freecad-guide.md` — MCP tools that exist, step timing, pitfalls on this machine
- `references/report-requirements.md` — report sections and status presentation rules
- `templates/` — vessel and tank inputs (demo data), project config
- `scripts/` — thin wrappers (validate, calculate, report, verify, package) usable without the CLI
- `tests/` — skill-level tests: `python -m unittest discover -s .claude/skills/tank_design/tests`

Library docs: `pv_design/README.md`, `pv_design/docs/` (SOURCE_AUDIT, ARCHITECTURE,
ACCEPTANCE_TESTS, KNOWN_LIMITATIONS).
