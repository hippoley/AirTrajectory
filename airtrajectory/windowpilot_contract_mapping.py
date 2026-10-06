"""Declarative response mapping for non-canonical WindowPilot payloads."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable, Mapping


_ALLOWED_ENDPOINTS = {
    "/api/capabilities",
    "/api/physical-readiness",
    "/api/state",
}


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _get_path(payload: Any, path: str) -> Any:
    current = payload
    for part in str(path).split("."):
        if not part:
            raise ValueError("mapping source path contains empty segment")
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = str(path).split(".")
    if not parts or any(not part for part in parts):
        raise ValueError("mapping target path is invalid")
    current = payload
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise ValueError(
                f"mapping target path collides with scalar at {part}"
            )
        current = child
    current[parts[-1]] = value


def _coerce(value: Any, kind: str | None) -> Any:
    if kind in (None, "identity"):
        return deepcopy(value)
    if kind == "string":
        return str(value)
    if kind == "float":
        return float(value)
    if kind == "int":
        return int(value)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"cannot coerce {value!r} to bool")
    raise ValueError(f"unsupported mapping coercion: {kind}")


def validate_windowpilot_contract_mapping(
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(profile, Mapping):
        raise ValueError("contract mapping profile must be an object")
    if profile.get("schema_version") != "0.1":
        raise ValueError("unsupported contract mapping schema_version")
    profile_id = str(profile.get("profile_id") or "")
    if not profile_id:
        raise ValueError("contract mapping profile_id is required")
    endpoint_specs = profile.get("endpoints")
    if not isinstance(endpoint_specs, Mapping) or not endpoint_specs:
        raise ValueError("contract mapping endpoints are required")

    normalized_endpoints = {}
    for endpoint, mappings in sorted(endpoint_specs.items()):
        endpoint = str(endpoint)
        if endpoint not in _ALLOWED_ENDPOINTS:
            raise ValueError(
                f"unsupported contract mapping endpoint: {endpoint}"
            )
        if not isinstance(mappings, Mapping) or not mappings:
            raise ValueError(
                f"contract mapping {endpoint} must contain target mappings"
            )
        normalized = {}
        for target, spec in sorted(mappings.items()):
            target = str(target)
            if not target:
                raise ValueError("contract mapping target is required")
            if isinstance(spec, str):
                source_path = spec
                coerce = "identity"
                required = True
                default_present = False
                default = None
            elif isinstance(spec, Mapping):
                source_path = str(spec.get("path") or "")
                coerce = str(spec.get("coerce") or "identity")
                required = bool(spec.get("required", True))
                default_present = "default" in spec
                default = spec.get("default")
            else:
                raise ValueError(
                    f"mapping for {endpoint}:{target} must be string/object"
                )
            if not source_path:
                raise ValueError(
                    f"mapping for {endpoint}:{target} requires source path"
                )
            if coerce not in {
                "identity",
                "string",
                "float",
                "int",
                "bool",
            }:
                raise ValueError(
                    f"unsupported mapping coercion: {coerce}"
                )
            if required and default_present:
                raise ValueError(
                    f"required mapping {endpoint}:{target} cannot define default"
                )
            normalized[target] = {
                "path": source_path,
                "coerce": coerce,
                "required": required,
                "default_present": default_present,
                "default": default,
            }
        normalized_endpoints[endpoint] = normalized

    payload = {
        "schema_version": "0.1",
        "profile_id": profile_id,
        "endpoints": normalized_endpoints,
    }
    return {
        **payload,
        "profile_sha256": _sha256(payload),
    }


def apply_windowpilot_contract_mapping(
    *,
    profile: Mapping[str, Any],
    endpoint: str,
    payload: Any,
) -> dict[str, Any]:
    normalized = validate_windowpilot_contract_mapping(profile)
    endpoint = str(endpoint)
    mappings = normalized["endpoints"].get(endpoint)
    if mappings is None:
        raise ValueError(
            f"contract mapping profile has no mapping for {endpoint}"
        )
    if not isinstance(payload, dict):
        raise ValueError("raw WindowPilot payload must be a JSON object")

    output: dict[str, Any] = {}
    missing = []
    for target, spec in mappings.items():
        try:
            value = _get_path(payload, spec["path"])
        except KeyError:
            if spec["default_present"]:
                value = spec["default"]
            elif spec["required"]:
                missing.append({
                    "target": target,
                    "source_path": spec["path"],
                })
                continue
            else:
                continue
        _set_path(
            output,
            target,
            _coerce(value, spec["coerce"]),
        )

    if missing:
        details = ",".join(
            f"{row['target']}<-{row['source_path']}"
            for row in missing
        )
        raise ValueError(
            f"contract mapping missing required source fields: {details}"
        )
    return output


def build_windowpilot_response_adapter(
    profile: Mapping[str, Any],
) -> Callable[[str, Any], dict[str, Any]]:
    normalized = validate_windowpilot_contract_mapping(profile)

    def adapter(endpoint: str, payload: Any) -> dict[str, Any]:
        return apply_windowpilot_contract_mapping(
            profile=normalized,
            endpoint=endpoint,
            payload=payload,
        )

    adapter.profile_id = normalized["profile_id"]  # type: ignore[attr-defined]
    adapter.profile_sha256 = normalized["profile_sha256"]  # type: ignore[attr-defined]
    return adapter
