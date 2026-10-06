"""Read-only WindowPilot -> raw field-capture adapter.

The adapter never issues actuator commands. It samples measured CO2 from
WindowPilot sensor receipts and measured opening position from physical
readiness, then emits the timestamped event contract used by field validation.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any, Mapping

from .contam_field_validation import validate_field_validation_protocol
from .layout import LayoutContract
from .physical import PhysicalWindowDriver


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(
        float(ts), tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")


def _capture_spec(
    *,
    layout: LayoutContract,
    config: dict[str, Any],
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    normalized = validate_field_validation_protocol(layout, protocol)
    capture = config.get("field_capture")
    if not isinstance(capture, dict):
        raise ValueError("WindowPilot config requires field_capture section")
    source = capture.get("source")
    if not isinstance(source, dict):
        raise ValueError("field_capture source must be an object")
    for key in ("kind", "id", "model", "serial", "calibration_ref"):
        if not str(source.get(key) or ""):
            raise ValueError(
                "field_capture source requires kind, id, model, serial, and calibration_ref"
            )
    co2_sources = capture.get("co2_zone_sources")
    if not isinstance(co2_sources, dict):
        raise ValueError("field_capture co2_zone_sources must be an object")
    expected_zones = set(normalized["co2"]["zones"])
    if set(co2_sources) != expected_zones:
        raise ValueError(
            "field_capture co2_zone_sources must cover protocol CO2 zones"
        )
    endpoint_ids = set(config.get("windowpilot_endpoints") or {})
    unknown = sorted(set(str(x) for x in co2_sources.values()) - endpoint_ids)
    if unknown:
        raise ValueError(
            "field_capture CO2 source references unknown endpoint: "
            + ",".join(unknown)
        )
    measured_openings = list(
        normalized["opening_position"]["openings"]
    )
    missing = sorted(set(measured_openings) - endpoint_ids)
    if missing:
        raise ValueError(
            "measured opening has no WindowPilot endpoint: "
            + ",".join(missing)
        )
    fixed_config = {
        str(k): float(v)
        for k, v in (config.get("fixed_openings") or {}).items()
    }
    if fixed_config != normalized["opening_position"]["fixed_openings"]:
        raise ValueError(
            "WindowPilot fixed_openings do not match validation protocol assumptions"
        )
    return (
        {key: source[key] for key in (
            "kind", "id", "model", "serial", "calibration_ref"
        )},
        {str(k): str(v) for k, v in co2_sources.items()},
        measured_openings,
    )


def collect_windowpilot_field_capture(
    *,
    layout: LayoutContract,
    config: dict[str, Any],
    drivers: Mapping[str, PhysicalWindowDriver],
    protocol: dict[str, Any],
    runtime_receipt: dict[str, Any],
    validation_id: str,
    sample_count: int | None = None,
    sleep_fn=time.sleep,
    clock_fn=time.time,
) -> dict[str, Any]:
    source, co2_sources, measured_openings = _capture_spec(
        layout=layout,
        config=config,
        protocol=protocol,
    )
    normalized = validate_field_validation_protocol(layout, protocol)
    if runtime_receipt.get("status") != "ENGINEERING_RUNTIME_VERIFIED":
        raise ValueError("runtime receipt is not ENGINEERING_RUNTIME_VERIFIED")
    if runtime_receipt.get("topology_id") != layout.topology_id:
        raise ValueError("runtime receipt topology_id does not match layout")
    steps = int(runtime_receipt.get("steps") or 0)
    count = steps if sample_count is None else int(sample_count)
    if count != steps:
        raise ValueError(
            "WindowPilot field capture must sample every runtime prediction step"
        )
    if count < normalized["min_samples"]:
        raise ValueError("WindowPilot sample_count is below protocol minimum")

    endpoints = set(config.get("windowpilot_endpoints") or {})
    if set(drivers) != endpoints:
        raise ValueError(
            "WindowPilot driver set must exactly match configured endpoints"
        )

    for endpoint_id, driver in drivers.items():
        caps = driver.capabilities()
        if caps.simulated:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} is simulated"
            )
        if endpoint_id in measured_openings and not caps.measured_position:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} lacks measured position"
            )

    interval_s = float(
        normalized["alignment"]["sampling_interval_s"]
    )
    started_at = float(clock_fn())
    records: list[dict[str, Any]] = []
    sample_receipts = []
    endpoint_identity_sha256: dict[str, str] = {}
    observed_site_ids: set[str] = set()

    for sample_index in range(count):
        sleep_fn(interval_s)
        sample_records = []

        for zone_id, endpoint_id in sorted(co2_sources.items()):
            readings = list(drivers[endpoint_id].read_sensors())
            co2 = [row for row in readings if row.sensor_type == "co2"]
            if len(co2) != 1:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} must expose exactly one measured CO2 reading"
                )
            reading = co2[0]
            if reading.timestamp <= 0:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} CO2 timestamp is invalid"
                )
            if not reading.provenance:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} CO2 lacks ThingModel/site provenance"
                )
            site_id = str(reading.provenance.get("site_id") or "")
            if not site_id:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} CO2 provenance missing site_id"
                )
            observed_site_ids.add(site_id)
            if len(observed_site_ids) > 1:
                raise RuntimeError(
                    "WindowPilot field capture spans multiple physical sites"
                )
            row = {
                "timestamp": _iso(reading.timestamp),
                "signal_type": "co2_ppm",
                "target_id": zone_id,
                "value": float(reading.value),
                "unit": "ppm",
                "quality": "measured",
                "source_quality": str(reading.quality),
                "source_id": str(reading.sensor_id),
                "source_provenance_sha256": _sha256(
                    dict(reading.provenance)
                ),
            }
            records.append(row)
            sample_records.append(row)

        for opening_id in sorted(measured_openings):
            readiness = drivers[opening_id].physical_readiness()
            feedback = (
                readiness.get("latest_position_feedback")
                if isinstance(readiness, dict)
                else None
            )
            if not isinstance(feedback, dict):
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} missing latest_position_feedback"
                )
            identity = readiness.get("hardware_identity")
            if not isinstance(identity, dict):
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} missing hardware_identity"
                )
            identity_sha = str(identity.get("identity_sha256") or "")
            if len(identity_sha) != 64:
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} has invalid hardware identity"
                )
            prior = endpoint_identity_sha256.get(opening_id)
            if prior is not None and prior != identity_sha:
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} hardware identity changed during capture"
                )
            endpoint_identity_sha256[opening_id] = identity_sha
            if feedback.get("measured") is not True:
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} position is not measured"
                )
            timestamp = float(feedback.get("timestamp") or 0)
            position = feedback.get("position_pct")
            if timestamp <= 0 or position is None:
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} measured position evidence is incomplete"
                )
            value = float(position)
            if not 0 <= value <= 100:
                raise RuntimeError(
                    f"WindowPilot endpoint {opening_id} measured position is outside [0,100]"
                )
            row = {
                "timestamp": _iso(timestamp),
                "signal_type": "opening_pct",
                "target_id": opening_id,
                "value": value,
                "unit": "percent",
                "quality": "measured",
                "source_quality": str(
                    feedback.get("quality") or "measured-windowpilot"
                ),
                "source_id": str(
                    feedback.get("source") or opening_id
                ),
            }
            records.append(row)
            sample_records.append(row)

        sample_receipts.append({
            "sample_index": sample_index,
            "record_count": len(sample_records),
            "records_sha256": _sha256(sample_records),
        })

    adapter_payload = {
        "adapter": "windowpilot-field-capture-v1",
        "topology_id": layout.topology_id,
        "configured_endpoints": sorted(endpoints),
        "measured_openings": sorted(measured_openings),
        "fixed_opening_assumptions": normalized[
            "opening_position"
        ]["fixed_openings"],
        "co2_zone_sources": dict(sorted(co2_sources.items())),
        "physical_site_id": next(iter(observed_site_ids), None),
        "endpoint_identity_sha256": dict(
            sorted(endpoint_identity_sha256.items())
        ),
        "driver_capabilities": {
            key: asdict(drivers[key].capabilities())
            for key in sorted(drivers)
        },
        "sample_receipts": sample_receipts,
    }
    return {
        "schema_version": "0.1",
        "validation_id": str(validation_id),
        "protocol_id": normalized["protocol_id"],
        "protocol_sha256": normalized["protocol_sha256"],
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "started_at": _iso(started_at),
        "source": source,
        "records": records,
        "windowpilot_capture_provenance": {
            **adapter_payload,
            "adapter_receipt_sha256": _sha256(adapter_payload),
        },
    }
