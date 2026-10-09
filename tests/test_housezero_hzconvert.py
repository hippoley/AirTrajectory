import unittest

from airtrajectory.housezero_hzconvert import (
    adapt_hzconvert_row,
    discover_hzconvert_zone_ids,
)


class HouseZeroHzconvertAdapterTests(unittest.TestCase):
    def test_discovers_real_hzconvert_zone_vocabulary(self):
        columns = [
            "timestamp",
            "zone/Z31/co2",
            "zone/Z31/air_temperature",
            "zone/Z31/window_opening/south",
            "zone/Z33/co2",
            "load/it",
        ]
        self.assertEqual(
            discover_hzconvert_zone_ids(columns),
            ["Z31", "Z33"],
        )

    def test_row_projects_environment_and_window_evidence(self):
        row = {
            "timestamp": "2025-05-21T12:00:00-04:00",
            "zone/Z31/co2": "1120",
            "zone/Z31/air_temperature": "77",
            "zone/Z31/humidity": "54",
            "zone/Z31/window_opening/south": "35",
            "zone/Z31/window_opening/sky": "12",
            "outdoor/weather/air_temperature": "68",
            "outdoor/weather/humidity": "62",
            "outdoor/weather/wind_speed": "2.4",
            "outdoor/weather/wind_direction": "225",
            "outdoor/weather/rain": "0",
        }
        receipt = adapt_hzconvert_row(
            row,
            topology_id="housezero.external.v0",
        )

        self.assertEqual(
            receipt["source_project"],
            "slitvinov/hzconvert",
        )
        state = receipt["environmental_state"]
        z31 = state["zones"]["Z31"]["values"]
        self.assertEqual(z31["co2_ppm"]["value"], 1120.0)
        self.assertEqual(z31["co2_ppm"]["evidence"], "measured")
        self.assertAlmostEqual(
            z31["temperature_c"]["value"],
            25.0,
            places=6,
        )
        self.assertEqual(
            state["outdoor"]["values"]["wind_speed_m_s"]["value"],
            2.4,
        )
        self.assertEqual(
            state["outdoor"]["values"]["rain"]["value"],
            False,
        )
        self.assertEqual(
            receipt["opening_observations"][
                "zone/Z31/window_opening/south"
            ]["position_pct"],
            35.0,
        )

    def test_invalid_window_percentage_fails_closed(self):
        row = {
            "timestamp": "2025-05-21T12:00:00-04:00",
            "zone/Z31/co2": "1000",
            "zone/Z31/window_opening/south": "150",
        }
        with self.assertRaisesRegex(ValueError, "outside \\[0,100\\]"):
            adapt_hzconvert_row(row, topology_id="housezero.external.v0")

    def test_missing_values_stay_unavailable(self):
        row = {
            "timestamp": "2025-05-21T12:01:00-04:00",
            "zone/Z31/co2": "",
            "zone/Z31/air_temperature": "nan",
            "zone/Z31/humidity": None,
            "zone/Z31/window_opening/south": "",
            "outdoor/weather/air_temperature": "",
            "outdoor/weather/humidity": "",
            "outdoor/weather/wind_speed": "",
            "outdoor/weather/wind_direction": "",
            "outdoor/weather/rain": "",
        }
        receipt = adapt_hzconvert_row(
            row,
            topology_id="housezero.external.v0",
            zone_ids=["Z31"],
        )
        values = receipt["environmental_state"]["zones"]["Z31"]["values"]
        self.assertTrue(
            all(v["evidence"] == "unavailable" for v in values.values())
        )
        opening = receipt["opening_observations"][
            "zone/Z31/window_opening/south"
        ]
        self.assertIsNone(opening["position_pct"])
        self.assertEqual(opening["evidence"], "unavailable")


if __name__ == "__main__":
    unittest.main()
