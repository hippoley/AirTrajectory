import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
SCRIPT = ROOT / "examples" / "bind_contam_boundary.py"
BOUNDARY = ROOT / "examples" / "contam_boundary_profile.example.json"


class ContamBoundaryCliTests(unittest.TestCase):
    def _metric_layout_file(self, directory: Path) -> Path:
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        for wall in payload["walls"]:
            wall["length_m"] = 5.0
            wall["azimuth_deg"] = 90.0
        for opening in payload["openings"]:
            opening["width_m"] = 1.0
            opening["height_m"] = 2.0
            opening["sill_height_m"] = 0.2 if opening["kind"] == "door" else 0.9
            opening["max_area_m2"] = min(opening["max_area_m2"], 2.0)
        path = directory / "metric-layout.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_cli_builds_forced_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            layout = self._metric_layout_file(directory)
            out = directory / "forced.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(layout),
                    str(BOUNDARY),
                    "--illustrative-demo-airflow",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["compiler"], "contam-forced-manifest")
            self.assertEqual(payload["contaminant_numbers"]["co2"], 1)
            self.assertTrue(payload["weather"])

    def test_production_gate_rejects_demo_airflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            layout = self._metric_layout_file(directory)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(layout),
                    str(BOUNDARY),
                    "--illustrative-demo-airflow",
                    "--require-engineering-validated",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("engineering-validated", proc.stderr)


if __name__ == "__main__":
    unittest.main()
