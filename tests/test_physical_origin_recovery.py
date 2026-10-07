import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.physical import DriverCapabilities
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_origin_lease import (
    bind_recovery_origin_to_execution_lease,
    claim_physical_origin_execution,
    finalize_physical_origin_execution,
    verify_physical_origin_execution_lease,
)
from airtrajectory.physical_origin_recovery import capture_recovery_physical_origin
from airtrajectory.trajectory import SensorReading


def sha(payload):
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def previous_origin():
    origin={
        "co2_ppm":{"living":1388.0,"bedroom":875.0},
        "opening_pct":{"W1":4.9,"W2":35.0},
        "scalar_values":{"rain":0.0},
    }
    payload={
        "schema_version":"0.1",
        "source":"windowpilot-replanned-physical-step-v1",
        "origin":origin,
        "parent_physical_origin_sha256":"a"*64,
        "parent_physical_origin_receipt_sha256":"b"*64,
        "replanned_action_authorization_sha256":"c"*64,
        "command_ack_sha256":"d"*64,
        "command_request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "command_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "command_accepted_at":20.0,
        "sensor_snapshot_sha256":"e"*64,
        "opening_id":"W1",
        "zone_id":"living",
        "measured_position_pct":4.9,
        "actuator_feedback_timestamp":21.0,
        "opening_hardware_identities":{"W1":"f"*64},
        "opening_observed_at":{"W1":21.0},
        "zone_observed_at":{"living":22.0},
        "rain_observed_at":22.0,
        "current_step_measured_zones":["living"],
        "current_step_measured_openings":["W1"],
        "measured_zones":["living"],
        "measured_openings":["W1"],
        "inherited_zones":["bedroom"],
        "inherited_openings":["W2"],
        "whole_home_measurement_skew_s":None,
        "whole_home_measurement_max_skew_s":10.0,
        "whole_home_physically_measured":False,
        "evidence_boundary":"test physical origin",
    }
    return {
        **payload,
        "origin_sha256":sha(origin),
        "physical_origin_receipt_sha256":sha(payload),
    }


class RecoveryDriver:
    def __init__(
        self,
        *,
        identity="f"*64,
        position=7.0,
        position_ts=30.0,
        co2=1200.0,
        sensor_ts=31.0,
        rain=False,
    ):
        self.identity=identity
        self.position=position
        self.position_ts=position_ts
        self.co2=co2
        self.sensor_ts=sensor_ts
        self.rain=rain
        self.motion_calls=[]

    def capabilities(self):
        return DriverCapabilities(
            transport="thingmodel-http",
            simulated=False,
            measured_position=True,
            sensor_types=("co2","rain"),
        )

    def physical_readiness(self):
        return {
            "physical_write_ready":True,
            "hardware_identity":{"identity_sha256":self.identity},
            "latest_position_feedback":{
                "measured":True,
                "position_pct":self.position,
                "timestamp":self.position_ts,
                "quality":"encoder-measured",
            },
        }

    def read_sensors(self):
        return [
            SensorReading(
                sensor_id="co2-1",
                sensor_type="co2",
                value=self.co2,
                unit="ppm",
                timestamp=self.sensor_ts,
                quality="measured",
                provenance={"site_id":"test"},
            ),
            SensorReading(
                sensor_id="rain-1",
                sensor_type="rain",
                value=1.0 if self.rain else 0.0,
                unit="bool",
                timestamp=self.sensor_ts,
                quality="measured",
                provenance={"site_id":"test"},
            ),
        ]

    def set_position(self,*args,**kwargs):
        self.motion_calls.append((args,kwargs))
        raise AssertionError("recovery capture must not move hardware")


class RecoveryOriginTests(unittest.TestCase):
    def _lease(self,root,origin):
        claim=claim_physical_origin_execution(
            lease_dir=root/"leases",
            origin_receipt_sha256=origin["physical_origin_receipt_sha256"],
            origin_sha256=origin["origin_sha256"],
            planner_receipt_sha256="1"*64,
            planner_step_sha256="2"*64,
            opening_id="W1",
            zone_id="living",
            claimed_at=23.0,
            owner_host="host-a",
            owner_pid=1111,
        )
        return finalize_physical_origin_execution(
            lease_path=claim["lease_path"],
            status="RECOVERY_REQUIRED",
            finalized_at=24.0,
            recovery={
                "reason":"OWNER_PROCESS_NOT_RUNNING",
                "requires_new_physical_origin":True,
            },
        )

    def test_read_only_recovery_refreshes_only_selected_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            lease=self._lease(root,origin)
            driver=RecoveryDriver()
            recovered=capture_recovery_physical_origin(
                driver=driver,
                previous_origin_receipt=origin,
                lease_path=lease["lease_path"],
                opening_id="W1",
                zone_id="living",
                max_observation_age_s=5.0,
                clock_fn=lambda:32.0,
            )
            verified=verify_physical_origin_receipt(recovered)
            self.assertEqual(verified["source"],"windowpilot-recovery-physical-origin-v1")
            self.assertEqual(verified["measured_zones"],["living"])
            self.assertEqual(verified["measured_openings"],["W1"])
            self.assertEqual(verified["inherited_zones"],["bedroom"])
            self.assertEqual(verified["inherited_openings"],["W2"])
            self.assertEqual(verified["origin"]["co2_ppm"]["living"],1200.0)
            self.assertEqual(verified["origin"]["co2_ppm"]["bedroom"],875.0)
            self.assertEqual(verified["origin"]["opening_pct"]["W1"],7.0)
            self.assertEqual(verified["origin"]["opening_pct"]["W2"],35.0)
            self.assertEqual(driver.motion_calls,[])

    def test_recovery_rejects_hardware_identity_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            lease=self._lease(root,origin)
            driver=RecoveryDriver(identity="9"*64)
            with self.assertRaisesRegex(RuntimeError,"does not match previous origin"):
                capture_recovery_physical_origin(
                    driver=driver,
                    previous_origin_receipt=origin,
                    lease_path=lease["lease_path"],
                    opening_id="W1",
                    zone_id="living",
                    clock_fn=lambda:32.0,
                )
            self.assertEqual(driver.motion_calls,[])

    def test_recovery_rejects_stale_observations(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            lease=self._lease(root,origin)
            driver=RecoveryDriver(position_ts=10.0,sensor_ts=11.0)
            with self.assertRaisesRegex(RuntimeError,"observations are stale"):
                capture_recovery_physical_origin(
                    driver=driver,
                    previous_origin_receipt=origin,
                    lease_path=lease["lease_path"],
                    opening_id="W1",
                    zone_id="living",
                    max_observation_age_s=5.0,
                    clock_fn=lambda:32.0,
                )
            self.assertEqual(driver.motion_calls,[])

    def test_inflight_lease_must_be_sealed_before_recovery_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            claim=claim_physical_origin_execution(
                lease_dir=root/"leases",
                origin_receipt_sha256=origin["physical_origin_receipt_sha256"],
                origin_sha256=origin["origin_sha256"],
                planner_receipt_sha256="1"*64,
                planner_step_sha256="2"*64,
                opening_id="W1",
                zone_id="living",
                claimed_at=23.0,
                owner_host="host-a",
                owner_pid=1111,
            )
            with self.assertRaisesRegex(RuntimeError,"RECOVERY_REQUIRED"):
                capture_recovery_physical_origin(
                    driver=RecoveryDriver(),
                    previous_origin_receipt=origin,
                    lease_path=claim["lease_path"],
                    opening_id="W1",
                    zone_id="living",
                    clock_fn=lambda:32.0,
                )

    def test_verified_recovery_origin_can_bind_and_finish_lease(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            lease=self._lease(root,origin)
            recovered=capture_recovery_physical_origin(
                driver=RecoveryDriver(),
                previous_origin_receipt=origin,
                lease_path=lease["lease_path"],
                opening_id="W1",
                zone_id="living",
                clock_fn=lambda:32.0,
            )
            final=bind_recovery_origin_to_execution_lease(
                lease_path=lease["lease_path"],
                recovery_origin_receipt=recovered,
                bound_at=33.0,
            )
            self.assertEqual(final["status"],"RECOVERED")
            self.assertFalse(final["recovery"]["requires_new_physical_origin"])
            self.assertEqual(
                final["recovery"]["recovery_origin_receipt_sha256"],
                recovered["physical_origin_receipt_sha256"],
            )
            verified=verify_physical_origin_execution_lease(
                lease_path=lease["lease_path"],
            )
            self.assertEqual(verified["status"],"RECOVERED")
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=root/"leases",
                    origin_receipt_sha256=origin["physical_origin_receipt_sha256"],
                    origin_sha256=origin["origin_sha256"],
                    planner_receipt_sha256="1"*64,
                    planner_step_sha256="2"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=34.0,
                )

    def test_binding_rejects_unrelated_recovery_origin(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=previous_origin()
            lease=self._lease(root,origin)
            recovered=capture_recovery_physical_origin(
                driver=RecoveryDriver(),
                previous_origin_receipt=origin,
                lease_path=lease["lease_path"],
                opening_id="W1",
                zone_id="living",
                clock_fn=lambda:32.0,
            )
            recovered["parent_physical_origin_receipt_sha256"]="8"*64
            payload={
                key:value
                for key,value in recovered.items()
                if key not in {"origin_sha256","physical_origin_receipt_sha256"}
            }
            recovered["physical_origin_receipt_sha256"]=sha(payload)
            with self.assertRaisesRegex(RuntimeError,"does not descend"):
                bind_recovery_origin_to_execution_lease(
                    lease_path=lease["lease_path"],
                    recovery_origin_receipt=recovered,
                    bound_at=33.0,
                )


if __name__=="__main__":
    unittest.main()
