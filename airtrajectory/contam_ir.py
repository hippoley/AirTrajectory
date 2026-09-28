"""CONTAM-oriented intermediate representation.

This compiler consumes the backend-neutral spatial plan and produces stable
CONTAM semantics without writing a .prj file or inventing numeric CONTAM IDs.

Boundary:
- metric geometry must be complete;
- symbolic zone/path/control IDs are stable across opening moves;
- exterior openings terminate at the declared ambient node;
- internal openings connect two modeled zones;
- numeric CONTAM IDs and PRJ serialization remain a later writer concern.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .layout import LayoutContract
from .spatial_compile import compile_spatial_plan


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def compile_contam_ir(
    layout: LayoutContract,
    *,
    opening_positions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compile a metric-ready layout into CONTAM-oriented symbolic IR."""

    spatial = compile_spatial_plan(
        layout,
        opening_positions=opening_positions,
    )
    requirement = spatial["backend_requirements"]["contam"]
    if not requirement["metric_inputs_ready"]:
        raise ValueError(
            "layout is not CONTAM metric-input ready: "
            + json.dumps(
                {
                    "walls": requirement["missing_metric_wall_fields"],
                    "openings": requirement["missing_metric_opening_fields"],
                },
                sort_keys=True,
            )
        )

    zone_ids = {room.id for room in layout.rooms}
    wall_map = {wall.id: wall for wall in layout.walls}

    zones = [
        {
            "key": f"zone:{room.id}",
            "layout_zone_id": room.id,
            "name": room.name,
            "volume_m3": room.volume_m3,
            "contam_zone_number": None,
        }
        for room in layout.rooms
    ]

    ambient_boundaries = [
        {
            "key": f"ambient:{layout.outside_id}",
            "layout_node_id": layout.outside_id,
            "kind": "ambient",
            "contam_zone_number": None,
        }
    ]

    flow_paths = []
    controls = []
    for opening in spatial["openings"]:
        wall = wall_map[opening["wall_id"]]
        source = opening["source"]
        target = opening["target"]
        exterior = layout.outside_id in (source, target)
        if exterior:
            indoor = target if source == layout.outside_id else source
            if indoor not in zone_ids:
                raise ValueError(
                    f"opening {opening['id']} has invalid exterior endpoint"
                )
            from_key = f"zone:{indoor}"
            to_key = f"ambient:{layout.outside_id}"
        else:
            if source not in zone_ids or target not in zone_ids:
                raise ValueError(
                    f"opening {opening['id']} has invalid internal endpoints"
                )
            from_key = f"zone:{source}"
            to_key = f"zone:{target}"

        metric = opening["metric"]
        flow_paths.append(
            {
                "key": opening["path_key"],
                "layout_opening_id": opening["id"],
                "kind": opening["kind"],
                "boundary_kind": "exterior" if exterior else "internal",
                "from": from_key,
                "to": to_key,
                "wall_key": f"wall:{opening['wall_id']}",
                "position_t": opening["position_t"],
                "distance_along_wall_m": metric["distance_along_wall_m"],
                "wall_length_m": metric["wall_length_m"],
                "wall_azimuth_deg": metric["wall_azimuth_deg"],
                "width_m": metric["width_m"],
                "height_m": metric["height_m"],
                "sill_height_m": metric["sill_height_m"],
                "max_area_m2": opening["max_area_m2"],
                "contam_path_number": None,
                "airflow_element": {
                    "kind": "opening-placeholder",
                    "contam_element_number": None,
                    "note": (
                        "airflow element selection/calibration is a PRJ-writer "
                        "or engineering-profile concern"
                    ),
                },
            }
        )

        if opening["controllable"]:
            controls.append(
                {
                    "key": opening["control_key"],
                    "layout_opening_id": opening["id"],
                    "path_key": opening["path_key"],
                    "input_domain": {
                        "kind": "opening_pct",
                        "min": 0.0,
                        "max": 100.0,
                    },
                    "output_domain": {
                        "kind": "normalized_control",
                        "closed": 0.0,
                        "open": 1.0,
                    },
                    "contam_control_number": None,
                }
            )

    walls = [
        {
            "key": f"wall:{wall.id}",
            "layout_wall_id": wall.id,
            "kind": wall.kind,
            "source": wall.source,
            "target": wall.target,
            "length_m": wall.length_m,
            "azimuth_deg": wall.azimuth_deg,
        }
        for wall in layout.walls
    ]

    semantic_payload = {
        "zones": zones,
        "ambient_boundaries": ambient_boundaries,
        "walls": walls,
        "flow_paths": flow_paths,
        "controls": controls,
    }

    return {
        "schema_version": "0.1",
        "compiler": "contam-ir",
        "status": "READY_FOR_PRJ_WRITER",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "spatial_connectivity_sha256": spatial["connectivity_sha256"],
        "contam_semantics_sha256": _sha256(semantic_payload),
        "outside_id": layout.outside_id,
        **semantic_payload,
        "writer_contract": {
            "numeric_id_assignment": "reserved",
            "airflow_element_binding": "reserved",
            "prj_serialization": "reserved",
            "weather/wind_profile": "reserved",
            "contaminant_definition": "reserved",
            "ready": False,
        },
    }
