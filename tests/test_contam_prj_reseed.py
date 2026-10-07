import unittest

from airtrajectory.contam_prj_reseed import reseed_initial_zone_mass_fractions


SAMPLE = """ContamW 3.4.0.4 0
sample.prj
3 ! initial zone concentrations:
! Z#      CO2
   1 1.00000000e-03
   2 2.00000000e-03
   3 3.00000000e-03
-999
* end project file.
"""


class ContamPrjReseedTests(unittest.TestCase):
    def test_reseed_changes_only_section_15_rows(self):
        out = reseed_initial_zone_mass_fractions(
            SAMPLE,
            {1: 0.0011, 2: 0.0022, 3: 0.0033},
        )
        self.assertIn("   1 1.10000000e-03", out["text"])
        self.assertIn("   2 2.20000000e-03", out["text"])
        self.assertIn("   3 3.30000000e-03", out["text"])
        self.assertEqual(out["receipt"]["zone_count"], 3)
        self.assertNotEqual(
            out["receipt"]["source_prj_sha256"],
            out["receipt"]["reseeded_prj_sha256"],
        )

    def test_reseed_requires_exact_zone_set(self):
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            reseed_initial_zone_mass_fractions(
                SAMPLE,
                {1: 0.0011, 2: 0.0022},
            )

    def test_reseed_rejects_negative_mass_fraction(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            reseed_initial_zone_mass_fractions(
                SAMPLE,
                {1: -0.001, 2: 0.002, 3: 0.003},
            )


if __name__ == "__main__":
    unittest.main()
