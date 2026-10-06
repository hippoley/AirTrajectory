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


if __name__ == "__main__":
    unittest.main()
