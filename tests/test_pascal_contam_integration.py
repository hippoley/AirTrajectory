"""Annotated Pascal fixture -> Node bridge -> Python LayoutContract -> symbolic CONTAM IR.
Not a native browser save/reopen or a physics solver execution.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/pascal-scene-two-rooms.json"


class PascalContamIntegration(unittest.TestCase):
    def test_pascal_fixture_through_contam_cli(self):
        from airtrajectory.layout import LayoutContract
        from airtrajectory.contam_ir import compile_contam_ir

        with tempfile.TemporaryDirectory() as tmp:
            layout_path = Path(tmp) / "layout.json"
            run = subprocess.run(["node", "scripts/export-pascal-scene.cjs", str(SOURCE), str(layout_path)],
                                 cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "LAYOUT_IMPORTED_NOT_PHYSICS_VERIFIED")
            layout = LayoutContract.from_file(layout_path)
            source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            self.assertEqual(layout.source_provenance["source_sha256"], source_sha)
            self.assertEqual({r.id for r in layout.rooms}, {"zone_a", "zone_b"})
            self.assertEqual({o.id for o in layout.openings}, {"window_1", "door_1"})
            ir = compile_contam_ir(layout)
            self.assertEqual(ir["status"], "READY_FOR_PRJ_WRITER")
            self.assertFalse(ir["writer_contract"]["ready"])
            self.assertEqual(len(ir["zones"]), 2)
            paths = {p["layout_opening_id"]: p for p in ir["flow_paths"]}
            self.assertEqual(set(paths), {"window_1", "door_1"})
            self.assertEqual(paths["window_1"]["boundary_kind"], "exterior")
            self.assertEqual(paths["door_1"]["boundary_kind"], "internal")
            self.assertEqual(paths["window_1"]["sill_height_m"], .9)
            self.assertEqual(paths["door_1"]["sill_height_m"], 0)
            self.assertEqual(paths["window_1"]["to"], "ambient:OUTSIDE")
            self.assertEqual(paths["door_1"]["to"], "zone:zone_b")
            self.assertTrue(all(0 <= p["wall_azimuth_deg"] < 360 for p in paths.values()))
            # Stable opening IDs are sufficient for symbolic mapping; no renderer is exercised.
            mapping = {p["layout_opening_id"]: p["key"] for p in ir["flow_paths"]}
            self.assertEqual(set(mapping), {"window_1", "door_1"})

            ir_path = Path(tmp) / "contam-ir.json"
            cli = subprocess.run([sys.executable, "examples/compile_contam_ir.py", str(layout_path),
                                  "--out", str(ir_path)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertEqual(json.loads(ir_path.read_text())["contam_semantics_sha256"],
                             ir["contam_semantics_sha256"])
            print(json.dumps({"status": "PASSED_ANNOTATED_FIXTURE_TO_SYMBOLIC_IR",
                              "source_sha256": source_sha,
                              "layout_contract_sha256": layout.sha256(),
                              "contam_semantics_sha256": ir["contam_semantics_sha256"],
                              "zones": len(ir["zones"]), "flow_paths": len(paths),
                              "mapping_ids": sorted(mapping),
                              "native_save_reopen_verified": False,
                              "physical_solver_executed": False,
                              "native_3d_overlay_verified": False}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
