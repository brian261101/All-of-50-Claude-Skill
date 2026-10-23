import copy
import unittest

from pressure_vessel.inputs import validate_vessel
from pressure_vessel.inputs.tank_schema import validate_tank
from pressure_vessel.materials import MaterialDatabase, MaterialError, record_from_dict

from .helpers import TANK, demo_raw
from pressure_vessel.inputs import read_input


def _errors(raw):
    vi, rep = validate_vessel(raw, MaterialDatabase.load())
    return vi, [str(e) for e in rep.errors], rep


class DemoInput(unittest.TestCase):
    def test_demo_validates_with_questions(self):
        vi, errs, rep = _errors(demo_raw())
        self.assertEqual(errs, [])
        self.assertIsNotNone(vi)
        self.assertGreater(len(rep.warnings), 0)          # weld sizes missing etc.
        self.assertAlmostEqual(vi.process.design_pressure, 1.0)
        self.assertAlmostEqual(vi.geometry.nozzles[0].neck.wall, 0.337 * 25.4)

    def test_hash_changes_with_input(self):
        a = _errors(demo_raw())[0].input_hash
        raw = demo_raw()
        raw["process"]["design_pressure"] = "1.1 MPa(g)"
        self.assertNotEqual(a, _errors(raw)[0].input_hash)


class NoSilentDefaults(unittest.TestCase):
    def test_missing_joint_is_an_error_not_a_default(self):
        raw = demo_raw()
        del raw["fabrication"]["joints"]["shell_longitudinal"]
        vi, errs, _ = _errors(raw)
        self.assertIsNone(vi)
        self.assertTrue(any("No default joint efficiency" in e for e in errs))

    def test_bare_number_rejected(self):
        raw = demo_raw()
        raw["process"]["design_pressure"] = 1.0
        _, errs, _ = _errors(raw)
        self.assertTrue(any("has no unit" in e for e in errs))

    def test_absolute_design_pressure_rejected(self):
        raw = demo_raw()
        raw["process"]["design_pressure"] = "160 psia"
        _, errs, _ = _errors(raw)
        self.assertTrue(any("gauge" in e for e in errs))

    def test_course_lengths_must_close_tt(self):
        raw = demo_raw()
        raw["geometry"]["shell_courses"][1]["length"] = "1400 mm"
        _, errs, _ = _errors(raw)
        self.assertTrue(any("tangent-to-tangent" in e for e in errs))

    def test_head_needs_formed_thickness(self):
        raw = demo_raw()
        del raw["geometry"]["heads"]["top"]["min_thickness_after_forming"]
        _, errs, _ = _errors(raw)
        self.assertTrue(any("min_thickness_after_forming" in e for e in errs))

    def test_operating_above_design_rejected(self):
        raw = demo_raw()
        raw["process"]["operating_pressure"] = "1.2 MPa(g)"
        _, errs, _ = _errors(raw)
        self.assertTrue(any("operating pressure exceeds" in e for e in errs))

    def test_demo_basis_cannot_be_locked(self):
        raw = demo_raw()
        raw["design_basis"] = {"locked": True, "confirmed_by": "x", "confirmed_on": "2026-01-01"}
        _, errs, _ = _errors(raw)
        self.assertTrue(any("DEMO_SAMPLE" in e for e in errs))

    def test_unknown_material_key(self):
        raw = demo_raw()
        raw["geometry"]["shell_courses"][0]["material"] = "NOPE"
        _, errs, _ = _errors(raw)
        self.assertTrue(any("NOPE" in e for e in errs))

    def test_not_applicable_needs_reason(self):
        raw = demo_raw()
        raw["loads"]["wind"] = {"not_applicable": ""}
        _, errs, _ = _errors(raw)
        self.assertTrue(any("needs a reason" in e for e in errs))

    def test_api650_input_refused_by_vessel_schema(self):
        raw = demo_raw()
        raw["project"]["design_code"] = "API_650"
        _, errs, _ = _errors(raw)
        self.assertTrue(any("own schema" in e for e in errs))


class TankRouting(unittest.TestCase):
    def test_tank_validates(self):
        ti, rep = validate_tank(read_input(TANK))
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(len(ti.courses), 5)

    def test_vessel_code_refused_by_tank_schema(self):
        raw = read_input(TANK)
        raw["project"]["design_code"] = "ASME_VIII_1"
        ti, rep = validate_tank(raw)
        self.assertIsNone(ti)


class MaterialRecords(unittest.TestCase):
    def test_lookup_rules(self):
        db = MaterialDatabase.load()
        r = db.get("SA-516-70_PLATE_REP")
        s, how = r.allowable_stress(37.8)
        self.assertIn("tabulated", how)
        s2, how2 = r.allowable_stress(300.0)
        self.assertIn("interpolation", how2)
        with self.assertRaises(MaterialError):
            r.allowable_stress(500.0)            # beyond the table: no extrapolation
        with self.assertRaises(MaterialError):
            r.allowable_stress(-50.0)
        self.assertEqual(str(r.status), "REPRESENTATIVE_EXAMPLE")

    def test_interpolation_must_be_permitted(self):
        d = {"id": "X", "spec": "S", "allowable_stress": {"temperature_degC": [0, 100], "S_MPa": [100, 90]},
             "interpolation": "", "verification_status": "UNVERIFIED"}
        with self.assertRaises(MaterialError):
            record_from_dict(d).allowable_stress(50)

    def test_verified_status_needs_verifier(self):
        d = {"id": "X", "spec": "S", "allowable_stress": {"temperature_degC": [0, 100], "S_MPa": [100, 90]},
             "verification_status": "VERIFIED_OFFICIAL"}
        with self.assertRaises(MaterialError):
            record_from_dict(d)


if __name__ == "__main__":
    unittest.main()
