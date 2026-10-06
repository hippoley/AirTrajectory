import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "bind_contam_prj_profile.py"
PROFILE = ROOT / "examples" / "contam_prj_profile.example.json"


class ContamPrjProfileCliTests(unittest.TestCase):
    def test_cli_can_reach_ready_with_explicit_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            forced = directory / "forced.json"
            forced.write_text(json.dumps({
                "compiler":"contam-forced-manifest",
                "topology_id":"demo",
                "layout_contract_sha256":"a"*64,
                "mapping_sha256":"b"*64,
                "airflow_binding_sha256":"c"*64,
                "boundary_binding_sha256":"d"*64,
                "zones":[
                    {"key":"zone:living","name":"living","volume_m3":75.0},
                    {"key":"zone:bedroom","name":"bedroom","volume_m3":37.5},
                    {"key":"zone:study","name":"study","volume_m3":40.0}
                ],
                "flow_paths":[
                    {"key":"path:W1","layout_opening_id":"W1","kind":"window","wall_azimuth_deg":270.0},
                    {"key":"path:W2","layout_opening_id":"W2","kind":"window","wall_azimuth_deg":90.0},
                    {"key":"path:W3","layout_opening_id":"W3","kind":"window","wall_azimuth_deg":180.0},
                    {"key":"path:D1","layout_opening_id":"D1","kind":"door","wall_azimuth_deg":90.0},
                    {"key":"path:D2","layout_opening_id":"D2","kind":"door","wall_azimuth_deg":180.0}
                ],
                "airflow_elements":[
                    {"key":"element:W1","layout_opening_id":"W1","flow_exponent":0.5,"flow_area_m2":1.0,"discharge_coefficient":0.6},
                    {"key":"element:W2","layout_opening_id":"W2","flow_exponent":0.5,"flow_area_m2":1.0,"discharge_coefficient":0.6},
                    {"key":"element:W3","layout_opening_id":"W3","flow_exponent":0.5,"flow_area_m2":1.0,"discharge_coefficient":0.6},
                    {"key":"element:D1","layout_opening_id":"D1","flow_exponent":0.5,"flow_area_m2":1.0,"discharge_coefficient":0.6},
                    {"key":"element:D2","layout_opening_id":"D2","flow_exponent":0.5,"flow_area_m2":1.0,"discharge_coefficient":0.6}
                ],
                "contaminants":[{
                    "key":"co2","name":"CO2","contam_contaminant_number":1,
                    "outdoor_concentration":430.0,
                    "initial_zone_concentration":{
                        "zone:living":1400.0,"zone:bedroom":900.0,"zone:study":800.0
                    }
                }]
            }), encoding="utf-8")
            out = directory / "profiled.json"
            readiness = directory / "readiness.json"
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), str(forced), str(PROFILE),
                    "--out", str(out), "--readiness-out", str(readiness)
                ],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            audit = json.loads(readiness.read_text(encoding="utf-8"))
            self.assertTrue(audit["prj_serialization_ready"])
            self.assertEqual(audit["missing"], {})


if __name__ == "__main__":
    unittest.main()
