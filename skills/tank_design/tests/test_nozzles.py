"""Nozzle checks through the skill scripts."""

import unittest

from _support import calculated_package, record, results, value


def _no_pad(raw):
    raw["geometry"]["nozzles"][0]["pad"] = "none"


class Nozzles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = results(calculated_package())

    def test_area_method_values(self):
        """See pv_design/data/benchmarks/hand_calcs_si.json case H6."""
        r = record(self.res, "NZ-N1-UG37")
        self.assertAlmostEqual(value(r, "A"), 447.8533427349266, places=6)
        self.assertAlmostEqual(value(r, "A_avail"), 1039.9062246461674, places=6)

    def test_ug45_value(self):
        r = record(self.res, "NZ-N1-UG45")
        self.assertAlmostEqual(value(r, "t_UG45"), 5.880917698470502, places=9)

    def test_opening_governs_mawp(self):
        self.assertEqual(value(record(self.res, "MAWP"), "governing"), "opening N4")

    def test_missing_flange_rating_is_not_evaluated(self):
        self.assertEqual(record(self.res, "NZ-N2-FLG")["status"], "NOT_EVALUATED")

    def test_without_pad_the_check_fails_and_blocks(self):
        res = results(calculated_package(mutate=_no_pad, key="nopad"))
        self.assertEqual(record(res, "NZ-N1-UG37")["status"], "FAIL")
        self.assertTrue(res["gate"]["blockers"][0].startswith("FAIL"))
        self.assertEqual(res["gate"]["stage"], "PRELIMINARY")


if __name__ == "__main__":
    unittest.main()
