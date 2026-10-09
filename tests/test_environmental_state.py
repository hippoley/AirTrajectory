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

    def test_tvoc_and_formaldehyde_measurements_preserve_distinct_units(self):
        zone = ZoneEnvironmentalState("living", {
            "tvoc_ug_m3": EnvironmentalValue(240.0, "measured", source_id="tvoc-sensor"),
            "hcho_mg_m3": EnvironmentalValue(0.06, "measured", source_id="hcho-sensor"),
        })
        self.assertEqual(zone.as_dict()["values"]["tvoc_ug_m3"]["value"], 240.0)
        self.assertEqual(zone.as_dict()["values"]["hcho_mg_m3"]["value"], 0.06)

    def test_invalid_voc_and_hcho_rejected_but_negative_celsius_allowed(self):
        for field in ("tvoc_ug_m3", "hcho_mg_m3"):
            for bad in (-0.1, float("nan"), float("inf"), True):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ValueError):
                        ZoneEnvironmentalState("living", {field: EnvironmentalValue(bad, "measured")})
        zone = ZoneEnvironmentalState("living", {"temperature_c": EnvironmentalValue(-4.0, "measured")})
        self.assertEqual(zone.values["temperature_c"].value, -4.0)

    def test_cross_metric_invalid_concentrations_and_humidity_rejected(self):
        for field in ("co2_ppm", "pm25_ug_m3", "tvoc_ug_m3", "hcho_mg_m3"):
            for bad in (-1.0, True, float("nan"), float("inf")):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ValueError):
                        ZoneEnvironmentalState(
                            "living", {field: EnvironmentalValue(bad, "measured")}
                        )
        for bad in (-0.1, 100.1, True):
            with self.subTest(humidity=bad):
                with self.assertRaisesRegex(ValueError, "relative_humidity_pct"):
                    ZoneEnvironmentalState(
                        "living", {"relative_humidity_pct": EnvironmentalValue(bad, "measured")}
                    )

    def test_invalid_outdoor_boundaries_fail_closed(self):
        invalid = {
            "pm25_ug_m3": [-1.0, True, float("nan")],
            "wind_speed_m_s": [-0.1, True],
            "pressure_pa": [-1.0, True],
            "relative_humidity_pct": [-0.1, 101, True],
            "wind_direction_deg": [-1, 360, True],
            "rain": [0, 1, "false"],
        }
        for name, values in invalid.items():
            for bad in values:
                with self.subTest(name=name, bad=bad):
                    with self.assertRaises(ValueError):
                        OutdoorEnvironmentalState(values={
                            name: EnvironmentalValue(bad, "measured")
                        })
        outdoor = OutdoorEnvironmentalState(values={
            "temperature_c": EnvironmentalValue(-8.0, "measured"),
            "wind_direction_deg": EnvironmentalValue(359.9, "measured"),
            "rain": EnvironmentalValue(False, "measured"),
        })
        self.assertEqual(outdoor.values["temperature_c"].value, -8.0)

    def test_occupancy_requires_integer_and_confidence_requires_numeric_probability(self):
        for bad in (-1, 1.5, True, "2"):
            with self.subTest(occupancy=bad):
                with self.assertRaisesRegex(ValueError, "occupancy_count"):
                    ZoneEnvironmentalState(
                        "living", {"occupancy_count": EnvironmentalValue(bad, "measured")}
                    )
        for bad in (True, False, "0.8", float("nan"), float("inf")):
            with self.subTest(confidence=bad):
                with self.assertRaisesRegex(ValueError, "confidence"):
                    EnvironmentalValue(10.0, "estimated", confidence=bad)
        self.assertEqual(
            ZoneEnvironmentalState("living", {
                "occupancy_count": EnvironmentalValue(0, "measured")
            }).values["occupancy_count"].value, 0
        )

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
