import unittest

from airtrajectory.environmental_state import (
    EnvironmentalState,
    EnvironmentalValue,
    OutdoorEnvironmentalState,
    ZoneEnvironmentalState,
)
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode


class EnvironmentalStateTests(unittest.TestCase):
    def setUp(self):
        self.topology = BuildingTopology.from_parts(
            [ZoneNode("living", 50), ZoneNode("bedroom", 35)],
            [
                OpeningEdge("W1", "living", "OUTSIDE", "window", 1.0),
                OpeningEdge("D1", "living", "bedroom", "door", 1.5),
            ],
        )

    def test_multi_environment_state_preserves_evidence_classes(self):
        state = EnvironmentalState(
            topology_id="home-v1",
            zones={
                "living": ZoneEnvironmentalState(
                    "living",
                    {
                        "co2_ppm": EnvironmentalValue(
                            1350, "measured", observed_at="2026-10-08T07:00:00Z", source_id="co2-1"
                        ),
                        "pm25_ug_m3": EnvironmentalValue(
                            18, "estimated", confidence=0.72, source_id="soft-pm25"
                        ),
                        "temperature_c": EnvironmentalValue(24.5, "measured"),
                        "relative_humidity_pct": EnvironmentalValue(55, "measured"),
                        "tvoc_ug_m3": EnvironmentalValue(None, "unavailable"),
                    },
                ),
                "bedroom": ZoneEnvironmentalState(
                    "bedroom",
                    {
                        "co2_ppm": EnvironmentalValue(900, "stale"),
                        "pm25_ug_m3": EnvironmentalValue(12, "simulated"),
                    },
                ),
            },
            outdoor=OutdoorEnvironmentalState(
                values={
                    "pm25_ug_m3": EnvironmentalValue(88, "measured"),
                    "temperature_c": EnvironmentalValue(9.0, "measured"),
                    "wind_speed_m_s": EnvironmentalValue(3.2, "estimated", confidence=0.8),
                    "rain": EnvironmentalValue(False, "measured"),
                }
            ),
        )
        state.require_topology(self.topology)
        payload = state.as_dict()

        self.assertEqual(
            payload["zones"]["living"]["values"]["pm25_ug_m3"]["evidence"],
            "estimated",
        )
        self.assertIsNone(
            payload["zones"]["living"]["values"]["tvoc_ug_m3"]["value"]
        )
        self.assertGreater(payload["quality"]["measured_fraction"], 0)
        self.assertLess(payload["quality"]["measured_fraction"], 1)

    def test_unavailable_cannot_carry_fake_value(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            EnvironmentalValue(12.0, "unavailable")

    def test_estimate_cannot_be_silently_retyped_as_measurement(self):
        estimated = EnvironmentalValue(22.0, "estimated", confidence=0.6)
        self.assertEqual(estimated.evidence, "estimated")
        self.assertNotEqual(estimated.evidence, "measured")

    def test_topology_mismatch_fails_closed(self):
        state = EnvironmentalState(
            topology_id="home-v1",
            zones={
                "living": ZoneEnvironmentalState(
                    "living", {"co2_ppm": EnvironmentalValue(900, "measured")}
                )
            },
            outdoor=OutdoorEnvironmentalState(),
        )
        with self.assertRaisesRegex(ValueError, "topology mismatch"):
            state.require_topology(self.topology)

    def test_unknown_environment_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported indoor fields"):
            ZoneEnvironmentalState(
                "living",
                {"magic_air_score": EnvironmentalValue(1, "estimated")},
            )


if __name__ == "__main__":
    unittest.main()
