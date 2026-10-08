---
name: Equipment_tech
description: Build a parametric 3D CAD model of the Triumph VQLNG-2000/16 Ambient Air Vaporizer (AAV), capacity 2000 Sm3/h, from the supplied engineering drawing. Use the drawing as the primary source of truth, preserve shown geometry and dimensions, separate exact/inferred/TBD dimensions, and perform geometry, dimension, orientation, and collision checks before producing the CAD model and inspection views.
---

# AAV VQLNG-2000/16 — Text-to-CAD Skill

## Purpose

Use this skill to create a technical 3D model of the Ambient Air Vaporizer (AAV):

- Model: VQLNG-2000/16
- Capacity: 2000 Sm3/h
- Fluid: LNG/NG
- Design pressure: 1.6 MPa
- Test pressure: 1.76 MPa
- MDMT: -196 °C
- Design temperature: 50 °C
- Design code: ASME Section VIII Division 1, 2023
- Serial: F25-836
- Year built: 2025

The supplied engineering drawing is the primary source of truth.

## Critical modeling rules

1. Read and inspect the supplied drawing before modeling.
2. Do not invent dimensions.
3. Do not silently replace a drawing value with a generic industry value.
4. If a dimension cannot be read reliably, create a parameter named `TBD_FROM_DRAWING`.
5. Clearly classify dimensions as:
   - EXACT_DRAWING
   - INFERRED
   - TBD_FROM_DRAWING
   - ASSUMPTION
6. Model the equipment as a component-based assembly, not as one generic solid.
7. Use millimetres for geometry.
8. Preserve the drawing proportions and component arrangement.
9. This is an engineering/layout model, not a fabrication-certified model.
10. Before finalizing, run geometry, dimension, orientation and collision checks.

## Main geometry

Create these components:

- AAV_2000
- FRAME
- LOWER_HEADER
- UPPER_HEADER
- TUBE_BUNDLE
- FIN_SYSTEM
- NOZZLE_N1
- NOZZLE_N2
- TOP_CONNECTIONS
- LIFTING_LUG_L
- LIFTING_LUG_R
- SUPPORT

The equipment is a vertical ambient vaporizer with:

- vertical finned tubes
- upper header
- lower header
- process nozzles
- structural frame/support
- top lifting lugs
- finned heat-transfer surfaces

## Known drawing values to verify

Use these values only after confirming their position and meaning on the supplied drawing:

- Fin OD: Ø200 mm
- Tube: Ø33.5 × 4 mm
- Lifting lug detail: Ø90 × 8 mm
- Drawing dimensions include approximately:
  - 6200
  - 7075
  - 715
  - 515
  - 800
  - 450
  - 350
  - 184
  - 197
  - 1953
  - 2053
  - 2208
- Tube/module indication: 6 × 239 = 1434
- Offset indication: approximately 259.5
- Bottom structural member indication: 500 × 200
- Other shown sections include approximately:
  - Ø25 × 3.5
  - Ø48.3 × 3.68
  - Ø50 × 5
  - Ø88.9 × 5.49
  - Ø90 × 8

These are not automatically fabrication dimensions. Verify against the drawing before hard-coding.

## Parametric variables

Create a parameter block similar to:

```text
AAV_CAPACITY = 2000
DESIGN_PRESSURE = 1.6
TEST_PRESSURE = 1.76
MDMT = -196
DESIGN_TEMPERATURE = 50

TUBE_OD = 33.5
TUBE_WALL = 4.0
FIN_OD = 200
LIFTING_LUG_OD = 90

TUBE_LENGTH = TBD_FROM_DRAWING
TUBE_COUNT = TBD_FROM_DRAWING
TUBE_PITCH = TBD_FROM_DRAWING
ROW_COUNT = TBD_FROM_DRAWING
HEADER_SIZE = TBD_FROM_DRAWING
OVERALL_HEIGHT = TBD_FROM_DRAWING
```

## Coordinate system

Use:

- X = left/right width of tube bundle
- Y = equipment depth
- Z = vertical direction
- Z=0 = bottom support reference plane
- Origin = equipment center/reference point

Create a clear centerline/reference axis.

Keep N1 and N2 orientation explicit.

## Modeling sequence

Follow this order:

1. Inspect drawing.
2. Extract geometry and dimensions.
3. Create skeleton/reference geometry.
4. Create bottom frame/support.
5. Create lower header.
6. Create tube pattern.
7. Create fin system.
8. Create upper header.
9. Create N1.
10. Create N2.
11. Create top connections.
12. Create lifting lugs.
13. Add secondary structural members.
14. Build assembly hierarchy.
15. Add metadata.
16. Validate geometry.
17. Validate dimensions.
18. Validate orientation.
19. Run collision checks.
20. Generate inspection views.
21. Export the requested CAD formats.

## Tube bundle requirements

Do not represent the tube bundle as one featureless solid.

Create a parametric pattern containing:

- tube OD
- tube wall thickness
- fin OD
- tube pitch
- tube count
- row count
- tube length

Each tube/fin module should remain editable when the CAD system permits.

## Headers and nozzles

Create upper and lower headers according to the drawing.

Create N1 and N2 only where shown.

Do not add extra process nozzles.

Verify:

- nozzle position
- nozzle direction
- nozzle diameter
- connection type
- elevation
- relationship to frame and headers

## Materials

Where readable from the supplied drawing/BOM, preserve the specified material information.

Known drawing material information includes:

- Fin tube: SB-221 A96063-T5, thickness 4 mm
- Aluminium flange: SB-247 A96061-T6
- Cover plate: SB-247 A96061-T6
- Aluminium pipe: SB-241 A96061-T6
- SS flange: SA-182M F304, Class 300, Sch 40S

Do not infer material for items whose material cannot be established from the drawing.

## Metadata

Attach to the main assembly:

```text
Equipment_Type = Ambient Air Vaporizer
Model = VQLNG-2000/16
Capacity = 2000 Sm3/h
Fluid = LNG/NG
Design_Pressure = 1.6 MPa
Test_Pressure = 1.76 MPa
MDMT = -196 C
Design_Temperature = 50 C
Design_Code = ASME VIII Div.1 2023
Serial_Number = F25-836
Year_Built = 2025
```

## Validation

### Geometry

Check:

- all major components exist
- tubes connect correctly to headers
- N1/N2 are on the correct sides
- lifting lugs connect correctly to the top structure
- supports do not pass through tube bundles

### Dimensions

Check:

- overall height
- overall width
- tube bundle width/depth
- header spacing
- N1/N2 elevations
- base width
- top structure dimensions

### Collision

Check:

- tube ↔ tube
- tube ↔ header
- tube ↔ frame
- nozzle ↔ frame
- lifting lug ↔ top structure

### Views

Generate:

- front
- rear
- left
- right
- top
- isometric

## Final report

Return a report containing:

1. Exact drawing dimensions used
2. Inferred dimensions
3. TBD dimensions
4. Modeling assumptions
5. Component list
6. Tube count and pattern
7. Nozzle locations
8. Overall envelope
9. Collision-check result
10. Exported file names/formats

## Final instruction

Do not claim the model is fabrication-ready.

The final model must be traceable to the supplied drawing, and every uncertain dimension must remain explicitly identified rather than silently guessed.
