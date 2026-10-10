"""Strict node-ID projection of verified CONTAM prediction series onto Pascal SceneNodes.

Projection is a renderer-neutral view model, not evidence of a native Pascal 3D render.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .layout import LayoutContract


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def project_contam_to_pascal(
    layout: LayoutContract, runtime_receipt: dict[str, Any]
) -> dict[str, Any]:
    if runtime_receipt.get("status") != "ENGINEERING_RUNTIME_VERIFIED":
        raise ValueError("requires ENGINEERING_RUNTIME_VERIFIED receipt")
    if runtime_receipt.get("runtime_verified") is not True:
        raise ValueError("requires runtime_verified=true")
    if runtime_receipt.get("layout_contract_sha256") != layout.sha256():
        raise ValueError("runtime/layout hash mismatch")
    series = runtime_receipt.get("prediction_series")
    if not isinstance(series, list) or not series:
        raise ValueError("missing prediction_series")
    if runtime_receipt.get("prediction_series_sha256") != _hash(series):
        raise ValueError("prediction series integrity mismatch")
    room_ids = {room.id for room in layout.rooms}
    opening_ids = {opening.id for opening in layout.openings}
    frames = []
    for frame in series:
        zones = frame.get("co2_ppm")
        positions = frame.get("opening_pct")
        paths = frame.get("path_flow_kg_s")
        if not all(isinstance(x, dict) for x in (zones, positions, paths)):
            raise ValueError("incomplete runtime frame")
        if set(zones) != room_ids or set(positions) != opening_ids or set(paths) != opening_ids:
            raise ValueError("runtime frame node ID coverage mismatch")
        for mapping in (zones, positions, paths):
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in mapping.values()):
                raise ValueError("non-finite runtime value")
        if any(v < 0 or v > 100 for v in positions.values()):
            raise ValueError("invalid opening percentage")
        frames.append({
            "step": frame["step"],
            "simulation_time_s": frame["simulation_time_s"],
            "rooms": {k: {"native_node_id": k, "co2_ppm": zones[k]} for k in sorted(room_ids)},
            "openings": {k: {"native_node_id": k, "opening_pct": positions[k], "path_flow_kg_s": paths[k]}
                         for k in sorted(opening_ids)},
        })
    payload = {"schema_version": "0.1", "type": "pascal-native-contam-projection",
               "topology_id": layout.topology_id, "layout_contract_sha256": layout.sha256(),
               "runtime_receipt_sha256": runtime_receipt["runtime_receipt_sha256"],
               "source_prediction_series_sha256": runtime_receipt["prediction_series_sha256"],
               "rendered_in_pascal": False, "frames": frames}
    return {**payload, "projection_sha256": _hash(payload)}
