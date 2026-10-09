"""CLI counterexamples: imported layouts cannot inherit fixed-demo PRJ profiles."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "examples/generate_multispace_contam_prj.py"
FIXTURE = ROOT / "web/data/home_topology.fixed.json"


class ImportedPrjCliSafetyTests(unittest.TestCase):
    def test_imported_layout_requires_all_explicit_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            source = json.loads(FIXTURE.read_text(encoding="utf-8"))
            source["source_kind"] = "imported-floorplan"
            source["capabilities"]["floorplan_geometry_editable"] = True
            source["capabilities"]["arbitrary_topology_import"] = "supported"
            source["source_provenance"] = {
                "format": "JSON", "source_sha256": "a" * 64,
                "importer": {"id": "test", "version": "1"},
            }
            path = Path(directory) / "unfamiliar.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CLI), "--layout", str(path),
                 "--out", str(Path(directory) / "out.prj")],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("imported layouts require explicitly supplied", result.stderr)
            for required in ("--metric-profile", "--boundary-profile",
                             "--prj-profile", "--airflow-profile"):
                self.assertIn(required, result.stderr)
            self.assertFalse((Path(directory) / "out.prj").exists())


if __name__ == "__main__":
    unittest.main()
