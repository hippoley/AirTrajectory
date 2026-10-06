"""Explicit metric geometry overlay for physics compilation.

The base layout remains the single topology/source-of-truth. Metric engineering
inputs are overlaid by entity ID and hashed separately so UI geometry is never
silently treated as metres.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .layout import LayoutContract


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def apply_metric_geometry_overlay(
    layout: LayoutContract,
    overlay: dict[str, Any],
) -> tuple[LayoutContract, dict[str, Any]]:
    if overlay.get("schema_version") != "0.1":
        raise ValueError("unsupported metric overlay schema_version")
    if overlay.get("topology_id") != layout.topology_id:
        raise ValueError("metric overlay topology_id does not match layout")

    rooms = overlay.get("rooms")
    walls = overlay.get("walls")
    openings = overlay.get("openings")
    if not isinstance(walls, dict) or not isinstance(openings, dict):
        raise ValueError("metric overlay requires walls and openings objects")

    payload = layout.web_snapshot()
    room_ids = {item["id"] for item in payload["rooms"]}
    wall_ids = {item["id"] for item in payload["walls"]}
    opening_ids = {item["id"] for item in payload["openings"]}

    if rooms is not None and not isinstance(rooms, dict):
        raise ValueError("metric overlay rooms must be an object")
    unknown_rooms = set(rooms or {}) - room_ids
    missing_rooms = room_ids - set(rooms or {}) if rooms is not None else set()
    unknown_walls = set(walls) - wall_ids
    unknown_openings = set(openings) - opening_ids
    missing_walls = wall_ids - set(walls)
    missing_openings = opening_ids - set(openings)
    if unknown_rooms or missing_rooms or unknown_walls or unknown_openings or missing_walls or missing_openings:
        parts = []
        if unknown_rooms:
            parts.append("unknown rooms=" + ",".join(sorted(unknown_rooms)))
        if missing_rooms:
            parts.append("missing rooms=" + ",".join(sorted(missing_rooms)))
        if unknown_walls:
            parts.append("unknown walls=" + ",".join(sorted(unknown_walls)))
        if missing_walls:
            parts.append("missing walls=" + ",".join(sorted(missing_walls)))
        if unknown_openings:
            parts.append("unknown openings=" + ",".join(sorted(unknown_openings)))
        if missing_openings:
            parts.append("missing openings=" + ",".join(sorted(missing_openings)))
        raise ValueError("incomplete metric geometry overlay: " + "; ".join(parts))

    if rooms is not None:
        for item in payload["rooms"]:
            item["volume_m3"] = float(rooms[item["id"]]["volume_m3"])

    for item in payload["walls"]:
        cfg = walls[item["id"]]
        item["length_m"] = float(cfg["length_m"])
        item["azimuth_deg"] = float(cfg["azimuth_deg"])

    for item in payload["openings"]:
        cfg = openings[item["id"]]
        item["width_m"] = float(cfg["width_m"])
        item["height_m"] = float(cfg["height_m"])
        item["sill_height_m"] = float(cfg["sill_height_m"])
        if "max_area_m2" in cfg:
            item["max_area_m2"] = float(cfg["max_area_m2"])

    resolved = LayoutContract.from_dict(payload)
    meta = {
        "metric_geometry_profile_id": str(overlay.get("profile_id") or ""),
        "metric_geometry_profile_sha256": _sha256(overlay),
        "engineering_validated": overlay.get("engineering_validated") is True,
        "evidence_level": overlay.get("evidence_level"),
        "evidence_receipts": list(overlay.get("evidence_receipts") or []),
    }
    return resolved, meta
