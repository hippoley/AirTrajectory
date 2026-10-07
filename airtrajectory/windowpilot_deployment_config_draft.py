"""Build a sanitized WindowPilot deployment config draft from first-contact evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .windowpilot_contract_mapping import (
    validate_windowpilot_contract_mapping,
)


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_workspace(workspace: Mapping[str, Any]) -> None:
    if not isinstance(workspace, Mapping):
        raise ValueError("first-contact workspace must be an object")
    provided = str(workspace.get("workspace_sha256") or "")
    payload = dict(workspace)
    payload.pop("workspace_sha256", None)
    if provided != _sha256(payload):
        raise ValueError("first-contact workspace SHA-256 integrity check failed")


def _sanitized_endpoint(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise ValueError("WindowPilot endpoint spec must be an object")
    base_url = str(spec.get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("WindowPilot endpoint base_url is required")
    result = {
        "base_url": base_url,
        "timeout_s": float(spec.get("timeout_s", 2.0)),
        "feedback_timeout_s": float(
            spec.get("feedback_timeout_s", 5.0)
        ),
        "position_tolerance_pct": float(
            spec.get("position_tolerance_pct", 1.0)
        ),
    }
    headers_env = spec.get("headers_env") or {}
    if not isinstance(headers_env, Mapping):
        raise ValueError("endpoint headers_env must be an object")
    if headers_env:
        result["headers_env"] = {
            str(header): str(env_name)
            for header, env_name in sorted(headers_env.items())
        }
    return result


def build_windowpilot_deployment_config_draft(
    *,
    source_config: Mapping[str, Any],
    workspace: Mapping[str, Any],
    mapping_profile: Mapping[str, Any] | None = None,
    mapping_profile_name: str = "first-contact",
) -> tuple[dict[str, Any], dict[str, Any]]:
    _verify_workspace(workspace)
    endpoints = source_config.get("windowpilot_endpoints")
    if not isinstance(endpoints, Mapping) or not endpoints:
        raise ValueError("source config windowpilot_endpoints are required")

    captured_ids = set(workspace.get("endpoint_ids") or [])
    if not captured_ids:
        raise ValueError("workspace contains no captured endpoints")
    unknown = captured_ids - set(str(key) for key in endpoints)
    if unknown:
        raise ValueError(
            "workspace references endpoints absent from source config: "
            + ",".join(sorted(unknown))
        )

    evaluations = workspace.get("mapping_evaluations") or {}
    if not isinstance(evaluations, Mapping):
        raise ValueError("workspace mapping_evaluations must be an object")

    normalized_profile = None
    profile_name = str(mapping_profile_name or "").strip()
    if mapping_profile is not None:
        if not profile_name:
            raise ValueError("mapping_profile_name is required")
        normalized_profile = validate_windowpilot_contract_mapping(
            mapping_profile
        )
        workspace_profile_hashes = {
            str(row.get("mapping_profile_sha256") or "")
            for endpoint_id, row in evaluations.items()
            if endpoint_id in captured_ids
            and isinstance(row, Mapping)
            and row.get("mapping_profile_sha256")
        }
        if workspace_profile_hashes and workspace_profile_hashes != {
            normalized_profile["profile_sha256"]
        }:
            raise ValueError(
                "mapping profile SHA-256 does not match workspace evaluation"
            )

    blockers = []
    endpoint_drafts = {}
    endpoint_readiness = {}
    for endpoint_id in sorted(captured_ids):
        spec = endpoints[endpoint_id]
        draft = _sanitized_endpoint(spec)
        evaluation = evaluations.get(endpoint_id)
        eval_status = (
            str(evaluation.get("status") or "")
            if isinstance(evaluation, Mapping)
            else ""
        )

        existing_profile_name = spec.get("contract_mapping_profile")
        if normalized_profile is not None:
            draft["contract_mapping_profile"] = profile_name
        elif existing_profile_name is not None:
            draft["contract_mapping_profile"] = str(
                existing_profile_name
            )

        if eval_status == "COMPATIBLE":
            readiness = "COMPATIBLE"
        elif eval_status:
            readiness = eval_status
            blockers.append(
                f"endpoint {endpoint_id} mapping status is {eval_status}"
            )
        else:
            readiness = "COMPATIBILITY_NOT_EVALUATED"
            blockers.append(
                f"endpoint {endpoint_id} compatibility was not evaluated"
            )

        endpoint_drafts[endpoint_id] = draft
        endpoint_readiness[endpoint_id] = readiness

    capture_errors = workspace.get("capture_errors") or []
    if capture_errors:
        failed = sorted(
            str(row.get("endpoint_id") or "")
            for row in capture_errors
            if isinstance(row, Mapping)
        )
        blockers.append(
            "first-contact capture incomplete for endpoints: "
            + ",".join(item for item in failed if item)
        )

    draft_config: dict[str, Any] = {
        "schema_version": "0.1",
        "windowpilot_endpoints": endpoint_drafts,
        "fixed_openings": dict(
            source_config.get("fixed_openings") or {}
        ),
        "contract_mapping_profiles": {},
    }
    if source_config.get("topology_id") is not None:
        draft_config["topology_id"] = str(
            source_config["topology_id"]
        )

    if normalized_profile is not None:
        draft_config["contract_mapping_profiles"][
            profile_name
        ] = normalized_profile
    else:
        source_profiles = source_config.get(
            "contract_mapping_profiles"
        ) or {}
        referenced = {
            str(spec.get("contract_mapping_profile"))
            for spec in endpoint_drafts.values()
            if spec.get("contract_mapping_profile") is not None
        }
        for name in sorted(referenced):
            profile = source_profiles.get(name)
            if not isinstance(profile, Mapping):
                blockers.append(
                    f"referenced mapping profile {name} is unavailable"
                )
                continue
            draft_config["contract_mapping_profiles"][name] = (
                validate_windowpilot_contract_mapping(profile)
            )

    field_capture = source_config.get("field_capture")
    if isinstance(field_capture, Mapping):
        draft_config["field_capture"] = json.loads(
            json.dumps(field_capture)
        )
        source = field_capture.get("source")
        if not isinstance(source, Mapping):
            blockers.append("field_capture.source is missing")
        else:
            required_source = (
                "kind",
                "id",
                "model",
                "serial",
                "calibration_ref",
            )
            for key in required_source:
                value = str(source.get(key) or "")
                if not value or value.startswith("replace-with-"):
                    blockers.append(
                        f"field_capture.source.{key} requires real deployment metadata"
                    )
        zone_sources = field_capture.get("co2_zone_sources")
        if not isinstance(zone_sources, Mapping) or not zone_sources:
            blockers.append(
                "field_capture.co2_zone_sources requires explicit room-to-endpoint mapping"
            )
        else:
            missing_targets = sorted(
                set(str(value) for value in zone_sources.values())
                - captured_ids
            )
            if missing_targets:
                blockers.append(
                    "field_capture.co2_zone_sources references uncaptured endpoints: "
                    + ",".join(missing_targets)
                )
    else:
        blockers.extend([
            "field_capture.source requires real deployment metadata",
            "field_capture.co2_zone_sources requires explicit room-to-endpoint mapping",
        ])

    blockers = sorted(set(blockers))
    status = (
        "READY_FOR_LIVE_PROBE"
        if not blockers
        else "DRAFT_WITH_BLOCKERS"
    )
    receipt_payload = {
        "schema_version": "0.1",
        "draft": "windowpilot-deployment-config-draft-v1",
        "status": status,
        "workspace_sha256": workspace["workspace_sha256"],
        "endpoint_ids": sorted(captured_ids),
        "endpoint_readiness": endpoint_readiness,
        "mapping_profile_name": (
            profile_name if normalized_profile is not None else None
        ),
        "mapping_profile_sha256": (
            normalized_profile["profile_sha256"]
            if normalized_profile is not None
            else None
        ),
        "blockers": blockers,
        "deployment_config_sha256": _sha256(draft_config),
        "secret_values_embedded": False,
    }
    receipt = {
        **receipt_payload,
        "draft_receipt_sha256": _sha256(receipt_payload),
    }
    return draft_config, receipt
