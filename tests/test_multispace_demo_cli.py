import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "run_multispace_demo.py"


class MultiSpaceDemoCliTests(unittest.TestCase):
    def test_demo_uses_one_runtime_snapshot_for_multiwindow_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--steps",
                    "2",
                    "--topology-revision",
                    "4",
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
            self.assertEqual(payload["topology_revision"], 4)
            self.assertEqual(
                payload["runtime_snapshot_sha256"],
                payload["trajectory"]["context"][
                    "demo_runtime_snapshot_sha256"
                ],
            )
            self.assertEqual(
                set(payload["opening_ids"]),
                {"W1", "W2", "W3", "D1", "D2"},
            )
            self.assertEqual(len(payload["trajectory"]["steps"]), 2)


if __name__ == "__main__":
    unittest.main()
