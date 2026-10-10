"""Gate verifier must never turn fixture-only work into three executed gates."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.verify_pascal_three_gates import verify_manifest


class ThreeGateEvidenceTests(unittest.TestCase):
    def test_rejects_missing_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            p.write_text(json.dumps({
                "schema_version": "1.0", "source_scene_sha256": "a" * 64,
                "gates": {
                    "native_persistence": {"status": "pending"},
                    "contam_execution": {"status": "pending"},
                    "native_rendering": {"status": "pending"},
                },
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not executed"):
                verify_manifest(p)

    def test_rejects_invalid_artifact_and_scene_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            gates = {name: {"status": "executed", "source_scene_sha256": "a" * 64,
                            "runner": "self-hosted", "execution_command": "command",
                            "artifacts": {}} for name in (
                                "native_persistence", "contam_execution", "native_rendering")}
            gates["native_rendering"]["source_scene_sha256"] = "b" * 64
            p.write_text(json.dumps({"schema_version": "1.0",
                                     "source_scene_sha256": "a" * 64, "gates": gates}))
            with self.assertRaisesRegex(ValueError, "missing mandatory artifacts"):
                verify_manifest(p)


if __name__ == "__main__":
    unittest.main()
