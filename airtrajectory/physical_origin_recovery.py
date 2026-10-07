"""Read-only recovery of a fresh physical origin after an abandoned execution."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping

from .physical_origin import verify_physical_origin_receipt
from .physical_origin_lease import verify_physical_origin_execution_lease


def _sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def capture_recovery_physical_origin(
    *,
    driver,
    previous_origin_receipt: Mapping[str, Any],
    lease_path,
    opening_id: str,
    zone_id: str,
    max_observation_age_s: float=10.0,
    clock_fn=time.time,
) -> dict[str, Any]:
    previous=verify_physical_origin_receipt(previous_origin_receipt)
    lease=verify_physical_origin_execution_lease(
        lease_path=lease_path,
        expected_origin_receipt_sha256=previous["receipt_sha256"],
    )
    if lease["status"]!="RECOVERY_REQUIRED":
        raise RuntimeError(
            "recovery physical origin requires a RECOVERY_REQUIRED lease"
        )
    recovery=lease.get("recovery")
    if not isinstance(recovery,Mapping):
        raise RuntimeError("recovery-required lease lacks recovery metadata")
    if recovery.get("requires_new_physical_origin") is not True:
        raise RuntimeError(
            "recovery-required lease does not require a new physical origin"
        )

    opening=str(opening_id or "")
    zone=str(zone_id or "")
    if opening!=str(lease.get("opening_id") or ""):
        raise RuntimeError("recovery opening does not match abandoned execution lease")
    if zone!=str(lease.get("zone_id") or ""):
        raise RuntimeError("recovery zone does not match abandoned execution lease")
    if opening not in previous["origin"]["opening_pct"]:
        raise RuntimeError("recovery opening is not present in previous origin")
    if zone not in previous["origin"]["co2_ppm"]:
        raise RuntimeError("recovery zone is not present in previous origin")

    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("recovery physical origin requires non-simulated WindowPilot")
    if caps.measured_position is not True:
        raise RuntimeError("recovery physical origin requires measured position feedback")

    readiness=driver.physical_readiness()
    if not isinstance(readiness,Mapping):
        raise RuntimeError("WindowPilot physical readiness returned invalid payload")
    identity_payload=readiness.get("hardware_identity")
    if not isinstance(identity_payload,Mapping):
        raise RuntimeError("recovery readiness lacks hardware identity")
    live_identity=str(identity_payload.get("identity_sha256") or "")
    if len(live_identity)!=64 or any(
        ch not in "0123456789abcdef" for ch in live_identity.lower()
    ):
        raise RuntimeError("recovery readiness hardware identity is invalid")
    prior_identity=str(
        previous["opening_hardware_identities"].get(opening) or ""
    )
    if not prior_identity:
        raise RuntimeError(
            "previous physical origin lacks hardware identity for recovery opening"
        )
    if live_identity!=prior_identity:
        raise RuntimeError(
            "recovery WindowPilot hardware identity does not match previous origin"
        )

    feedback=readiness.get("latest_position_feedback")
    if not isinstance(feedback,Mapping):
        raise RuntimeError("recovery readiness lacks latest position feedback")
    if feedback.get("measured") is not True:
        raise RuntimeError("recovery position feedback is not measured")
    position=feedback.get("position_pct")
    position_ts=float(feedback.get("timestamp") or 0)
    if position is None or position_ts<=0:
        raise RuntimeError("recovery position feedback is incomplete")
    position=float(position)
    if not 0<=position<=100:
        raise RuntimeError("recovery position is outside [0,100]")

    readings=list(driver.read_sensors())
    co2=[row for row in readings if row.sensor_type=="co2"]
    rain=[row for row in readings if row.sensor_type=="rain"]
    if len(co2)!=1 or len(rain)!=1:
        raise RuntimeError(
            "recovery requires exactly one measured CO2 and rain reading"
        )
    co2_row=co2[0]
    rain_row=rain[0]
    co2_ts=float(co2_row.timestamp)
    rain_ts=float(rain_row.timestamp)
    co2_value=float(co2_row.value)
    rain_value=bool(float(rain_row.value))
    if co2_ts<=0 or rain_ts<=0:
        raise RuntimeError("recovery sensor timestamps are invalid")
    if co2_value<0:
        raise RuntimeError("recovery CO2 must be non-negative")

    max_age=float(max_observation_age_s)
    if max_age<=0:
        raise ValueError("max_observation_age_s must be positive")
    now=float(clock_fn())
    ages={
        "opening":now-position_ts,
        "zone":now-co2_ts,
        "rain":now-rain_ts,
    }
    future=[key for key,age in ages.items() if age < -1.0]
    if future:
        raise RuntimeError(
            "recovery observations are future-dated: "
            + ",".join(sorted(future))
        )
    stale={key:age for key,age in ages.items() if age>max_age}
    if stale:
        rendered=", ".join(
            f"{key}={age:.3f}s"
            for key,age in sorted(stale.items())
        )
        raise RuntimeError(
            "recovery observations are stale: "
            +rendered+f" > {max_age:.3f}s"
        )

    origin={
        "co2_ppm":dict(previous["origin"]["co2_ppm"]),
        "opening_pct":dict(previous["origin"]["opening_pct"]),
        "scalar_values":dict(previous["origin"]["scalar_values"]),
    }
    origin["co2_ppm"][zone]=co2_value
    origin["opening_pct"][opening]=position
    origin["scalar_values"]["rain"]=1.0 if rain_value else 0.0
    normalized={
        "co2_ppm":dict(sorted((k,float(v)) for k,v in origin["co2_ppm"].items())),
        "opening_pct":dict(
            sorted((k,float(v)) for k,v in origin["opening_pct"].items())
        ),
        "scalar_values":dict(
            sorted((k,float(v)) for k,v in origin["scalar_values"].items())
        ),
    }

    snapshot_payload={
        "opening_id":opening,
        "zone_id":zone,
        "hardware_identity_sha256":live_identity,
        "position_pct":position,
        "position_timestamp":position_ts,
        "co2_ppm":co2_value,
        "co2_timestamp":co2_ts,
        "rain":rain_value,
        "rain_timestamp":rain_ts,
        "captured_at":now,
        "max_observation_age_s":max_age,
    }
    snapshot_sha=_sha256(snapshot_payload)

    all_zones=set(normalized["co2_ppm"])
    all_openings=set(normalized["opening_pct"])
    payload={
        "schema_version":"0.1",
        "source":"windowpilot-recovery-physical-origin-v1",
        "parent_physical_origin_sha256":previous["origin_sha256"],
        "parent_physical_origin_receipt_sha256":previous["receipt_sha256"],
        "recovery_execution_lease_sha256":str(lease["lease_sha256"]),
        "recovery_snapshot":snapshot_payload,
        "recovery_snapshot_sha256":snapshot_sha,
        "opening_id":opening,
        "zone_id":zone,
        "origin":normalized,
        "opening_hardware_identities":{opening:live_identity},
        "opening_observed_at":{opening:position_ts},
        "zone_observed_at":{zone:co2_ts},
        "rain_observed_at":rain_ts,
        "measured_zones":[zone],
        "measured_openings":[opening],
        "inherited_zones":sorted(all_zones-{zone}),
        "inherited_openings":sorted(all_openings-{opening}),
        "whole_home_physically_measured":(
            all_zones=={zone} and all_openings=={opening}
        ),
        "recovery_observation_age_s":dict(sorted(ages.items())),
        "evidence_boundary":(
            "read-only recovery snapshot after an abandoned execution; only "
            "the selected opening/zone plus rain are refreshed as measured, "
            "all other controller state remains inherited"
        ),
    }
    return {
        **payload,
        "origin_sha256":_sha256(normalized),
        "physical_origin_receipt_sha256":_sha256(payload),
    }
