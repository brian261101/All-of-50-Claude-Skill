"""Handoff zip (web calculator -> Claude Code): packing, resume, tamper checks,
and the web build that ships the same engine."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from pressure_vessel.handoff import (SCHEMA, compare_results, engine_files, engine_fingerprint, make_handoff,
                                     read_handoff, resume)
from pressure_vessel.package.pipeline import calculate

from . import ROOT
from .helpers import DEMO, TANK


def _rewrite(src: Path, dst: Path, edit):
    """Copy a zip, passing each member through edit(name, bytes) -> bytes."""
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            zo.writestr(n, edit(n, zi.read(n)))


class Handoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pv_handoff_test_"))
        calculate(DEMO, cls.tmp / "pkg")
        (cls.tmp / "pkg" / "00_INPUT" / "source_register.md").write_text("# register\n", encoding="utf-8")
        cls.zip = cls.tmp / "demo_handoff.zip"
        cls.h = make_handoff(cls.tmp / "pkg", cls.zip, tool="test")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_contents(self):
        h = read_handoff(self.zip)
        self.assertEqual(h["handoff"], SCHEMA)
        self.assertEqual([s["step"] for s in h["steps_next"]], [9, 10, 11, 12])
        self.assertEqual(h["input_file"], "00_INPUT/vessel_input.yaml")
        self.assertIn("NOT RELEASED", h["fabrication_release"])
        with zipfile.ZipFile(self.zip) as z:
            names = z.namelist()
            self.assertIn("pv.py resume", z.read("README_FOR_CLAUDE.md").decode())
        self.assertIn("00_INPUT/source_register.md", names)
        self.assertFalse([n for n in names if n.startswith(("02_", "03_", "04_", "05_"))])

    def test_resume_round_trip(self):
        out = self.tmp / "resumed"
        c = resume(self.zip, out)
        self.assertTrue(c["identical"], c["items"])
        self.assertTrue(all(i["ok"] for i in c["items"]))
        self.assertTrue(any("pv.py cad" in n for n in c["next"]))
        self.assertTrue((out / "00_INPUT" / "source_register.md").is_file())
        self.assertTrue((out / "00_INPUT" / self.zip.name).is_file())
        self.assertTrue(json.loads((out / "05_QA" / "handoff_check.json").read_text(encoding="utf-8"))["identical"])

    def test_tampered_file_is_caught(self):
        bad = self.tmp / "tampered.zip"
        _rewrite(self.zip, bad, lambda n, b: b.replace(b'"PASS"', b'"FAIL"', 1)
                 if n.endswith("calculation_results.json") else b)
        c = resume(bad, self.tmp / "tampered")
        self.assertFalse(c["identical"])
        self.assertFalse(c["items"][0]["ok"])          # file hash
        self.assertTrue(c["next"][0].startswith("STOP"))

    def test_results_not_reproduced_is_caught(self):
        # a consistent zip (hashes updated) whose results the local engine does not produce
        bad = self.tmp / "other_results.zip"
        h = json.loads(json.dumps(self.h))

        def edit(n, b):
            if n.endswith("calculation_results.json"):
                r = json.loads(b)
                r["mawp_MPa"] *= 1.01
                b = json.dumps(r).encode()
                next(f for f in h["files"] if f["path"] == n)["sha256"] = hashlib.sha256(b).hexdigest()
            return b
        with zipfile.ZipFile(self.zip) as zi, zipfile.ZipFile(bad, "w") as zo:
            for n in zi.namelist():
                if n != "HANDOFF.json":
                    zo.writestr(n, edit(n, zi.read(n)))
            zo.writestr("HANDOFF.json", json.dumps(h))
        c = resume(bad, self.tmp / "other")
        self.assertFalse(c["identical"])
        item = next(i for i in c["items"] if i["check"].startswith("calculation results"))
        self.assertFalse(item["ok"])
        self.assertIn("mawp_MPa", item["detail"]["differences"])

    def test_unsafe_member_rejected(self):
        bad = self.tmp / "unsafe.zip"
        shutil.copy(self.zip, bad)
        with zipfile.ZipFile(bad, "a") as z:
            z.writestr("../evil.txt", "x")
        with self.assertRaises(ValueError):
            resume(bad, self.tmp / "unsafe")


class TankHandoff(unittest.TestCase):
    def test_tank_next_steps_stop_at_report_and_package(self):
        with tempfile.TemporaryDirectory(prefix="pv_handoff_tank_") as tmp:
            tmp = Path(tmp)
            calculate(TANK, tmp / "pkg")
            make_handoff(tmp / "pkg", tmp / "t.zip")
            c = resume(tmp / "t.zip", tmp / "out")
            self.assertTrue(c["identical"], c["items"])
            self.assertFalse(any("pv.py cad" in n or "pv.py bom" in n for n in c["next"]))
            self.assertTrue(any("not implemented" in n for n in c["next"]))


class CompareResults(unittest.TestCase):
    BASE = {"input_file": "a", "material_db": {"path": "x", "name": "db"}, "results_hash": "h",
            "records": [{"calc_id": "A", "status": "PASS", "results": [{"value": 3.845309338229787}]}], "n": 3}

    def _other(self, **kw):
        o = json.loads(json.dumps(self.BASE))
        o.update(kw)
        return o

    def test_last_digit_rounding_and_paths_accepted(self):
        o = self._other(input_file="b", results_hash="g", material_db={"path": "y", "name": "db"})
        o["records"][0]["results"][0]["value"] = 3.8453093382297867
        c = compare_results(self.BASE, o)
        self.assertTrue(c["equal"], c)
        self.assertEqual(c["float_rounding_differences"], 1)

    def test_real_differences_rejected(self):
        o = self._other()
        o["records"][0]["results"][0]["value"] = 3.8453
        o["records"][0]["status"] = "FAIL"
        c = compare_results(self.BASE, o)
        self.assertFalse(c["equal"])
        self.assertEqual(set(c["differences"]), {"records.0.results.0.value", "records.0.status"})
        self.assertFalse(compare_results(self.BASE, self._other(n=True))["equal"])          # bool is not a number
        self.assertFalse(compare_results(self.BASE, self._other(material_db={"path": "x"}))["equal"])


class WebBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("pv_web_build", ROOT / "web" / "build.py")
        cls.build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.build)

    def test_engine_bundle_matches_fingerprint(self):
        eng = self.build.build_engine()
        self.assertEqual(eng["fingerprint"], engine_fingerprint())
        paths = [f["path"] for f in eng["files"]]
        self.assertIn("src/pressure_vessel/handoff.py", paths)
        self.assertIn("data/materials/material_db.json", paths)
        self.assertFalse([p for p in paths if "/cad/" in p or "/drawings/" in p or p.endswith("/cli.py")])
        self.assertEqual(len(paths), len(engine_files()))

    def test_page_builds_from_the_form(self):
        html = self.build.build_index(self.build.FORM.read_text(encoding="utf-8"))
        self.assertTrue(html.startswith("<!doctype html>"))
        for s in ('id="bCalc"', 'id="bZip"', "js/calc.js", "window.pvForm", "pdfmake@0.2.23"):
            self.assertIn(s, html)


if __name__ == "__main__":
    unittest.main()
