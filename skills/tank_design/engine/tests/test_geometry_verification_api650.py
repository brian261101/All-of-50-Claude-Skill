import copy
import math
import unittest

from pressure_vessel.codes.api_650 import design as api
from pressure_vessel.geometry import profiles as pf
from pressure_vessel.inputs import read_input
from pressure_vessel.inputs.tank_schema import validate_tank
from pressure_vessel.references import ReferenceRegister
from pressure_vessel.status import Status
from pressure_vessel.verification import independent as I
from pressure_vessel.verification.runner import run_verification

from .helpers import TANK, demo_raw, run_raw


class Geometry(unittest.TestCase):
    def test_head_volumes_against_closed_forms(self):
        a, t = 600.0, 8.0
        V, _ = pf.HeadProfile("hemispherical", a).solid_volume(0.0)
        self.assertAlmostEqual(V / (2 / 3 * math.pi * a ** 3), 1.0, places=6)
        V, _ = pf.HeadProfile("ellipsoidal", a, 2.0).solid_volume(0.0)
        self.assertAlmostEqual(V / I.ellipsoid_half(a, a / 2), 1.0, places=6)
        p = pf.HeadProfile("torispherical", a, L=1200.0, r=72.0)
        self.assertAlmostEqual(p.solid_volume(0.0)[0] / I.torispherical_solid(a, 1200.0, 72.0), 1.0, places=6)
        Vm, _ = pf.head_metal(pf.HeadProfile("hemispherical", a), t, 0.0)
        self.assertAlmostEqual(Vm / I.hemisphere_metal(a, t), 1.0, places=5)

    def test_demo_geometry_consistency(self):
        _, _, out, _ = run_raw(demo_raw())
        g = out["geometry"]
        self.assertAlmostEqual(g["vessel"]["overall_height"], 4000 + 300 + 8 + 200)   # TTL + depth + t + N4 projection
        tags = [c["tag"] for c in g["components"]]
        self.assertEqual(len(tags), len(set(tags)))
        self.assertEqual(sum(1 for c in g["components"] if c["kind"] == "leg"), 4)
        # nozzle holes reduce the parent course volume
        c1 = next(c for c in g["components"] if c["tag"] == "C1")
        ring = math.pi * (608 ** 2 - 600 ** 2) * 1500
        self.assertLess(c1["volume_mm3"], ring)
        self.assertIn("M1", c1["params"]["openings"])

    def test_nozzle_neck_integral_matches_straight_tube_limit(self):
        # tiny nozzle on a huge cylinder ~ straight tube between the two surfaces
        ig = pf.shell_nozzle_integrals(1e6, 1e6 + 10, 5.0, 6.0, 1e6 + 110, "set_in")
        self.assertAlmostEqual(ig["neck_V"], math.pi * (36 - 25) * 110, delta=0.5)


class Verification(unittest.TestCase):
    def test_demo_verification_passes(self):
        _, _, out, _ = run_raw(demo_raw())
        v = run_verification(out["results"], out["geometry"])
        self.assertTrue(v["passed"], v["discrepancies"])
        self.assertGreater(v["n_checks"], 50)
        self.assertEqual(v["pv_elite"]["status"], "NOT_AVAILABLE")

    def test_planted_discrepancy_is_caught(self):
        _, _, out, _ = run_raw(demo_raw())
        res = copy.deepcopy(out["results"])
        r = next(x for x in res["records"] if x["calc_id"] == "SH-C1")
        for tv in r["intermediates"]:
            if tv["symbol"] == "t_circ":
                tv["value"] *= 1.01
        v = run_verification(res, out["geometry"])
        self.assertFalse(v["passed"])
        self.assertTrue(any(d["id"] == "SH-C1" for d in v["discrepancies"]))

    def test_pv_elite_comparison_reports_deviations(self):
        import tempfile
        from pathlib import Path
        _, _, out, _ = run_raw(demo_raw())
        sh = next(r for r in out["records"] if r.calc_id == "SH-C1")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pve.csv"
            p.write_text("calc_id,symbol,value,unit,rel_tolerance\n# comment rows are skipped\n"
                         f"SH-C1,t_circ,{sh.value('t_circ')},mm,0.001\n"
                         f"SH-C1,t_long,{sh.value('t_long') * 1.05},mm,0.001\n", encoding="utf-8")
            v = run_verification(out["results"], out["geometry"], p)
        self.assertEqual(v["pv_elite"]["status"], "COMPARED")
        self.assertEqual((v["pv_elite"]["values"], v["pv_elite"]["deviations"]), (2, 1))
        self.assertFalse(v["passed"])          # a deviation from the reference stops release

    def test_independent_forms_agree(self):
        self.assertAlmostEqual(I.shell_circ_by_stress(1.0, 601.5, 137.9, 0.85), 601.5 / 116.615, places=8)
        self.assertAlmostEqual(I.ellipsoidal_outside_form(1.0, 1203.0, 137.9, 1.0, 2.0), 1203 / 275.6, places=9)


class Api650(unittest.TestCase):
    def test_demo_tank(self):
        ti, rep = validate_tank(read_input(TANK))
        out = api.run(ti, ReferenceRegister.load(), rep)
        r1 = next(r for r in out["records"] if r.calc_id == "API-SH-1")
        self.assertAlmostEqual(r1.value("td"), 4.9 * 10 * 8.3 / 137 + 1.5, places=9)
        self.assertEqual(r1.value("t_nom"), 5.0)          # table minimum governs
        self.assertEqual(r1.status, Status.NEEDS_ENGINEERING_REVIEW)

    def test_out_of_scope_conditions_stop_the_tank_path(self):
        raw = read_input(TANK)
        raw["process"]["internal_pressure"] = "50 kPa"
        ti, rep = validate_tank(raw)
        out = api.run(ti, ReferenceRegister.load(), rep)
        self.assertEqual(out["records"][0].status, Status.OUT_OF_SCOPE)
        self.assertEqual(len(out["records"]), 1)          # no API 650 thickness is produced


if __name__ == "__main__":
    unittest.main()
