import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "generate_multispace_contam_prj.py"


class GenerateMultispaceContamPrjTests(unittest.TestCase):
    def test_generator_emits_three_zone_five_path_project_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo.prj"
            prov = Path(tmp) / "demo.prj.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--out",
                    str(out),
                    "--provenance-out",
                    str(prov),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = out.read_text(encoding="utf-8")
            payload = json.loads(prov.read_text(encoding="utf-8"))

            self.assertIn("3 ! zones:", text)
            self.assertIn("5 ! flow paths:", text)
            self.assertEqual(payload["zones"], 3)
            self.assertEqual(payload["paths"], 5)
            self.assertFalse(payload["engineering_truth"])
            self.assertEqual(
                payload["purpose"],
                "generated topology/load smoke",
            )
            self.assertEqual(
                len(payload["demo_runtime_snapshot_sha256"]),
                64,
            )
            self.assertEqual(
                payload["input_control_ranges"]["W1"]["closed_value"],
                0.01,
            )
            self.assertAlmostEqual(
                payload["initial_input_controls"]["1"]["value"],
                0.01 + 0.99 * 0.65,
            )
            self.assertEqual(
                payload["engineering_readiness"]["status"],
                "SOFTWARE_VERIFIED_ONLY",
            )
            self.assertFalse(
                payload["engineering_readiness"]["engineering_truth"]
            )
            self.assertIn(
                "airflow_calibration",
                payload["engineering_readiness"]["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
