"""Shell results produced through the skill scripts, against hand arithmetic."""

import unittest

from _support import calculated_package, record, results, value


class Shells(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = results(calculated_package())

    def test_required_thickness_hand_value(self):
        """R = 601.5; t = 1.0 x 601.5 / (137.9 x 0.85 - 0.6) = 5.158 mm (representative S)."""
        r = record(self.res, "SH-C1")
        self.assertAlmostEqual(value(r, "t_circ"), 601.5 / (137.9 * 0.85 - 0.6), places=9)
        self.assertAlmostEqual(value(r, "t_long"), 601.5 / (2 * 137.9 * 0.85 + 0.4), places=9)

    def test_selection_and_undertolerance(self):
        r = record(self.res, "SH-C1")
        self.assertEqual(value(r, "t_nom"), 8.0)               # smallest listed plate that works
        self.assertAlmostEqual(value(r, "t_avail"), 6.2)        # 8 - 0.3 (> 0.25 mm, deducted) - 1.5

    def test_status_on_representative_data(self):
        r = record(self.res, "SH-C1")
        self.assertEqual(r["status"], "NEEDS_ENGINEERING_REVIEW")
        self.assertTrue(any("not verified" in s or "REPRESENTATIVE" in s for s in r["status_reasons"]))

    def test_traceability_chain(self):
        r = record(self.res, "SH-C1")
        for k in ("inputs", "formula", "substitution", "intermediates", "results", "references", "criterion"):
            self.assertTrue(r[k], k)
        self.assertEqual(len(r["formula"]), len(r["substitution"]))


if __name__ == "__main__":
    unittest.main()
