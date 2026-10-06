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
    capture_kwargs = {
        "config": config,
        "environ": environ,
    }
    if fetch_fn is not None:
        capture_kwargs["fetch_fn"] = fetch_fn

    manifest, captures = capture_windowpilot_first_contact(
        **capture_kwargs
    )

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

    if not evaluations:
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
