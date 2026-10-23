"""End-to-end package: calculation, report, BOM, CAD (freecadcmd, skipped when
FreeCAD is not installed), drawings, consistency. Slow (~30 s)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pressure_vessel.bom.bom import build_bom, write_bom
from pressure_vessel.cad.adapter import find_freecadcmd, run_headless
from pressure_vessel.inputs import read_input
from pressure_vessel.package import consistency
from pressure_vessel.package.pipeline import calculate
from pressure_vessel.reporting import generate_report

from .helpers import DEMO, TANK


class VesselPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pv_e2e_"))
        cls.pkg = cls.tmp / "pkg"
        cls.calc = calculate(DEMO, cls.pkg)
        cls.report = generate_report(cls.pkg, raw_input=read_input(DEMO))
        geo, res = cls.calc["geometry"], cls.calc["results"]
        cls.bom = build_bom(geo, res, read_input(DEMO))
        cls.bom_files = write_bom(cls.bom, cls.pkg / "04_BOM")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_calculation_files(self):
        for f in ("calculation_results.json", "design_geometry.json", "verification.json", "verification_report.md"):
            self.assertTrue((self.pkg / "01_CALCULATION" / f).stat().st_size > 0, f)
        self.assertTrue(self.calc["verification"]["passed"])

    def test_report(self):
        self.assertTrue(self.report["check"]["ok"], self.report["check"])

    def test_bom_matches_weight(self):
        self.assertAlmostEqual(self.bom["totals"]["net_theoretical_kg"], self.calc["results"]["weights_kg"]["empty"], places=6)
        for k in ("csv", "xlsx", "json"):
            self.assertTrue(Path(self.bom_files[k]).stat().st_size > 0)
        legs = next(r for r in self.bom["rows"] if r["kind"] == "leg")
        self.assertEqual(legs["quantity"], 4)

    @unittest.skipUnless(find_freecadcmd(), "FreeCAD (freecadcmd) not installed")
    def test_cad_drawings_consistency(self):
        cad = run_headless(self.pkg)
        self.assertTrue(cad.get("ok"), [i for i in cad.get("items", []) if not i["ok"]] or cad)
        from pressure_vessel.drawings import ga, hlr
        hlr.run(self.pkg)
        d = ga.generate(self.pkg)
        self.assertTrue(d["ok"], d)
        c = consistency.check(self.pkg)
        bad = [i for i in c["items"] if i["ok"] is False and "TechDraw" not in i["check"]]
        self.assertEqual(bad, [])


class TankPackage(unittest.TestCase):
    def test_tank_package_marks_cad_not_applicable(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / "tk"
            calculate(TANK, pkg)
            self.assertTrue(generate_report(pkg)["check"]["ok"])
            c = consistency.check(pkg)
            self.assertTrue(c["ok"], [i for i in c["items"] if i["ok"] is False])
            self.assertTrue(any(i["status"] == "NOT_APPLICABLE" for i in c["items"]))


if __name__ == "__main__":
    unittest.main()
