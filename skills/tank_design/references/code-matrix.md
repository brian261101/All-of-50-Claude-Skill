# Code matrix and module scope (pressure_vessel 0.1.0)

Edition is a project input (`project.code_edition`, `addenda`). No licensed code
text was available when the software was written; every reference is held in
`pv_design/data/code_references.json` with status UNVERIFIED until the project
verifies it (`code_reference_verification` in the input).

## Families

| Family | Documents | Status in v0.1 |
|---|---|---|
| ASME BPVC VIII-1 | UG-16, UG-22, UG-25, UG-27, UG-28, UG-32, App. 1-1/1-2/1-4, UG-33, UG-36, UG-37, UG-40, UG-41, UG-42, UG-44, UG-45, UG-98, UG-99, UG-100, UW-3, UW-11, UW-12, UW-14, UCS-56, UCS-66 | implemented subset below |
| ASME II-A/B | material specifications | referenced by spec/grade only |
| ASME II-D | Table 1A (S), Table Y-1, TM tables, Subpart 3 charts (Fig. G, CS-x) | data is **user supplied**; charts never approximated |
| ASME V / IX | NDE, welding qualification | recorded as requirements, not evaluated |
| ASME B16.5 / B16.47 | flange P-T ratings, dimensions | rating and dimensions user supplied, compared/used |
| ASME B16.20 / B16.21 | gaskets | BOM description only |
| ASME B36.10M / B36.19M | pipe OD / wall | subset table, UNVERIFIED |
| API 650 | 1.1 scope, 5.4.1, 5.6.1.1, 5.6.2.1, 5.6.3 | shell 1-foot method, bottom minimum, scope gate |
| API 620 | low-pressure tanks | OUT_OF_SCOPE |
| EN 13445 / PED | European route | OUT_OF_SCOPE (no PED category computed) |
| National (e.g. Vietnam QCVN for pressure equipment) | inspection/registration | project field only; confirm title and revision with the client |

Never mix: an input is one family; the validators refuse the other schema.

## ASME VIII-1 modules

| Check (calc id) | Rule | Scope / OUT_OF_SCOPE triggers |
|---|---|---|
| MAT-* | II-D Table 1A record lookup | out of tabulated range; interpolation only if the record permits |
| JE-* | Table UW-12 types 1–6 × full/spot/none; UW-12(d) seamless heads | no default joint: missing joint = input error |
| SH-<course> | UG-27(c)(1),(c)(2), UG-16(b), UG-16(c), UG-25, auto plate selection | P > 0.385SE or t > R/2 (App. 1-2) |
| HD-<pos> | App. 1-4(c) ellipsoidal (any D/2h 1–3), App. 1-4(d) torispherical, UG-32 hemispherical; ts/L ≥ 0.002 | App. 1-4(f), App. 1-3, torispherical geometry limits (FAIL) |
| HD-<pos>-SF | straight flange as cylinder | — |
| NZ-<tag>-UG45 | UG-45 ta/tb1/tb3, access openings ta only | external-pressure parts (tb2) → review flag |
| NZ-<tag>-UG37 | area replacement, Fig. UG-37.1, UG-40 limits, F = 1, radial; P_max of the opening by bisection | d > UG-36(b)(1) limit; head openings off-centre; non-2:1 ellipsoidal heads |
| NZ-<tag>-FLG | P ≤ user-supplied B16.5 rating | rating missing → NOT_EVALUATED |
| NZ-<tag>-UG41 | weld strength | not implemented → NOT_EVALUATED (or external assessment) |
| NZ-UG42 | overlapping limits | overlap → OUT_OF_SCOPE |
| EXT-SHELL | UG-28(c)(1) with user A, B (or A, E) | Do/t < 10 |
| EXT-HD-*-A1/A2 | UG-33(a)(1); A = 0.125/(Ro/t), Pa = B/(Ro/t) | K0 only for 2:1 |
| MAWP | UG-98: min of shells, heads, openings, necks, flange ratings, static head deducted | — |
| TEST-P / TEST-STRESS | UG-99(b) 1.3·MAWP·LSR / UG-100 1.1·MAWP·LSR; informational test stress vs 0.9 Sy | — |
| WT, VOL-REQ | exact-profile weights, capacity | — |
| SUP-REACT / SUP-STRUCT | leg reactions by statics / structural design | SUP-STRUCT not implemented |
| LUG-LOAD / LUG-CHECK / LUG-WELD / LUG-LOCAL | loads; indicative lug plate check with user allowables | weld and WRC local stress not implemented |
| LOAD-* | wind, seismic, piping, transport, snow, thermal | combined stress check (UG-23) not implemented |
| MDMT, PWHT, FATIGUE | UCS-66, UCS-56, UG-22 | user assessment needed; cyclic service OUT_OF_SCOPE |

Geometry/CAD/drawings: vertical vessels on legs. Horizontal vessels, skirts,
saddles, cones, flat heads, jackets: not in v0.1.

## Special configurations

| Configuration | What the engine covers | OUT_OF_SCOPE (state it, do not substitute) |
|---|---|---|
| Vacuum-insulated double-wall cryogenic / LNG tank | inner vessel as a VIII-1 vessel: shell, heads, openings on the head centreline, MAWP, test, weight of the inner vessel | outer jacket (UG-28 external pressure, stiffeners), annular insulation, inner-vessel supports, legs or skirt fixed to the jacket (leave `supports` out of the inner-vessel input), piping between the walls, boil-off and relief sizing |
| Inner vessel cold-stretched (VIII-1 Mandatory Appendix 44) | nothing specific: ordinary VIII-1 rules give a conventional design, thicker than the stretched one | Appendix 44 allowables, stretching procedure and pressure; run the conventional check only when the user accepts it in place of the vendor rule |
| Off-centre head nozzles (hillside, in the knuckle) | — | UG-37 for those openings |
| Vendor drawing marked "for quotation only" | values it states, classified DWG in the source register | dimensions it does not state (typically the inner vessel): ask, never scale from the drawing |

## API 650 module

| Check | Rule | Notes |
|---|---|---|
| API-SCOPE | design conditions vs **user-stated** limits of the part used (basic / Annex F / Annex M) | outside → OUT_OF_SCOPE, nothing else computed |
| API-SH-<n> | td = 4.9D(H−0.3)G/Sd + CA; tt = 4.9D(H−0.3)/St; min thickness table (user-confirmed) | diameter above the 1-foot limit → OUT_OF_SCOPE |
| API-BOTTOM | t ≥ minimum + CA (user-confirmed minimum) | — |
| API-WT | weights, capacity | — |
| roof, wind girders, wind, seismic (Annex E), anchorage, openings, annular plates, settlement | — | OUT_OF_SCOPE in v0.1 |

## External assessments

For checks the software does not implement, a qualified engineer may record
the result under `assessments:` in the input (`result`, `basis`, `by`, `date`,
`status`). Only NOT_EVALUATED / OUT_OF_SCOPE checks accept one; the record
states that the result came from outside the software.
