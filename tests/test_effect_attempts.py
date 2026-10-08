import unittest

from airtrajectory.effect_attempts import (
    build_effect_attempt_trace,
    validate_effect_attempt_trace,
)


class EffectAttemptTraceTests(unittest.TestCase):
    def test_lost_ack_then_retry_keeps_one_logical_effect(self):
        trace = build_effect_attempt_trace(
            logical_effect_id="effect-window-close-001",
            request_id="request-001",
            attempts=[
                {
                    "attempt_id": "attempt-1",
                    "status": "TRANSPORT_ERROR",
                    "transport_error": "ack lost",
                },
                {
                    "attempt_id": "attempt-2",
                    "status": "ACKED",
                    "ack_id": "ack-001",
                },
            ],
        )
        self.assertEqual(trace["logical_effect_id"], "effect-window-close-001")
        self.assertEqual(trace["request_id"], "request-001")
        self.assertEqual(len(trace["attempts"]), 2)
        self.assertEqual(trace["effect_outcome"], "UNRESOLVED")
        validate_effect_attempt_trace(trace)

    def test_attempt_ids_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "duplicate attempt_id"):
            build_effect_attempt_trace(
                logical_effect_id="effect-1",
                request_id="request-1",
                attempts=[
                    {"attempt_id": "a", "status": "DISPATCHED"},
                    {"attempt_id": "a", "status": "UNRESOLVED"},
                ],
            )

    def test_acked_attempt_requires_ack_identity(self):
        with self.assertRaisesRegex(ValueError, "requires ack_id"):
            build_effect_attempt_trace(
                logical_effect_id="effect-1",
                request_id="request-1",
                attempts=[{"attempt_id": "a", "status": "ACKED"}],
            )

    def test_transport_trace_cannot_claim_physical_success(self):
        trace = build_effect_attempt_trace(
            logical_effect_id="effect-1",
            request_id="request-1",
            attempts=[{"attempt_id": "a", "status": "DISPATCHED"}],
        )
        trace["effect_outcome"] = "SUCCEEDED"
        with self.assertRaisesRegex(ValueError, "cannot assign"):
            validate_effect_attempt_trace(trace)


if __name__ == "__main__":
    unittest.main()
