"""Head results through the skill scripts (2:1 template and a torispherical variant)."""

import math
import unittest

from _support import calculated_package, record, results, value


def _tori(raw):
    for pos in ("top", "bottom"):
        h = raw["geometry"]["heads"][pos]
        h.pop("aspect_ratio")
        h.update({"type": "torispherical", "crown_radius": "1200 mm", "knuckle_radius": "75 mm",
                  "nominal_thickness": "10 mm", "min_thickness_after_forming": "9 mm"})


class EllipsoidalHeads(unittest.TestCase):
    def test_2to1_hand_value_and_mawp(self):
        res = results(calculated_package())
        r = record(res, "HD-TOP")
        self.assertAlmostEqual(value(r, "t_req"), 1203 / (2 * 137.9 - 0.2), places=9)
        m = record(res, "HD-TOP-MAWP")
        self.assertAlmostEqual(value(m, "MAWP_top"), 2 * 137.9 * 5.5 / (1203 + 1.1), places=9)


class TorisphericalHeads(unittest.TestCase):
    def test_m_factor_form(self):
        res = results(calculated_package(mutate=_tori, key="tori"))
        r = record(res, "HD-BOT")
        L, rk = 1201.5, 76.5                                   # corroded crown and knuckle radii
        M = 0.25 * (3 + math.sqrt(L / rk))
        self.assertAlmostEqual(value(r, "M"), M, places=12)
        P = value(r, "P")
        self.assertAlmostEqual(value(r, "t_req"), P * L * M / (2 * 137.9 - 0.2 * P), places=9)
        self.assertEqual(value(r, "geometry_issues"), "none")


if __name__ == "__main__":
    unittest.main()
