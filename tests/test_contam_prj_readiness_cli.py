import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from airtrajectory.contam_prj_readiness import audit_prj_readiness


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "inspect_contam_prj_readiness.py"


class ContamPrjReadinessCliTests(unittest.TestCase):
    def _blocked_manifest(self, directory: Path) -> Path:
        manifest = {
            "compiler": "contam-forced-manifest",
            "topology_id": "demo",
            "layout_contract_sha256": "a" * 64,
            "mapping_sha256": "b" * 64,
            "airflow_binding_sha256": "c" * 64,
            "boundary_binding_sha256": "d" * 64,
            "zones": [
                {"key": "zone:z1", "volume_m3": 10.0}
            ],
            "airflow_elements": [
                {
                    "key": "element:w1",
                    "flow_exponent": 0.5,
                    "flow_area_m2": 1.0,
                    "discharge_coefficient": 0.6,
                }
            ],
            "flow_paths": [
                {
                    "key": "path:w1",
                    "wall_azimuth_deg": 90.0,
                }
            ],
            "contaminants": [
                {
                    "key": "co2",
                    "outdoor_concentration": 430.0,
                    "initial_zone_concentration": {"zone:z1": 900.0},
                }
            ],
        }
        path = directory / "forced.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_cli_emits_blockers_and_require_ready_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            manifest = self._blocked_manifest(directory)
            out = directory / "readiness.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(manifest),
                    "--require-ready",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["prj_serialization_ready"])
            self.assertTrue(result["missing"])


if __name__ == "__main__":
    unittest.main()
