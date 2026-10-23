# Source audit — `tank-vessel-design` skill (`/tank_design`)

Audit date: 2026-10-23. Auditor: Claude Code (Opus 5.5) for the repository owner.
Scope: environment, the two reference repositories named in the brief, the code
and standards catalogue, PV Elite as a process reference, and what of each the
`pressure_vessel` library reuses, rewrites or adds.

> Nothing in this document is a statement that any design complies with ASME or
> API. No licensed code text (ASME BPVC, API 650/620, EN 13445) was available in
> this environment, so every paragraph reference used by the software is held in
> a register with status `UNVERIFIED` until a person with the licensed edition
> confirms it (see `data/code_references.json`, section 5 below).

## 1. Environment

| Item | Found | How checked |
|---|---|---|
| OS | Windows 11 Pro 10.0.26100 | session environment |
| Python | 3.14.7 (`C:\Users\ADMIN\AppData\Local\Programs\Python\Python314`) | `python --version` |
| Claude Code | 2.1.270 | `claude --version` |
| FreeCAD | 1.1.4 (build 20260928), embedded Python 3.11.14, `C:\Program Files\FreeCAD 1.1\bin` | MCP `execute_code` |
| FreeCAD MCP | `freecad-mcp` via `uvx`, configured in `%APPDATA%\Claude\claude_desktop_config.json`; addon 0.1.25, protocol 1, RPC port 9875 | `get_rpc_status` |
| Project MCP config | `.mcp.json` has no servers; user config has only `rea` | file read |
| Git | 2.x (mingw64), `gh` CLI present | `which` |

Python packages present (used only where stated): PyYAML 6.0.3 (YAML input),
openpyxl 3.1.5 (BOM.xlsx), ezdxf 1.4.4 (DXF drawings), PyMuPDF 1.28.2 (PDF
rendering), matplotlib 3.11.2 (DXF → PDF rendering), numpy 2.5.3 (not used).
**Missing:** reportlab, pydantic, jsonschema, pytest, pypdf. Decision: the
calculation core is standard library only (dataclasses, own validator); tests
use `unittest`; the PDF report uses PyMuPDF, which is already installed.
Installing packages and executing the vendor test suite was refused by the
session's auto-mode policy (execution of downloaded code), so the vendor code was
reviewed statically only — see 2.3.

FreeCAD MCP tools actually exposed (no others are assumed): `create_document`,
`create_object`, `edit_object`, `delete_object`, `execute_code`,
`execute_code_async`, `get_async_status`, `execute_code_headless`, `get_object`,
`get_objects`, `get_parts_list`, `insert_part_from_library`, `get_view`,
`list_documents`, `reload_document`, `get_rpc_status`, `run_fem_analysis`.

FreeCAD capability probe (`src/pressure_vessel/cad/freecad_probe.py`, run through
MCP `execute_code`, 2026-10-23) — every item passed:

| Capability | Result |
|---|---|
| New document, `Part::Box`, `Part::Feature` with B-rep | ok, valid solid |
| Sketcher geometry + constraint | ok |
| `PartDesign::Body` | ok |
| Spreadsheet alias driving an object property by expression | ok (1200 mm read back) |
| TechDraw page, SVG template (2 found), `DrawViewPart` | ok |
| STEP export and re-import (`Import.export`, `Part.read`) | ok, volume preserved |
| `TechDraw.projectEx` hidden-line projection | ok, 10 edge groups |
| `TechDraw.writeDXFPage` | ok |
| `TechDrawGui.exportPageAsPdf` (GUI only) | ok |
| `doc.saveAs(*.FCStd)` | ok |

Known machine pitfalls carried over from earlier sessions: `execute_code_headless`
reported "freecadcmd not found" before (not relied upon); the GUI must be running
for the RPC server; the unit schema must be set to "Metric small parts & CNC" so
lengths above 10 m still display in mm.

## 2. Source 1 — ASME-PVDE (ry4ngch/ASME-PVDE)

| Field | Value |
|---|---|
| URL | https://github.com/ry4ngch/ASME-PVDE |
| Commit audited | `90873d4331bbed951cc20f7e5dc939c7bd849762` (2026-02-12, "Update README.md") |
| Version | 0.9.32 (changelog 2025-11-28) |
| License | **GNU GPL v3.0** |
| Form | Excel/VBA: `ASME VIII-1 Program.xlsm` (85 MB), material, flange, gasket, external-pressure, modulus and thermal-expansion workbooks, validation PDFs, sketches |
| Local copy | `pv_design/vendor/ASME-PVDE` (git-ignored, never modified) |

### 2.1 What was inspected

`README.md`, `changelog.md`, `LICENSE`, and the main workbook read **as data**
with `tools/audit_vendor_workbook.py` (openpyxl for sheets and formulas; an own
OLE + MS-OVBA decompressor for the VBA project — no macro was run, Excel was
never opened). Result: 89 worksheets, 149 VBA modules, 13 024 VBA lines.

Calculation sheets and their formula counts: `Shell` 1 087, `Head` 1 344,
`Nozzle` 1 560, `NozzleCalc` 1 024, `Cone` 1 192, `App2Flange` 617,
`Flat Head & Cover` 350, `UG-39 Check` 204, `UW-16` 260, `Saddle New` 1 711,
`Lifting Lug Type 1/2` 561/573, `ASCE Wind Load` 203, `EIH Support` 641,
`COG Calculation` 173. Data sheets: `Table-1A` (306 k cells), `Table-1B`,
`Table-Y1`, `Table G`, `ExtPData`, `MaterialDatabase`, `Flange Data`,
`B16.5FlangePTRating`, `GasketData`, `PipeData`, `UCS-66`, `TM1_Data`.

### 2.2 Findings

* **Architecture.** Each component is one worksheet; inputs are named ranges,
  every formula cell has a twin text cell that prints the substituted equation
  (e.g. `Head!AA10/AB10`: `IF(diameter_basis="ID","P*D*K/(2*S*El-0.2*P)",...)`).
  That "formula + substitution + value" pattern is the right model for an audit
  trail and is adopted (as data, not code) in our `CalcRecord`.
* **Shell/head formulas.** UG-27(c)(1)/(c)(2) with a switch to the Appendix 1-2
  exponential thick-wall form (`t = R(exp(P/SE)-1)`) when `P > 0.385SE`;
  ellipsoidal heads with general `K = (2+(D/2h)²)/6` on ID or OD basis and an
  option to use the corroded K; torispherical via Appendix 1-4. Code references
  found in sheet text: UG-27(c)(1), UG-32(f), App 1-2, Appendix 1-4, UG-37,
  Fig. UG-37.1, UG-45, UG-16(b), UW-16, UCS-66, UG-99(b)/(c), App 27-4, UG-44.
* **Databases.** Material allowables, yield, Table G and the external-pressure
  charts are transcriptions of ASME Section II-D (2019, 2021, 2023), flange
  dimensions/ratings of B16.5/B16.47, gaskets of B16.20/B16.21. These are ASME
  copyrighted tables redistributed in the repository; **none of this data is
  imported** into our project, and none of it can be treated as verified.
* **Fail-open pattern.** `CylindricalThkFunc.CalculateCylindricalShellThickness`
  returns `0` on any error ("Return a default value indicating an error"). A zero
  required thickness reads as a pass. Our engine raises or returns
  `NOT_EVALUATED` instead.
* **Security.** `ThisWorkbook.Workbook_Open` calls `InstallDotNetVersions`, which
  uses `WScript.Shell` to run PowerShell and enable .NET 3.5/4.x Windows
  features on open. Do not open the workbook with macros enabled outside a
  sandbox.
* **Validation material.** `Spreadsheet Validation/*.pdf` are worked examples
  apparently from ASME PTB-4 (E.4.5.x) — copyrighted; not reproduced and not used
  as benchmarks here.

### 2.3 Reuse decision

GPL-3.0 code cannot be copied into this (non-GPL) project. **Reused: ideas only**
— module list, formula-with-substitution reporting, code-edition switch, user
material database separated from code data, MDMT/UCS-66 as a separate check.
**Not reused:** any VBA, any formula cell, any data table.

## 3. Source 2 — asme-viii-pressure-vessel (LaelaZorana)

| Field | Value |
|---|---|
| URL | https://github.com/LaelaZorana/asme-viii-pressure-vessel |
| Commit audited | `24c20bb0c70700fb910fe8a633a05b8d3c4be096` (2026-08-15) |
| License | **MIT** (© 2026 Laela Zorana) — reuse permitted with notice |
| Basis claimed | ASME BPVC VIII-1, 2023 Edition; "educational … not for fabrication" |
| Size | 9 modules, 1 485 lines; 25 tests (370 lines); 5 YAML vessels; 2 CSVs |
| Dependencies | PyYAML; pytest for tests |
| Local copy | `pv_design/vendor/asme-viii-pressure-vessel` (git-ignored, never modified) |

### 3.1 Module review (static; the test suite was **not executed** — see §1)

| Module | Implements | Assessment |
|---|---|---|
| `shells.py` | UG-27(c)(1),(c)(2) t and MAWP; limits P ≤ 0.385SE, t ≤ R/2, P ≤ 1.25SE; corroded R = D/2 + CA | Formulas correct as commonly published. Reimplemented in SI with trace records. |
| `shells.py` (UG-28) | L/Do, Do/t, Pa = 4B/(3 Do/t), Pa = 2AE/(3 Do/t) with user B; a "screening" A from classical buckling relations | Pa equations reused in concept. **Screening A dropped**: the brief forbids substituting an approximation for Fig. G. |
| `heads.py` | 2:1 ellipsoidal UG-32(d), torispherical App 1-4(d) M-factor and UG-32(e), hemispherical UG-32(f) with limits | Correct forms. Gaps: no general-ratio ellipsoidal (App 1-4(c) K); knuckle check uses **6 % of crown radius L**, whereas the head-geometry rule as commonly cited is 6 % of the **skirt OD** — to verify, our module checks against skirt OD. |
| `nozzles.py` | UG-37 area method A, A1…A5, fr1…fr4, UG-40 limits, pad OD sizing; UG-45 ta/tb1/tb3 | Formulas match Fig. UG-37.1 as commonly published. Radial nozzle in a cylinder only, F = 1. Reimplemented with explicit status for out-of-scope cases (heads beyond the 80 % circle, hillside, UG-36(b)(1) large openings, UG-41 weld paths). |
| `pressure.py` | UG-98 min of component MAWPs; UG-99(b) 1.3·MAWP·LSR; UG-100 1.1·MAWP·LSR | No static-head deduction. Our version deducts static head per component when a liquid level is given. |
| `joints.py` | Table UW-12 types 1–3 | Types 4–6 missing; reimplemented with all six rows as a data table under reference control. |
| `materials.py`, CSV | Ten grades in psi vs °F, "representative of Table 1A" | **Representative, unverified.** Its SA-516-70 values (19.4 ksi at 600 °F) differ from other public summaries — exactly why such data must not be used for release. Converted values are carried only as `REPRESENTATIVE_EXAMPLE` records. |
| `pipe_schedules.csv` | OD/wall for NPS ½–12, STD/40/80/160 | Reused (MIT, attributed) after cross-checking against B36.10M values known to the author; status `UNVERIFIED` until checked against the licensed standard. |
| `report.py` | YAML → Markdown with substituted equations | Two issues: (1) a missing joint block silently defaults to type 1 + spot RT (E = 0.85); (2) the vessel `ok` flag ignores the external-pressure case when B is not supplied, so a vessel with an unevaluated mandatory check reports overall OK. Our engine forbids both. |
| `heads.py` (limit) | `t/L < 0.002` raises inside the thickness function | The limit is applied to the **required** thickness, so a low-pressure case (e.g. UG-33(a)(1) at 1.67 × 0.1 MPa) is refused although the head itself is thick enough. This engine had the same pattern in its first version (caught by the demo run) and now applies the limit to the specified minimum thickness after forming. |
| `report.py` (area inputs) | tn = tw(1 − mill tol) − CA, d = OD − 2tn | Conservative convention documented by the author; differs from UG-16(d) (undertolerance not required for UG-37 areas). Gives A = 3.070 in² vs 3.029 in² here for its example — kept as a reported method difference in the cross-implementation benchmark. |

### 3.2 Reuse decision

* **Reused (MIT, with attribution in `NOTICE.md`):** symbol conventions and the
  structure of the UG-37 area bookkeeping; the pipe schedule subset (converted
  to mm); the five US-unit worked results as a **cross-implementation regression
  benchmark** (`tests/benchmarks/laela_zorana_us_units.json`), clearly labelled as
  values produced by that library, not by ASME.
* **Rewritten:** everything else — SI units internally, explicit unit parsing,
  `CalcRecord` traceability, five-state status model, no silent defaults,
  reference register, material records with verification status.
* **Added (not in either source):** general ellipsoidal heads; static head;
  UG-16 minimum and undertolerance handling; nominal thickness selection from a
  plate list; UG-36(b)(1) opening-size scope gate; external pressure for heads
  (UG-33) with user-supplied chart data; flange P-T check against a user-supplied
  rating; weights, volumes, CG; hydrotest weight; support/lug load derivation;
  API 650 one-foot method as a separate code family; independent verification
  formulations; PDF report; FreeCAD model + STEP; DXF/PDF drawings; BOM;
  consistency checks; manifest.

## 4. Source 3 — codes and standards catalogue

The full matrix (scope, edition field, what the software does with each) is in
`.claude/skills/tank_design/references/code-matrix.md`. Summary:

| Family | Documents | In software v0.1 |
|---|---|---|
| Pressure vessel | ASME BPVC VIII-1; II-A/B (specs), II-D (allowables, charts, TM tables); V (NDE); IX (welding qualification); B16.5/B16.47 (flanges); B16.20/B16.21 (gaskets); B36.10M/B36.19M (pipe); B18.2.x/B1.1 (bolting) | VIII-1 internal-pressure core implemented; II-D data **user-supplied**; V, IX recorded as requirements only; flange rating compared against a **user-supplied** B16.5 rating |
| Storage tank | API 650; API 620 | API 650 one-foot shell method, minimum thickness, hydrotest case, scope gate; API 620 → `OUT_OF_SCOPE` |
| European | EN 13445, PED 2014/68/EU | Not implemented; selecting them returns `OUT_OF_SCOPE`. PED category is not computed. |
| National | Vietnam QCVN/TCVN for pressure equipment inspection (e.g. QCVN 01:2008/BLĐTBXH — **title and current revision to be confirmed by the project**) | Recorded as a project field only |

Rules enforced in code: one code family per equipment item; ASME VIII-1 and
API 650 live in separate packages with separate input schemas; an API 650 input
with internal pressure above the scope limit stated by the user's licensed
edition (field `api650_scope_limits`) or a refrigerated/pressurised service is
stopped with `OUT_OF_SCOPE`.

## 5. Code-reference register

Every formula cites a register id (e.g. `ASME8-1:UG-27(c)(1)`), never a free
string. Each entry stores paragraph, title, edition basis, how it is used,
`verification_status` (`UNVERIFIED` | `VERIFIED`), `verified_by`, `verified_on`,
and the public source that cites it. All entries ship `UNVERIFIED`. A check can
only reach `PASS` when its references and its material data are verified; with
unverified references an arithmetically satisfied check reports
`NEEDS_ENGINEERING_REVIEW` and says why. Sub-paragraph letters (e.g. UG-32(d)
vs (c)) have moved between editions; the register records the letter as cited by
the 2023-basis public source and flags it for confirmation.

## 6. Source 4 — PV Elite (Hexagon)

No licence, installation or sample output was available. Only publicly
described workflow concepts were used as a checklist (component-by-component
input, per-element MAWP/MAP, nozzle reinforcement summary, test pressures,
weights/CG, warnings list, summary of governing elements). No PV Elite code,
database or document text was copied. `pressure_vessel.verification.pv_elite`
provides a comparison harness that accepts a user-supplied CSV of PV Elite
results (component, quantity, value, unit) and reports per-value deviation; with
no file it records `NOT_AVAILABLE`. PV Elite agreement, when available, is one
piece of evidence, not proof.

## 7. Confirmed limitations of the sources

* Neither repository is a complete VIII-1 implementation; both say so.
* Both carry Section II-D-derived data whose verification state is unknown.
* PVDE is GPL and Excel-bound; the MIT library is internal-pressure only.
* Neither handles wind/seismic, nozzle loads, fatigue, MDMT (UCS-66) or supports
  as Code checks.

## 8. Points that must be verified against the licensed Code

1. Every register entry (paragraph letters, formula forms, limits).
2. Allowable stress S at design and test temperature for every material, and
   whether linear interpolation between tabulated temperatures is used.
3. Table UW-12 values and the UW-12(d) seamless-head rule.
4. Table UG-45 nozzle minimum thickness values (the software derives them as
   0.875 × standard-weight wall — the derivation itself must be confirmed).
5. UG-16(b) minimum thickness and UG-16(c) plate undertolerance limit.
6. UG-36(b)(1) opening-size limits; UG-37 tr definitions for heads (K1 = 0.9 for
   2:1 heads).
7. API 650 one-foot method constants, minimum thickness table, Sd/St rules.
8. ASME B16.5 flange P-T ratings and dimensions used for each nozzle.

## 9. Test and integration plan

1. Unit tests per function (valid, boundary, invalid, out-of-scope) — `unittest`.
2. Hand-calculated benchmarks with the arithmetic written out (JSON).
3. Independent formulations (outside-radius Appendix 1-1 forms, bisection on the
   MAWP relation, K-factor and M-factor general forms, analytic vs CAD volume).
4. Cross-implementation regression against the MIT library's published results.
5. PV Elite harness when the user provides results.
6. End-to-end: demo YAML → validation → calculations → verification → PDF →
   FreeCAD (MCP) → STEP → DXF/PDF drawings → BOM → consistency → manifest.
