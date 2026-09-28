import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
SCRIPT = ROOT / "examples" / "inspect_layout_readiness.py"


class LayoutReadinessCliTests(unittest.TestCase):
    def test_current_fixed_layout_reports_metric_blockers(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(LAYOUT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["metric_geometry_ready"])
        self.assertFalse(payload["contam_metric_inputs_ready"])
        self.assertFalse(payload["prj_generation_implemented"])
        self.assertTrue(payload["missing_metric_wall_fields"])
        self.assertTrue(payload["missing_metric_opening_fields"])

    def test_require_flag_fails_when_metric_geometry_is_incomplete(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(LAYOUT),
                "--require-contam-input-ready",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
