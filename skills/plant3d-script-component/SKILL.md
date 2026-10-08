---
name: plant3d-script-component
description: Build, test and install custom Python script components for AutoCAD Plant 3D - flanges, gaskets that draw the stud bolts of a joint, valves, strainers, fittings and equipment with their real shape instead of the stock Plant 3D model - and wire them into catalogs and specs so the BOM and isometrics stay right. Use this skill whenever the user mentions Plant 3D custom scripts, the CustomScripts folder, PLANTREGISTERCUSTOMSCRIPTS, testacpscript, varmain or @activate scripts, .pcat catalogs or .pspc/.pspx specs, the Spec Editor, bolts, nuts, washers or gaskets shown in a Plant 3D model, or wants a part to look real in Plant 3D ("tạo script component", "thêm hình dáng thật của valve", "model mặc định của Plant 3D") - even when they do not say the word script.
---

# Plant 3D script components

A Plant 3D catalog part is three separate things, and most mistakes come from mixing them up:

1. **Geometry**: a Python function in the `CustomScripts` folder that builds solids from a handful of
   primitives and declares the ports. It knows nothing about standards or units.
2. **Data**: the dimensions per size, with a note of where each number came from.
3. **Catalog / spec rows**: an SQLite row that names the script (`ContentGeometryTemplate`), passes it a
   parameter string (`ContentGeometryParamDefinition`) and carries the port properties. The bill of
   materials and the isometric are produced from these rows, never from the geometry.

So "make the valve look real" is a geometry job, "list the bolts in the BOM" is a row job, and both lean
on the same data.

## Home of the tools

Everything lives in `C:\ScriptComponents_for_AutoCAD_P3D` (read its `README.md` first; it records what
has been verified in the real program). If that folder is missing, say so and ask - do not rebuild it
from memory.

| Path | Use |
|---|---|
| `CustomScripts/flgcore.py` | shared geometry kit: `xcyl`, `xcone`, `join`, `cut`, `hex_prism`, `hex_nut`, `stud`, `flange_plate`, `joint_bolting`, parameter-block decorators |
| `CustomScripts/FLG_*.py`, `GSK_*.py` | the existing scripts; copy their shape for a new one |
| `tools/check_scripts.py` | imports every script the way the register command does and runs it once |
| `tools/p3demu/` | stand-in for the Plant 3D script API; records solids, booleans and ports |
| `tools/preview_freecad.py`, `tools/p3demu/freecad_build.py` | turn a recorded script into real solids in FreeCAD |
| `deploy.ps1` | copy scripts into the live `CustomScripts` folder |
| `tools/p3d_run.ps1` | run commands in a real Plant 3D session unattended (register, testacpscript, any .scr) |
| `tools/p3d_capture.ps1` | picture of the Plant 3D or Spec Editor window |
| `tools/retrofit_spec.py`, `tools/flgcat/retrofit.py` | switch the rows of a spec to new scripts, keeping everything else |
| `tools/build_catalog.py`, `tools/flgcat/` | build a catalog from `data/<standard>/` |
| `tools/check_spec_opens.ps1` | proves the Spec Editor really loads a spec or catalog |
| `tests/test_all.py` | `python -m unittest discover -s tests` |

All tools are standard-library Python or plain PowerShell; keep it that way (the user shares them with
colleagues who install nothing).

## Workflow

Work through these in order. Each step catches a different class of mistake, and the later ones are
slow, so do not skip the cheap early ones.

### 1. Pin the part down

Before any code, write down: the ports (how many, where, which way they face, which end type: `FL`, `BV`,
`SW`, `THDF`, `SO`, `LAP`, `WF`, `LUG`...), the parameters, and for every dimension where it comes from.
Class each dimension as taken from a standard or drawing, derived, or assumed, and never fill a gap with
a plausible number - a wrong dimension in a catalog is copied into every model that uses it. When two
sources exist, compare them and keep the comparison (see `tools/sources/compile_asme_b16_5.py`).

Look at how the stock catalog models the same kind of part before inventing a layout: open the stock
`.pcat` read-only with `sqlite3` and read a few rows of that class, their ports and their script. Stock
conventions (port positions, parameter meanings, iso `SKEY`) are what the rest of Plant 3D expects.

### 2. Decide which part draws what

Plant 3D does not control how two connected parts are turned against each other about the pipe axis.
Anything that must line up across a joint therefore has to be drawn by **one** part. That is why the stud
bolts, nuts and washers of a flanged joint are drawn by the joint's gasket (`GSK_*`), not half by each
flange: the first version drew half studs per flange and they came out 45 degrees apart on a 4-bolt
flange. A valve or strainer with flanged ends needs no bolt code at all - its joints get their bolts from
the gaskets. Only give a part an orientation-dependent feature when the feature really belongs to that
part (a handwheel, a drain boss).

### 3. Write the script

Start from `assets/script_template.py` in this skill, and read `references/script-api.md` for the
primitives, their axes and the decorators. The conventions that matter:

- The pipe axis is X. Port 1 sits at the origin and looks towards -X; the body grows towards +X.
- No absolute lengths inside a script. Every size is a parameter or a ratio of one, so the same script
  serves inch and millimetre catalogs.
- Every parameter has a default in the `def` line and a `@param` declaration; use `LENGTH0` for a
  dimension that may be zero and switch the feature off at zero.
- Tooltips go into an XML file unescaped: no `<`, `>`, `&` or `"` in them.
- Keep one solid per part (`join`, `cut`) unless there is a reason not to, and keep an eye on the number
  of boolean operations: each costs time when the part is first drawn (about 2 s for 24 detailed studs).
  Offer a detail parameter when detail is expensive.
- Follow the display flag for bores (`ignore_bores()`): Plant 3D draws parts unbored by default.

### 4. Check it without Plant 3D

```bash
python tools/check_scripts.py
```

```bash
python -m unittest discover -s tests
```

`check_scripts.py` also takes the live folder as argument; run it there before registering, because the
register command imports every `.py` in the folder and one broken file silently stops the registration
of all of them. Add a test for the new part to `tests/test_all.py`: run it through the emulator for every
catalog size and assert what must hold (one body, port positions, extents, counts of repeated features).
Testing every size is cheap and has found real data problems.

### 5. Look at it

Build real solids in FreeCAD and look at the picture, next to the user's reference image if there is one:

```bash
"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tools\preview_freecad.py
```

With the FreeCAD MCP server, run the same code through `execute_code` to get a screenshot, and check
`shape.isValid()` and the number of solids. Long boolean chains can outlast the tool call; poll
`get_rpc_status` and fetch the view afterwards.

### 6. Run it in the real program

```bash
powershell -ExecutionPolicy Bypass -File deploy.ps1
```

```bash
powershell -ExecutionPolicy Bypass -File tools\p3d_run.ps1 -Register
```

```bash
powershell -ExecutionPolicy Bypass -File tools\p3d_run.ps1 -Test FLG_WN,GSK_FLAT -SaveAs output\plant3d_test\look.dwg
```

Register and test in two separate runs: a script that was already loaded is only re-read after a
restart. Read `references/plant3d-automation.md` before doing anything beyond these three commands - it
lists the side effects that unattended sessions have had on this machine (dialog settings left off, a
user's project touched) and how the wrapper avoids them. The real program has differed from the emulator
before (parts are drawn unbored by default), so do not report a script as working on emulator evidence
alone.

### 7. Put it in a catalog or spec

Prefer changing existing rows over creating new ones. `tools/retrofit_spec.py` writes a copy of a spec in
which matching rows get the new script and parameters while ids, descriptions, ports, part-use priority
and the branch table stay as they were, and port positions are taken from the old part so models do not
shift. A new kind of part needs a mapping in `tools/flgcat/retrofit.py` (stock script to new script, which
stock parameters to keep). Read `references/catalog-spec-bom.md` for the table layout, how joints pick
gaskets and bolt sets, and what feeds the BOM and the isometric.

Then prove the result loads:

```bash
powershell -ExecutionPolicy Bypass -File tools\check_spec_opens.ps1 "C:\path\to\NEW_SPEC.pspx"
```

The Spec Editor shows its start page instead of an error when it rejects a file, so "no error" proves
nothing; this script looks for the controls that only exist with a file loaded.

### 8. Hand over

Say exactly how far each claim was checked: emulator, FreeCAD solid, `testacpscript` in Plant 3D, Spec
Editor opens the file, part routed in a project, BOM and isometric produced. The last two need a project
and usually the user; give them the few steps to do it and ask for a screenshot. Mention every setting or
file outside the project folder that was changed.

## Adding a valve, strainer or other in-line part

1. Read stock rows of that class first (`Valve` rows carry extra columns such as body type and actuator;
   mirror a stock row rather than guessing them).
2. Model the body between the two port faces. For flanged ends use `flange_plate(s, D, T, FD, FH)` at
   port 1 and a mirrored one at port 2; do not draw bolts. Take the face-to-face length and flange data
   from the standard (for example ASME B16.10 with B16.5 flanges) and record the source.
3. Put anything with a direction (stem, handwheel, lever, drain) along +Z so it points up on a horizontal
   line, as the stock valves do.
4. Keep the stock port positions if the script replaces a stock one in a spec (retrofit), so existing
   models keep their lengths.
5. Give the script `Group="Valve"` (or the group the stock script of that class uses - see
   `references/script-api.md`), register, test, retrofit a spec copy, check it opens.

For equipment and fittings the same steps apply; only the group, the ports and the catalog class differ.

## Reference files

- `references/script-api.md` - primitives and their axes, modifiers, decorators, parameter types, how
  scripts are registered and loaded, emulator coverage. Read when writing or debugging a script.
- `references/plant3d-automation.md` - driving Plant 3D and the Spec Editor unattended, what went wrong
  before, how to leave the user's machine as found. Read before starting any Plant 3D session.
- `references/catalog-spec-bom.md` - `.pcat` / `.pspc` / `.pspx` structure, joints, gaskets, bolt sets,
  BOM and isometric, spec identity in projects. Read before touching a catalog or spec.
- `assets/script_template.py` - starting point for a new script.
