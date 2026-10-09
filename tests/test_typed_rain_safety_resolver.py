"""Rain safety must never silently reclassify interior doors as windows."""
import unittest

from airtrajectory.physical import SafetyResolver
from airtrajectory.trajectory import TransitionAction


class TypedRainSafetyResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = SafetyResolver()
        self.actions = [
            TransitionAction("W1", 50),
            TransitionAction("D1", 100),
        ]

    def test_rain_closes_exterior_but_preserves_interior_door(self):
        result = self.resolver.resolve(
            {"rain": True, "exterior_openings": ["W1"]}, self.actions
        )
        self.assertEqual(result.intervention, "RAIN_SAFE_CLOSE")
        self.assertEqual(
            [(a.opening_id, a.target_pct) for a in result.executed],
            [("W1", 0), ("D1", 100)],
        )

    def test_missing_rain_evidence_preserves_interior_door(self):
        result = self.resolver.resolve(
            {"rain": None, "exterior_openings": ["W1"]}, self.actions
        )
        self.assertEqual(result.intervention, "RAIN_EVIDENCE_MISSING")
        self.assertEqual(
            [(a.opening_id, a.target_pct) for a in result.executed],
            [("W1", 0), ("D1", 100)],
        )

    def test_dry_weather_keeps_both_actions(self):
        result = self.resolver.resolve(
            {"rain": False, "exterior_openings": ["W1"]}, self.actions
        )
        self.assertIsNone(result.intervention)
        self.assertEqual(result.executed, self.actions)

    def test_without_typed_evidence_all_actions_remain_conservatively_exterior(self):
        result = self.resolver.resolve({"rain": True}, self.actions)
        self.assertEqual(
            [a.target_pct for a in result.executed], [0, 0]
        )

    def test_interior_door_only_is_not_blocked_by_rain(self):
        for rain in [True, None]:
            with self.subTest(rain=rain):
                result = self.resolver.resolve(
                    {"rain": rain, "exterior_openings": ["W1"]},
                    [TransitionAction("D1", 100)],
                )
                self.assertIsNone(result.intervention)
                self.assertEqual(result.executed[0].target_pct, 100)

    def test_malformed_exterior_classification_fails_conservatively(self):
        result = self.resolver.resolve(
            {"rain": True, "exterior_openings": "W1"}, self.actions
        )
        self.assertEqual(
            [a.target_pct for a in result.executed], [0, 0]
        )


if __name__ == "__main__":
    unittest.main()
