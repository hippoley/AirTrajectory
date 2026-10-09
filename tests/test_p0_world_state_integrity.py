import hashlib
import json
import unittest

from airtrajectory.world_state import CanonicalWorldState


class CanonicalWorldStateIntegrityTests(unittest.TestCase):
    def test_rejects_digest_mismatch(self):
        payload = b'{"execution_authorized":false}'
        with self.assertRaises(ValueError):
            CanonicalWorldState(payload, "0" * 64)

    def test_rejects_execution_authorization(self):
        payload = b'{"execution_authorized":true}'
        with self.assertRaises(ValueError):
            CanonicalWorldState(payload, hashlib.sha256(payload).hexdigest())

    def test_rejects_noncanonical_encoding(self):
        payload = b'{ "execution_authorized": false }'
        with self.assertRaises(ValueError):
            CanonicalWorldState(payload, hashlib.sha256(payload).hexdigest())

    def test_accepts_canonical_read_only_snapshot(self):
        payload = json.dumps({"execution_authorized": False}, sort_keys=True, separators=(",", ":")).encode()
        snapshot = CanonicalWorldState(payload, hashlib.sha256(payload).hexdigest())
        self.assertFalse(snapshot.as_dict()["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
