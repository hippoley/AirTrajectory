"""Read-only compatibility probe for real WindowPilot HTTP contracts.

Unlike validation preflight, this module is diagnostic: it collects all
available GET endpoint evidence even when one endpoint is incomplete, then
classifies exact contract gaps without issuing actuator commands.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Mapping

from .drivers.windowpilot import WindowPilotHTTPDriver
from .demo_physical_config import resolve_windowpilot_headers
from .windowpilot_contract_mapping import (
    build_windowpilot_response_adapter,
)


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _shape(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {
            str(key): _shape(child, depth=depth + 1)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        if not value:
            return []
        return [_shape(value[0], depth=depth + 1)]
    return type(value).__name__


def _get(mapping: Any, *path: str) -> Any:
    current = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _fetch(
    request_json: Callable[[str, str, Any], Any],
    path: str,
) -> dict[str, Any]:
    try:
        payload = request_json("GET", path, None)
    except Exception as exc:
        return {
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "payload_sha256": None,
            "shape": None,
            "payload": None,
        }
    if not isinstance(payload, dict):
        return {
            "reachable": True,
            "error_type": "InvalidPayload",
            "error": "endpoint returned non-object JSON",
            "payload_sha256": _sha256(payload),
            "shape": _shape(payload),
            "payload": payload,
        }
    return {
        "reachable": True,
        "error_type": None,
        "error": None,
        "payload_sha256": _sha256(payload),
        "shape": _shape(payload),
        "payload": payload,
    }


def _finding(
    *,
    code: str,
    severity: str,
    message: str,
    adapter_action: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "adapter_action": adapter_action,
    }


def probe_windowpilot_http_contract(
    *,
    base_url: str,
    request_json: Callable[[str, str, Any], Any] | None = None,
    response_adapter: Callable[[str, Any], dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
    clock_fn=time.time,
) -> dict[str, Any]:
    driver = WindowPilotHTTPDriver(
        base_url=base_url,
        request_json=request_json,
        response_adapter=response_adapter,
        headers=dict(headers or {}),
    )
    fetch = driver._request_json
    endpoints = {
        "capabilities": _fetch(fetch, "/api/capabilities"),
        "physical_readiness": _fetch(fetch, "/api/physical-readiness"),
        "state": _fetch(fetch, "/api/state"),
    }

    findings: list[dict[str, Any]] = []
    caps = endpoints["capabilities"]["payload"]
    ready = endpoints["physical_readiness"]["payload"]
    state = endpoints["state"]["payload"]

    for name, result in endpoints.items():
        if not result["reachable"]:
            findings.append(_finding(
                code=f"{name.upper()}_UNREACHABLE",
                severity="error",
                message=f"{name} endpoint is unreachable: {result['error']}",
                adapter_action="fix endpoint/network/auth before field validation",
            ))
        elif result["error_type"]:
            findings.append(_finding(
                code=f"{name.upper()}_INVALID_JSON_SHAPE",
                severity="error",
                message=f"{name} endpoint does not return a JSON object",
                adapter_action="add/adjust WindowPilot response adapter",
            ))

    execution = _get(caps, "execution")
    if isinstance(execution, dict):
        if execution.get("simulated") is not False:
            findings.append(_finding(
                code="EXECUTION_NOT_CONFIRMED_PHYSICAL",
                severity="error",
                message="capabilities.execution.simulated is not false",
                adapter_action="expose real execution state from WindowPilot",
            ))
        if execution.get("measured_position") is not True:
            findings.append(_finding(
                code="MEASURED_POSITION_CAPABILITY_MISSING",
                severity="error",
                message="capabilities.execution.measured_position is not true",
                adapter_action="publish measured position capability",
            ))
        if not str(execution.get("transport") or ""):
            findings.append(_finding(
                code="TRANSPORT_MISSING",
                severity="warning",
                message="capabilities.execution.transport is missing",
                adapter_action="publish physical transport identity",
            ))
    else:
        findings.append(_finding(
            code="EXECUTION_BLOCK_MISSING",
            severity="error",
            message="capabilities.execution object is missing",
            adapter_action="map real capability payload into execution contract",
        ))

    identity = _get(ready, "hardware_identity")
    identity_sha = _get(identity, "identity_sha256")
    if not isinstance(identity, dict):
        findings.append(_finding(
            code="HARDWARE_IDENTITY_MISSING",
            severity="error",
            message="physical-readiness.hardware_identity object is missing",
            adapter_action="publish commissioned hardware identity",
        ))
    elif not isinstance(identity_sha, str) or len(identity_sha) != 64:
        findings.append(_finding(
            code="HARDWARE_IDENTITY_SHA_INVALID",
            severity="error",
            message="hardware_identity.identity_sha256 is missing or invalid",
            adapter_action="publish deterministic hardware identity SHA-256",
        ))

    feedback = _get(ready, "latest_position_feedback")
    if not isinstance(feedback, dict):
        findings.append(_finding(
            code="POSITION_FEEDBACK_MISSING",
            severity="error",
            message="physical-readiness.latest_position_feedback is missing",
            adapter_action="publish latest measured position feedback",
        ))
    else:
        if feedback.get("measured") is not True:
            findings.append(_finding(
                code="POSITION_NOT_MEASURED",
                severity="error",
                message="latest_position_feedback.measured is not true",
                adapter_action="bind encoder/device feedback instead of estimated state",
            ))
        if feedback.get("position_pct") is None:
            findings.append(_finding(
                code="POSITION_VALUE_MISSING",
                severity="error",
                message="latest_position_feedback.position_pct is missing",
                adapter_action="publish measured position percentage",
            ))
        if not float(feedback.get("timestamp") or 0):
            findings.append(_finding(
                code="POSITION_TIMESTAMP_MISSING",
                severity="error",
                message="latest_position_feedback.timestamp is missing",
                adapter_action="publish source timestamp for measured position",
            ))

    thing_model = _get(state, "thing_model")
    sensors = _get(thing_model, "sensors")
    timestamps = _get(thing_model, "sensor_timestamps")
    evidence = _get(thing_model, "sensor_evidence")
    co2_evidence = None
    site_id = None
    if not isinstance(thing_model, dict):
        findings.append(_finding(
            code="THING_MODEL_MISSING",
            severity="error",
            message="state.thing_model object is missing",
            adapter_action="map runtime state into thing_model contract",
        ))
    else:
        if not isinstance(sensors, dict):
            findings.append(_finding(
                code="SENSORS_BLOCK_MISSING",
                severity="error",
                message="thing_model.sensors object is missing",
                adapter_action="publish sensor values under thing_model.sensors",
            ))
        elif sensors.get("co2_ppm") is None:
            findings.append(_finding(
                code="CO2_VALUE_MISSING",
                severity="error",
                message="thing_model.sensors.co2_ppm is missing",
                adapter_action="map CO2 measurement into co2_ppm",
            ))
        if not isinstance(timestamps, dict) or not float(timestamps.get("co2_ppm") or 0):
            findings.append(_finding(
                code="CO2_TIMESTAMP_MISSING",
                severity="error",
                message="thing_model.sensor_timestamps.co2_ppm is missing",
                adapter_action="publish CO2 source timestamp",
            ))
        co2_evidence = (
            evidence.get("co2_ppm")
            if isinstance(evidence, dict)
            and isinstance(evidence.get("co2_ppm"), dict)
            else None
        )
        if not isinstance(co2_evidence, dict):
            findings.append(_finding(
                code="CO2_EVIDENCE_MISSING",
                severity="error",
                message="thing_model.sensor_evidence.co2_ppm is missing",
                adapter_action="publish measured CO2 evidence receipt",
            ))
        else:
            if co2_evidence.get("measured") is not True:
                findings.append(_finding(
                    code="CO2_NOT_MEASURED",
                    severity="error",
                    message="CO2 evidence measured flag is not true",
                    adapter_action="bind live sensor measurement evidence",
                ))
            binding = co2_evidence.get("thingmodel_binding")
            site_id = binding.get("site_id") if isinstance(binding, dict) else None
            if not site_id:
                findings.append(_finding(
                    code="CO2_SITE_BINDING_MISSING",
                    severity="error",
                    message="CO2 evidence lacks thingmodel_binding.site_id",
                    adapter_action="bind CO2 source to physical site",
                ))

    errors = [row for row in findings if row["severity"] == "error"]
    warnings = [row for row in findings if row["severity"] == "warning"]
    if errors:
        status = "INCOMPATIBLE"
    elif warnings:
        status = "PARTIAL"
    else:
        status = "COMPATIBLE"

    endpoint_summary = {
        name: {
            key: result[key]
            for key in (
                "reachable",
                "error_type",
                "error",
                "payload_sha256",
                "shape",
            )
        }
        for name, result in endpoints.items()
    }

    payload = {
        "schema_version": "0.1",
        "probe": "windowpilot-http-contract-probe-v1",
        "status": status,
        "checked_at": float(clock_fn()),
        "base_url_sha256": hashlib.sha256(
            str(base_url).encode("utf-8")
        ).hexdigest(),
        "contract_mapping": driver.contract_mapping_identity(),
        "endpoints": endpoint_summary,
        "observed": {
            "execution": execution if isinstance(execution, dict) else None,
            "hardware_identity_sha256": identity_sha,
            "position_feedback": {
                "measured": feedback.get("measured"),
                "position_pct_present": feedback.get("position_pct") is not None,
                "timestamp_present": bool(float(feedback.get("timestamp") or 0)),
                "quality_present": bool(str(feedback.get("quality") or "")),
                "source_present": bool(str(feedback.get("source") or "")),
            } if isinstance(feedback, dict) else None,
            "co2_value_present": (
                isinstance(sensors, dict)
                and sensors.get("co2_ppm") is not None
            ),
            "co2_timestamp_present": (
                isinstance(timestamps, dict)
                and bool(float(timestamps.get("co2_ppm") or 0))
            ),
            "co2_evidence_present": (
                isinstance(evidence, dict)
                and isinstance(evidence.get("co2_ppm"), dict)
            ),
            "co2_site_id": (
                site_id
                if isinstance(co2_evidence, dict)
                else None
            ),
        },
        "findings": findings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "actuator_writes": 0,
    }
    return {
        **payload,
        "probe_receipt_sha256": _sha256(payload),
    }


def probe_windowpilot_config(
    *,
    config: Mapping[str, Any],
    request_json_factory=None,
    clock_fn=time.time,
) -> dict[str, Any]:
    endpoints = config.get("windowpilot_endpoints")
    if not isinstance(endpoints, dict) or not endpoints:
        raise ValueError("windowpilot_endpoints are required")
    reports = {}
    for endpoint_id, spec in sorted(endpoints.items()):
        if not isinstance(spec, dict):
            raise ValueError(f"endpoint {endpoint_id} must be an object")
        base_url = str(spec.get("base_url") or "")
        if not base_url:
            raise ValueError(f"endpoint {endpoint_id} missing base_url")
        request_json = (
            None
            if request_json_factory is None
            else request_json_factory(endpoint_id, spec)
        )
        response_adapter = None
        profile_name = spec.get("contract_mapping_profile")
        if profile_name is not None:
            profiles = config.get("contract_mapping_profiles") or {}
            profile = profiles.get(str(profile_name))
            if not isinstance(profile, Mapping):
                raise ValueError(
                    f"endpoint {endpoint_id} references unavailable contract mapping profile {profile_name}"
                )
            response_adapter = build_windowpilot_response_adapter(profile)
        reports[endpoint_id] = probe_windowpilot_http_contract(
            base_url=base_url,
            request_json=request_json,
            response_adapter=response_adapter,
            headers=resolve_windowpilot_headers(spec),
            clock_fn=clock_fn,
        )

    statuses = [row["status"] for row in reports.values()]
    if all(status == "COMPATIBLE" for status in statuses):
        status = "COMPATIBLE"
    elif any(status == "INCOMPATIBLE" for status in statuses):
        status = "INCOMPATIBLE"
    else:
        status = "PARTIAL"
    payload = {
        "schema_version": "0.1",
        "probe": "windowpilot-config-contract-probe-v1",
        "status": status,
        "endpoint_count": len(reports),
        "endpoints": reports,
        "actuator_writes": 0,
    }
    return {
        **payload,
        "config_probe_receipt_sha256": _sha256(payload),
    }
