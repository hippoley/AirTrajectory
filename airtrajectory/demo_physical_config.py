"""Configuration loader for mapping demo openings to WindowPilot runtimes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .drivers.windowpilot import WindowPilotHTTPDriver


def load_windowpilot_driver_config(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "0.1":
        raise ValueError("unsupported physical demo config schema_version")
    endpoints = payload.get("windowpilot_endpoints")
    if not isinstance(endpoints, dict) or not endpoints:
        raise ValueError("windowpilot_endpoints are required")
    fixed = payload.get("fixed_openings") or {}
    if not isinstance(fixed, dict):
        raise ValueError("fixed_openings must be an object")
    overlap = set(endpoints) & set(fixed)
    if overlap:
        raise ValueError(
            "opening cannot be both endpoint-driven and fixed: "
            + ",".join(sorted(overlap))
        )
    return payload


def build_windowpilot_drivers(
    config: dict[str, Any],
    *,
    request_json_factory=None,
) -> dict[str, WindowPilotHTTPDriver]:
    drivers = {}
    for opening_id, spec in config["windowpilot_endpoints"].items():
        if not isinstance(spec, dict):
            raise ValueError(f"endpoint {opening_id} must be an object")
        base_url = str(spec.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ValueError(f"endpoint {opening_id} missing base_url")
        kwargs = {
            "base_url": base_url,
            "timeout_s": float(spec.get("timeout_s", 2.0)),
            "feedback_timeout_s": float(spec.get("feedback_timeout_s", 5.0)),
            "position_tolerance_pct": float(
                spec.get("position_tolerance_pct", 1.0)
            ),
        }
        if request_json_factory is not None:
            kwargs["request_json"] = request_json_factory(opening_id, spec)
        drivers[opening_id] = WindowPilotHTTPDriver(**kwargs)
    return drivers
