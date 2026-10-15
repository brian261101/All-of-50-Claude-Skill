# Code-family routing rules

## ASME VIII-1 pressure vessel route

Use only when the equipment and service are within the scope of the specified ASME BPVC Section VIII Division 1 edition and project requirements. Confirm:
- exact edition/addenda and jurisdiction;
- material specification, product form and temperature-dependent properties from an authorized source;
- joint efficiency / weld category / NDE and applicable fabrication assumptions;
- internal pressure, external pressure/vacuum, temperature, loads and required load cases;
- applicable design rules for shell, heads, openings, flanges, supports and attachments.

Do not implement a formula from memory without a verified reference. Do not infer allowable stress from yield strength. Do not assume a simple thickness check covers all code requirements.

## API 650 storage tank route

Use only when tank type, pressure range, temperature, geometry and service fall within the selected API 650 edition's scope. Confirm:
- exact edition/addenda and client / jurisdiction requirements;
- tank diameter, height, roof type, bottom/annular details and shell courses;
- material group / product form and permitted source data;
- product level/density, corrosion allowance, design and hydrostatic cases;
- wind, seismic, anchorage, settlement and other applicable checks;
- weld, inspection, testing and foundation interfaces.

Do not substitute pressure-vessel equations for tank rules or vice versa.

## Route selection must fail closed

If scope is unclear or the equipment is outside the selected standard:
- status = `BLOCKED`;
- list the exact unresolved scope question;
- ask the user / responsible engineer to select the governing standard;
- do not generate a code-compliance claim.

API 620, ASME VIII Division 2, EN 13445, PD 5500 and local regulations are not implicitly supported by this default package.
