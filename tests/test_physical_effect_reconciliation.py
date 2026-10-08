import unittest

from airtrajectory.physical_effect_reconciliation import reconcile_physical_effect


class PhysicalEffectReconciliationTests(unittest.TestCase):
    def test_fresh_measured_readback_confirms_effect(self):
        result = reconcile_physical_effect(
            logical_effect_id="effect-1",
            intended_target_pct=40,
            observation={
                "measured": True,
                "fresh_after_action": True,
                "measured_position_pct": 39.4,
                "source": "actuator-encoder",
            },
            tolerance_pct=1.0,
        )
        self.assertEqual(result["status"], "CONFIRMED")

    def test_fresh_measured_readback_can_contradict_effect(self):
        result = reconcile_physical_effect(
            logical_effect_id="effect-1",
            intended_target_pct=40,
            observation={
                "measured": True,
                "fresh_after_action": True,
                "measured_position_pct": 12.0,
                "source": "actuator-encoder",
            },
        )
        self.assertEqual(result["status"], "CONTRADICTED")

    def test_stale_observation_cannot_resolve_effect(self):
        result = reconcile_physical_effect(
            logical_effect_id="effect-1",
            intended_target_pct=40,
            observation={
                "measured": True,
                "fresh_after_action": False,
                "measured_position_pct": 40.0,
                "source": "actuator-encoder",
            },
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["reason"], "OBSERVATION_NOT_FRESH")

    def test_estimated_state_cannot_resolve_effect(self):
        result = reconcile_physical_effect(
            logical_effect_id="effect-1",
            intended_target_pct=40,
            observation={
                "measured": False,
                "fresh_after_action": True,
                "measured_position_pct": 40.0,
                "source": "runtime-estimate",
            },
        )
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["reason"], "OBSERVATION_NOT_MEASURED")

    def test_missing_observation_remains_unresolved(self):
        result = reconcile_physical_effect(
            logical_effect_id="effect-1",
            intended_target_pct=40,
            observation=None,
        )
        self.assertEqual(result["status"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
