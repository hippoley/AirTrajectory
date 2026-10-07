import unittest

from airtrajectory.execution_evidence import (
    build_execution_evidence_envelope,
    validate_execution_evidence_envelope,
)


def base_envelope():
    return {
        "schema_version":"0.1",
        "record_type":"execution-evidence-envelope-v0.1",
        "execution_id":"exec-1",
        "parent_execution_id":None,
        "subject":{"kind":"conformance-execution","identity":"case-1","version":"0.1"},
        "target":{"kind":"device","identity":"device-1","scope":None},
        "operation":{"kind":"transition","request_id":"req-1","ack_id":"ack-1","mutation_expected":True,"parameters":{}},
        "harness_status":"COMPLETED",
        "result":"PASS",
        "reason_code":None,
        "observations":[],
        "recovery":{"required":False,"performed":False,"status":"NOT_REQUIRED","evidence_refs":[]},
        "verification":{"performed":True,"status":"PASS","verifier":"test","evidence_refs":[]},
        "provenance":{},
        "artifact_refs":[],
        "evidence_boundary":"test fixture",
        "extensions":{"physical":{"opening_id":"W1","zone_id":"living"}},
    }


class ExecutionEvidenceEnvelopeTests(unittest.TestCase):
    def test_pass_requires_verifier_pass(self):
        payload=base_envelope()
        validate_execution_evidence_envelope(payload)
        payload["verification"]["status"]="BLOCKED"
        with self.assertRaisesRegex(RuntimeError,"verifier PASS"):
            validate_execution_evidence_envelope(payload)

    def test_uncertain_requires_recovery(self):
        payload=base_envelope()
        payload["result"]="UNCERTAIN"
        payload["verification"]={"performed":False,"status":"NOT_PERFORMED","verifier":None,"evidence_refs":[]}
        payload["recovery"]={"required":False,"performed":False,"status":"NOT_REQUIRED","evidence_refs":[]}
        with self.assertRaisesRegex(RuntimeError,"requires recovery"):
            validate_execution_evidence_envelope(payload)

    def test_domain_fields_remain_in_extensions(self):
        payload=base_envelope()
        self.assertNotIn("opening_id",payload["target"])
        self.assertNotIn("zone_id",payload["target"])
        self.assertEqual(payload["extensions"]["physical"]["opening_id"],"W1")

    def test_blocked_write_preserves_mutation_intent_without_claiming_motion(self):
        field_record={
            "schema_version":"0.1",
            "record_type":"field-execution-record-v0.1",
            "execution_id":"a"*64,
            "parent_execution_id":None,
            "test_case_id":"blocked-write",
            "spec_clause_refs":[],
            "result":"BLOCKED",
            "reason_code":"READINESS_BLOCKED",
            "detail":"write gate closed",
            "motion_performed":False,
            "cycle_verified":False,
            "started_at":1.0,
            "completed_at":None,
            "target":{
                "target_identity":"b"*64,
                "opening_id":"W1",
                "zone_id":"living",
                "idempotency_scope_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            },
            "request":{
                "request_id":"req-1",
                "command_id":None,
                "command_ack_sha256":None,
                "authorized_target_pct":10.0,
            },
            "observation":{
                "measured_position_pct":None,
                "sensor_snapshot_sha256":None,
                "fresh_after_action":None,
            },
            "phases":[
                {
                    "phase":"PRECHECK",
                    "result":"BLOCKED",
                    "reason_code":"READINESS_BLOCKED",
                    "detail":"write gate closed",
                    "evidence_refs":[],
                },
                {
                    "phase":"EXECUTE",
                    "result":"BLOCKED",
                    "reason_code":"READINESS_BLOCKED",
                    "detail":None,
                    "evidence_refs":[],
                },
                {
                    "phase":"VERIFY",
                    "result":"BLOCKED",
                    "reason_code":"READINESS_BLOCKED",
                    "detail":None,
                    "evidence_refs":[],
                },
            ],
            "artifact_refs":[],
            "evidence_boundary":"test fixture",
        }
        envelope=build_execution_evidence_envelope(field_record)
        self.assertTrue(envelope["operation"]["mutation_expected"])
        self.assertFalse(envelope["extensions"]["physical"]["motion_performed"])
        self.assertFalse(envelope["extensions"]["physical"]["mutation_observed"])
        self.assertEqual(envelope["result"],"BLOCKED")

    def test_fail_can_be_a_successful_harness_execution(self):
        payload=base_envelope()
        payload["result"]="FAIL"
        payload["verification"]["status"]="FAIL"
        validate_execution_evidence_envelope(payload)
        self.assertEqual(payload["harness_status"],"COMPLETED")

    def test_harness_error_requires_not_evaluated(self):
        payload=base_envelope()
        payload["harness_status"]="ERROR"
        payload["result"]="NOT_EVALUATED"
        payload["verification"]={
            "performed":False,
            "status":"NOT_PERFORMED",
            "verifier":None,
            "evidence_refs":[],
        }
        validate_execution_evidence_envelope(payload)

    def test_harness_error_cannot_assign_target_fail(self):
        payload=base_envelope()
        payload["harness_status"]="ERROR"
        payload["result"]="FAIL"
        payload["verification"]={
            "performed":False,
            "status":"NOT_PERFORMED",
            "verifier":None,
            "evidence_refs":[],
        }
        with self.assertRaisesRegex(RuntimeError,"cannot assign target result"):
            validate_execution_evidence_envelope(payload)

    def test_not_evaluated_requires_incomplete_harness(self):
        payload=base_envelope()
        payload["result"]="NOT_EVALUATED"
        payload["verification"]={
            "performed":False,
            "status":"NOT_PERFORMED",
            "verifier":None,
            "evidence_refs":[],
        }
        with self.assertRaisesRegex(RuntimeError,"requires incomplete harness"):
            validate_execution_evidence_envelope(payload)

    def test_pass_rejects_harness_error(self):
        payload=base_envelope()
        payload["harness_status"]="ERROR"
        with self.assertRaisesRegex(RuntimeError,"cannot assign target result"):
            validate_execution_evidence_envelope(payload)


if __name__=="__main__":
    unittest.main()
