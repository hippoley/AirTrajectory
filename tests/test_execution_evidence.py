import unittest

from airtrajectory.execution_evidence import validate_execution_evidence_envelope


def base_envelope():
    return {
        "schema_version":"0.1",
        "record_type":"execution-evidence-envelope-v0.1",
        "execution_id":"exec-1",
        "parent_execution_id":None,
        "subject":{"kind":"conformance-execution","identity":"case-1","version":"0.1"},
        "target":{"kind":"device","identity":"device-1","scope":None},
        "operation":{"kind":"transition","request_id":"req-1","ack_id":"ack-1","mutation_expected":True,"parameters":{}},
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


if __name__=="__main__":
    unittest.main()
