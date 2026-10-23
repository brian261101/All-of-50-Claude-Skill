"""Calculation engine on the demo vessel and on targeted variations."""

import unittest

from pressure_vessel.status import RecordKind, Status

from .helpers import MINIMAL, demo_raw, rec, run_raw
from pressure_vessel.inputs import read_input


class DemoVessel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vi, cls.rep, cls.out, cls.refs = run_raw(demo_raw())

    def test_selected_thickness_and_margins(self):
        sel = self.out["results"]["selected_thickness_mm"]
        self.assertEqual(sel, {"C1": 8.0, "C2": 8.0, "bottom": 8.0, "top": 8.0})
        r = rec(self.out, "SH-C1")
        self.assertAlmostEqual(r.value("t_circ"), 601.5 / 116.615, places=9)
        self.assertAlmostEqual(r.value("t_avail"), 8.0 - 0.3 - 1.5)   # 0.3 > 0.25: deducted (UG-16(c))

    def test_no_check_passes_on_representative_data(self):
        for r in self.out["records"]:
            if r.kind == RecordKind.CHECK and r.materials:
                self.assertNotEqual(r.status, Status.PASS, r.calc_id)

    def test_project_requirement_can_pass(self):
        self.assertEqual(rec(self.out, "VOL-REQ").status, Status.PASS)

    def test_mawp_and_test_pressure(self):
        res = self.out["results"]
        parts = res["mawp_parts_MPa"]
        self.assertAlmostEqual(parts["shell C1"], 117.215 * 6.2 / (601.5 + 3.72), places=9)
        self.assertAlmostEqual(res["mawp_MPa"], min(parts.values()), places=12)
        # the unpadded NPS 2 safety-valve opening in the top head governs (UG-98: lowest part)
        self.assertEqual(rec(self.out, "MAWP").value("governing"), "opening N4")
        self.assertAlmostEqual(res["test_pressure_top_MPa"], 1.3 * res["mawp_MPa"], places=9)

    def test_opening_mawp_is_the_area_check_limit(self):
        from pressure_vessel.codes.asme_viii_1 import formulas as F
        r = rec(self.out, "NZ-N4-UG37")
        Pm = r.value("P_max_opening")
        args = dict(d=r.value("d"), t=r.value("t"), tn=r.value("tn"), Sv=r.value("Sv"), Sn=r.value("Sn"))
        def margin(P):
            Dc = 1203.0
            tr = P * 0.9 * Dc / (2 * args["Sv"] - 0.2 * P)
            trn = P * args["d"] / 2 / (args["Sn"] - 0.6 * P)
            a = F.area_replacement(tr=tr, trn=trn, **args)
            return a["A_avail"] - a["A"]
        self.assertGreaterEqual(margin(Pm), -1e-6)
        self.assertLess(margin(Pm * 1.001), 0)

    def test_unsupplied_data_is_not_evaluated(self):
        for cid in ("EXT-SHELL", "NZ-N2-FLG", "MDMT", "LOAD-WIND", "NZ-N1-UG41"):
            self.assertEqual(rec(self.out, cid).status, Status.NOT_EVALUATED, cid)
        self.assertTrue(rec(self.out, "EXT-SHELL").questions)

    def test_every_record_traces_to_register(self):
        for r in self.out["records"]:
            for rid in r.references:
                self.refs.get(rid)
            if r.kind == RecordKind.CHECK and r.status not in (Status.NOT_EVALUATED, Status.OUT_OF_SCOPE):
                self.assertTrue(r.criterion, r.calc_id)
            self.assertEqual(len(r.formula), len(r.substitution), r.calc_id)

    def test_gate_blocks_release(self):
        gate = self.out["results"]["gate"]
        self.assertEqual(gate["stage"], "PRELIMINARY")
        self.assertIn("NOT RELEASED", gate["fabrication_release"])


class Variations(unittest.TestCase):
    def test_nozzle_without_pad_fails(self):
        raw = demo_raw()
        raw["geometry"]["nozzles"][0]["pad"] = "none"
        _, _, out, _ = run_raw(raw)
        self.assertEqual(rec(out, "NZ-N1-UG37").status, Status.FAIL)
        self.assertIn("FAIL", out["results"]["gate"]["blockers"][0])

    def test_large_opening_is_out_of_scope(self):
        raw = demo_raw()
        raw["geometry"]["nozzles"][5]["neck"]["od"] = "700 mm"
        raw["geometry"]["nozzles"][5]["pad"] = {"thickness": "8 mm", "outside_diameter": "1000 mm", "material": "PLATE"}
        _, _, out, _ = run_raw(raw)
        self.assertEqual(rec(out, "NZ-M1-UG37").status, Status.OUT_OF_SCOPE)

    def test_thin_shell_fails(self):
        raw = demo_raw()
        raw["geometry"]["shell_courses"][0]["nominal_thickness"] = "6 mm"
        _, _, out, _ = run_raw(raw)
        self.assertEqual(rec(out, "SH-C1").status, Status.FAIL)

    def test_external_pressure_with_user_chart_data(self):
        raw = demo_raw()
        raw["external_pressure_data"]["shell"] = {"A": 0.00011, "B": "10.5 MPa",
                                                  "source": "TEST values, not chart readings"}
        _, _, out, _ = run_raw(raw)
        r = rec(out, "EXT-SHELL")
        Dot = r.value("Do/t")
        self.assertAlmostEqual(r.value("Pa"), 4 * 10.5 / (3 * Dot), places=12)
        self.assertEqual(r.status, Status.NEEDS_ENGINEERING_REVIEW if r.value("Pa") >= 0.1 else Status.FAIL)

    def test_liquid_static_head_raises_bottom_pressure(self):
        raw = demo_raw()
        raw["process"]["fluid_phase"] = "liquid"
        raw["process"]["liquid_level"] = "2900 mm"
        raw["process"]["liquid_density"] = "1000 kg/m3"
        _, _, out, _ = run_raw(raw)
        p_c1 = rec(out, "SH-C1").value("P")
        p_c2 = rec(out, "SH-C2").value("P")
        self.assertGreater(p_c1, p_c2)
        self.assertAlmostEqual(p_c1 - 1.0, 1000e-9 * 9806.65 * (2900 - 40) * 1e-3, places=12)

    def test_assessment_must_target_open_check(self):
        raw = demo_raw()
        raw["assessments"] = {"SH-C1": {"result": "pass", "basis": "x", "by": "y", "status": "USER_SUPPLIED_VERIFIED"}}
        with self.assertRaises(ValueError):
            run_raw(raw)


class ReleaseGate(unittest.TestCase):
    def test_fully_verified_minimal_case_reaches_calculation_verified(self):
        from pressure_vessel.codes.asme_viii_1.design import release_gate
        from pressure_vessel.verification.runner import run_verification
        vi, _, out, refs = run_raw(read_input(MINIMAL), verify_all_refs=True)
        checks = [r for r in out["records"] if r.kind == RecordKind.CHECK and r.mandatory]
        self.assertTrue(checks)
        self.assertEqual({r.status for r in checks}, {Status.PASS}, [(r.calc_id, r.status) for r in checks])
        ver = run_verification(out["results"], out["geometry"])
        self.assertTrue(ver["passed"])
        gate = release_gate(vi, out["records"], refs, ver)
        self.assertEqual(gate["stage"], "CALCULATION_VERIFIED", gate["blockers"])
        self.assertIn("NOT RELEASED", gate["fabrication_release"])     # never set by software

    def test_same_case_without_reference_verification_stays_preliminary(self):
        from pressure_vessel.codes.asme_viii_1.design import release_gate
        vi, _, out, refs = run_raw(read_input(MINIMAL))
        gate = release_gate(vi, out["records"], refs, {"passed": True})
        self.assertEqual(gate["stage"], "PRELIMINARY")


if __name__ == "__main__":
    unittest.main()
