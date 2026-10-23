"""Static audit of an Excel/VBA workbook (.xlsm) for docs/SOURCE_AUDIT.md.

Nothing in the workbook is executed: sheets and formulas are read with
openpyxl, and the VBA project is read as data (OLE compound file + MS-OVBA
decompression, both implemented here) so module names and source text can be
grepped for formulas and code paragraph citations.

Usage:
    python -I tools/audit_vendor_workbook.py <workbook.xlsm> [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# OLE compound file (MS-CFB) reader, read-only and minimal
# ---------------------------------------------------------------------------

class OleFile:
    ENDOFCHAIN = 0xFFFFFFFE
    FREESECT = 0xFFFFFFFF

    def __init__(self, data: bytes):
        if data[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise ValueError("not an OLE compound file")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 0x1E)[0]
        self.mini_size = 1 << struct.unpack_from("<H", data, 0x20)[0]
        n_fat = struct.unpack_from("<I", data, 0x2C)[0]
        dir_start = struct.unpack_from("<I", data, 0x30)[0]
        self.mini_cutoff = struct.unpack_from("<I", data, 0x38)[0]
        minifat_start = struct.unpack_from("<I", data, 0x3C)[0]
        difat_start = struct.unpack_from("<I", data, 0x44)[0]
        n_difat = struct.unpack_from("<I", data, 0x48)[0]

        difat = list(struct.unpack_from("<109I", data, 0x4C))
        sect = difat_start
        for _ in range(n_difat):
            vals = struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(sect))
            difat.extend(vals[:-1])
            sect = vals[-1]
        fat_sectors = [s for s in difat if s not in (self.FREESECT, self.ENDOFCHAIN)][:n_fat]
        self.fat: list[int] = []
        for s in fat_sectors:
            self.fat.extend(struct.unpack_from(f"<{self.sector_size // 4}I", self._sector(s)))

        dir_bytes = self._chain(dir_start)
        self.entries = []
        for i in range(len(dir_bytes) // 128):
            e = dir_bytes[i * 128:(i + 1) * 128]
            name_len = struct.unpack_from("<H", e, 64)[0]
            name = e[:max(name_len - 2, 0)].decode("utf-16-le", "replace")
            etype = e[66]
            left, right, child = struct.unpack_from("<III", e, 68)
            start = struct.unpack_from("<I", e, 116)[0]
            size = struct.unpack_from("<Q", e, 120)[0]
            self.entries.append(dict(name=name, type=etype, left=left, right=right,
                                     child=child, start=start, size=size))
        root = self.entries[0]
        self.ministream = self._chain(root["start"])[:root["size"]]
        self.minifat: list[int] = []
        if minifat_start != self.ENDOFCHAIN:
            mf = self._chain(minifat_start)
            self.minifat = list(struct.unpack_from(f"<{len(mf) // 4}I", mf))

    def _sector(self, n: int) -> bytes:
        off = (n + 1) * self.sector_size
        return self.data[off:off + self.sector_size]

    def _chain(self, start: int) -> bytes:
        out, s, guard = [], start, 0
        while s not in (self.ENDOFCHAIN, self.FREESECT) and guard < 10_000_000:
            out.append(self._sector(s))
            s = self.fat[s]
            guard += 1
        return b"".join(out)

    def _mini_chain(self, start: int, size: int) -> bytes:
        out, s = [], start
        while s not in (self.ENDOFCHAIN, self.FREESECT):
            off = s * self.mini_size
            out.append(self.ministream[off:off + self.mini_size])
            s = self.minifat[s]
        return b"".join(out)[:size]

    def paths(self) -> dict[str, dict]:
        """Map 'storage/stream' paths to directory entries (red-black tree walk)."""
        result: dict[str, dict] = {}

        def walk(idx: int, prefix: str):
            if idx == self.FREESECT or idx >= len(self.entries):
                return
            e = self.entries[idx]
            walk(e["left"], prefix)
            path = f"{prefix}{e['name']}"
            result[path] = e
            if e["type"] in (1, 5):  # storage or root
                walk(e["child"], path + "/" if e["type"] == 1 else "")
            walk(e["right"], prefix)

        walk(0, "")
        return result

    def read(self, entry: dict) -> bytes:
        if entry["size"] < self.mini_cutoff:
            return self._mini_chain(entry["start"], entry["size"])
        return self._chain(entry["start"])[:entry["size"]]


# ---------------------------------------------------------------------------
# MS-OVBA decompression (section 2.4.1)
# ---------------------------------------------------------------------------

def ovba_decompress(buf: bytes) -> bytes:
    if not buf or buf[0] != 0x01:
        raise ValueError("bad compressed container signature")
    out = bytearray()
    pos = 1
    while pos < len(buf):
        header = struct.unpack_from("<H", buf, pos)[0]
        chunk_size = (header & 0x0FFF) + 3
        compressed = header & 0x8000
        chunk_end = min(pos + chunk_size, len(buf))
        pos += 2
        chunk_start = len(out)
        if not compressed:
            out.extend(buf[pos:pos + 4096])
            pos += 4096
            continue
        while pos < chunk_end:
            flags = buf[pos]
            pos += 1
            for bit in range(8):
                if pos >= chunk_end:
                    break
                if not (flags >> bit) & 1:
                    out.append(buf[pos])
                    pos += 1
                else:
                    token = struct.unpack_from("<H", buf, pos)[0]
                    pos += 2
                    diff = len(out) - chunk_start
                    bit_count = max((diff - 1).bit_length(), 4)
                    length_mask = 0xFFFF >> bit_count
                    offset = (token >> (16 - bit_count)) + 1
                    length = (token & length_mask) + 3
                    for _ in range(length):
                        out.append(out[-offset])
    return bytes(out)


def vba_modules(ole: OleFile) -> dict[str, str]:
    """Return {module name: source text} from the VBA project."""
    paths = ole.paths()
    dir_key = next((p for p in paths if p.upper().endswith("VBA/DIR")), None)
    if dir_key is None:
        return {}
    prefix = dir_key[: -len("dir")]
    d = ovba_decompress(ole.read(paths[dir_key]))
    modules, pos, current = [], 0, {}
    while pos + 6 <= len(d):
        rid, size = struct.unpack_from("<HI", d, pos)
        pos += 6
        if rid == 0x0009:  # PROJECTVERSION: "size" is a reserved 4, payload is 4+2 bytes
            size = 6
        payload = d[pos:pos + size]
        pos += size
        if rid == 0x0019:
            current = {"name": payload.decode("latin-1")}
        elif rid == 0x001A:
            current["stream"] = payload.decode("latin-1")
        elif rid == 0x0031:
            current["offset"] = struct.unpack_from("<I", payload)[0]
        elif rid == 0x002B:
            modules.append(current)
            current = {}
    out = {}
    for m in modules:
        key = prefix + m.get("stream", m.get("name", ""))
        if key not in paths:
            continue
        raw = ole.read(paths[key])
        try:
            out[m["name"]] = ovba_decompress(raw[m.get("offset", 0):]).decode("latin-1")
        except Exception as exc:  # noqa: BLE001 - audit tool, record and continue
            out[m["name"]] = f"<<decompression failed: {exc}>>"
    return out


# ---------------------------------------------------------------------------
# Workbook audit
# ---------------------------------------------------------------------------

CODE_REF = re.compile(r"\b(U[GWCHN][A-Z]?-\d+[A-Za-z0-9().]*|Appendix\s+\d+[-\d]*|App\.?\s*\d+-\d+"
                      r"|Table\s+[A-Z]{1,3}-?\d+[A-Z0-9.\-]*|Fig\.?\s*[A-Z]{1,3}-\d+[A-Z0-9.\-]*)")


def audit(path: Path) -> dict:
    import openpyxl  # read-only data parsing; macros are never run

    report: dict = {"file": str(path), "size_bytes": path.stat().st_size}
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_vba=False)
    sheets = []
    for ws in wb.worksheets:
        n_formula, n_values, refs, samples = 0, 0, Counter(), []
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if v is None:
                    continue
                if isinstance(v, str) and v.startswith("="):
                    n_formula += 1
                    if len(samples) < 12 and len(v) > 25:
                        samples.append(f"{c.coordinate}: {v[:160]}")
                else:
                    n_values += 1
                    if isinstance(v, str):
                        refs.update(CODE_REF.findall(v))
        sheets.append(dict(name=ws.title, formulas=n_formula, values=n_values,
                           code_refs=dict(refs.most_common(15)), formula_samples=samples))
    report["sheets"] = sheets
    wb.close()

    with zipfile.ZipFile(path) as z:
        vba_name = next((n for n in z.namelist() if n.lower().endswith("vbaproject.bin")), None)
        if vba_name:
            ole = OleFile(z.read(vba_name))
            mods = vba_modules(ole)
            report["vba_modules"] = {
                name: dict(lines=src.count("\n"),
                           procedures=re.findall(r"^(?:Public |Private )?(?:Function|Sub)\s+(\w+)",
                                                 src, re.M)[:40],
                           code_refs=dict(Counter(CODE_REF.findall(src)).most_common(12)))
                for name, src in mods.items()
            }
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workbook", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--dump-vba", type=Path, help="directory to write decompressed VBA modules")
    args = ap.parse_args(argv)
    rep = audit(args.workbook)
    if args.dump_vba:
        args.dump_vba.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.workbook) as z:
            name = next(n for n in z.namelist() if n.lower().endswith("vbaproject.bin"))
            for mod, src in vba_modules(OleFile(z.read(name))).items():
                (args.dump_vba / f"{mod}.bas").write_text(src, encoding="utf-8")
    text = json.dumps(rep, indent=1, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
