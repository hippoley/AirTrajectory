"""Fresh measured sensor snapshot after a replanned physical action."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import time
from typing import Any, Mapping


def _sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _row(reading):
    if is_dataclass(reading):
        return asdict(reading)
    if isinstance(reading,Mapping):
        return dict(reading)
    raise RuntimeError("post-action sensor reading is invalid")


def capture_post_action_snapshot(
    *,
    driver,
    after_timestamp: float,
    timeout_s: float=10.0,
    poll_interval_s: float=0.1,
    sleep_fn=time.sleep,
    clock_fn=time.time,
) -> dict[str, Any]:
    after=float(after_timestamp)
    if after<=0:
        raise ValueError("after_timestamp must be positive")
    timeout=float(timeout_s)
    interval=float(poll_interval_s)
    if timeout<=0:
        raise ValueError("timeout_s must be positive")
    if interval<0:
        raise ValueError("poll_interval_s must be non-negative")

    deadline=clock_fn()+timeout
    last_reason="no CO2/rain sensor evidence"
    while clock_fn()<=deadline:
        readings=[_row(row) for row in driver.read_sensors()]
        by_type={
            str(row.get("sensor_type") or ""):row
            for row in readings
        }
        co2=by_type.get("co2")
        rain=by_type.get("rain")
        if co2 is not None and rain is not None:
            co2_ts=float(co2.get("timestamp") or 0)
            rain_ts=float(rain.get("timestamp") or 0)
            if co2_ts>after and rain_ts>after:
                payload={
                    "schema_version":"0.1",
                    "snapshot":"post-replanned-action-physical-v1",
                    "after_timestamp":after,
                    "co2_ppm":float(co2["value"]),
                    "co2_timestamp":co2_ts,
                    "rain":bool(float(rain["value"])),
                    "rain_timestamp":rain_ts,
                    "sensor_readings":readings,
                    "fresh_after_action":True,
                }
                return {
                    **payload,
                    "snapshot_sha256":_sha256(payload),
                }
            stale=[]
            if co2_ts<=after:
                stale.append("co2")
            if rain_ts<=after:
                stale.append("rain")
            last_reason="sensor evidence not newer than action feedback: "+",".join(stale)
        sleep_fn(interval)

    raise RuntimeError("post-action sensor timeout: "+last_reason)
