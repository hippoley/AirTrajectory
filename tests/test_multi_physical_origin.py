import hashlib
import json
import unittest

from airtrajectory.physical_origin import (
    merge_physical_next_origins,
    verify_physical_origin_receipt,
)


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def reconcile(
    opening_id,
    zone_id,
    co2,
    position,
    *,
    rain=False,
    seed="a",
    sensor_timestamp=13.0,
):
    payload = {
        "schema_version": "0.1",
        "reconcile": "sim-to-physical-first-contact-v1",
        "opening_id": opening_id,
        "selected_label": "joint-balanced-medium",
        "planned_target_pct": 75.0,
        "authorized_target_pct": 5.0,
        "action_feedback_position_pct": 4.9,
        "action_feedback_timestamp": 10.0,
        "measured_minus_authorized_pct": -0.1,
        "post_closeout_position_pct": position,
        "post_closeout_timestamp": 12.0,
        "terminal_position_pct": position,
        "terminal_position_source": "safe-closeout-measured-feedback",
        "next_origin_position_verified": True,
        "terminal_co2_ppm": co2,
        "terminal_co2_timestamp": sensor_timestamp,
        "terminal_rain": rain,
        "terminal_rain_timestamp": sensor_timestamp,
        "terminal_snapshot_sha256": seed * 64,
        "next_origin_sensor_verified": True,
        "physical_next_origin_ready": True,
        "planner_action_fully_executed": False,
        "physical_intervention": "FIRST_CONTACT_BOUNDED_TO_COMMISSIONED_EXCURSION",
        "pre_action_co2_ppm": 1400.0,
        "post_action_co2_ppm": 1392.0,
        "measured_co2_delta_ppm": -8.0,
        "predicted_zone_id": zone_id,
        "predicted_zone_co2_ppm": 900.0,
        "measured_minus_predicted_zone_co2_ppm": co2 - 900.0,
        "planner_handoff_sha256": "1" * 64,
        "physical_authorization_sha256": "2" * 64,
        "evidence_boundary": (
            "bounded first-contact physical handoff; planner target may be safety-limited "
            "and therefore is not claimed as full closed-loop field execution"
        ),
    }
    return {
        **payload,
        "physical_reconcile_sha256": sha(payload),
    }


class MultiPhysicalOriginTests(unittest.TestCase):
    def base(self):
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

    def test_merges_two_independently_measured_endpoints(self):
        out = merge_physical_next_origins(
            current_origin=self.base(),
            measurements=[
                {
                    "zone_id": "living",
                    "reconcile": reconcile("W1", "living", 1388.0, 0.2, seed="a"),
                },
                {
                    "zone_id": "bedroom",
                    "reconcile": reconcile("W2", "bedroom", 875.0, 0.1, seed="b"),
                },
            ],
        )
        origin = out["origin"]
        self.assertEqual(origin["co2_ppm"]["living"], 1388.0)
        self.assertEqual(origin["co2_ppm"]["bedroom"], 875.0)
        self.assertEqual(origin["co2_ppm"]["study"], 800.0)
        self.assertEqual(origin["opening_pct"]["W1"], 0.2)
        self.assertEqual(origin["opening_pct"]["W2"], 0.1)
        self.assertEqual(origin["opening_pct"]["W3"], 55.0)
        self.assertEqual(out["measured_zones"], ["bedroom", "living"])
        self.assertEqual(out["measured_openings"], ["W1", "W2"])
        self.assertEqual(out["inherited_zones"], ["study"])
        self.assertEqual(out["inherited_openings"], ["D1", "D2", "W3"])
        self.assertFalse(out["whole_home_physically_measured"])
        self.assertEqual(out["physical_measurement_count"], 2)
        self.assertEqual(len(out["multi_physical_origin_receipt_sha256"]), 64)

    def test_duplicate_zone_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate physical coverage for zone"):
            merge_physical_next_origins(
                current_origin=self.base(),
                measurements=[
                    {"zone_id": "living", "reconcile": reconcile("W1", "living", 1300, 0.2)},
                    {"zone_id": "living", "reconcile": reconcile("W2", "living", 1290, 0.1, seed="b")},
                ],
            )

    def test_duplicate_opening_is_rejected(self):
        second = reconcile("W1", "bedroom", 880, 0.1, seed="b")
        with self.assertRaisesRegex(RuntimeError, "duplicate physical coverage for opening"):
            merge_physical_next_origins(
                current_origin=self.base(),
                measurements=[
                    {"zone_id": "living", "reconcile": reconcile("W1", "living", 1300, 0.2)},
                    {"zone_id": "bedroom", "reconcile": second},
                ],
            )

    def test_conflicting_rain_receipts_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "conflicting measured rain"):
            merge_physical_next_origins(
                current_origin=self.base(),
                measurements=[
                    {"zone_id": "living", "reconcile": reconcile("W1", "living", 1300, 0.2, rain=False)},
                    {"zone_id": "bedroom", "reconcile": reconcile("W2", "bedroom", 880, 0.1, rain=True, seed="b")},
                ],
            )

    def test_temporally_incoherent_measurements_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "max temporal skew"):
            merge_physical_next_origins(
                current_origin=self.base(),
                measurements=[
                    {
                        "zone_id":"living",
                        "reconcile":reconcile(
                            "W1","living",1300,0.2,sensor_timestamp=13.0
                        ),
                    },
                    {
                        "zone_id":"bedroom",
                        "reconcile":reconcile(
                            "W2","bedroom",880,0.1,seed="b",sensor_timestamp=30.0
                        ),
                    },
                ],
                max_measurement_skew_s=10.0,
            )

    def test_temporally_coherent_receipt_records_measurement_span(self):
        out=merge_physical_next_origins(
            current_origin=self.base(),
            measurements=[
                {
                    "zone_id":"living",
                    "reconcile":reconcile(
                        "W1","living",1300,0.2,sensor_timestamp=13.0
                    ),
                },
                {
                    "zone_id":"bedroom",
                    "reconcile":reconcile(
                        "W2","bedroom",880,0.1,seed="b",sensor_timestamp=16.0
                    ),
                },
            ],
            max_measurement_skew_s=10.0,
        )
        window=out["measurement_time_range"]
        self.assertEqual(window["earliest_timestamp"],13.0)
        self.assertEqual(window["latest_timestamp"],16.0)
        self.assertEqual(window["skew_s"],3.0)
        self.assertEqual(window["max_allowed_skew_s"],10.0)

    def test_hash_valid_multi_receipt_cannot_overclaim_measured_zones(self):
        out=merge_physical_next_origins(
            current_origin=self.base(),
            measurements=[
                {
                    "zone_id":"living",
                    "reconcile":reconcile("W1","living",1300,0.2),
                },
                {
                    "zone_id":"bedroom",
                    "reconcile":reconcile(
                        "W2","bedroom",880,0.1,seed="b"
                    ),
                },
            ],
        )
        out["measured_zones"]=["bedroom","living","study"]
        payload={
            key:value
            for key,value in out.items()
            if key not in {
                "multi_physical_origin_receipt_sha256",
                "origin_sha256",
            }
        }
        out["multi_physical_origin_receipt_sha256"]=sha(payload)
        with self.assertRaisesRegex(
            RuntimeError,
            "measured_zones do not match applied measurements",
        ):
            verify_physical_origin_receipt(out)

    def test_hash_valid_multi_receipt_cannot_fake_inherited_coverage(self):
        out=merge_physical_next_origins(
            current_origin=self.base(),
            measurements=[
                {
                    "zone_id":"living",
                    "reconcile":reconcile("W1","living",1300,0.2),
                },
                {
                    "zone_id":"bedroom",
                    "reconcile":reconcile(
                        "W2","bedroom",880,0.1,seed="b"
                    ),
                },
            ],
        )
        out["inherited_openings"]=[]
        payload={
            key:value
            for key,value in out.items()
            if key not in {
                "multi_physical_origin_receipt_sha256",
                "origin_sha256",
            }
        }
        out["multi_physical_origin_receipt_sha256"]=sha(payload)
        with self.assertRaisesRegex(
            RuntimeError,
            "inherited_openings do not complement measured coverage",
        ):
            verify_physical_origin_receipt(out)

    def test_tampered_child_receipt_is_rejected(self):
        bad = reconcile("W1", "living", 1300, 0.2)
        bad["terminal_co2_ppm"] = 1.0
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            merge_physical_next_origins(
                current_origin=self.base(),
                measurements=[{"zone_id": "living", "reconcile": bad}],
            )


if __name__ == "__main__":
    unittest.main()
