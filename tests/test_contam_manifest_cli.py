import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
SCRIPT = ROOT / "examples" / "compile_contam_manifest.py"


class ContamManifestCliTests(unittest.TestCase):
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

    def test_cli_writes_deterministic_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            layout = self._metric_layout_file(directory)
            out = directory / "contam-manifest.json"

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(layout), "--out", str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "READY_FOR_PRJ_SERIALIZATION")
            self.assertEqual(payload["writer_contract"]["numeric_id_assignment"], "implemented")
            self.assertFalse(payload["writer_contract"]["ready"])
            self.assertEqual(len(payload["mapping_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
