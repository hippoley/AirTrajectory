import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "probes" / "catalog.v0.1.json"

class ProbeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_catalog_has_stable_shape(self):
        self.assertEqual(self.catalog["schema"], "playable-correctness-probe-catalog-v0.1")
        self.assertEqual(self.catalog["retrieval_principle"], "human-behavior-first, not technology-first")
        self.assertGreaterEqual(len(self.catalog["probes"]), 3)

    def test_probe_ids_are_unique_and_reality_bounded(self):
        ids = [probe["id"] for probe in self.catalog["probes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for probe in self.catalog["probes"]:
            self.assertTrue(probe["observed_phenomenon"])
            self.assertTrue(probe["behavioral_mechanism"])
            self.assertTrue(probe["probe_primitive"])
            self.assertTrue(probe["measurable_behavior"])
            self.assertTrue(probe["invariant"])
            self.assertIn("build", probe["build_double_kill"])
            self.assertIn("double", probe["build_double_kill"])
            self.assertIn("kill", probe["build_double_kill"])
            self.assertIn("field campaign incomplete", probe["maturity"])

    def test_referenced_repo_artifacts_exist(self):
        keys = {"machine_vector","reconciliation_vector","implementation","reconciliation","execution_path","external_native_fixture"}
        for probe in self.catalog["probes"]:
            evidence = probe["reality_evidence"]
            for key in keys.intersection(evidence):
                path = ROOT / evidence[key]
                self.assertTrue(path.exists(), msg=f"{probe['id']} references missing {key}: {path}")

    def test_browser_probe_never_claims_physical_evidence(self):
        for probe in self.catalog["probes"]:
            self.assertIn("explanatory only", probe["reality_evidence"]["browser"])
            self.assertNotIn("field-observed", probe["maturity"].lower())

if __name__ == "__main__":
    unittest.main()
