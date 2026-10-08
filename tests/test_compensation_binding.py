import unittest

from airtrajectory.compensation_binding import (
    build_compensation_binding,
    validate_compensation_binding,
)


def closeout():
    return {
        "confirmed_closed": True,
        "feedback": {
            "measured_position_pct": 0.2,
            "timestamp": 120.0,
            "source": "actuator-encoder",
        },
    }


class CompensationBindingTests(unittest.TestCase):
    def test_verified_compensation_binds_to_original_effect(self):
        binding = build_compensation_binding(
            original_effect_id="effect-open-001",
            compensation_effect_id="effect-close-001",
            compensation_target_pct=0.0,
            closeout_evidence=closeout(),
        )
        self.assertEqual(binding["relation"], "COMPENSATES")
        self.assertFalse(binding["original_effect_history_rewritten"])
        validate_compensation_binding(binding)

    def test_compensation_must_have_distinct_identity(self):
        with self.assertRaisesRegex(ValueError, "distinct identity"):
            build_compensation_binding(
                original_effect_id="effect-1",
                compensation_effect_id="effect-1",
                compensation_target_pct=0.0,
                closeout_evidence=closeout(),
            )

    def test_unverified_closeout_cannot_claim_compensation(self):
        bad = closeout()
        bad["confirmed_closed"] = False
        with self.assertRaisesRegex(ValueError, "verified closeout"):
            build_compensation_binding(
                original_effect_id="effect-open-001",
                compensation_effect_id="effect-close-001",
                compensation_target_pct=0.0,
                closeout_evidence=bad,
            )

    def test_tampering_is_detected(self):
        binding = build_compensation_binding(
            original_effect_id="effect-open-001",
            compensation_effect_id="effect-close-001",
            compensation_target_pct=0.0,
            closeout_evidence=closeout(),
        )
        binding["verified_observation"]["measured_position_pct"] = 8.0
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            validate_compensation_binding(binding)


if __name__ == "__main__":
    unittest.main()
