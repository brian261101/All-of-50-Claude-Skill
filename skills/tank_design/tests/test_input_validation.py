import json
import tempfile
import unittest
from pathlib import Path

import yaml

from _support import TEMPLATES, run


class TemplatesValidate(unittest.TestCase):
    def test_vessel_template_is_valid(self):
        rc, out, err = run("validate_input.py", TEMPLATES / "vessel-input.yaml")
        self.assertEqual(rc, 0, out + err)
        rep = json.loads(out)
        self.assertTrue(rep["ok"])
        self.assertGreater(len(rep["warnings"]), 0)        # e.g. weld sizes not given
        # the open questions for the user are raised by the calculation records
        from _support import calculated_package, results
        self.assertGreater(len(results(calculated_package())["questions"]), 10)

    def test_tank_template_is_valid(self):
        rc, out, err = run("validate_input.py", TEMPLATES / "tank-input.yaml")
        self.assertEqual(rc, 0, out + err)

    def test_templates_match_library_examples(self):
        lib = Path(__file__).resolve().parents[4] / "pv_design" / "examples"
        if not lib.is_dir():                       # installed package: bundled engine
            lib = Path(__file__).resolve().parents[1] / "engine" / "examples"
        self.assertEqual((TEMPLATES / "vessel-input.yaml").read_text(encoding="utf-8"),
                         (lib / "PV-DEMO-001" / "vessel_input.yaml").read_text(encoding="utf-8"))


class BadInputsAreRejected(unittest.TestCase):
    def _check(self, mutate, needle):
        raw = yaml.safe_load((TEMPLATES / "vessel-input.yaml").read_text(encoding="utf-8"))
        mutate(raw)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.yaml"
            p.write_text(yaml.safe_dump(raw), encoding="utf-8")
            rc, out, err = run("validate_input.py", p)
        self.assertEqual(rc, 2, out)
        self.assertIn(needle, out)

    def test_number_without_unit(self):
        self._check(lambda r: r["process"].__setitem__("design_temperature", 80), "has no unit")

    def test_missing_joint_efficiency_is_not_defaulted(self):
        self._check(lambda r: r["fabrication"]["joints"].pop("shell_circumferential"), "No default joint efficiency")

    def test_mixed_dimension(self):
        self._check(lambda r: r["geometry"].__setitem__("diameter", "1.2 MPa"), "expected a length")


if __name__ == "__main__":
    unittest.main()
