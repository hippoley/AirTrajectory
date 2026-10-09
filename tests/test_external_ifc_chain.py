"""Adversarial external-source identity tests; no simulated solver promotion."""
import hashlib
import unittest

from examples.verify_external_ifc_chain import verify


class ExternalIfcChainTests(unittest.TestCase):
    def setUp(self):
        self.source = b"independent IFC bytes fixture; not a real building"
        digest = hashlib.sha256(self.source).hexdigest()
        self.layout = {
            "source_kind": "imported-floorplan",
            "topology_id": "ifc:external-1",
            "source_provenance": {
                "format": "IFC", "source_sha256": digest,
                "geometry_fidelity": "bbox-and-boundary-projection",
            },
        }
        self.native = {
            "marker": "IMPORTED_CONTAM_NATIVE_EXECUTED",
            "topology_id": "ifc:external-1",
            "source_ifc_sha256": digest, "receipt_sha256": "a" * 64,
            "engineering_truth": False,
        }
        self.scoring = {
            "status": "NATIVE_CONTAM_SCORED",
            "source_ifc_sha256": digest,
            "native_receipt_sha256": "a" * 64,
            "receipt_sha256": "b" * 64,
        }

    def test_matching_identity_is_only_evidence_present_not_closed(self):
        result = verify(self.layout, self.native, self.scoring, self.source)
        self.assertFalse(result["product_verified_closed"])
        self.assertFalse(result["independent_replay_verified"])

    def test_reject_source_and_chain_identity_drift(self):
        for field, value in (
            ("source_bytes", b"tampered"),
            ("native_source", "0" * 64),
            ("scoring_source", "0" * 64),
            ("native_receipt", "0" * 64),
        ):
            with self.subTest(field=field):
                layout = dict(self.layout)
                native = dict(self.native)
                scoring = dict(self.scoring)
                source = self.source
                if field == "source_bytes": source = value
                if field == "native_source": native["source_ifc_sha256"] = value
                if field == "scoring_source": scoring["source_ifc_sha256"] = value
                if field == "native_receipt": scoring["native_receipt_sha256"] = value
                with self.assertRaises(ValueError):
                    verify(layout, native, scoring, source)

    def test_synthetic_import_is_not_external_evidence(self):
        self.layout["source_provenance"]["format"] = "synthetic-json"
        with self.assertRaisesRegex(ValueError, "external IFC"):
            verify(self.layout, self.native, self.scoring, self.source)


if __name__ == "__main__":
    unittest.main()
