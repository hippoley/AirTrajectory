"""Freeze and compare WindowPilot contract baselines.

A baseline intentionally excludes dynamic values such as CO2 readings,
timestamps, and full payload hashes. It preserves stable API shape plus the
physical instance identity needed to detect contract and hardware/site drift.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


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


def _verify_probe_report(report: dict[str, Any]) -> None:
    if not isinstance(report, dict):
        raise ValueError("WindowPilot probe report must be an object")
    provided = str(report.get("config_probe_receipt_sha256") or "")
    payload = dict(report)
    payload.pop("config_probe_receipt_sha256", None)
    if provided != _sha256(payload):
        raise ValueError("config probe receipt SHA-256 integrity check failed")

    endpoints = report.get("endpoints")
    if not isinstance(endpoints, dict) or not endpoints:
        raise ValueError("config probe endpoints are required")
    for endpoint_id, endpoint in endpoints.items():
        if not isinstance(endpoint, dict):
            raise ValueError(f"probe endpoint {endpoint_id} must be an object")
        endpoint_sha = str(endpoint.get("probe_receipt_sha256") or "")
        endpoint_payload = dict(endpoint)
        endpoint_payload.pop("probe_receipt_sha256", None)
        if endpoint_sha != _sha256(endpoint_payload):
            raise ValueError(
                f"endpoint {endpoint_id} probe receipt SHA-256 integrity check failed"
            )


def _stable_endpoint_contract(endpoint: dict[str, Any]) -> dict[str, Any]:
    observed = endpoint.get("observed") or {}
    execution = observed.get("execution")
    execution_stable = None
    if isinstance(execution, dict):
        execution_stable = {
            "simulated": execution.get("simulated"),
            "measured_position": execution.get("measured_position"),
            "transport": execution.get("transport"),
        }
    endpoint_shapes = {}
    for key in ("capabilities", "physical_readiness", "state"):
        row = (endpoint.get("endpoints") or {}).get(key) or {}
        endpoint_shapes[key] = row.get("shape")

    position = observed.get("position_feedback")
    position_stable = None
    if isinstance(position, dict):
        position_stable = {
            "measured": position.get("measured"),
            "position_pct_present": position.get("position_pct_present"),
            "timestamp_present": position.get("timestamp_present"),
            "quality_present": position.get("quality_present"),
            "source_present": position.get("source_present"),
        }

    return {
        "contract": {
            "endpoint_shapes": endpoint_shapes,
            "execution": execution_stable,
            "position_feedback": position_stable,
            "co2_value_present": observed.get("co2_value_present"),
            "co2_timestamp_present": observed.get("co2_timestamp_present"),
            "co2_evidence_present": observed.get("co2_evidence_present"),
        },
        "instance": {
            "base_url_sha256": endpoint.get("base_url_sha256"),
            "hardware_identity_sha256": observed.get(
                "hardware_identity_sha256"
            ),
            "co2_site_id": observed.get("co2_site_id"),
        },
    }


def freeze_windowpilot_contract_baseline(
    report: dict[str, Any],
    *,
    baseline_id: str,
) -> dict[str, Any]:
    _verify_probe_report(report)
    if report.get("status") != "COMPATIBLE":
        raise ValueError(
            "only a fully COMPATIBLE probe can be frozen as a baseline"
        )
    baseline_id = str(baseline_id or "")
    if not baseline_id:
        raise ValueError("baseline_id is required")

    endpoints = {
        endpoint_id: _stable_endpoint_contract(endpoint)
        for endpoint_id, endpoint in sorted(report["endpoints"].items())
    }
    payload = {
        "schema_version": "0.1",
        "baseline": "windowpilot-contract-baseline-v1",
        "baseline_id": baseline_id,
        "status": "FROZEN",
        "source_config_probe_receipt_sha256": report[
            "config_probe_receipt_sha256"
        ],
        "endpoint_count": len(endpoints),
        "endpoint_ids": sorted(endpoints),
        "endpoints": endpoints,
    }
    return {
        **payload,
        "baseline_sha256": _sha256(payload),
    }


def _verify_baseline(baseline: dict[str, Any]) -> None:
    if not isinstance(baseline, dict):
        raise ValueError("WindowPilot contract baseline must be an object")
    provided = str(baseline.get("baseline_sha256") or "")
    payload = dict(baseline)
    payload.pop("baseline_sha256", None)
    if provided != _sha256(payload):
        raise ValueError("contract baseline SHA-256 integrity check failed")
    if baseline.get("status") != "FROZEN":
        raise ValueError("contract baseline status is not FROZEN")


def _drift(
    *,
    endpoint_id: str,
    category: str,
    path: str,
    expected: Any,
    actual: Any,
) -> dict[str, Any]:
    return {
        "endpoint_id": endpoint_id,
        "category": category,
        "path": path,
        "expected": expected,
        "actual": actual,
    }


def _walk_diff(
    *,
    endpoint_id: str,
    category: str,
    path: str,
    expected: Any,
    actual: Any,
    out: list[dict[str, Any]],
) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            _walk_diff(
                endpoint_id=endpoint_id,
                category=category,
                path=f"{path}.{key}" if path else key,
                expected=expected.get(key),
                actual=actual.get(key),
                out=out,
            )
        return
    if expected != actual:
        out.append(
            _drift(
                endpoint_id=endpoint_id,
                category=category,
                path=path,
                expected=expected,
                actual=actual,
            )
        )


def compare_windowpilot_contract_baseline(
    *,
    baseline: dict[str, Any],
    current_report: dict[str, Any],
) -> dict[str, Any]:
    _verify_baseline(baseline)
    _verify_probe_report(current_report)

    drifts: list[dict[str, Any]] = []
    expected_ids = set(baseline.get("endpoint_ids") or [])
    current_ids = set((current_report.get("endpoints") or {}).keys())

    for endpoint_id in sorted(expected_ids - current_ids):
        drifts.append(
            _drift(
                endpoint_id=endpoint_id,
                category="INSTANCE_DRIFT",
                path="endpoint",
                expected="present",
                actual="missing",
            )
        )
    for endpoint_id in sorted(current_ids - expected_ids):
        drifts.append(
            _drift(
                endpoint_id=endpoint_id,
                category="INSTANCE_DRIFT",
                path="endpoint",
                expected="absent",
                actual="added",
            )
        )

    for endpoint_id in sorted(expected_ids & current_ids):
        expected = baseline["endpoints"][endpoint_id]
        current = _stable_endpoint_contract(
            current_report["endpoints"][endpoint_id]
        )
        _walk_diff(
            endpoint_id=endpoint_id,
            category="CONTRACT_DRIFT",
            path="contract",
            expected=expected["contract"],
            actual=current["contract"],
            out=drifts,
        )
        _walk_diff(
            endpoint_id=endpoint_id,
            category="INSTANCE_DRIFT",
            path="instance",
            expected=expected["instance"],
            actual=current["instance"],
            out=drifts,
        )
        if current_report["endpoints"][endpoint_id].get("status") != "COMPATIBLE":
            drifts.append(
                _drift(
                    endpoint_id=endpoint_id,
                    category="CONTRACT_DRIFT",
                    path="probe_status",
                    expected="COMPATIBLE",
                    actual=current_report["endpoints"][endpoint_id].get("status"),
                )
            )

    contract_count = sum(
        1 for row in drifts if row["category"] == "CONTRACT_DRIFT"
    )
    instance_count = sum(
        1 for row in drifts if row["category"] == "INSTANCE_DRIFT"
    )
    payload = {
        "schema_version": "0.1",
        "comparison": "windowpilot-contract-baseline-compare-v1",
        "status": "MATCH" if not drifts else "DRIFT",
        "baseline_id": baseline["baseline_id"],
        "baseline_sha256": baseline["baseline_sha256"],
        "current_config_probe_receipt_sha256": current_report[
            "config_probe_receipt_sha256"
        ],
        "contract_drift_count": contract_count,
        "instance_drift_count": instance_count,
        "drifts": drifts,
    }
    return {
        **payload,
        "comparison_sha256": _sha256(payload),
    }
