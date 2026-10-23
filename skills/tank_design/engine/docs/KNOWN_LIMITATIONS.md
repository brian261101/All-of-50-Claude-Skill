# Known limitations (v0.1.0)

## Data and verification
- **No licensed code text was used.** The 56 register entries ship
  UNVERIFIED (except the two non-code entries for project requirements and
  plain statics); clause letters (e.g. UG-32(d)/(e)/(f)) are as cited by the public
  sources and must be confirmed for the project edition.
- **Material data is representative.** The bundled database (10 grades) is
  REPRESENTATIVE_EXAMPLE, converted from an MIT educational repository; its
  values differ from other public summaries in places. Verified records must
  be supplied per project.
- Table UG-45 values are derived (0.875 × STD wall); the derivation itself is unverified.
- Pipe dimensions (B36.10M subset) and the demo flange data (B16.5) are unverified.
- Flange P-T ratings, external-pressure chart factors (A, B, E), MDMT and PWHT
  determinations are user inputs; nothing approximates them.
- PV Elite comparison: harness only; no licensed results were available.
- The vendor test suite of the MIT library was not executed (auto-mode policy
  on downloaded code); its code was reviewed statically.

## ASME VIII-1 scope not implemented
- Thick shells/heads (App. 1-2, 1-3), heads with ts/L < 0.002 (App. 1-4(f)).
- Conical sections, flat heads/covers (UG-34), Appendix 2 flanges, bolting
  calculations, tubesheets, jackets, stiffening rings.
- Openings: large openings (App. 1-7), hillside/off-centre head nozzles,
  multiple-opening rules (UG-42 overlap → OUT_OF_SCOPE), weld strength (UG-41)
  and UW-16 weld sizing (weld areas are counted as zero when not given).
- External pressure for nozzle necks (UG-45 tb2); combined loads UG-22/UG-23
  (wind, seismic, nozzle loads) — values can be entered but no stress check is made.
- Supports and lugs: only loads; leg buckling, base plate, local shell stress
  (WRC 537), lug welds are not implemented (external assessment possible).
- MDMT (UCS-66), PWHT (UCS-56), fatigue: assessments from the user only.
- Test stress screening uses 0.9 × minimum yield at room temperature and is
  informational.

## API 650 scope not implemented
Variable-design-point method, roofs, wind girders, wind/seismic (Annex E),
anchorage, openings, annular plates, settlement, Annex F/M details; all API 650
constants are project inputs. No geometry, CAD, drawings or BOM for tanks.

## Geometry, CAD, drawings
- Vertical vessels on pipe legs only; no skirts, saddles, horizontal vessels.
- Model is regenerated from `design_geometry.json` (not a FreeCAD feature-tree
  parametric model); outer surface of ellipsoidal heads is the exact normal
  offset represented by an interpolated B-spline.
- Flanges are simplified weld-neck/blind solids from the input dimensions;
  gaskets and bolting are not modelled; legs are tangent to the shell (no
  pads/gussets); weld beads are not modelled.
- Exact hidden-line removal stalls on the B-spline head surfaces on this
  machine; views use polygonal HLR (OCP `HLRBRep_PolyAlgo`, TechDraw
  `CoarseView`) — fine at drawing scale, not exact edges.
- Drawings show no weld symbols, bevels, tolerances, surface finish or NDE
  marks because the input does not define them. GA views are labelled with
  their viewing direction rather than laid out in strict projection.
- The TechDraw page carries views only; dimensions are on the ezdxf sheets.
- MCP calls return "Request timed out" after about a minute even when FreeCAD
  completes; steps are split and completion is read from files.

## Process
- The release gate stops at CALCULATION_VERIFIED; engineering review and
  approval are human acts recorded outside the software.
- The calculation report is generated in English, SI units.
