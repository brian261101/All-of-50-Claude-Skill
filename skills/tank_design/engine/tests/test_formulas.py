"""Formula layer: hand calculations (arithmetic in the docstrings), limits,
round trips and boundary cases."""

import math
import unittest

from pressure_vessel.codes.asme_viii_1 import formulas as F


class Shells(unittest.TestCase):
    def test_circumferential_hand_value(self):
        """R = 601.5; t = 601.5 / (137.9 x 0.85 - 0.6) = 601.5 / 116.615 = 5.157999 mm."""
        self.assertAlmostEqual(F.shell_t_circ(1.0, 601.5, 137.9, 0.85), 601.5 / 116.615, places=12)

    def test_longitudinal_hand_value(self):
        """t = 601.5 / (2 x 117.215 + 0.4) = 2.561427 mm."""
        self.assertAlmostEqual(F.shell_t_long(1.0, 601.5, 137.9, 0.85), 601.5 / 234.83, places=12)

    def test_mawp_round_trip(self):
        for t in (3.0, 6.2, 20.0):
            P = F.shell_mawp_circ(t, 601.5, 137.9, 0.85)
            self.assertAlmostEqual(F.shell_t_circ(P, 601.5, 137.9, 0.85), t, places=9)
            P2 = F.shell_mawp_long(t, 601.5, 137.9, 0.85)
            self.assertAlmostEqual(F.shell_t_long(P2, 601.5, 137.9, 0.85), t, places=9)

    def test_applicability_limits(self):
        with self.assertRaises(F.OutOfScope):      # P > 0.385 SE
            F.shell_t_circ(60.0, 500.0, 137.9, 1.0)
        F.shell_t_circ(0.385 * 137.9 * 0.999, 500.0, 137.9, 1.0)   # just inside the limit
        with self.assertRaises(F.OutOfScope):      # t > R/2 in the MAWP direction
            F.shell_mawp_circ(300.0, 500.0, 137.9, 1.0)

    def test_invalid_inputs_raise(self):
        for args in ((-1, 600, 138, 1), (1, 0, 138, 1), (1, 600, 138, 0), (1, 600, 138, 1.2)):
            with self.assertRaises(ValueError):
                F.shell_t_circ(*args)

    def test_sensitivity_is_monotonic(self):
        ts = [F.shell_t_circ(p, 601.5, 137.9, 0.85) for p in (0.5, 1.0, 1.5, 2.0)]
        self.assertEqual(ts, sorted(ts))
        te = [F.shell_t_circ(1.0, 601.5, 137.9, e) for e in (0.7, 0.85, 1.0)]
        self.assertEqual(te, sorted(te, reverse=True))


class Heads(unittest.TestCase):
    def test_2to1_equals_ug32_form(self):
        """K = 1 for D/2h = 2, so t = PD/(2SE - 0.2P) = 1203 / 275.6 = 4.365022 mm."""
        self.assertAlmostEqual(F.ellipsoidal_K(2.0), 1.0)
        self.assertAlmostEqual(F.ellipsoidal_t(1.0, 1203.0, 137.9, 1.0), 1203 / 275.6, places=12)

    def test_general_ellipsoidal_K(self):
        self.assertAlmostEqual(F.ellipsoidal_K(2.5), (2 + 6.25) / 6)
        self.assertAlmostEqual(F.ellipsoidal_K(1.0), 0.5)     # hemispherical limit
        with self.assertRaises(F.OutOfScope):
            F.ellipsoidal_K(3.2)

    def test_torispherical_M_and_standard_head(self):
        """r = 6 % L: M = (3 + sqrt(16.667))/4 = 1.7706; the M-form and the
        0.885 form agree within 0.2 %."""
        L = 1200.0
        r = 0.06 * L
        M = F.torispherical_M(L, r)
        self.assertAlmostEqual(M, 0.25 * (3 + math.sqrt(1 / 0.06)), places=12)
        t_m = F.torispherical_t(1.0, L, r, 137.9, 1.0)
        t_885 = 0.885 * 1.0 * L / (137.9 - 0.1)
        self.assertLess(abs(t_m - t_885) / t_885, 2e-3)
        with self.assertRaises(F.OutOfScope):
            F.torispherical_M(1200.0, 70.0)      # L/r = 17.1 > 16 2/3

    def test_torispherical_geometry_rules(self):
        self.assertEqual(F.torispherical_geometry_issues(1200, 75, 1216, 8), [])
        issues = F.torispherical_geometry_issues(1300, 50, 1216, 20)
        self.assertEqual(len(issues), 3)    # crown > OD, knuckle < 6 % OD, knuckle < 3t

    def test_hemispherical_limits(self):
        self.assertAlmostEqual(F.hemispherical_t(1.0, 601.5, 137.9, 0.85), 601.5 / 234.23, places=12)
        with self.assertRaises(F.OutOfScope):
            F.hemispherical_t(100.0, 600.0, 137.9, 1.0)

    def test_thin_head_limit_uses_specified_thickness(self):
        F.thin_head_scope(7.0, 1203.0)               # 0.0058: in scope
        with self.assertRaises(F.OutOfScope):
            F.thin_head_scope(2.0, 1203.0)           # 0.0017 < 0.002
        # a small REQUIRED thickness (low pressure) is not itself out of scope
        self.assertGreater(F.ellipsoidal_t(0.05, 1203.0, 137.9, 1.0), 0)


class PlateUndertolerance(unittest.TestCase):
    def test_ug16c_rule(self):
        self.assertEqual(F.plate_undertolerance_deduction(8.0, 0.25)[0], 0.0)     # 0.25 <= min(0.25, 0.48)
        self.assertEqual(F.plate_undertolerance_deduction(8.0, 0.30)[0], 0.30)
        self.assertEqual(F.plate_undertolerance_deduction(3.0, 0.20)[0], 0.20)    # 6 % of 3 mm = 0.18
        self.assertEqual(F.plate_undertolerance_deduction(8.0, None)[0], 0.0)


class AreaReplacement(unittest.TestCase):
    BASE = dict(d=100.1804, t=6.2, tr=4.380917698470502, tn=7.0598, trn=0.42702642796248924,
                Sv=137.9, Sn=117.9)

    def test_hand_values_with_pad(self):
        """See data/benchmarks/hand_calcs_si.json case H6 for the arithmetic."""
        r = F.area_replacement(**self.BASE, Sp=137.9, te=8.0, Dp=200.0)
        self.assertAlmostEqual(r["A"], 447.8533427349266, places=9)
        self.assertAlmostEqual(r["A1"], 178.511270850374, places=9)
        self.assertAlmostEqual(r["A2"], 175.7949537957933, places=9)
        self.assertAlmostEqual(r["A5"], 685.6, places=9)
        self.assertTrue(r["adequate"])

    def test_without_pad_fails(self):
        r = F.area_replacement(**self.BASE)
        self.assertFalse(r["adequate"])
        self.assertAlmostEqual(r["A_avail"], 178.511270850374 + 175.79495379579, places=6)

    def test_set_on_nozzle_has_fr1_one(self):
        r = F.area_replacement(**self.BASE, inserted=False)
        self.assertEqual(r["fr1"], 1.0)
        self.assertAlmostEqual(r["A"], self.BASE["d"] * self.BASE["tr"], places=9)

    def test_pad_limits_are_enforced(self):
        big = F.area_replacement(**self.BASE, Sp=137.9, te=40.0, Dp=1000.0)
        self.assertAlmostEqual(big["te_eff"], big["limit_normal"])
        self.assertAlmostEqual(big["Dp_eff"], 2 * big["limit_parallel"])

    def test_strength_ratio_capped_at_one(self):
        r = F.area_replacement(**{**self.BASE, "Sn": 200.0})
        self.assertEqual(r["fr2"], 1.0)


if __name__ == "__main__":
    unittest.main()
