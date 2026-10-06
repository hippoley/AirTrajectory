import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "export_demo_runtime_snapshot.py"
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


class DemoRuntimeExportTests(unittest.TestCase):
    def test_export_matches_resolved_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "runtime.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--layout",
                    str(LAYOUT),
                    "--out",
                    str(out),
                    "--topology-revision",
                    "5",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            expected = DemoRuntimeSnapshot.resolve(
                LayoutContract.from_file(LAYOUT),
                topology_revision=5,
            )
            self.assertEqual(
                payload["runtime"]["snapshot_sha256"],
                expected.sha256(),
            )
            self.assertEqual(payload["runtime"]["topology_revision"], 5)
            self.assertEqual(payload["runtime"]["source"], "DemoRuntimeSnapshot")


if __name__ == "__main__":
    unittest.main()
