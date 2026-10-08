from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"examples"/"verify_imported_topology.py"
FIXTURE=ROOT/"tests"/"data"/"topology.imported-four-room.json"

class ImportedTopologyCliTests(unittest.TestCase):
    def test_imported_fixture_emits_pass_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"receipt.json"
            p=subprocess.run(
                [sys.executable,str(SCRIPT),str(FIXTURE),"--out",str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(p.returncode,0,p.stderr)
            payload=json.loads(out.read_text())
            self.assertEqual(payload["source_kind"],"imported-floorplan")
            self.assertEqual(payload["arbitrary_topology_import"],"supported")
            self.assertEqual(payload["runtime_acceptance"]["status"],"PASS")
            self.assertEqual(
                payload["runtime_acceptance"]["expected"]["zone_ids"],
                ["center_room","east_room","north_room","south_room"],
            )

if __name__=="__main__":
    unittest.main()
