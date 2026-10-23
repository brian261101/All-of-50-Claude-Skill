"""The skill's own contract: frontmatter, binding rules, gates and the files SKILL.md names."""

from __future__ import annotations

import re
import unittest

from _support import SKILL

TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")


class SkillContract(unittest.TestCase):
    def test_frontmatter(self):
        m = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", TEXT)
        self.assertIsNotNone(m, "frontmatter must hold name and description")
        self.assertEqual(m.group(1).strip(), "tank-vessel-design")
        self.assertLess(len(m.group(2)), 1500)

    def test_binding_rules_present(self):
        for phrase in ("## This skill is binding", "One engine, no parallel calculations",
                       "Missing capability = OUT_OF_SCOPE", "The primary document wins",
                       "Name every standard the documents cite"):
            self.assertIn(phrase, TEXT)

    def test_gates_in_order(self):
        gates = [int(g) for g in re.findall(r"\*\*G(\d):", TEXT)]
        self.assertEqual(gates, sorted(gates))
        self.assertEqual(gates[0], 1)
        self.assertIn("0. **Source intake.**", TEXT)

    def test_named_files_exist(self):
        for rel in re.findall(r"`((?:references|templates)/[\w.-]+)`", TEXT):
            self.assertTrue((SKILL / rel).is_file(), rel)
        self.assertTrue((SKILL / "templates" / "source-register.md").is_file())

    def test_standards_classes_known(self):
        ref = (SKILL / "references" / "standards-references.md").read_text(encoding="utf-8")
        rows = [r for r in ref.splitlines() if r.startswith("| ") and not r.startswith(("| Standard", "| Class",
                                                                                         "| Document"))]
        classes = {"IMPLEMENTED", "DATA_SOURCE", "CITED_ONLY", "OUT_OF_SCOPE"}
        for r in rows:
            if r.split("|")[1].strip() in classes:      # the table that defines the classes
                continue
            cell = r.rstrip(" |").split("|")[-1]
            self.assertTrue(any(c in cell for c in classes), r)


if __name__ == "__main__":
    unittest.main()
