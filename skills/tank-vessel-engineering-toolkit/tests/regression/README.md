# Regression test policy

Do not add guessed numerical “expected answers”. For each real code module, add an independently checked reference case with:
- exact standard and edition;
- permitted source / clause reference;
- all inputs and units;
- intermediate values and final expected results;
- reviewer and date;
- tolerances / rounding basis;
- test provenance and permission to store the example.

A regression test is required before the module may be marked `VERIFIED`. Until then it must remain `BLOCKED` or `PRELIMINARY`.
