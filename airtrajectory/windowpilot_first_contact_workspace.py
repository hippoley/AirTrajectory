"""One-shot first-contact workspace for WindowPilot hardware integration."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .windowpilot_first_contact import capture_windowpilot_first_contact
from .windowpilot_mapping_fixture import evaluate_windowpilot_mapping_files


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def build_windowpilot_first_contact_workspace(
    *,
    config: Mapping[str, Any],
    mapping_profile_bytes: bytes | None = None,
    environ: Mapping[str, str] | None = None,
    fetch_fn=None,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, bytes]],
    dict[str, dict[str, Any]],
]:
    endpoints = config.get("windowpilot_endpoints")
    if not isinstance(endpoints, Mapping) or not endpoints:
        raise ValueError("windowpilot_endpoints are required")

    captures: dict[str, dict[str, bytes]] = {}
    endpoint_manifests: dict[str, dict[str, Any]] = {}
    capture_errors = []
    network_requests = 0

    for endpoint_id, spec in sorted(endpoints.items()):
        single_config = dict(config)
        single_config["windowpilot_endpoints"] = {
            str(endpoint_id): spec
        }
        capture_kwargs = {
            "config": single_config,
            "environ": environ,
        }
        if fetch_fn is not None:
            capture_kwargs["fetch_fn"] = fetch_fn
        try:
            single_manifest, single_captures = (
                capture_windowpilot_first_contact(
                    **capture_kwargs
                )
            )
        except Exception as exc:
            capture_errors.append({
                "endpoint_id": str(endpoint_id),
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue
        captures.update(single_captures)
        endpoint_manifests[str(endpoint_id)] = (
            single_manifest["endpoints"][str(endpoint_id)]
        )
        network_requests += int(
            single_manifest.get("network_requests") or 0
        )

    if not captures:
        details = "; ".join(
            f"{row['endpoint_id']}: {row['error']}"
            for row in capture_errors
        )
        raise RuntimeError(
            "WindowPilot first-contact workspace captured no endpoints"
            + (f": {details}" if details else "")
        )

    manifest_payload = {
        "schema_version": "0.1",
        "capture": "windowpilot-first-contact-workspace-source-v1",
        "status": (
            "CAPTURED"
            if not capture_errors
            else "PARTIAL_CAPTURE"
        ),
        "endpoint_count": len(endpoint_manifests),
        "endpoint_ids": sorted(endpoint_manifests),
        "request_method": "GET",
        "allowed_paths": [
            "/api/capabilities",
            "/api/physical-readiness",
            "/api/state",
        ],
        "network_requests": network_requests,
        "actuator_writes": 0,
        "endpoints": endpoint_manifests,
        "capture_errors": capture_errors,
    }
    manifest = {
        **manifest_payload,
        "first_contact_capture_sha256": _sha256_json(
            manifest_payload
        ),
    }

    evaluations: dict[str, dict[str, Any]] = {}
    if mapping_profile_bytes is not None:
        for endpoint_id, files in sorted(captures.items()):
            try:
                report, canonical = evaluate_windowpilot_mapping_files(
                    profile_bytes=mapping_profile_bytes,
                    capabilities_bytes=files["capabilities.json"],
                    physical_readiness_bytes=files[
                        "physical_readiness.json"
                    ],
                    state_bytes=files["state.json"],
                    fixture_id=f"{endpoint_id}-first-contact",
                )
            except Exception as exc:
                report = {
                    "schema_version": "0.1",
                    "evaluation": "windowpilot-offline-mapping-fixture-v1",
                    "fixture_id": f"{endpoint_id}-first-contact",
                    "status": "MAPPING_ERROR",
                    "mapping_profile_id": None,
                    "mapping_profile_sha256": None,
                    "endpoint_receipts": {},
                    "mapping_errors": [{
                        "endpoint": "profile-or-fixture",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }],
                    "compatibility_probe_receipt_sha256": None,
                    "actuator_writes": 0,
                    "network_requests": 0,
                }
                report["evaluation_sha256"] = _sha256_json(
                    {
                        key: value
                        for key, value in report.items()
                        if key != "evaluation_sha256"
                    }
                )
                report["compatibility"] = None
                canonical = {}
            evaluations[endpoint_id] = {
                "report": report,
                "canonical": canonical,
            }

    evaluation_statuses = {
        endpoint_id: value["report"]["status"]
        for endpoint_id, value in sorted(evaluations.items())
    }

    if capture_errors:
        if not evaluations:
            status = "PARTIAL_CAPTURE"
        else:
            status = "PARTIAL_CAPTURE_WITH_MAPPING"
    elif not evaluations:
        status = "CAPTURED_ONLY"
    elif all(
        value == "COMPATIBLE"
        for value in evaluation_statuses.values()
    ):
        status = "CAPTURED_AND_COMPATIBLE"
    elif any(
        value == "MAPPING_ERROR"
        for value in evaluation_statuses.values()
    ):
        status = "CAPTURED_WITH_MAPPING_ERROR"
    else:
        status = "CAPTURED_WITH_INCOMPATIBLE_MAPPING"

    payload = {
        "schema_version": "0.1",
        "workspace": "windowpilot-first-contact-workspace-v1",
        "status": status,
        "first_contact_capture_sha256": manifest[
            "first_contact_capture_sha256"
        ],
        "endpoint_ids": manifest["endpoint_ids"],
        "endpoint_count": manifest["endpoint_count"],
        "capture_errors": capture_errors,
        "mapping_profile_supplied": mapping_profile_bytes is not None,
        "mapping_profile_file_sha256": (
            hashlib.sha256(mapping_profile_bytes).hexdigest()
            if mapping_profile_bytes is not None
            else None
        ),
        "mapping_evaluations": {
            endpoint_id: {
                "status": value["report"]["status"],
                "evaluation_sha256": value["report"][
                    "evaluation_sha256"
                ],
                "mapping_profile_id": value["report"][
                    "mapping_profile_id"
                ],
                "mapping_profile_sha256": value["report"][
                    "mapping_profile_sha256"
                ],
                "compatibility_probe_receipt_sha256": value[
                    "report"
                ]["compatibility_probe_receipt_sha256"],
            }
            for endpoint_id, value in sorted(evaluations.items())
        },
        "network_requests": manifest["network_requests"],
        "actuator_writes": 0,
    }
    workspace = {
        **payload,
        "workspace_sha256": _sha256_json(payload),
    }
    return workspace, captures, evaluations
