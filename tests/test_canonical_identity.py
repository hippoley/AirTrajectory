"""Independent counterexamples for canonical identity collisions in P0 topology intake."""
import copy
import json
import unittest
from pathlib import Path

from airtrajectory.layout import LayoutContract

FIXTURE = Path(__file__).resolve().parents[1] / "web/data/home_topology.fixed.json"


class CanonicalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_room_id_cannot_alias_ambient(self):
        payload = copy.deepcopy(self.base)
        payload["rooms"][0]["id"] = payload["outside_id"]
        with self.assertRaisesRegex(ValueError, "room id cannot equal outside_id"):
            LayoutContract.from_dict(payload)

    def test_all_identity_collections_reject_blank_ids(self):
        for collection in ("rooms", "walls", "openings"):
            with self.subTest(collection=collection):
                payload = copy.deepcopy(self.base)
                payload[collection][0]["id"] = "  "
                with self.assertRaisesRegex(ValueError, "id must be nonblank"):
                    LayoutContract.from_dict(payload)

    def test_ambient_id_must_not_be_blank(self):
        payload = copy.deepcopy(self.base)
        payload["outside_id"] = " "
        with self.assertRaisesRegex(ValueError, "outside_id must be nonblank"):
            LayoutContract.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
