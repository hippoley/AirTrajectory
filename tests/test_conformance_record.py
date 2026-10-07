import unittest

from airtrajectory.conformance_record import (
    build_field_execution_record,
    validate_field_execution_record,
)


EXECUTION_SHA="a"*64
STEP_SHA="b"*64
ORIGIN_RECEIPT_SHA="c"*64
AUTH_SHA="d"*64
LEASE_SHA="e"*64
ACK_SHA="f"*64
SNAPSHOT_SHA="1"*64
NEXT_SHA="2"*64
VERIFY_SHA="3"*64
IDENTITY_SHA="4"*64
SCOPE_ID="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQUEST_ID="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
COMMAND_ID="cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def pass_cycle():
    return {
        "schema_version":"0.1",
        "workflow":"verified-replanned-physical-cycle-v1",
        "mode":"execute",
        "status":"PASS",
        "motion_performed":True,
        "cycle_verified":True,
        "opening_id":"W1",
        "zone_id":"living",
        "verified_physical_cycle_sha256":EXECUTION_SHA,
        "physical_cycle_verification_sha256":VERIFY_SHA,
        "command_request_id":REQUEST_ID,
        "command_idempotency_scope_id":SCOPE_ID,
        "command_ack_sha256":ACK_SHA,
        "sensor_snapshot_sha256":SNAPSHOT_SHA,
        "previous_origin_receipt":"artifacts/origin-1.json",
        "planner_receipt":"artifacts/planner.json",
        "step_summary":"artifacts/step.json",
        "next_origin":"artifacts/origin-2.json",
        "verification_receipt":"artifacts/verify.json",
    }


def pass_step():
    return {
        "schema_version":"0.1",
        "workflow":"replanned-windowpilot-physical-step-v1",
        "mode":"execute",
        "status":"PASS",
        "opening_id":"W1",
        "zone_id":"living",
        "motion_performed":True,
        "next_origin_ready":True,
        "physical_write_ready":True,
        "physical_origin_receipt_sha256":ORIGIN_RECEIPT_SHA,
        "replanned_action_authorization_sha256":AUTH_SHA,
        "execution_lease_claim_sha256":LEASE_SHA,
        "replanned_physical_step_sha256":STEP_SHA,
        "readiness_hardware_identity_sha256":IDENTITY_SHA,
        "origin_hardware_identity_sha256":IDENTITY_SHA,
        "command_request_id":REQUEST_ID,
        "command_idempotency_scope_id":SCOPE_ID,
        "command_ack_sha256":ACK_SHA,
        "command_ack":{
            "command_id":COMMAND_ID,
            "command_ack_sha256":ACK_SHA,
        },
        "authorized_target_pct":10.0,
        "origin_freshness_checked_at":100.0,
        "actuator_feedback":{
            "timestamp":101.0,
            "measured_position_pct":9.9,
        },
        "sensor_snapshot_sha256":SNAPSHOT_SHA,
        "sensor_snapshot":{
            "fresh_after_action":True,
            "snapshot_sha256":SNAPSHOT_SHA,
        },
        "next_physical_origin_receipt_sha256":NEXT_SHA,
    }


def pass_verification():
    return {
        "schema_version":"0.1",
        "verification":"persisted-replanned-physical-cycle-v1",
        "status":"PASS",
        "opening_id":"W1",
        "zone_id":"living",
        "origin_hardware_identity_sha256":IDENTITY_SHA,
        "command_request_id":REQUEST_ID,
        "command_idempotency_scope_id":SCOPE_ID,
        "command_id":COMMAND_ID,
        "command_ack_sha256":ACK_SHA,
        "sensor_snapshot_sha256":SNAPSHOT_SHA,
        "authorized_target_pct":10.0,
        "measured_position_pct":9.9,
        "physical_cycle_verification_sha256":VERIFY_SHA,
    }


class FieldExecutionRecordTests(unittest.TestCase):
    def test_pass_cycle_projects_to_transport_neutral_record(self):
        record=build_field_execution_record(
            cycle_summary=pass_cycle(),
            step_summary=pass_step(),
            verification_receipt=pass_verification(),
            spec_clause_refs=("GEISA-field-tool-observe","GEISA-field-tool-execute"),
        )
        self.assertEqual(record["result"],"PASS")
        self.assertTrue(record["motion_performed"])
        self.assertTrue(record["cycle_verified"])
        self.assertEqual(record["execution_id"],EXECUTION_SHA)
        self.assertEqual(record["parent_execution_id"],STEP_SHA)
        self.assertEqual(record["target"]["target_identity"],IDENTITY_SHA)
        self.assertEqual(record["target"]["idempotency_scope_id"],SCOPE_ID)
        self.assertEqual(record["request"]["request_id"],REQUEST_ID)
        self.assertEqual(record["request"]["command_id"],COMMAND_ID)
        self.assertEqual(record["request"]["command_ack_sha256"],ACK_SHA)
        self.assertEqual(record["request"]["authorized_target_pct"],10.0)
        self.assertEqual(record["observation"]["measured_position_pct"],9.9)
        self.assertEqual(
            [row["phase"] for row in record["phases"]],
            ["PRECHECK","EXECUTE","OBSERVE","VERIFY"],
        )
        self.assertTrue(
            all(row["result"]=="PASS" for row in record["phases"])
        )
        validate_field_execution_record(record)

    def test_post_motion_verifier_failure_stays_blocked(self):
        cycle=pass_cycle()
        cycle.update({
            "status":"BLOCKED_VERIFICATION_FAILED",
            "cycle_verified":False,
            "verification_error":"next origin mismatch",
        })
        step=pass_step()
        record=build_field_execution_record(
            cycle_summary=cycle,
            step_summary=step,
            verification_receipt=None,
        )
        self.assertEqual(record["result"],"BLOCKED")
        self.assertTrue(record["motion_performed"])
        self.assertFalse(record["cycle_verified"])
        self.assertEqual(record["reason_code"],"BLOCKED_VERIFICATION_FAILED")
        verify_phase=[
            row for row in record["phases"] if row["phase"]=="VERIFY"
        ][0]
        self.assertEqual(verify_phase["result"],"BLOCKED")
        self.assertIn("next origin mismatch",verify_phase["detail"])

    def test_recovery_required_projects_to_uncertain(self):
        cycle=pass_cycle()
        cycle.update({
            "status":"RECOVERY_REQUIRED",
            "cycle_verified":False,
        })
        step=pass_step()
        step.update({
            "status":"RECOVERY_REQUIRED",
            "safe_closeout":{
                "confirmed_closed":False,
                "error":"transport lost",
            },
        })
        record=build_field_execution_record(
            cycle_summary=cycle,
            step_summary=step,
            verification_receipt=None,
        )
        self.assertEqual(record["result"],"UNCERTAIN")
        self.assertTrue(record["motion_performed"])
        self.assertFalse(record["cycle_verified"])
        recovery=[
            row for row in record["phases"] if row["phase"]=="RECOVERY"
        ][0]
        self.assertEqual(recovery["result"],"UNCERTAIN")

    def test_pass_without_verification_is_rejected(self):
        cycle=pass_cycle()
        cycle["cycle_verified"]=False
        with self.assertRaisesRegex(RuntimeError,"PASS cycle"):
            build_field_execution_record(
                cycle_summary=cycle,
                step_summary=pass_step(),
                verification_receipt=None,
            )

    def test_verified_non_pass_record_is_rejected(self):
        cycle=pass_cycle()
        cycle["status"]="BLOCKED_VERIFICATION_FAILED"
        with self.assertRaisesRegex(RuntimeError,"verified cycle"):
            build_field_execution_record(
                cycle_summary=cycle,
                step_summary=pass_step(),
                verification_receipt=pass_verification(),
            )

    def test_validator_rejects_pass_without_motion(self):
        record=build_field_execution_record(
            cycle_summary=pass_cycle(),
            step_summary=pass_step(),
            verification_receipt=pass_verification(),
        )
        record["motion_performed"]=False
        with self.assertRaisesRegex(RuntimeError,"must prove motion"):
            validate_field_execution_record(record)


if __name__=="__main__":
    unittest.main()
