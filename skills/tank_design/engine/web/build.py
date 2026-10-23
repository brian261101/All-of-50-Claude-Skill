"""Build the web calculator (static site) from the skill's design request form
and the pv_design engine.

    python pv_design/web/build.py [--out DIR]      (default pv_design/web/dist)

dist/index.html   the form (templates/design-request-form.html) + the calculation section
dist/js/calc.js   glue: form -> engine (Pyodide) -> PDF (pdfmake) -> handoff zip
dist/engine.json  the engine files used by steps 1-8 (handoff.engine_files) and their fingerprint

The calculation is never reimplemented in JavaScript: the page runs these
same Python files, and `pv.py resume` proves it by recomputing the hashes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent
PV = WEB.parent
sys.path.insert(0, str(PV / "src"))

from pressure_vessel import __version__  # noqa: E402
from pressure_vessel.handoff import engine_files, engine_fingerprint  # noqa: E402

# the form lives in the skill; the engine is either pv_design/ next to .claude/ or the skill's engine/
FORM = next((p for p in (PV.parent / ".claude" / "skills" / "tank_design" / "templates" / "design-request-form.html",
                         PV.parent / "templates" / "design-request-form.html") if p.is_file()), None)
LIBS = ["https://cdn.jsdelivr.net/npm/pdfmake@0.2.23/build/pdfmake.min.js",
        "https://cdn.jsdelivr.net/npm/pdfmake@0.2.23/build/vfs_fonts.js",
        "https://cdn.jsdelivr.net/npm/html-to-pdfmake@2.5.34/browser.js"]
TITLE = "Tính toán thiết kế bình & bồn"
CSS = """
body{margin:0}
.steps{list-style:none;padding:0;margin:8px 0 12px;display:flex;flex-direction:column;gap:5px;font-size:14px}
.steps li{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.steps .dot{width:10px;height:10px;border-radius:50%;border:2px solid var(--rule);flex:0 0 auto;transform:translateY(1px)}
.steps .s-run .dot{border-color:var(--accent);background:var(--accent-soft)}
.steps .s-ok .dot{border-color:var(--ok);background:var(--ok)}
.steps .s-warn .dot{border-color:var(--req);background:var(--req-soft)}
.steps .s-bad .dot{border-color:var(--req);background:var(--req)}
.steps .s-wait{color:var(--ink-2)}
.steps .sn{font-family:var(--f-mono);font-size:12px;color:var(--ink-2)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:6px 0 10px}
.kpi{border:1px solid var(--rule);border-radius:5px;padding:10px 12px;background:var(--paper)}
.kpi .kl{display:block;font-size:12px;color:var(--ink-2);text-transform:uppercase;letter-spacing:.5px}
.kpi b{font-family:var(--f-head);font-size:20px;font-weight:700;overflow-wrap:anywhere}
.st-ok{color:var(--ok)} .st-warn{color:var(--req)} .st-bad{color:var(--req)}
.counts{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px}
.badge{display:inline-block;font-family:var(--f-mono);font-size:11.5px;padding:2px 7px;border-radius:4px;border:1px solid var(--rule);white-space:nowrap}
.b-ok{color:var(--ok);border-color:var(--ok)} .b-bad{color:var(--sheet);background:var(--req);border-color:var(--req)}
.b-warn{color:var(--req);border-color:var(--req)} .b-mute{color:var(--ink-2)}
#calcDetail h3{margin:14px 0 4px}
#calcDetail ul{margin:4px 0 8px;padding-left:20px;font-size:13.5px}
#calcDetail ul.errs li{color:var(--req)}
#calcDetail details{margin:8px 0}
#calcDetail summary{cursor:pointer;font-weight:600}
.tw{overflow-x:auto}
table.rec{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
table.rec th,table.rec td{border-bottom:1px solid var(--rule-2);padding:4px 6px;text-align:left;vertical-align:top}
.btn:disabled{opacity:.5;cursor:not-allowed}
"""


def _replace(s: str, old: str, new: str) -> str:
    if old not in s:
        raise SystemExit(f"build.py: the form template changed, cannot find {old[:60]!r}")
    return s.replace(old, new, 1)


def build_index(form: str) -> str:
    head, body = form.split('<div class="page">', 1)
    head = _replace(head, "<title>Phiếu yêu cầu thiết kế bình & bồn</title>", f"<title>{TITLE}</title>")
    head = _replace(head, "</style>", CSS.strip() + "\n</style>")
    head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    body = '<div class="page">' + body
    body = _replace(body, "<h1>Phiếu yêu cầu thiết kế bình &amp; bồn</h1>", f"<h1>{TITLE.replace('&', '&amp;')}</h1>")
    body = _replace(body, "Điền dữ liệu đầu vào cho skill",
                    "Công cụ chạy bước 1–8 của skill <code>tank-vessel-design</code>: điền phiếu, bấm “Tính toán”, "
                    "nhận calculation PDF và một gói <code>.zip</code> để Claude Code làm tiếp bước 9–12 "
                    "(FreeCAD, bản vẽ 2D, BOM, gói hồ sơ). Điền dữ liệu đầu vào cho skill")
    calc = (WEB / "calc_section.html").read_text(encoding="utf-8")
    body = _replace(body, '    <section class="card out" id="sec-out"', calc + '    <section class="card out" id="sec-out"')
    body = _replace(body, """'<li><a href="#sec-out">Kết quả</a></li>'""",
                    """'<li><a href="#sec-calc">Tính toán và xuất file</a></li><li><a href="#sec-out">File đầu vào</a></li>'""")
    body = _replace(body, '<h2 id="hOut">Kết quả: file đầu vào cho skill</h2>',
                    '<h2 id="hOut">File đầu vào (để lưu riêng nếu cần)</h2>')
    body = body.replace("pvform.draft.v1", "pvcalc.draft.v1")
    scripts = "".join(f'<script src="{u}" defer></script>\n' for u in LIBS) + '<script src="js/calc.js" defer></script>\n'
    return ('<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="description" content="ASME VIII-1 / API 650 design calculation in the browser with the pv_design engine '
            '(tank-vessel-design skill): calculation PDF and a handoff zip for Claude Code.">\n'
            + head + "</head>\n<body>\n" + body.rstrip() + "\n" + scripts + "</body>\n</html>\n")


def build_engine() -> dict:
    files = engine_files()
    out = [{"path": rel, "text": p.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")} for rel, p in files]
    return {"name": "pressure_vessel", "version": __version__, "fingerprint": engine_fingerprint(files),
            "files": out}


README = """# Tank / vessel design calculator (web)

Static page that runs steps 1-8 of the `tank-vessel-design` Claude Code skill in the browser:
design request form → input validation → design basis → ASME VIII-1 / API 650 calculation →
verification → release gate → calculation PDF, plus a handoff zip.

The calculation is the skill's own Python engine (`pv_design`, version {version}, fingerprint
`{fp}`), run by Pyodide; nothing is reimplemented in JavaScript and no data leaves the browser.

Give the handoff zip to Claude Code with the skill installed and say "use /tank_design to continue
from this handoff". It runs `python pv_design/pv.py resume <zip> --out pv_design/output/<ID>`, recomputes
locally, checks every hash and only then continues with step 9 (FreeCAD model through the MCP),
10 (2D drawings and BOM), 11 (consistency) and 12 (package).

Results are preliminary engineering calculations, never fabrication-ready: the highest stage the
software can reach is CALCULATION_VERIFIED, and release needs review and signature by a qualified engineer.

Built by `pv_design/web/build.py`; do not edit the files here by hand.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=WEB / "dist")
    a = ap.parse_args(argv)
    out = a.out
    (out / "js").mkdir(parents=True, exist_ok=True)
    eng = build_engine()
    (out / "index.html").write_text(build_index(FORM.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    shutil.copyfile(WEB / "calc.js", out / "js" / "calc.js")
    (out / "engine.json").write_text(json.dumps(eng, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "README.md").write_text(README.format(version=eng["version"], fp=eng["fingerprint"][:16]),
                                   encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(out), "engine_files": len(eng["files"]), "fingerprint": eng["fingerprint"][:16],
                      "engine_kB": round((out / "engine.json").stat().st_size / 1024)}))


if __name__ == "__main__":
    main()
