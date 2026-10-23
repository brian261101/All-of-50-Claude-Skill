# Source register — <PROJECT_ID> / <TAG>

Written at workflow step 0, before the input file. Every value that goes into
`vessel_input.yaml` (or `tank_input.yaml`) appears here with its source.

## Documents

| Ref | Document | Number / revision / date | Status stated on it | Read on |
|---|---|---|---|---|
| D1 | e.g. vendor drawing | SQF-… Rev 0, 2026-06-05 | "for quotation only" | YYYY-MM-DD |
| U1 | figures typed by the user in chat | — | — | YYYY-MM-DD |

## Source classes

`DWG` drawing · `DATASHEET` · `SPEC` specification · `USER` typed by the user ·
`INFERRED` read from a view / P&ID, not written as a number (to confirm) ·
`USER_ASSUMPTION` chosen by the user as an assumption · `NOT_SUPPLIED`.

## Values

| Input field | Value | Class | Ref (sheet / table / note) | Remark |
|---|---|---|---|---|
| process.design_pressure | 0.95 MPa(g) | DWG | D1 data sheet | MAWP 0.80 MPa on the same sheet |
| geometry.diameter | none | NOT_SUPPLIED | — | D1 dimensions the jacket only |

## Conflicts between sources

| Field | Source A | Source B | Used | Why |
|---|---|---|---|---|
| process.design_pressure | U1: 0.8 MPa | D1: 0.95 MPa | D1 | primary document wins (rule 8) |

## Standards cited by the documents

| Standard (edition) | Where cited | Class (`references/standards-references.md`) | Consequence |
|---|---|---|---|
| ASME VIII-1 2025 | D1 data sheet | IMPLEMENTED (subset) | — |
| ASME VIII-1 App. 44 | D1 data sheet | OUT_OF_SCOPE | conventional-rules check only, if the user accepts |
