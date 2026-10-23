# International standards — how this skill uses them

No licensed standard text was available when the engine was written. Titles
below are given for identification; confirm the edition in force for the
project. Every clause the engine applies is held in
`pv_design/data/code_references.json` (status UNVERIFIED until the project
verifies it).

## Usage classes

| Class | Meaning | What you may do |
|---|---|---|
| IMPLEMENTED | the engine evaluates the rule (subset in `code-matrix.md`) | run it; results carry the five-state status |
| DATA_SOURCE | the standard supplies data the engine consumes (allowables, ratings, pipe walls) | use only user-verified or recorded values; never values from memory |
| CITED_ONLY | named for traceability, screening or a requirement the report lists | list it in the report as a requirement / open item; no numbers |
| OUT_OF_SCOPE | governs part of the design the engine does not cover | say so in the first reply and in the report; stop if it governs the part being designed |

Rule: list every standard named in the user's documents (drawing data sheet,
title block, notes, specification) in `source_register.md` with its class. A
standard that is not in this file is OUT_OF_SCOPE until added here.

## Pressure vessels

| Standard | Subject | Class |
|---|---|---|
| ASME BPVC Section VIII Div. 1 | unfired pressure vessels — UG, UW, UCS, UHA parts, Appendices 1-1/1-2/1-4 | IMPLEMENTED (subset) |
| ASME VIII-1 Mandatory Appendix 44 | cold stretching of austenitic stainless steel vessels | OUT_OF_SCOPE — a vessel designed to it is not reproduced by the ordinary rules |
| ASME VIII-1 Part UHA, UHA-51 | high-alloy steels, impact test exemptions | CITED_ONLY (assessment by the engineer) |
| ASME BPVC Section VIII Div. 2 | alternative rules, design by analysis, fatigue (Part 5) | OUT_OF_SCOPE |
| EN 13445 (parts 1–5) | unfired pressure vessels (European route) | OUT_OF_SCOPE |
| PD 5500 | unfired fusion-welded pressure vessels (UK) | OUT_OF_SCOPE |
| GB/T 150 (parts 1–4) | pressure vessels (China; common on vendor drawings) | OUT_OF_SCOPE |
| Pressure Equipment Directive 2014/68/EU | conformity, category | OUT_OF_SCOPE |

## Materials

| Standard | Subject | Class |
|---|---|---|
| ASME BPVC Section II-A / II-B | ferrous / non-ferrous material specifications (SA-240, SA-312, SA-516 …) | CITED_ONLY (spec / grade) |
| ASME BPVC Section II-D | allowable stresses (Table 1A), yield (Y-1), external-pressure charts | DATA_SOURCE (user-verified records only; charts never approximated) |
| EN 10028-7 / EN 10216-5 / EN 10217-7 | stainless plates and tubes (European) | CITED_ONLY |

## Cryogenic and LNG storage

| Standard | Subject | Class |
|---|---|---|
| ISO 21009-1 / -2 | static vacuum-insulated cryogenic vessels — design / operation | CITED_ONLY |
| EN 13458-1 / -2 / -3 | static vacuum-insulated cryogenic vessels (European) | CITED_ONLY |
| CGA 341 | insulated cargo tanks for nonflammable cryogenic liquids | CITED_ONLY |
| CGA S-1.3 | pressure relief device standards — stationary storage containers | CITED_ONLY |
| NFPA 59A | production, storage and handling of LNG (siting, spacing) | CITED_ONLY |
| EN 1473 | LNG installations and equipment | CITED_ONLY |
| API 620 incl. Annex Q / R | large low-pressure welded storage tanks, refrigerated / LNG | OUT_OF_SCOPE |
| EN 14620 | site-built flat-bottomed refrigerated tanks −5 to −165 °C | OUT_OF_SCOPE |

For a vacuum-insulated double-wall tank the engine designs the **inner vessel
only**. The outer jacket under external pressure, the annular insulation, the
inner-vessel supports and legs fixed to the jacket are OUT_OF_SCOPE (see
`code-matrix.md`).

## Atmospheric storage tanks

| Standard | Subject | Class |
|---|---|---|
| API 650 | welded steel tanks for oil storage | IMPLEMENTED (shell 1-foot method, bottom minimum, scope gate) |
| API 650 Annexes E, F, M | seismic, internal pressure, elevated temperature | OUT_OF_SCOPE (Annex F/M limits only as user-stated scope data) |
| EN 14015 | site-built vertical tanks above ambient | OUT_OF_SCOPE |

## Piping, flanges, gaskets, relief

| Standard | Subject | Class |
|---|---|---|
| ASME B36.10M / B36.19M | carbon / stainless pipe dimensions | DATA_SOURCE (subset table, UNVERIFIED) |
| ASME B16.5 / B16.47 | flanges NPS ½–24 / 26–60, P-T ratings, dimensions | DATA_SOURCE (user-supplied rating and dimensions) |
| ASME B16.20 / B16.21 | metallic / non-metallic gaskets | CITED_ONLY (BOM text) |
| ASME B31.3 | process piping (outside the vessel boundary) | OUT_OF_SCOPE |
| ASME VIII-1 UG-125 … UG-140 | overpressure protection | CITED_ONLY |
| API 520 / API 521, ISO 4126 | relief device sizing, relieving scenarios | OUT_OF_SCOPE |

## Loads, supports, local stresses

| Standard | Subject | Class |
|---|---|---|
| ASCE 7 | wind, seismic loads | OUT_OF_SCOPE (forces come in as inputs with their basis) |
| EN 1991-1-4, EN 1998-4 | wind actions; silos, tanks and pipelines (seismic) | OUT_OF_SCOPE (as above) |
| GB 50009 / GB 50011 | loads / seismic design (China; "basic wind pressure", "intensity 7" on vendor drawings) | OUT_OF_SCOPE (as above) |
| TCVN 2737, TCVN 9386 | loads and actions / seismic design (Vietnam) | OUT_OF_SCOPE (as above); confirm current edition |
| AISC 360 | structural steel (legs, lugs) | OUT_OF_SCOPE in the engine (SUP-STRUCT, LUG-CHECK indicative only) |
| WRC 107 / WRC 537 / WRC 297 | local stresses from attachment / nozzle loads | OUT_OF_SCOPE |
| L.P. Zick method | horizontal vessels on saddles | OUT_OF_SCOPE |

## Fabrication, welding, inspection

| Standard | Subject | Class |
|---|---|---|
| ASME BPVC Section IX | welding and brazing qualifications | CITED_ONLY |
| ASME BPVC Section V | non-destructive examination | CITED_ONLY |
| ASME VIII-1 UW-11, UW-12, UW-51, UW-52, App. 6, App. 8 | RT extent, joint efficiency, RT / MT / PT acceptance | IMPLEMENTED for UW-12 E; others CITED_ONLY |
| AWS D1.1 | structural welding (non-pressure parts) | CITED_ONLY |

## National rules (Vietnam)

| Document | Subject | Class |
|---|---|---|
| QCVN 01:2008/BLĐTBXH | safety of boilers and pressure vessels (registration, inspection) | CITED_ONLY — confirm the revision in force with the client |
| TCVN 8366 | pressure vessels — technical requirements (design, fabrication) | CITED_ONLY — confirm edition |

`project.jurisdiction` records which national rules apply; the engine does not
evaluate them.
