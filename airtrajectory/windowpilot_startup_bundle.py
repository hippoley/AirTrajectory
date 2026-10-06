"""Build and independently verify replayable WindowPilot startup bundles.

A startup bundle binds the four read-only artifacts required before timed field
sampling: frozen contract baseline, current compatibility probe, baseline
comparison, and validation preflight. It stores only hashes and normalized
identity summaries, never raw endpoint payloads.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
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


def _verify_hash(payload: dict[str, Any], field: str, label: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    provided = str(payload.get(field) or "")
    body = dict(payload)
    body.pop(field, None)
    if provided != _sha256(body):
        raise ValueError(f"{label} SHA-256 integrity check failed")


def _verify_probe(report: dict[str, Any]) -> None:
    _verify_hash(
        report,
        "config_probe_receipt_sha256",
        "config probe receipt",
    )
    endpoints = report.get("endpoints")
    if not isinstance(endpoints, dict) or not endpoints:
        raise ValueError("config probe endpoints are required")
    for endpoint_id, endpoint in endpoints.items():
        _verify_hash(
            endpoint,
            "probe_receipt_sha256",
            f"endpoint {endpoint_id} probe receipt",
        )


def _identity_summary(
    baseline: dict[str, Any],
    probe: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    baseline_ids = set(baseline.get("endpoint_ids") or [])
    probe_ids = set((probe.get("endpoints") or {}).keys())
    preflight_ids = set((preflight.get("endpoints") or {}).keys())
    if not baseline_ids:
        raise ValueError("baseline endpoint_ids are required")
    if baseline_ids != probe_ids or baseline_ids != preflight_ids:
        raise ValueError(
            "baseline/probe/preflight endpoint sets do not match"
        )

    baseline_sites = set()
    endpoints = {}
    for endpoint_id in sorted(baseline_ids):
        baseline_endpoint = baseline["endpoints"][endpoint_id]
        expected_instance = baseline_endpoint.get("instance") or {}
        expected_identity = str(
            expected_instance.get("hardware_identity_sha256") or ""
        )
        expected_site = str(expected_instance.get("co2_site_id") or "")
        if len(expected_identity) != 64:
            raise ValueError(
                f"baseline endpoint {endpoint_id} hardware identity is invalid"
            )
        if not expected_site:
            raise ValueError(
                f"baseline endpoint {endpoint_id} physical site is missing"
            )
        baseline_sites.add(expected_site)

        probe_observed = (
            probe["endpoints"][endpoint_id].get("observed") or {}
        )
        probe_identity = str(
            probe_observed.get("hardware_identity_sha256") or ""
        )
        probe_site = str(probe_observed.get("co2_site_id") or "")
        preflight_row = preflight["endpoints"][endpoint_id]
        preflight_identity = str(
            preflight_row.get("hardware_identity_sha256") or ""
        )

        if probe_identity != expected_identity:
            raise ValueError(
                f"probe hardware identity drift for endpoint {endpoint_id}"
            )
        if preflight_identity != expected_identity:
            raise ValueError(
                f"preflight hardware identity drift for endpoint {endpoint_id}"
            )
        if probe_site != expected_site:
            raise ValueError(
                f"probe physical site drift for endpoint {endpoint_id}"
            )

        endpoints[endpoint_id] = {
            "hardware_identity_sha256": expected_identity,
            "physical_site_id": expected_site,
            "base_url_sha256": expected_instance.get("base_url_sha256"),
        }

    if len(baseline_sites) != 1:
        raise ValueError(
            "startup baseline must resolve to one physical site"
        )
    physical_site_id = next(iter(baseline_sites))
    if str(preflight.get("physical_site_id") or "") != physical_site_id:
        raise ValueError(
            "preflight physical_site_id does not match baseline"
        )

    return {
        "physical_site_id": physical_site_id,
        "endpoint_ids": sorted(baseline_ids),
        "endpoints": endpoints,
    }


def build_windowpilot_startup_bundle(
    *,
    baseline: dict[str, Any],
    probe_report: dict[str, Any],
    comparison: dict[str, Any],
    preflight: dict[str, Any],
    bundle_id: str,
) -> dict[str, Any]:
    _verify_hash(baseline, "baseline_sha256", "contract baseline")
    _verify_probe(probe_report)
    _verify_hash(
        comparison,
        "comparison_sha256",
        "contract comparison",
    )
    _verify_hash(
        preflight,
        "preflight_receipt_sha256",
        "validation preflight",
    )

    expected_comparison = compare_windowpilot_contract_baseline(
        baseline=baseline,
        current_report=probe_report,
    )
    if comparison != expected_comparison:
        raise ValueError(
            "supplied contract comparison does not replay exactly"
        )
    if comparison.get("status") != "MATCH":
        raise ValueError(
            "startup bundle requires contract comparison MATCH"
        )
    if preflight.get("status") != "PASS":
        raise ValueError("startup bundle requires preflight PASS")
    if int(preflight.get("actuator_writes") or 0) != 0:
        raise ValueError(
            "startup preflight must prove zero actuator writes"
        )

    bundle_id = str(bundle_id or "")
    if not bundle_id:
        raise ValueError("bundle_id is required")

    identity = _identity_summary(
        baseline,
        probe_report,
        preflight,
    )
    payload = {
        "schema_version": "0.1",
        "bundle": "windowpilot-startup-evidence-v1",
        "bundle_id": bundle_id,
        "status": "VERIFIED_READ_ONLY_STARTUP",
        "baseline_id": baseline["baseline_id"],
        "baseline_sha256": baseline["baseline_sha256"],
        "config_probe_receipt_sha256": probe_report[
            "config_probe_receipt_sha256"
        ],
        "contract_comparison_sha256": comparison[
            "comparison_sha256"
        ],
        "preflight_receipt_sha256": preflight[
            "preflight_receipt_sha256"
        ],
        "runtime_receipt_sha256": preflight[
            "runtime_receipt_sha256"
        ],
        "protocol_sha256": preflight["protocol_sha256"],
        "physical_site_id": identity["physical_site_id"],
        "endpoint_ids": identity["endpoint_ids"],
        "endpoints": identity["endpoints"],
        "actuator_writes": 0,
        "evidence_boundary": (
            "read-only startup continuity only; not field-model accuracy"
        ),
    }
    return {
        **payload,
        "startup_bundle_sha256": _sha256(payload),
    }


def verify_windowpilot_startup_bundle(
    *,
    bundle: dict[str, Any],
    baseline: dict[str, Any],
    probe_report: dict[str, Any],
    comparison: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(
        bundle,
        "startup_bundle_sha256",
        "startup bundle",
    )
    rebuilt = build_windowpilot_startup_bundle(
        baseline=baseline,
        probe_report=probe_report,
        comparison=comparison,
        preflight=preflight,
        bundle_id=str(bundle.get("bundle_id") or ""),
    )
    if bundle != rebuilt:
        raise ValueError(
            "startup bundle does not exactly replay from supplied artifacts"
        )
    payload = {
        "schema_version": "0.1",
        "verification": "windowpilot-startup-bundle-replay-v1",
        "status": "VERIFIED",
        "startup_bundle_sha256": bundle[
            "startup_bundle_sha256"
        ],
        "baseline_sha256": baseline["baseline_sha256"],
        "config_probe_receipt_sha256": probe_report[
            "config_probe_receipt_sha256"
        ],
        "contract_comparison_sha256": comparison[
            "comparison_sha256"
        ],
        "preflight_receipt_sha256": preflight[
            "preflight_receipt_sha256"
        ],
        "actuator_writes": 0,
    }
    return {
        **payload,
        "verification_sha256": _sha256(payload),
    }
