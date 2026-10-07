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
    "run_physical_field_handoff",
    EXAMPLES/"run_physical_field_handoff.py",
)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FieldHandoffTests(unittest.TestCase):
    def test_default_mode_is_read_only_and_never_calls_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            preflight=root/"preflight.json"
            summary=root/"summary.json"
            with patch.object(
                module,
                "check_physical_tau0_preflight",
                return_value={"status":"PASS"},
            ) as pre, patch.object(
                module,
                "capture_physical_tau0",
                side_effect=AssertionError("capture must not run"),
            ):
                out=module.run_field_handoff(
                    driver=object(),
                    commission_bundle=root/"bringup.json",
                    opening_id="W1",
                    topology_id="demo",
                    preflight_receipt=preflight,
                    trajectory_out=root/"tau.jsonl",
                    tau0_receipt=root/"tau.json",
                    summary_receipt=summary,
                    execute=False,
                )
            pre.assert_called_once()
            self.assertEqual(out["status"],"READY_FOR_EXPLICIT_EXECUTION")
            self.assertFalse(out["motion_performed"])
            self.assertFalse(out["tau0_captured"])
            self.assertEqual(len(out["field_handoff_sha256"]),64)
            persisted=json.loads(summary.read_text())
            self.assertEqual(persisted["field_handoff_sha256"],out["field_handoff_sha256"])

    def test_execute_runs_capture_then_independent_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            trajectory=root/"tau.jsonl"
            tau=root/"tau.json"
            summary=root/"summary.json"
            capture={
                "valid_tau0":True,
                "trajectory_sha256":"a"*64,
                "sim_to_physical_handoff_verified":False,
                "physical_reconcile":None,
            }
            verification={
                "valid_artifacts":True,
                "receipt_sha256":"b"*64,
                "commissioning_identity_sha256":"c"*64,
                "runtime_hardware_identity_sha256":"c"*64,
            }
            order=[]
            def do_preflight(**kwargs):
                order.append("preflight")
                return {"status":"PASS"}
            def do_capture(**kwargs):
                order.append("capture")
                return capture
            def do_verify(**kwargs):
                order.append("verify")
                return verification
            with patch.object(module,"check_physical_tau0_preflight",side_effect=do_preflight), \
                 patch.object(module,"capture_physical_tau0",side_effect=do_capture), \
                 patch.object(module,"verify_physical_tau0_artifacts",side_effect=do_verify):
                out=module.run_field_handoff(
                    driver=object(),
                    commission_bundle=root/"bringup.json",
                    opening_id="W1",
                    topology_id="demo",
                    preflight_receipt=root/"preflight.json",
                    trajectory_out=trajectory,
                    tau0_receipt=tau,
                    summary_receipt=summary,
                    execute=True,
                )
            self.assertEqual(order,["preflight","capture","verify"])
            self.assertEqual(out["status"],"PASS")
            self.assertTrue(out["motion_performed"])
            self.assertTrue(out["artifacts_verified"])
            self.assertEqual(out["verified_tau0_receipt_sha256"],"b"*64)

    def test_failed_independent_verification_stops_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch.object(module,"check_physical_tau0_preflight",return_value={"status":"PASS"}), \
                 patch.object(module,"capture_physical_tau0",return_value={
                     "valid_tau0":True,
                     "physical_reconcile":None,
                 }), \
                 patch.object(module,"verify_physical_tau0_artifacts",return_value={
                     "valid_artifacts":False,
                     "reasons":["tampered command acknowledgement"],
                 }):
                with self.assertRaisesRegex(RuntimeError,"tampered command acknowledgement"):
                    module.run_field_handoff(
                        driver=object(),
                        commission_bundle=root/"bringup.json",
                        opening_id="W1",
                        topology_id="demo",
                        preflight_receipt=root/"preflight.json",
                        trajectory_out=root/"tau.jsonl",
                        tau0_receipt=root/"tau.json",
                        summary_receipt=root/"summary.json",
                        execute=True,
                    )

    def test_next_origin_inputs_fail_closed_if_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch.object(module,"check_physical_tau0_preflight",return_value={"status":"PASS"}), \
                 patch.object(module,"capture_physical_tau0") as capture:
                with self.assertRaisesRegex(RuntimeError,"supplied together"):
                    module.run_field_handoff(
                        driver=object(),
                        commission_bundle=root/"bringup.json",
                        opening_id="W1",
                        topology_id="demo",
                        preflight_receipt=root/"preflight.json",
                        trajectory_out=root/"tau.jsonl",
                        tau0_receipt=root/"tau.json",
                        summary_receipt=root/"summary.json",
                        execute=True,
                        current_origin=root/"origin.json",
                    )
            capture.assert_not_called()


if __name__=="__main__":
    unittest.main()
