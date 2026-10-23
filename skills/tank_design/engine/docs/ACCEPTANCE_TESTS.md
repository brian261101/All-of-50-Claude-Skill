# Acceptance tests

Run on 2026-10-23, Windows 11, Python 3.14.7, FreeCAD 1.1.4, FreeCAD MCP 0.1.25.

Automated suites:

```bash
python -m unittest discover -s pv_design/tests -t pv_design                       # 74 tests
python -m unittest discover -s .claude/skills/tank_design/tests         # 20 tests
```

Result: **74/74 OK** (library, incl. end-to-end with freecadcmd) and **20/20 OK**
(skill scripts). Transcript of the last library run:
`output/PV-DEMO-001/05_QA/test_results.txt`.

Legend: ✅ met and evidenced · ⚠️ met with a stated limitation · ❌ not met.

## Skill and architecture
| Criterion | Result | Evidence |
|---|---|---|
| Skill discoverable by Claude Code | ✅ | listed as `tank_design (tank-vessel-design)` in the session's skill list; invoked with `/tank_design` |
| Workflow and modules described | ✅ | SKILL.md, docs/ARCHITECTURE.md, references/ |
| Sources and licences recorded | ✅ | docs/SOURCE_AUDIT.md, NOTICE.md |
| No unnecessary dependency | ✅ | core stdlib only; optional packages already installed; nothing installed |

## Calculation engine
| Criterion | Result | Evidence |
|---|---|---|
| Implemented calculations have unit tests | ✅ | tests/test_formulas.py, test_engine.py |
| Independent benchmark | ✅ | 66 verification checks pass: alternative formulations + `data/benchmarks/hand_calcs_si.json` (17 hand cases) + cross-implementation (5 cases) |
| Unit checking | ✅ | test_units_and_status.py; bare numbers / wrong dimensions rejected |
| Wrong input and boundary cases | ✅ | limits (0.385SE, R/2, L/r, ts/L), invalid E, missing joints, absolute pressure, T/T closure |
| Every calculation has a code reference | ✅ | test_every_record_traces_to_register |
| Limits reported | ✅ | OUT_OF_SCOPE records, KNOWN_LIMITATIONS.md |
| Nothing unevaluated marked PASS | ✅ | test_no_check_passes_on_representative_data, test_unevaluated_check_is_not_pass, computations shown COMPUTED |
| Gate can open only on verified data | ✅ | test_fully_verified_minimal_case_reaches_calculation_verified (test fixture) vs ..._stays_preliminary |
| Discrepancy stops release | ✅ | test_planted_discrepancy_is_caught |
| PV Elite comparison | ⚠️ | harness implemented and tested with a synthetic CSV (deviation detected, release stopped); no licensed PV Elite results available → NOT_AVAILABLE for the demo |

## PDF report
| Criterion | Result | Evidence |
|---|---|---|
| PDF opens | ✅ | `report_check.json` (re-opened, 53 pages) |
| Design information complete | ✅ | 24 numbered sections + cover |
| Formulas, intermediates, results | ✅ | per-record chain; all 67 calc ids found in the PDF text |
| Data sources and revision | ✅ | material and reference tables, hashes on cover and footer |
| No missing tables/pages | ✅ | required headings present (ligature-normalised text check) |

## FreeCAD
| Criterion | Result | Evidence |
|---|---|---|
| MCP adapter tested | ✅ | build, TechDraw create, TechDraw export executed through `execute_code`; `cad-status` reads the result files |
| Real model created | ✅ | 30 solids, `02_CAD_3D/V_101_rev00.FCStd` (mode "GUI (MCP)") |
| FCStd opens | ✅ | re-opened in FreeCAD for the TechDraw step |
| STEP exported | ✅ | re-imported: 30 solids, volume diff 8.1e-6 |
| Geometry valid | ✅ | all solids valid; 0 collisions > 1 mm³ |
| Main dimensions = calculation data | ✅ | overall height, envelope, nozzle orientation/elevation, OCC vs analytic volume (worst 4.9e-4) |
| Headless fallback | ✅ | freecadcmd build in 7 s, same checks |

## 2D drawings
| Criterion | Result | Evidence |
|---|---|---|
| Required views | ✅ | front, side, section A-A (hatched), plan with orientation; head, base plate, lug details; shell development |
| Fabrication dimensions | ⚠️ | 41 true DIMENSION entities (DIMLFAC = scale), all equal to design values; weld sizes / tolerances not drawn because not defined in the input (stated on the sheets) |
| Nozzle orientation correct | ✅ | plan view + CAD centre-of-mass check |
| Title block and revision | ✅ | both sheets (and the TechDraw page, fields set explicitly) |
| PDF opens | ✅ | GA.pdf, fabrication_drawings.pdf, TechDraw PDF |
| DXF checked | ✅ | re-read with ezdxf, audit 0 errors, DIMENSION count recorded |

## BOM
| Criterion | Result | Evidence |
|---|---|---|
| All components in scope | ✅ | 23 modelled lines + gasket/bolting for the supplied joint |
| Quantities and materials | ✅ | grouped legs ×4, plates ×4, lugs ×2; material spec/grade from records |
| Cross-check with CAD | ✅ | consistency: BOM components = design components = CAD components |
| Total weight method stated | ✅ | net theoretical = calculated empty weight (1257.92 kg); procurement estimate with stated allowances and exclusions |

## Consistency
| Criterion | Result | Evidence |
|---|---|---|
| Same revision/hashes across input, calc, CAD, drawings, BOM | ✅ | `05_QA/consistency.json` (28/28) |
| Important errors recorded | ✅ | gate blockers, open mandatory checks, questions, engineering_review.md |
| Final test report | ✅ | 05_QA/test_results.txt, manifest.json |

## What acceptance does NOT mean
Passing these tests shows the software computes what it claims, consistently
and traceably. It does not show code compliance: the register's references
and the material data must still be verified against the licensed editions,
and the missing evaluations (KNOWN_LIMITATIONS.md) must be done by engineers.
