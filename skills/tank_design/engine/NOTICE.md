# Third-party notices

## LaelaZorana/asme-viii-pressure-vessel (MIT)

Copyright (c) 2026 Laela Zorana. Permission is hereby granted, free of charge,
to any person obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, subject to the condition that
the above copyright notice and this permission notice are included in all
copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS
IS", WITHOUT WARRANTY OF ANY KIND.

Used here (commit 24c20bb0c707):
- `data/materials_sec_ii_d_representative.csv` → converted to
  `data/materials/material_db.json` (REPRESENTATIVE_EXAMPLE records) by
  `tools/build_material_db.py`;
- `data/pipe_schedules.csv` → part of `data/pipe/pipe_dimensions.json`;
- the published example results → `data/benchmarks/laela_zorana_us_units.json`
  (cross-implementation benchmark);
- symbol conventions of the UG-37 area bookkeeping. No source file is copied.

## ry4ngch/ASME-PVDE (GPL-3.0)

Audited statically only (`tools/audit_vendor_workbook.py`). No code, formula
cell or data from it is included in this project.

## Python packages used at run time (not vendored)
PyYAML (MIT), openpyxl (MIT), ezdxf (MIT), PyMuPDF (AGPL-3.0 or commercial —
used to render the report and drawing PDFs; review its licence before
distributing outside the company), cadquery-ocp / OpenCASCADE (LGPL-2.1 with
exception), FreeCAD (LGPL-2.0+).
