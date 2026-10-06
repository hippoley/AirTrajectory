"""Read-only preflight for WindowPilot field validation."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import time
from typing import Any, Mapping

from .contam_field_validation import validate_field_validation_protocol
from .layout import LayoutContract
from .physical import PhysicalWindowDriver
from .windowpilot_field_capture import _capture_spec


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _require_configured_source(source: dict[str, Any]) -> None:
    for key, value in source.items():
        text = str(value or "")
        if text.startswith("replace-with-"):
            raise ValueError(
                f"field_capture source {key} is still a template placeholder"
            )


def preflight_windowpilot_field_validation(
    *,
    layout: LayoutContract,
    config: dict[str, Any],
    drivers: Mapping[str, PhysicalWindowDriver],
    protocol: dict[str, Any],
    runtime_receipt: dict[str, Any],
    clock_fn=time.time,
) -> dict[str, Any]:
    source, co2_sources, measured_openings = _capture_spec(
        layout=layout,
        config=config,
        protocol=protocol,
    )
    _require_configured_source(source)
    normalized = validate_field_validation_protocol(layout, protocol)

    if runtime_receipt.get("status") != "ENGINEERING_RUNTIME_VERIFIED":
        raise ValueError("runtime receipt is not ENGINEERING_RUNTIME_VERIFIED")
    if runtime_receipt.get("runtime_verified") is not True:
        raise ValueError("runtime receipt is not runtime_verified")
    if runtime_receipt.get("topology_id") != layout.topology_id:
        raise ValueError("runtime receipt topology_id does not match layout")
    if runtime_receipt.get("layout_contract_sha256") != layout.sha256():
        raise ValueError("runtime receipt layout SHA-256 drift")

    steps = int(runtime_receipt.get("steps") or 0)
    if steps < normalized["min_samples"]:
        raise ValueError("runtime prediction steps are below protocol minimum")

    endpoints = set(config.get("windowpilot_endpoints") or {})
    if set(drivers) != endpoints:
        raise ValueError(
            "WindowPilot driver set must exactly match configured endpoints"
        )

    capture_cfg = config.get("field_capture") or {}
    max_sample_age_s = float(capture_cfg.get("max_sample_age_s", 10.0))
    max_future_skew_s = float(capture_cfg.get("max_future_skew_s", 2.0))
    if max_sample_age_s <= 0:
        raise ValueError("field_capture max_sample_age_s must be positive")
    if max_future_skew_s < 0:
        raise ValueError(
            "field_capture max_future_skew_s must be non-negative"
        )

    now = float(clock_fn())
    observed_site_ids: set[str] = set()
    endpoint_rows = {}
    co2_by_endpoint = {}

    for endpoint_id in sorted(endpoints):
        driver = drivers[endpoint_id]
        caps = driver.capabilities()
        if caps.simulated:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} is simulated"
            )
        if endpoint_id in measured_openings and not caps.measured_position:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} lacks measured position"
            )

        readiness = driver.physical_readiness()
        if not isinstance(readiness, dict):
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} readiness is invalid"
            )
        identity = readiness.get("hardware_identity")
        if not isinstance(identity, dict):
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} missing hardware_identity"
            )
        identity_sha = str(identity.get("identity_sha256") or "")
        if len(identity_sha) != 64:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} has invalid hardware identity"
            )

        position_summary = None
        if endpoint_id in measured_openings:
            feedback = readiness.get("latest_position_feedback")
            if not isinstance(feedback, dict):
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} missing latest_position_feedback"
                )
            if feedback.get("measured") is not True:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} position is not measured"
                )
            ts = float(feedback.get("timestamp") or 0)
            pct = feedback.get("position_pct")
            if ts <= 0 or pct is None:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} measured position evidence is incomplete"
                )
            age = now - ts
            if age > max_sample_age_s:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} position feedback is stale"
                )
            if age < -max_future_skew_s:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} position timestamp is too far in the future"
                )
            value = float(pct)
            if not 0 <= value <= 100:
                raise RuntimeError(
                    f"WindowPilot endpoint {endpoint_id} measured position is outside [0,100]"
                )
            position_summary = {
                "position_pct": value,
                "timestamp": ts,
                "age_s": age,
                "quality": str(feedback.get("quality") or ""),
                "source": str(feedback.get("source") or ""),
            }

        readings = list(driver.read_sensors())
        co2 = [row for row in readings if row.sensor_type == "co2"]
        if len(co2) != 1:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} must expose exactly one measured CO2 reading"
            )
        reading = co2[0]
        if reading.unit != "ppm":
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} CO2 unit must be ppm"
            )
        age = now - float(reading.timestamp)
        if age > max_sample_age_s:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} CO2 reading is stale"
            )
        if age < -max_future_skew_s:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} CO2 timestamp is too far in the future"
            )
        provenance = dict(reading.provenance or {})
        site_id = str(provenance.get("site_id") or "")
        if not site_id:
            raise RuntimeError(
                f"WindowPilot endpoint {endpoint_id} CO2 provenance missing site_id"
            )
        observed_site_ids.add(site_id)
        if len(observed_site_ids) > 1:
            raise RuntimeError(
                "WindowPilot field validation preflight spans multiple physical sites"
            )

        co2_by_endpoint[endpoint_id] = {
            "sensor_id": str(reading.sensor_id),
            "value_ppm": float(reading.value),
            "timestamp": float(reading.timestamp),
            "age_s": age,
            "quality": str(reading.quality),
            "site_id": site_id,
            "provenance_sha256": _sha256(provenance),
        }
        endpoint_rows[endpoint_id] = {
            "capabilities": asdict(caps),
            "hardware_identity_sha256": identity_sha,
            "position_feedback": position_summary,
        }

    missing_zone_sources = [
        zone
        for zone, endpoint_id in co2_sources.items()
        if endpoint_id not in co2_by_endpoint
    ]
    if missing_zone_sources:
        raise RuntimeError(
            "WindowPilot CO2 source missing after preflight: "
            + ",".join(sorted(missing_zone_sources))
        )

    payload = {
        "schema_version": "0.1",
        "preflight": "windowpilot-field-validation-preflight-v1",
        "status": "PASS",
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "protocol_sha256": normalized["protocol_sha256"],
        "physical_site_id": next(iter(observed_site_ids)),
        "source": source,
        "co2_zone_sources": dict(sorted(co2_sources.items())),
        "measured_openings": sorted(measured_openings),
        "fixed_opening_assumptions": normalized[
            "opening_position"
        ]["fixed_openings"],
        "max_sample_age_s": max_sample_age_s,
        "max_future_skew_s": max_future_skew_s,
        "checked_at": now,
        "endpoints": endpoint_rows,
        "co2_by_endpoint": co2_by_endpoint,
        "actuator_writes": 0,
    }
    return {
        **payload,
        "preflight_receipt_sha256": _sha256(payload),
    }
