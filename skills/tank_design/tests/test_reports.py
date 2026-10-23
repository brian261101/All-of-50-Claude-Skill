"""Report generation through the skill script."""

import json
import re
import unittest

from _support import calculated_package, run


class Report(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = calculated_package()
        cls.rc, cls.out, cls.err = run("generate_report.py", cls.pkg)

    def test_pdf_written_and_checked(self):
        self.assertEqual(self.rc, 0, self.out + self.err)
        r = json.loads(self.out)
        self.assertTrue(r["check"]["ok"], r["check"])
        self.assertGreater(r["pages"], 20)
        self.assertTrue(r["pdf"].endswith("PV-DEMO-001_V-101_Design_Calculation_Rev00.pdf"))

    def test_status_presentation(self):
        html = next((self.pkg / "01_CALCULATION").glob("*.html")).read_text(encoding="utf-8")
        self.assertIn("NOT FOR FABRICATION", html)
        self.assertIn("NEEDS_ENGINEERING_REVIEW", html)
        self.assertIn("NOT_EVALUATED", html)
        # no green: nothing unevaluated may look accepted
        self.assertIsNone(re.search(r"color:\s*(green|#0[0-9a-f]{1}[89a-f][0-9a-f]{3})", html, re.I))

    def test_every_calculation_is_in_the_report(self):
        res = json.loads((self.pkg / "01_CALCULATION" / "calculation_results.json").read_text(encoding="utf-8"))
        chk = json.loads((self.pkg / "01_CALCULATION" / "report_check.json").read_text(encoding="utf-8"))
        self.assertEqual(chk["missing_strings"], [])
        self.assertGreater(len(res["records"]), 50)


if __name__ == "__main__":
    unittest.main()
