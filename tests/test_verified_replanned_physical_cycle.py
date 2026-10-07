import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0,str(EXAMPLES))

SPEC=importlib.util.spec_from_file_location(
    "run_verified_replanned_physical_cycle",
    EXAMPLES/"run_verified_replanned_physical_cycle.py",
)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class VerifiedReplannedPhysicalCycleTests(unittest.TestCase):
    def _paths(self,root):
        previous=root/"previous.json"
        planner=root/"planner.json"
        previous.write_text(json.dumps({"previous":True}),encoding="utf-8")
        planner.write_text(json.dumps({"planner":True}),encoding="utf-8")
        return {
            "previous":previous,
            "planner":planner,
            "step":root/"step.json",
            "next":root/"next.json",
            "verification":root/"verification.json",
            "summary":root/"cycle.json",
            "leases":root/"leases",
        }

    def _fake_step(self,paths):
        def run(**kwargs):
            step={
                "schema_version":"0.1",
                "workflow":"replanned-windowpilot-physical-step-v1",
                "mode":"execute",
                "status":"PASS",
                "motion_performed":True,
                "next_origin_ready":True,
                "replanned_physical_step_sha256":"a"*64,
                "next_physical_origin_receipt_sha256":"b"*64,
            }
            Path(kwargs["summary_out"]).write_text(
                json.dumps(step),
                encoding="utf-8",
            )
            Path(kwargs["next_origin_out"]).write_text(
                json.dumps({"next":True}),
                encoding="utf-8",
            )
            return step
        return run

    def _verification(self):
        return {
            "schema_version":"0.1",
            "verification":"persisted-replanned-physical-cycle-v1",
            "status":"PASS",
            "field_transition_contract_verified":True,
            "physical_cycle_verification_sha256":"c"*64,
            "previous_origin_receipt_sha256":"d"*64,
            "planner_receipt_sha256":"e"*64,
            "planner_step_sha256":"f"*64,
            "command_request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "command_idempotency_scope_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "command_ack_sha256":"1"*64,
            "sensor_snapshot_sha256":"2"*64,
            "next_origin_receipt_sha256":"3"*64,
        }

    def test_default_mode_is_read_only_and_does_not_claim_cycle_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths=self._paths(root)
            step={
                "status":"READY_FOR_EXPLICIT_EXECUTION",
                "motion_performed":False,
                "next_origin_ready":False,
                "replanned_physical_step_sha256":"a"*64,
            }
            with patch.object(
                module,
                "run_replanned_physical_step",
                return_value=step,
            ) as runner, patch.object(
                module,
                "verify_persisted_physical_cycle",
            ) as verifier:
                out=module.run_verified_replanned_physical_cycle(
                    driver=object(),
                    previous_origin_receipt=paths["previous"],
                    planner_receipt=paths["planner"],
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10,
                    step_summary_out=paths["step"],
                    next_origin_out=paths["next"],
                    verification_out=paths["verification"],
                    cycle_summary_out=paths["summary"],
                    execute=False,
                    lease_dir=paths["leases"],
                )
            self.assertEqual(out["status"],"READY_FOR_EXPLICIT_EXECUTION")
            self.assertFalse(out["motion_performed"])
            self.assertFalse(out["cycle_verified"])
            verifier.assert_not_called()
            self.assertFalse(runner.call_args.kwargs["execute"])
            persisted=json.loads(paths["summary"].read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"],"READY_FOR_EXPLICIT_EXECUTION")

    def test_execute_requires_independent_verifier_pass_before_final_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths=self._paths(root)
            verification=self._verification()
            with patch.object(
                module,
                "run_replanned_physical_step",
                side_effect=self._fake_step(paths),
            ) as runner, patch.object(
                module,
                "verify_persisted_physical_cycle",
                return_value=verification,
            ) as verifier:
                out=module.run_verified_replanned_physical_cycle(
                    driver=object(),
                    previous_origin_receipt=paths["previous"],
                    planner_receipt=paths["planner"],
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10,
                    step_summary_out=paths["step"],
                    next_origin_out=paths["next"],
                    verification_out=paths["verification"],
                    cycle_summary_out=paths["summary"],
                    execute=True,
                    lease_dir=paths["leases"],
                )
            self.assertTrue(runner.call_args.kwargs["execute"])
            verifier.assert_called_once()
            self.assertEqual(out["status"],"PASS")
            self.assertTrue(out["motion_performed"])
            self.assertTrue(out["cycle_verified"])
            self.assertTrue(out["field_transition_contract_verified"])
            self.assertEqual(
                out["physical_cycle_verification_sha256"],
                "c"*64,
            )
            persisted_verification=json.loads(
                paths["verification"].read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_verification["status"],"PASS")
            persisted_summary=json.loads(
                paths["summary"].read_text(encoding="utf-8")
            )
            self.assertEqual(persisted_summary["status"],"PASS")

    def test_verifier_failure_after_motion_persists_blocked_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            paths=self._paths(root)
            with patch.object(
                module,
                "run_replanned_physical_step",
                side_effect=self._fake_step(paths),
            ), patch.object(
                module,
                "verify_persisted_physical_cycle",
                side_effect=RuntimeError("next origin mismatch"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "physical action executed but persisted-cycle verification failed",
                ):
                    module.run_verified_replanned_physical_cycle(
                        driver=object(),
                        previous_origin_receipt=paths["previous"],
                        planner_receipt=paths["planner"],
                        opening_id="W1",
                        zone_id="living",
                        max_delta_pct=10,
                        step_summary_out=paths["step"],
                        next_origin_out=paths["next"],
                        verification_out=paths["verification"],
                        cycle_summary_out=paths["summary"],
                        execute=True,
                        lease_dir=paths["leases"],
                    )
            persisted=json.loads(paths["summary"].read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["status"],
                "BLOCKED_VERIFICATION_FAILED",
            )
            self.assertTrue(persisted["motion_performed"])
            self.assertFalse(persisted["cycle_verified"])
            self.assertTrue(persisted["next_origin_ready"])
            self.assertIn("next origin mismatch",persisted["verification_error"])
            self.assertFalse(paths["verification"].exists())


if __name__=="__main__":
    unittest.main()
