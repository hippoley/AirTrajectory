import hashlib
import json
import unittest

from airtrajectory.physical_origin import physical_next_origin_from_reconcile


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


class PhysicalOriginTests(unittest.TestCase):
    def current(self):
        return {
            "co2_ppm": {
                "living": 1400.0,
                "bedroom": 900.0,
                "study": 800.0,
            },
            "opening_pct": {
                "W1": 65.0,
                "W2": 35.0,
                "W3": 55.0,
                "D1": 100.0,
                "D2": 100.0,
            },
            "scalar_values": {},
        }

    def reconcile(self):
        payload = {
            "schema_version": "0.1",
            "reconcile": "sim-to-physical-first-contact-v1",
            "opening_id": "W1",
            "selected_label": "joint-balanced-medium",
            "planned_target_pct": 75.0,
            "authorized_target_pct": 5.0,
            "action_feedback_position_pct": 4.9,
            "action_feedback_timestamp": 10.0,
            "measured_minus_authorized_pct": -0.1,
            "post_closeout_position_pct": 0.2,
            "post_closeout_timestamp": 12.0,
            "terminal_position_pct": 0.2,
            "terminal_position_source": "safe-closeout-measured-feedback",
            "next_origin_position_verified": True,
            "terminal_co2_ppm": 1388.0,
            "terminal_co2_timestamp": 13.0,
            "terminal_rain": False,
            "terminal_rain_timestamp": 13.0,
            "terminal_snapshot_sha256": "f" * 64,
            "next_origin_sensor_verified": True,
            "physical_next_origin_ready": True,
            "planner_action_fully_executed": False,
            "physical_intervention": "FIRST_CONTACT_BOUNDED_TO_COMMISSIONED_EXCURSION",
            "pre_action_co2_ppm": 1400.0,
            "post_action_co2_ppm": 1392.0,
            "measured_co2_delta_ppm": -8.0,
            "predicted_zone_id": "living",
            "predicted_zone_co2_ppm": 909.74,
            "measured_minus_predicted_zone_co2_ppm": 482.26,
            "planner_handoff_sha256": "a" * 64,
            "physical_authorization_sha256": "b" * 64,
            "evidence_boundary": (
                "bounded first-contact physical handoff; planner target may be safety-limited "
                "and therefore is not claimed as full closed-loop field execution"
            ),
        }
        return {
            **payload,
            "physical_reconcile_sha256": sha(payload),
        }

    def test_updates_only_measured_zone_and_opening(self):
        out = physical_next_origin_from_reconcile(
            current_origin=self.current(),
            reconcile=self.reconcile(),
            zone_id="living",
        )
        origin = out["origin"]
        self.assertEqual(origin["co2_ppm"]["living"], 1388.0)
        self.assertEqual(origin["co2_ppm"]["bedroom"], 900.0)
        self.assertEqual(origin["opening_pct"]["W1"], 0.2)
        self.assertEqual(origin["opening_pct"]["W2"], 35.0)
        self.assertEqual(origin["scalar_values"]["rain"], 0.0)
        self.assertEqual(len(out["origin_sha256"]), 64)
        self.assertIn("single physical opening/zone", out["evidence_boundary"])

    def test_tampered_reconcile_is_rejected(self):
        receipt = self.reconcile()
        receipt["terminal_co2_ppm"] = 999.0
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            physical_next_origin_from_reconcile(
                current_origin=self.current(),
                reconcile=receipt,
                zone_id="living",
            )

    def test_not_ready_receipt_is_rejected(self):
        receipt = self.reconcile()
        receipt["physical_next_origin_ready"] = False
        payload = dict(receipt)
        payload.pop("physical_reconcile_sha256")
        receipt["physical_reconcile_sha256"] = sha(payload)
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            physical_next_origin_from_reconcile(
                current_origin=self.current(),
                reconcile=receipt,
                zone_id="living",
            )

    def test_wrong_zone_binding_is_rejected(self):
        receipt = self.reconcile()
        with self.assertRaisesRegex(RuntimeError, "predicted_zone_id"):
            physical_next_origin_from_reconcile(
                current_origin=self.current(),
                reconcile=receipt,
                zone_id="bedroom",
            )

    def test_unmeasured_openings_remain_inherited(self):
        out = physical_next_origin_from_reconcile(
            current_origin=self.current(),
            reconcile=self.reconcile(),
            zone_id="living",
        )
        origin = out["origin"]
        self.assertEqual(origin["opening_pct"]["W2"], 35.0)
        self.assertEqual(origin["opening_pct"]["W3"], 55.0)
        self.assertEqual(origin["opening_pct"]["D1"], 100.0)
        self.assertEqual(origin["opening_pct"]["D2"], 100.0)


if __name__ == "__main__":
    unittest.main()
