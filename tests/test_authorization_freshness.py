import unittest

from airtrajectory.authorization_freshness import (
    validate_authorization_use_freshness,
)


def authorization():
    return {
        "current_measured_pct": 10.0,
        "current_rain": False,
    }


class AuthorizationUseFreshnessTests(unittest.TestCase):
    def test_matching_fresh_state_allows_use(self):
        result = validate_authorization_use_freshness(
            authorization=authorization(),
            freshness_checked_at=100.0,
            position_feedback={
                "measured": True,
                "position_pct": 10.4,
                "timestamp": 101.0,
            },
            sensor_readings=[
                {"sensor_type": "rain", "value": 0.0, "timestamp": 101.5},
            ],
        )
        self.assertEqual(result["authorization_use_status"], "FRESH")

    def test_position_drift_rejects_old_authorization(self):
        with self.assertRaisesRegex(RuntimeError, "position drift"):
            validate_authorization_use_freshness(
                authorization=authorization(),
                freshness_checked_at=100.0,
                position_feedback={
                    "measured": True,
                    "position_pct": 25.0,
                    "timestamp": 101.0,
                },
                sensor_readings=[
                    {"sensor_type": "rain", "value": 0.0, "timestamp": 101.5},
                ],
            )

    def test_rain_change_rejects_old_authorization(self):
        with self.assertRaisesRegex(RuntimeError, "rain state drift"):
            validate_authorization_use_freshness(
                authorization=authorization(),
                freshness_checked_at=100.0,
                position_feedback={
                    "measured": True,
                    "position_pct": 10.0,
                    "timestamp": 101.0,
                },
                sensor_readings=[
                    {"sensor_type": "rain", "value": 1.0, "timestamp": 101.5},
                ],
            )

    def test_cached_position_cannot_revalidate_authorization(self):
        with self.assertRaisesRegex(RuntimeError, "not newer"):
            validate_authorization_use_freshness(
                authorization=authorization(),
                freshness_checked_at=100.0,
                position_feedback={
                    "measured": True,
                    "position_pct": 10.0,
                    "timestamp": 100.0,
                },
                sensor_readings=[
                    {"sensor_type": "rain", "value": 0.0, "timestamp": 101.5},
                ],
            )

    def test_cached_rain_cannot_revalidate_authorization(self):
        with self.assertRaisesRegex(RuntimeError, "not newer"):
            validate_authorization_use_freshness(
                authorization=authorization(),
                freshness_checked_at=100.0,
                position_feedback={
                    "measured": True,
                    "position_pct": 10.0,
                    "timestamp": 101.0,
                },
                sensor_readings=[
                    {"sensor_type": "rain", "value": 0.0, "timestamp": 100.0},
                ],
            )


if __name__ == "__main__":
    unittest.main()
