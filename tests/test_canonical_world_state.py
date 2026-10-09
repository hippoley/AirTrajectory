"""Canonical state cannot hide missing metrics or self-promote field evidence."""
import copy
import unittest

from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.world_state import CanonicalWorldState, EvidenceRef


def topology():
    return BuildingTopology.from_parts(
        [ZoneNode("living", 60), ZoneNode("bed", 35)],
        [
            OpeningEdge("W1", "living", "OUTSIDE", "window", 1.0),
            OpeningEdge("D1", "living", "bed", "door", 1.5),
        ],
    )


def state(**overrides):
    params = {
        "topology": topology(),
        "opening_pct": {"W1": 0, "D1": 100},
        "zone_environment": {
            "living": {"co2_ppm": 1300, "pm25_ug_m3": None},
            "bed": {"co2_ppm": 900, "pm25_ug_m3": None},
        },
        "rain": None,
        "observed_at": 123456.0,
        "evidence": EvidenceRef("E2", "toy-simulator", "toy-episode-001"),
        "hardware_bindings": {"W1": "driver-001"},
        "sensor_bindings": {"living": "sensor-001"},
    }
    params.update(overrides)
    return CanonicalWorldState.from_parts(**params)


class CanonicalWorldStateTests(unittest.TestCase):
    def test_same_input_is_same_digest_independent_of_mapping_order(self):
        first = state()
        second = state(
            opening_pct={"D1": 100.0, "W1": 0.0},
            zone_environment={
                "bed": {"pm25_ug_m3": None, "co2_ppm": 900},
                "living": {"pm25_ug_m3": None, "co2_ppm": 1300},
            },
        )
        self.assertEqual(first.sha256, second.sha256)
        self.assertFalse(first.as_dict()["execution_authorized"])
        self.assertIsNone(first.as_dict()["zone_environment"]["living"]["pm25_ug_m3"])

    def test_nested_source_mutation_cannot_change_snapshot(self):
        original = {"living": {"co2_ppm": 1300}, "bed": {"co2_ppm": 900}}
        snap = state(zone_environment=original)
        original["living"]["co2_ppm"] = 0
        changed = snap.as_dict()
        changed["zone_environment"]["living"]["co2_ppm"] = 1
        self.assertEqual(snap.as_dict()["zone_environment"]["living"]["co2_ppm"], 1300)

    def test_stale_origin_fails(self):
        with self.assertRaisesRegex(RuntimeError, "origin changed"):
            state().assert_same_origin("0" * 64)

    def test_unknown_opening_and_zone_rejected(self):
        with self.assertRaisesRegex(ValueError, "opening coverage"):
            state(opening_pct={"W1": 0})
        with self.assertRaisesRegex(ValueError, "zone coverage"):
            state(zone_environment={"living": {"co2_ppm": 900}})

    def test_duplicate_hardware_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity collision"):
            state(hardware_bindings={"W1": "same", "D1": "same"})

    def test_invalid_metric_and_boolean_numeric_rejected(self):
        for value in [float("nan"), float("inf"), True, -1]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    state(zone_environment={
                        "living": {"co2_ppm": value},
                        "bed": {"co2_ppm": 900},
                    })

    def test_evidence_class_does_not_self_promote(self):
        with self.assertRaisesRegex(ValueError, "self-asserted E4/E5"):
            EvidenceRef("E4", "sensor", "fake-physical")
        with self.assertRaisesRegex(ValueError, "source and level"):
            EvidenceRef("E3", "toy-simulator", "misclassified", "contamx", "a"*64)
        with self.assertRaisesRegex(ValueError, "receipt SHA-256"):
            EvidenceRef("E3", "contamx", "case", "contamx", "bad")
        verified_backend = EvidenceRef("E3", "contamx", "case", "contamx", "a"*64)
        snap = state(evidence=verified_backend)
        self.assertFalse(snap.as_dict()["evidence"]["field_measurement_verified"])
        self.assertFalse(snap.as_dict()["evidence"]["independent_adoption_verified"])

    def test_software_world_cannot_authorize_physical_actuation(self):
        with self.assertRaisesRegex(RuntimeError, "not a physical authorization"):
            state().require_physical_authorization()


if __name__ == "__main__":
    unittest.main()
