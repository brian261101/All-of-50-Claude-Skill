import unittest

from pressure_vessel import units
from pressure_vessel.status import DataStatus, Status, aggregate, decide
from pressure_vessel.trace import CalcRecord
from pressure_vessel.status import RecordKind


class UnitParsing(unittest.TestCase):
    def test_pressure_conversions(self):
        self.assertAlmostEqual(units.parse("1.0 MPa").value, 1.0)
        self.assertAlmostEqual(units.parse("150 psi").value, 150 * 0.006894757293168361, places=12)
        self.assertAlmostEqual(units.parse("10 bar").value, 1.0)
        self.assertAlmostEqual(units.parse("100 kPa").value, 0.1)
        q = units.parse("10 barg")
        self.assertEqual(q.pressure_ref, "g")
        self.assertEqual(units.parse("14.7 psia").pressure_ref, "a")
        self.assertEqual(units.parse("1 MPa(g)").pressure_ref, "g")

    def test_length_temperature_and_mapping_form(self):
        self.assertAlmostEqual(units.parse("4 in").value, 101.6)
        self.assertAlmostEqual(units.parse("1.2 m").value, 1200.0)
        self.assertAlmostEqual(units.parse("212 degF").value, 100.0)
        self.assertAlmostEqual(units.parse("-10 degC").value, -10.0)
        self.assertAlmostEqual(units.parse("373.15 K").value, 100.0)
        self.assertAlmostEqual(units.parse({"value": 8, "unit": "mm"}).value, 8.0)
        self.assertAlmostEqual(units.parse("12.5 %").value, 0.125)
        self.assertAlmostEqual(units.parse("3.5 m3").value, 3.5e9)

    def test_bare_numbers_and_wrong_dimensions_are_rejected(self):
        with self.assertRaises(units.UnitError):
            units.parse(8, expect=units.LENGTH)
        with self.assertRaises(units.UnitError):
            units.parse("8", expect=units.LENGTH)
        with self.assertRaises(units.UnitError):
            units.parse("1 MPa", expect=units.LENGTH)       # pressure where a length is expected
        with self.assertRaises(units.UnitError):
            units.parse("8 furlongs")
        with self.assertRaises(units.UnitError):
            units.parse({"value": 8})

    def test_round_trip_display(self):
        self.assertAlmostEqual(units.to(units.parse("250 psi").value, units.PRESSURE, "psi"), 250.0)
        self.assertAlmostEqual(units.to(25.4, units.LENGTH, "in"), 1.0)


class StatusRules(unittest.TestCase):
    def test_decide(self):
        self.assertEqual(decide(None)[0], Status.NOT_EVALUATED)
        self.assertEqual(decide(False)[0], Status.FAIL)
        self.assertEqual(decide(True)[0], Status.PASS)
        self.assertEqual(decide(True, unverified_items=["x"])[0], Status.NEEDS_ENGINEERING_REVIEW)
        self.assertEqual(decide(True, out_of_scope="beyond")[0], Status.OUT_OF_SCOPE)
        # a failed criterion is a FAIL even on unverified data
        self.assertEqual(decide(False, unverified_items=["x"])[0], Status.FAIL)

    def test_aggregate_is_worst_case(self):
        self.assertEqual(aggregate([Status.PASS, Status.NEEDS_ENGINEERING_REVIEW]), Status.NEEDS_ENGINEERING_REVIEW)
        self.assertEqual(aggregate([Status.PASS, Status.NOT_EVALUATED, Status.FAIL]), Status.FAIL)
        self.assertEqual(aggregate([Status.PASS, Status.OUT_OF_SCOPE]), Status.OUT_OF_SCOPE)
        self.assertIsNone(aggregate([]))

    def test_computation_never_shows_pass(self):
        r = CalcRecord("X", "c", "t", kind=RecordKind.COMPUTATION)
        r.criterion_met = True
        r.finalize()
        self.assertIsNone(r.status)
        self.assertEqual(r.status_text, "COMPUTED")

    def test_unevaluated_check_is_not_pass(self):
        r = CalcRecord("Y", "c", "t").finalize()
        self.assertEqual(r.status, Status.NOT_EVALUATED)

    def test_release_eligibility(self):
        self.assertTrue(DataStatus.VERIFIED_OFFICIAL.release_eligible)
        self.assertTrue(DataStatus.USER_SUPPLIED_VERIFIED.release_eligible)
        for s in (DataStatus.REPRESENTATIVE_EXAMPLE, DataStatus.UNVERIFIED, DataStatus.USER_SUPPLIED_UNVERIFIED):
            self.assertFalse(s.release_eligible)


if __name__ == "__main__":
    unittest.main()
