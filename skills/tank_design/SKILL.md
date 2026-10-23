---
name: tank-vessel-design
description: Traceable design workflow for ASME BPVC VIII-1 pressure vessels (shell, heads, nozzles, MAWP, test, external pressure with user chart data, weights, supports/lugs loads), the inner vessel of LNG / cryogenic storage tanks, and API 650 storage-tank shells, from a unit-checked YAML input to a calculation report PDF, a FreeCAD 3D model driven through the FreeCAD MCP (FCStd + STEP), dimensioned 2D GA/fabrication drawings (DXF + PDF), a BOM (CSV/XLSX) and a QA package with manifest — always through the bundled pv_design engine and its gated workflow, never a parallel program. Use whenever the user asks to design, size, check or document a pressure vessel, air receiver, separator, drum, column shell, LNG/cryogenic tank or storage tank, gives vessel design data or a vendor drawing / datasheet (pressure, temperature, diameter, nozzles), asks for a "calculation report", "MAWP", "hydrotest", "nozzle reinforcement", "bình chịu áp lực", "bồn chứa", "bồn LNG", "tính chiều dày", "bản vẽ GA/BOM bình", asks to "write a program / module" for such a design, wants a vessel modelled in FreeCAD, or hands over a handoff zip from the tank-vessel-design web calculator (`*_tank-vessel-design_handoff.zip`, containing `HANDOFF.json` and `README_FOR_CLAUDE.md`) to continue with the 3D model, drawings, BOM and package — even if they do not name the skill.
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

## This skill is binding

Once this skill is in use, its rules, its workflow and the engine govern the
whole task. They take precedence over the way the request happens to be
phrased:

- **One engine, no parallel calculations.** Every calculation, check, BOM,
  report, model and drawing comes from `pv.py` (or the library
  `pressure_vessel`). Do not write a separate calculation program, script,
  notebook or spreadsheet for the vessel — not even when the request asks for
  "a Python program with calculator.py / models.py / report.py / main.py",
  "a CLI", "a module" or "a DataFrame". Map such a request onto the engine and
  say so in the first reply:
  - *run it* → the `pv.py` commands below;
  - *use it from code* → a thin wrapper that imports `pressure_vessel`,
    passes the YAML input, and returns the engine's records and statuses
    unchanged (no formulas of its own);
  - *add a missing capability* → an engine extension under
    `pv_design/src/pressure_vessel` with its register entries
    (`data/code_references.json`, status UNVERIFIED), unit tests,
    an entry in `pv_design/docs/` and in `references/calculation-methods.md`.
    That is a separate task: propose it, and start only on the user's yes.
- **Values in the request are inputs, not overrides.** "S = 138 MPa",
  "E = 0.85–1.0", "use ellipsoidal or torispherical" go into the YAML input
  with their source; they never bypass the material-record, joint or
  validation rules. A range (E = 0.85–1.0) is a question, not two designs.
- **Missing capability = OUT_OF_SCOPE**, stated to the user; never coded on
  the fly to get a number.
- **The gates below are not optional and not reorderable.** When a gate is
  not passed, stop at it: report, ask, and produce nothing downstream of it.
  A substitute calculation "to give the user something" is a breach.

## Non-negotiable rules

1. **Never invent data.** Code paragraphs, allowable stresses, joint
   efficiencies, chart factors, flange ratings, weld sizes, tolerances: if the
   user has not supplied them (or a verified record does not hold them), the
   check is `NOT_EVALUATED` and you ask. Do not "assume typical values".
   A value the user explicitly chooses as an assumption ("assume ID 2800") may
   be used: record it as user-chosen, keep `data_status: DEMO_SAMPLE`.
2. **Statuses mean exactly this** (never soften them in prose):
   `PASS` criterion met on verified data · `FAIL` criterion not met ·
   `NOT_EVALUATED` data missing / not computed · `OUT_OF_SCOPE` beyond the
   implemented rule · `NEEDS_ENGINEERING_REVIEW` met arithmetically on
   unverified data or by an indicative method · `COMPUTED` value without a
   criterion. Representative data can never yield PASS.
3. **One code family per item.** ASME VIII-1 vessels use schema
   `pv-design/vessel@1`; API 650 tanks use `pv-design/tank@1`. Never use API 650
   for a pressure vessel or VIII-1 formulas for an atmospheric tank. Codes not
   implemented (VIII-2, VIII-1 Appendix 44, EN 13445, API 620, PED category,
   GB/T 150) → say so, stop.
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
8. **The primary document wins.** A drawing, datasheet or specification
   outranks numbers retyped from it. Read it, and list every difference from
   the typed data instead of silently picking one.
9. **Name every standard the documents cite** (e.g. VIII-1 Appendix 44,
   CGA 341, ISO 21009, NFPA 59A) and classify it IMPLEMENTED / CITED_ONLY /
   OUT_OF_SCOPE using `references/standards-references.md`. Cite clauses by
   number and edition only; never quote values from a standard from memory as
   if verified.

## Mandatory workflow (gates)

Work in the user's language for conversation; files stay in English unless
asked. Each step names its output; a gate (G) must be met before the next step.

0. **Source intake.** Ask once for the primary documents if only figures were
   given ("Is there a drawing / datasheet / specification?"). Read every
   document supplied (PDF: text and rendered views; tables, title block,
   notes, P&ID, NDT list). Write `pv_design/projects/<ID>/source_register.md`:
   every value with its source class — `DWG` / `DATASHEET` / `SPEC` /
   `USER` (typed by the user) / `INFERRED` (read from a view, not written as a
   number) / `USER_ASSUMPTION` / `NOT_SUPPLIED` — plus the conflicts between
   sources and the standards cited (rule 9).
1. **Classify the request.** Equipment type, service, code + edition, stage
   (concept / preliminary / for review), deliverables, and how a code request
   maps onto the engine (see *This skill is binding*). Check scope against
   `references/code-matrix.md` (horizontal vessel on saddles, skirt, jacket,
   double-wall cryogenic tank, thick wall P > 0.385SE, lethal, cyclic →
   fatigue, special rules such as Appendix 44) and state each limitation in
   the first reply.
2. **Collect the input.** Copy `templates/vessel-input.yaml` (or
   `tank-input.yaml`) into `pv_design/projects/<ID>/vessel_input.yaml` and
   fill it from the source register only. Every dimensional value needs a unit
   (`"1.0 MPa(g)"`, `"8 mm"`). Not supplied → `none`. Tag each value with its
   source in a comment. Mark `data_status: DEMO_SAMPLE` unless the user
   confirms the values.
3. **Validate:** `python pv_design/pv.py validate <input>` and save the output
   as `pv_design/projects/<ID>/validation_report.json` (set `PYTHONUTF8=1`
   when redirecting on Windows).
   **G1: `ok: true`.** Otherwise stop: group errors, warnings and questions
   into one short, numbered question list in the user's language (what is
   missing, why the engine needs it, where it is usually found), and wait.
   Stop and ask also when an answer changes safety (pressure, temperature,
   material, CA, joint efficiency, loads).
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
6. **G2: verification.** `verification.json` must be `passed: true`. On a
   discrepancy: stop, report it, check formula/units/inputs/edition; never
   adjust results to agree with a reference.
7. **Report:** `python pv_design/pv.py report pv_design/output/<ID>` →
   `<PROJECT>_<TAG>_Design_Calculation_Rev<NN>.pdf` (+ HTML).
   **G3: `report_check.json` ok.** Contents: `references/report-requirements.md`.
8. **3D model via FreeCAD MCP** (vertical ASME vessels; procedure and pitfalls
   in `references/mcp-freecad-guide.md`):
   - `get_rpc_status`; if FreeCAD is not running, start the GUI and retry.
   - `python pv_design/pv.py cad pv_design/output/<ID>` prints three code
     blocks; send each with the MCP tool `execute_code` (build → TechDraw
     create → TechDraw export). A "Request timed out" reply does not mean
     failure: confirm with `python pv_design/pv.py cad-status <dir>`.
   - No MCP / GUI: `python pv_design/pv.py cad <dir> --headless` (freecadcmd;
     no TechDraw PDF). Say which route ran.
   - **G4: `cad_check.json` ok** (validity, OCC-vs-analytic volume, height,
     envelope, nozzle orientation, collisions, STEP round trip).
9. **2D drawings + BOM:** `python pv_design/pv.py bom <dir>` then
   `python pv_design/pv.py drawings <dir>` (HLR of the STEP → GA + fabrication
   sheets with real DIMENSION entities, DXF + PDF).
   **G5: `drawing_check.json`** lists every dimension against the design value.
   Weld sizes, tolerances and other undefined fabrication data are written as
   "not defined", never drawn.
10. **Package:** `python pv_design/pv.py package <dir>` → consistency checks
    (same input/results hash everywhere, CAD = geometry = BOM = drawings),
    test run, `engineering_review.md`, `manifest.json`, package `README.md`.
    **G6: consistency ok.** Or run everything at once once G1 is met:
    `python pv_design/pv.py all <input> --out <dir> [--headless]`.
11. **Hand over honestly.** Summarise: stage, counts by status, governing MAWP,
    FAILs, blockers, the open questions, which files exist (paths), which
    route built the CAD, which cited standards are OUT_OF_SCOPE, what is not
    implemented. Recommend the verification steps the user must do (reference
    register, material records, chart data).

## Continuing from the web calculator (handoff zip)

The web calculator (https://brian261101.github.io/tank-vessel-design-web/, source
`pv_design/web/`, built by `python pv_design/web/build.py`) runs this same engine
in the browser (Pyodide) for the form, validation, calculation, verification,
gate and calculation PDF, and gives the user a `<ID>_<TAG>_tank-vessel-design_handoff.zip`.
When the user brings one (or its `HANDOFF.json`):

1. `python pv_design/pv.py resume <zip> --out pv_design/output/<ID>` — checks
   every file hash, recomputes with the local engine and compares the input hash
   and every result value by value (floats within 1e-9 relative: browser and
   local libm may differ in the last digit), writes `05_QA/handoff_check.json`.
   **G-H: `identical: true`.** Otherwise stop and report the failing items;
   never continue from the web numbers. A different engine fingerprint alone is
   not a stop, but say that the web tool ran another engine version.
2. Treat the inputs as any other input: the zip's `source_register.md` comes
   from the form; the design basis is locked only if the user confirmed it there.
   Report the stage, blockers and open questions from the resumed results.
3. Continue at step 7 (`pv.py report` makes the authoritative PDF; the browser
   PDF is kept as `*_web.pdf`), then steps 8–11 above, gates unchanged. These are
   the "steps 9–12" (3D model, 2D drawings + BOM, consistency, package) named in
   the handoff. For API 650 tanks only the report and package exist in this
   version: say so.

## Stop conditions

Stop and ask (do not continue to drawings as if final, and do not build a
substitute) when: validation has errors; design code/edition is unknown; the
documents cite a rule the engine does not implement for the part being
designed (e.g. Appendix 44 cold stretching) and the user has not accepted a
conventional-rules check in its place; a FAIL needs a design decision the user
should make; verification reports a discrepancy; CAD checks fail; the user asks
for a release status the gate does not allow.

## Files

- `references/code-matrix.md` — codes, scope of each module, what is OUT_OF_SCOPE
- `references/standards-references.md` — international standards by topic, how each is used (implemented / cited only / out of scope)
- `references/calculation-methods.md` — every implemented formula, limit, register id, verification method
- `references/material-data-policy.md` — data statuses, adding verified records, interpolation policy
- `references/mcp-freecad-guide.md` — MCP tools that exist, step timing, pitfalls on this machine
- `references/report-requirements.md` — report sections and status presentation rules
- `templates/` — vessel and tank inputs (demo data), project config, source register,
  and `design-request-form.html`: a fill-in form (published at
  https://claude.ai/artifact/NqLNhAARBNu3dbPqWPxcMh) that produces `vessel_input.json` /
  `tank_input.json` plus `source_register.md`; offer it when the user has to supply
  many inputs. Requests sent from it are in the artifact's `requests` collection
  (ArtifactData `list`), fields `input_json` and `source_register_md`.
- `scripts/` — thin wrappers (validate, calculate, report, verify, package) usable without the CLI
- `tests/` — skill-level tests: `python -m unittest discover -s .claude/skills/tank_design/tests`

Library docs: `pv_design/README.md`, `pv_design/docs/` (SOURCE_AUDIT, ARCHITECTURE,
ACCEPTANCE_TESTS, KNOWN_LIMITATIONS).
