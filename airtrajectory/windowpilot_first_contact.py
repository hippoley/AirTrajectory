"""Read-only first-contact capture for WindowPilot HTTP payloads."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .demo_physical_config import resolve_windowpilot_headers


_ENDPOINTS = {
    "capabilities": "/api/capabilities",
    "physical_readiness": "/api/physical-readiness",
    "state": "/api/state",
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


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


def _default_fetch(
    *,
    url: str,
    headers: Mapping[str, str],
    timeout_s: float,
) -> tuple[int, Mapping[str, str], bytes]:
    request = Request(
        url,
        method="GET",
        headers=dict(headers),
    )
    with urlopen(request, timeout=float(timeout_s)) as response:
        status = int(getattr(response, "status", 200))
        response_headers = {
            str(key): str(value)
            for key, value in response.headers.items()
        }
        body = response.read()
    return status, response_headers, body


def capture_windowpilot_first_contact(
    *,
    config: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
    fetch_fn: Callable[..., tuple[int, Mapping[str, str], bytes]] = _default_fetch,
) -> tuple[dict[str, Any], dict[str, dict[str, bytes]]]:
    endpoints = config.get("windowpilot_endpoints")
    if not isinstance(endpoints, Mapping) or not endpoints:
        raise ValueError("windowpilot_endpoints are required")

    captures: dict[str, dict[str, bytes]] = {}
    endpoint_receipts = {}

    for endpoint_id, spec in sorted(endpoints.items()):
        endpoint_id = str(endpoint_id)
        if not _SAFE_ID.fullmatch(endpoint_id):
            raise ValueError(
                f"unsafe WindowPilot endpoint id for artifact path: {endpoint_id}"
            )
        if not isinstance(spec, Mapping):
            raise ValueError(f"endpoint {endpoint_id} must be an object")
        base_url = str(spec.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ValueError(f"endpoint {endpoint_id} missing base_url")
        timeout_s = float(spec.get("timeout_s", 2.0))
        if timeout_s <= 0:
            raise ValueError(f"endpoint {endpoint_id} timeout_s must be positive")

        headers = resolve_windowpilot_headers(
            spec,
            environ=environ,
        )
        response_files = {}
        response_receipts = {}

        for name, path in _ENDPOINTS.items():
            status, response_headers, body = fetch_fn(
                url=base_url + path,
                headers=headers,
                timeout_s=timeout_s,
            )
            if not isinstance(body, (bytes, bytearray)):
                raise ValueError(
                    f"first-contact fetch for {endpoint_id}:{name} returned non-bytes body"
                )
            body = bytes(body)
            try:
                decoded = json.loads(body.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"first-contact response {endpoint_id}:{name} is not valid JSON"
                ) from exc
            if not isinstance(decoded, dict):
                raise ValueError(
                    f"first-contact response {endpoint_id}:{name} must be a JSON object"
                )
            if int(status) < 200 or int(status) >= 300:
                raise ValueError(
                    f"first-contact response {endpoint_id}:{name} HTTP status {status}"
                )

            filename = f"{name}.json"
            response_files[filename] = body
            content_type = ""
            for key, value in response_headers.items():
                if str(key).lower() == "content-type":
                    content_type = str(value)
                    break
            response_receipts[name] = {
                "path": path,
                "filename": filename,
                "http_status": int(status),
                "content_type": content_type,
                "body_length": len(body),
                "body_sha256": _sha256_bytes(body),
            }

        captures[endpoint_id] = response_files
        endpoint_payload = {
            "endpoint_id": endpoint_id,
            "base_url_sha256": hashlib.sha256(
                base_url.encode("utf-8")
            ).hexdigest(),
            "request_header_names": sorted(headers),
            "request_count": len(_ENDPOINTS),
            "actuator_writes": 0,
            "responses": response_receipts,
        }
        endpoint_receipts[endpoint_id] = {
            **endpoint_payload,
            "endpoint_capture_sha256": _sha256_json(endpoint_payload),
        }

    payload = {
        "schema_version": "0.1",
        "capture": "windowpilot-first-contact-v1",
        "status": "CAPTURED",
        "endpoint_count": len(endpoint_receipts),
        "endpoint_ids": sorted(endpoint_receipts),
        "request_method": "GET",
        "allowed_paths": list(_ENDPOINTS.values()),
        "network_requests": len(endpoint_receipts) * len(_ENDPOINTS),
        "actuator_writes": 0,
        "endpoints": endpoint_receipts,
    }
    return (
        {
            **payload,
            "first_contact_capture_sha256": _sha256_json(payload),
        },
        captures,
    )
