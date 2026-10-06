"""Offline evaluation for WindowPilot raw payload + mapping profiles."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .windowpilot_contract_mapping import (
    apply_windowpilot_contract_mapping,
    validate_windowpilot_contract_mapping,
)
from .windowpilot_contract_probe import probe_windowpilot_http_contract


_ENDPOINTS = {
    "capabilities": "/api/capabilities",
    "physical_readiness": "/api/physical-readiness",
    "state": "/api/state",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def evaluate_windowpilot_mapping_fixture(
    *,
    profile: Mapping[str, Any],
    raw_payloads: Mapping[str, Any],
    raw_sha256: Mapping[str, str] | None = None,
    fixture_id: str = "offline-windowpilot-fixture",
    clock_fn=lambda: 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = validate_windowpilot_contract_mapping(profile)
    expected_keys = set(_ENDPOINTS)
    if set(raw_payloads) != expected_keys:
        raise ValueError(
            "raw_payloads must contain exactly: "
            + ",".join(sorted(expected_keys))
        )

    canonical: dict[str, Any] = {}
    mapping_errors = []
    endpoint_receipts = {}

    for name, endpoint in _ENDPOINTS.items():
        raw = raw_payloads[name]
        raw_hash = (
            str((raw_sha256 or {}).get(name) or "")
            if raw_sha256 is not None
            else _sha256_json(raw)
        )
        if len(raw_hash) != 64:
            raise ValueError(
                f"raw payload SHA-256 is invalid for {name}"
            )
        try:
            mapped = apply_windowpilot_contract_mapping(
                profile=normalized,
                endpoint=endpoint,
                payload=raw,
            )
        except Exception as exc:
            mapping_errors.append({
                "endpoint": endpoint,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            endpoint_receipts[name] = {
                "endpoint": endpoint,
                "raw_sha256": raw_hash,
                "canonical_sha256": None,
                "status": "MAPPING_ERROR",
            }
            continue

        canonical[name] = mapped
        endpoint_receipts[name] = {
            "endpoint": endpoint,
            "raw_sha256": raw_hash,
            "canonical_sha256": _sha256_json(mapped),
            "status": "MAPPED",
        }

    compatibility = None
    if not mapping_errors:
        def request_json(method: str, path: str, body: Any):
            if method != "GET":
                raise RuntimeError("offline fixture permits GET only")
            for key, endpoint in _ENDPOINTS.items():
                if endpoint == path:
                    return canonical[key]
            raise RuntimeError(f"unexpected offline endpoint: {path}")

        compatibility = probe_windowpilot_http_contract(
            base_url=f"offline://{fixture_id}",
            request_json=request_json,
            clock_fn=clock_fn,
        )
        status = compatibility["status"]
    else:
        status = "MAPPING_ERROR"

    payload = {
        "schema_version": "0.1",
        "evaluation": "windowpilot-offline-mapping-fixture-v1",
        "fixture_id": str(fixture_id),
        "status": status,
        "mapping_profile_id": normalized["profile_id"],
        "mapping_profile_sha256": normalized["profile_sha256"],
        "endpoint_receipts": endpoint_receipts,
        "mapping_errors": mapping_errors,
        "compatibility_probe_receipt_sha256": (
            compatibility["probe_receipt_sha256"]
            if compatibility is not None
            else None
        ),
        "actuator_writes": 0,
        "network_requests": 0,
    }
    return (
        {
            **payload,
            "evaluation_sha256": _sha256_json(payload),
            "compatibility": compatibility,
        },
        canonical,
    )


def load_json_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON") from exc


def evaluate_windowpilot_mapping_files(
    *,
    profile_bytes: bytes,
    capabilities_bytes: bytes,
    physical_readiness_bytes: bytes,
    state_bytes: bytes,
    fixture_id: str = "offline-windowpilot-fixture",
    clock_fn=lambda: 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = load_json_bytes(profile_bytes, label="mapping profile")
    raw_bytes = {
        "capabilities": capabilities_bytes,
        "physical_readiness": physical_readiness_bytes,
        "state": state_bytes,
    }
    raw_payloads = {
        name: load_json_bytes(data, label=name)
        for name, data in raw_bytes.items()
    }
    raw_sha256 = {
        name: _sha256_bytes(data)
        for name, data in raw_bytes.items()
    }
    return evaluate_windowpilot_mapping_fixture(
        profile=profile,
        raw_payloads=raw_payloads,
        raw_sha256=raw_sha256,
        fixture_id=fixture_id,
        clock_fn=clock_fn,
    )
