---
name: dwg-text-edit
description: Find and replace text inside AutoCAD .dwg drawings in bulk - drawing numbers, revision / issue marks, dates, project or sheet titles, title-block attribute values - across a whole folder of drawings, safely (backup, working copies, re-open verification, visual check) through AutoCAD's core console. Use this skill whenever the user wants text changed in one or many DWG files, gives a folder of .dwg files together with something to change, or sends a screenshot of a title block with a value to correct - for example "sửa REV", "đổi BD sang DD", "đổi số hiệu bản vẽ", "cập nhật lần phát hành", "sửa khung tên", "sửa ngày trong bản vẽ", "change the revision on all sheets", "rename the drawing number in the title block", "batch edit DWG text" - even when they do not say find and replace. Also use it to find out where a text lives in a set of drawings. Not for geometry edits, plotting, or converting DWG to other formats.
---

# Editing text in DWG drawings

The user has a folder of drawings and wants a piece of text to read differently in all of
them: the drawing number moves from basic design `BD` to detailed design `DD`, the issue goes
from `LẦN 0` to `LẦN 1`, a revision letter or a date changes. Opening a hundred drawings by hand
is slow and error-prone, so the edit is done by AutoCAD's command-line engine
(`accoreconsole.exe`) driven by `scripts/dwgtext.ps1`.

Three facts shape the whole procedure:

- **A DWG cannot be searched from outside.** The file is compressed; only AutoCAD can say where
  a text lives. So every job starts with a *scan*, and the scan result - not a guess - decides
  the rule.
- **What you see on the sheet is not what is stored.** A title block is usually a block: its
  fixed text sits once in the block *definition*, its variable text in *attributes* of the block
  reference. MTEXT carries formatting codes (`\pxqc;{\W0.8;LNGFT-BD-05-DWG-002}`). The same
  words may sit in several blocks, including unused ones.
- **These are deliverables.** A wrong replace across 136 drawings is expensive, so the tool never
  touches the user's files until the edited copies have been re-opened and checked, and it
  always leaves a backup.

## What you need from the user

1. **The folder** that holds the `.dwg` files (subfolders are included).
2. **The change**: what it reads now and what it should read. A screenshot of the title block
   cell is a perfectly good way to say it - read the label and the value from the image.

If the user only says "sửa REV lên 1", that is enough to start: the scan will show what the
revision currently reads. Ask only for what the scan cannot tell you.

## Running the tool

Use the **PowerShell** tool (not Bash: Git Bash rewrites the `/i` `/s` switches AutoCAD needs).
`<skill>` is this skill's base directory.

```powershell
$dt = '<skill>\scripts\dwgtext.ps1'
& $dt inventory -Root 'D:\Project\Isometrics'
```

If scripts are blocked: `powershell -NoProfile -ExecutionPolicy Bypass -File $dt inventory -Root '...'`.
Every action prints a short report; the same text is saved as `summary.txt` in the job's `runs`
folder, and scans also write `all.tsv` with one line per text found.

Rough speed: 0.6 s per drawing for a scan, about 1.2 s for apply plus verification. Give the
tool call a long timeout (up to 10 minutes), and for several hundred drawings run `scan` /
`apply` in the background or one subfolder at a time with `-File 'LNG\*'`.

## Procedure

### 1. Look at the folder - `inventory`

```powershell
& $dt inventory -Root '<folder>'
```

Changes nothing. Read three things from it: how many drawings and in which subfolders, the DWG
format(s), and whether any drawing **looks open in AutoCAD** (`OPEN?` lines). AutoCAD does not
hold a drawing open on disk, so an open drawing can be overwritten - and the user's next save
would then silently undo the edit. Tell the user which files to close; you can carry on with
steps 2-6 meanwhile, only `commit` needs them closed.

### 2. Back up and make working copies - `prepare`

```powershell
& $dt prepare -Root '<folder>'
```

Copies every drawing to `_BACKUP_<time>_<folder name>` next to the folder (hashes checked) and to
a job folder with working copies. It prints the **job folder**; pass it as `-Job` to every later
action. From here on nothing touches the user's folder until `commit`.

When the user wants only part of the folder changed ("chỉ thư mục PCCC"), prepare that
subfolder as the root. It is simpler and safer than remembering `-File 'PCCC\*'` on every later
action - an `apply` without it would edit the other working copies too.

### 3. Find where the text lives - `scan`

```powershell
& $dt scan -Job '<job>' -Text 'LNGFT-BD'
```

`-Text` is a literal fragment, case-insensitive. The report groups identical hits:

```
files  ents  space      block        type   tag  flags text (raw, as stored)
  136   136  BLOCKDEF   Title Block  MTEXT             \pxsm1.2,qc;{\W0.8;LNGFT-BD-05-DWG-002}
Hits per file: 1 hit(s) x136 file(s)
```

- `space` is the layout the text is placed in (`Model`, `Layout1` ...) or `BLOCKDEF` for text
  inside a block definition. `block` is that block, or for an `ATTRIB` the block it belongs to.
- **One row covering every file is the easy case.** Several rows, or files without a hit, mean
  the drawings are not uniform: look at the rows before writing a rule.

When the text is not found, or you need to understand the title block first, look instead of
guessing:

```powershell
& $dt scan -Job '<job>' -Block '*title*' -Sample 3     # everything inside the title block of 3 drawings
& $dt scan -Job '<job>' -Type ATTRIB -Sample 3         # every attribute value
& $dt scan -Job '<job>' -Text 'LẦN'                    # a label next to the value
```

Typical reasons a literal is not found: the visible text is split over several entities, a
formatting code sits in the middle of it, the characters differ (`O`/`0`, a different dash), or
it comes from an xref or a field. `references/troubleshooting.md` covers each.

Other filters: `-Pattern` (AutoCAD wildcard instead of a literal), `-Space`, `-Tag`, `-File`
(a subset by name), `-Top` (more rows).

### 4. Write the rules, then rehearse - `apply -DryRun`

Write a rules file into the job folder (`<job>\rules.json`, UTF-8 - Vietnamese text is fine):

```json
{ "rules": [
  { "match": "contains", "find": "LNGFT-BD-05-DWG-002", "replace": "LNGFT-DD-05-DWG-002",
    "block": "Title Block", "expect": 1 },
  { "match": "exact", "find": "LẦN 0", "replace": "LẦN 1",
    "block": "Title Block", "type": "TEXT", "expect": 1 }
] }
```

- `contains` replaces a fragment and keeps the rest (formatting codes included) - right for a
  distinctive string such as a drawing number.
- `exact` replaces the whole stored text when it equals `find` - the only safe choice for short
  values (`0`, `A`, `R1`): as a fragment, `0` would also hit `\W0.8` and every other zero.
- `any` sets an attribute (it needs a `tag`) whatever it holds now - for "REV becomes C
  everywhere" when the drawings are at different revisions.
- Filters (`block`, `space`, `type`, `tag`, `layer`) pin the rule to what the scan showed. The
  block filter matters more than it seems: templates often carry spare title blocks holding the
  same words.
- `expect` is how many texts the rule must hit **in each drawing**. A drawing where the count is
  different is left completely untouched and reported. Take the number from the scan
  ("1 hit(s) x136 file(s)" -> `1`); it is what stops a rule from quietly doing too much or too
  little.

`references/rules.md` has every field and worked examples (attributes, empty values, several
rules, wildcards).

```powershell
& $dt apply -Job '<job>' -Rules '<job>\rules.json' -DryRun
```

Read the `old -> new` table: every distinct change is listed with the number of drawings. This
is the moment to catch a rule that is too wide - a table with rows you did not intend, or
formatting codes changing (`\W0.8` -> `\W1.8`), means the rule must be narrowed, not applied.

### 5. Apply and verify - `apply`

```powershell
& $dt apply -Job '<job>' -Rules '<job>\rules.json'
```

Edits the working copies, saves each in its original DWG format, then re-opens every saved
drawing and checks that the texts read as written, that no entity appeared or vanished, and that
the format is unchanged. `MISMATCH` and `ERROR` drawings were not saved; find out why (scan
those files with `-File`) rather than loosening `expect` blindly. `reset -Job` throws the edits
away if you need to start over.

### 6. Look at one - `preview`

```powershell
& $dt preview -Job '<job>'            # first changed drawing; -File / -Handle to choose
```

Plots the drawing to PNG: a full sheet and a zoom on the changed text. **Read the zoom image.**
The data check in step 5 cannot see that the new text is longer and now runs over a border, or
that the edited text is not the one visible on the sheet. If the drawings come from different
templates or subfolders, preview one of each.

### 7. Write the result back - `commit`

```powershell
& $dt commit -Job '<job>'
```

Copies the verified working copies over the originals. A drawing is skipped (and listed) when
it looks open, is read-only, or was changed by someone since `prepare`. The user's request is
the go-ahead to commit; stop and ask first only when the scan or the dry run showed something
they did not describe - several candidate texts, drawings that differ, skipped files.

Finish with a scan for the old value; it should find nothing:

```powershell
& $dt scan -Job '<job>' -Text 'LNGFT-BD'
```

### 8. Tell the user

Answer in the user's language, briefly: what now reads what, in how many drawings (per subfolder
if there are several), that the result was re-opened and checked, where the backup is, and
anything skipped or left for them - a file that was open, text that is a field, and names that
still carry the old value (the tool edits text *inside* drawings; file and folder names are not
renamed unless asked). `restore -Job` puts the originals back if they want to undo.

## What the tool will not edit

The scan flags these and `apply` refuses them rather than doing something fragile:

| Flag | Meaning | What to do |
|---|---|---|
| `F` | a field: the text is computed | change the source (drawing property, sheet set, file name) |
| `X` | dimension, multileader or table text | report it; the user edits it in AutoCAD |
| `MX` | multiline attribute with its own formatting | same |
| xref line | text belongs to an attached drawing | run the job on the xref file itself, once |

`L` (locked layer) and `M` (plain multiline attribute) are handled. Details and less common
situations: `references/troubleshooting.md`.

## Ground rules

- Go through the tool, not hand-written AutoCAD scripts. Core-console scripts that set system
  variables (`FILEDIA`, `CMDDIA` ...) change the user's AutoCAD profile permanently, and a bare
  `QSAVE` silently converts an older drawing to the newest DWG format.
- `-Force` on `commit` / `restore` overrides the open / read-only / changed-since checks. Use it
  only when the user has said so for those files.
- The backup folder and the job folder (under `%LOCALAPPDATA%\dwg-text-edit`) are the user's
  to delete once they are happy; mention them, do not remove them.
- After changing `dwgtext.ps1` or `dwgtext.lsp`, or on a machine where the tool has not run
  before, run `scripts\selftest.ps1`: it builds its own drawings and checks the whole chain.
