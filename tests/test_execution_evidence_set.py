import unittest

from airtrajectory.execution_evidence_set import (
    build_execution_evidence_set,
    validate_execution_evidence_set,
)


def record(execution_id, result, harness_status="COMPLETED"):
    return {
        "schema_version":"0.1",
        "record_type":"execution-evidence-envelope-v0.1",
        "execution_id":execution_id,
        "parent_execution_id":None,
        "subject":{"kind":"case","identity":execution_id,"version":"0.1"},
        "target":{"kind":"device","identity":"device-1","scope":None},
        "operation":{"kind":"test","request_id":None,"ack_id":None,"mutation_expected":False,"parameters":{}},
        "harness_status":harness_status,
        "result":result,
        "reason_code":None,
        "observations":[],
        "recovery":{"required":result=="UNCERTAIN","performed":False,"status":"UNCERTAIN" if result=="UNCERTAIN" else "NOT_REQUIRED","evidence_refs":[]},
        "verification":{"performed":result=="PASS","status":"PASS" if result=="PASS" else "NOT_PERFORMED","verifier":"fixture" if result=="PASS" else None,"evidence_refs":[]},
        "provenance":{},
        "artifact_refs":[],
        "evidence_boundary":"fixture",
        "extensions":{},
    }


class ExecutionEvidenceSetTests(unittest.TestCase):
    def test_membership_digest_is_order_independent(self):
        a=record("exec-a","PASS")
        b=record("exec-b","FAIL")
        first=build_execution_evidence_set([a,b],suite_id="suite-1")
        second=build_execution_evidence_set([b,a],suite_id="suite-1")
        self.assertEqual(first["records"],second["records"])
        self.assertEqual(first["manifest_sha256"],second["manifest_sha256"])

    def test_uncertain_dominates_not_evaluated(self):
        uncertain=record("exec-a","UNCERTAIN")
        not_evaluated=record("exec-b","NOT_EVALUATED","ERROR")
        manifest=build_execution_evidence_set(
            [not_evaluated,uncertain],
            suite_id="suite-1",
        )
        self.assertEqual(manifest["aggregate_result"],"UNCERTAIN")
        self.assertEqual(manifest["counts"]["UNCERTAIN"],1)
        self.assertEqual(manifest["counts"]["NOT_EVALUATED"],1)

    def test_not_evaluated_prevents_pass(self):
        good=record("exec-a","PASS")
        missing=record("exec-b","NOT_EVALUATED","INTERRUPTED")
        manifest=build_execution_evidence_set([good,missing],suite_id="suite-1")
        self.assertEqual(manifest["aggregate_result"],"NOT_EVALUATED")

    def test_duplicate_execution_id_is_rejected(self):
        a=record("exec-a","PASS")
        with self.assertRaisesRegex(ValueError,"duplicate execution_id"):
            build_execution_evidence_set([a,a],suite_id="suite-1")

    def test_manifest_tampering_is_detected(self):
        manifest=build_execution_evidence_set(
            [record("exec-a","PASS")],
            suite_id="suite-1",
        )
        manifest["record_count"]=2
        with self.assertRaisesRegex(ValueError,"record_count"):
            validate_execution_evidence_set(manifest)


if __name__=="__main__":
    unittest.main()
