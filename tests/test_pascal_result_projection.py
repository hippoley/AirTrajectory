import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.pascal_result_projection import project_contam_to_pascal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/pascal-scene-two-rooms.json"


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class ProjectionContractTests(unittest.TestCase):
    def test_verified_runtime_receipt_identity_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "layout.json"
            run = subprocess.run(["node", "scripts/export-pascal-scene.cjs", str(SOURCE), str(output)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            layout = LayoutContract.from_file(output)
            frame = {"step": 0, "simulation_time_s": 60,
                     "co2_ppm": {"zone_a": 800, "zone_b": 950},
                     "opening_pct": {"window_1": 30, "door_1": 100},
                     "path_flow_kg_s": {"window_1": .01, "door_1": -.02}}
            # Constructed receipt verifies projection contract only, NOT a solver execution.
            receipt = {"status": "ENGINEERING_RUNTIME_VERIFIED", "runtime_verified": True,
                       "layout_contract_sha256": layout.sha256(), "runtime_receipt_sha256": "synthetic",
                       "prediction_series": [frame], "prediction_series_sha256": digest([frame])}
            out = project_contam_to_pascal(layout, receipt)
            self.assertFalse(out["rendered_in_pascal"])
            self.assertEqual(out["frames"][0]["rooms"]["zone_a"]["co2_ppm"], 800)
            self.assertEqual(out["frames"][0]["openings"]["window_1"]["opening_pct"], 30)
            with self.assertRaisesRegex(ValueError, "runtime/layout hash"):
                project_contam_to_pascal(layout, {**receipt, "layout_contract_sha256": "wrong"})
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                project_contam_to_pascal(layout, {**receipt, "prediction_series_sha256": "wrong"})
            with self.assertRaisesRegex(ValueError, "node ID coverage"):
                bad = {**frame, "co2_ppm": {"zone_a": 800}}
                project_contam_to_pascal(layout, {**receipt, "prediction_series": [bad],
                                                  "prediction_series_sha256": digest([bad])})
            with self.assertRaisesRegex(ValueError, "ENGINEERING_RUNTIME_VERIFIED"):
                project_contam_to_pascal(layout, {**receipt, "status": "READY_FOR_PRJ_WRITER"})
            print(json.dumps({"status": "PASSED_PROJECTION_CONTRACT_SYNTHETIC_RECEIPT",
                              "projection_sha256": out["projection_sha256"],
                              "native_3d_render_executed": False,
                              "real_solver_executed_by_this_test": False}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
