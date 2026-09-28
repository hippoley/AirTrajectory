"""Spatial compile plan between LayoutContract and physics backends.

This module deliberately stops short of generating a CONTAM PRJ. The current
fixed layout stores browser/canvas coordinates, not metric building geometry.
The compile plan therefore preserves normalized opening placement and a
deterministic anchor in the source coordinate space while making the missing
metric fields explicit.

Future arbitrary-floorplan importers should emit the same placement semantics
with a metric coordinate space; the CONTAM PRJ compiler can then consume this
plan without changing UI or trajectory contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from .layout import LayoutContract, LayoutOpening, LayoutWall


_REQUIRED_METRIC_OPENING_FIELDS = (
    "width_m",
    "height_m",
    "sill_height_m",
)
_REQUIRED_METRIC_WALL_FIELDS = (
    "azimuth_deg",
)


@dataclass(frozen=True)
class OpeningPlacement:
    id: str
    kind: str
    wall_id: str
    source: str
    target: str
    position_t: float
    anchor_x: float
    anchor_y: float
    wall_dx: float
    wall_dy: float
    wall_length_source_units: float
    max_area_m2: float
    controllable: bool
    wall_length_m: float|None
    wall_azimuth_deg: float|None
    width_m: float|None
    height_m: float|None
    sill_height_m: float|None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "wall_id": self.wall_id,
            "source": self.source,
            "target": self.target,
            "position_t": self.position_t,
            "anchor": {
                "x": self.anchor_x,
                "y": self.anchor_y,
            },
            "wall_vector": {
                "dx": self.wall_dx,
                "dy": self.wall_dy,
                "length_source_units": self.wall_length_source_units,
            },
            "max_area_m2": self.max_area_m2,
            "controllable": self.controllable,
            "metric": {
                "wall_length_m": self.wall_length_m,
                "wall_azimuth_deg": self.wall_azimuth_deg,
                "distance_along_wall_m": (
                    None if self.wall_length_m is None
                    else self.wall_length_m * self.position_t
                ),
                "width_m": self.width_m,
                "height_m": self.height_m,
                "sill_height_m": self.sill_height_m,
            },
            "path_key": f"path:{self.id}",
            "control_key": f"control:{self.id}" if self.controllable else None,
        }


def _resolve_positions(
    layout: LayoutContract,
    overrides: dict[str, float] | None,
) -> dict[str, float]:
    positions = {opening.id: opening.position_t for opening in layout.openings}
    if not overrides:
        return positions

    unknown = set(overrides) - set(positions)
    if unknown:
        raise ValueError(
            "unknown opening positions: " + ",".join(sorted(unknown))
        )

    for opening_id, raw in overrides.items():
        value = float(raw)
        if not 0 <= value <= 1:
            raise ValueError(
                f"opening {opening_id} position must be between 0 and 1"
            )
        positions[opening_id] = value
    return positions


def _placement(
    opening: LayoutOpening,
    wall: LayoutWall,
    position_t: float,
) -> OpeningPlacement:
    dx = wall.x2 - wall.x1
    dy = wall.y2 - wall.y1
    return OpeningPlacement(
        id=opening.id,
        kind=opening.kind,
        wall_id=opening.wall_id,
        source=opening.source,
        target=opening.target,
        position_t=position_t,
        anchor_x=wall.x1 + dx * position_t,
        anchor_y=wall.y1 + dy * position_t,
        wall_dx=dx,
        wall_dy=dy,
        wall_length_source_units=math.hypot(dx, dy),
        max_area_m2=opening.max_area_m2,
        controllable=opening.state_editable,
        wall_length_m=wall.length_m,
        wall_azimuth_deg=wall.azimuth_deg,
        width_m=opening.width_m,
        height_m=opening.height_m,
        sill_height_m=opening.sill_height_m,
    )


def compile_spatial_plan(
    layout: LayoutContract,
    *,
    opening_positions: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compile layout placement into a backend-neutral deterministic plan.

    The current fixed-floorplan source uses browser/canvas coordinates. This
    function never labels those coordinates as metres and never claims that the
    returned plan is sufficient to generate an engineering-valid CONTAM PRJ.
    """

    positions = _resolve_positions(layout, opening_positions)
    wall_map = {wall.id: wall for wall in layout.walls}
    placements = [
        _placement(opening, wall_map[opening.wall_id], positions[opening.id])
        for opening in layout.openings
    ]

    connectivity = [
        {
            "opening_id": opening.id,
            "source": opening.source,
            "target": opening.target,
            "wall_id": opening.wall_id,
            "path_key": f"path:{opening.id}",
            "control_key": (
                f"control:{opening.id}" if opening.state_editable else None
            ),
        }
        for opening in layout.openings
    ]

    connectivity_sha256 = hashlib.sha256(
        json.dumps(
            connectivity,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    coordinate_space = (
        "layout-canvas"
        if layout.source_kind == "fixed-floorplan"
        else "source-defined"
    )

    missing_wall_fields = {
        wall.id: [
            field
            for field in _REQUIRED_METRIC_WALL_FIELDS
            if getattr(wall, field) is None
        ]
        for wall in layout.walls
    }
    missing_wall_fields = {
        wall_id: fields
        for wall_id, fields in missing_wall_fields.items()
        if fields
    }
    missing_opening_fields = {
        opening.id: [
            field
            for field in _REQUIRED_METRIC_OPENING_FIELDS
            if getattr(opening, field) is None
        ]
        for opening in layout.openings
    }
    missing_opening_fields = {
        opening_id: fields
        for opening_id, fields in missing_opening_fields.items()
        if fields
    }
    metric_geometry_ready = not missing_wall_fields and not missing_opening_fields

    return {
        "schema_version": "0.1",
        "compiler": "spatial-plan",
        "status": "READY_FOR_BACKEND_COMPILER",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "coordinate_space": coordinate_space,
        "metric_geometry_ready": metric_geometry_ready,
        "connectivity_sha256": connectivity_sha256,
        "zones": [
            {
                "id": room.id,
                "volume_m3": room.volume_m3,
                "zone_key": f"zone:{room.id}",
            }
            for room in layout.rooms
        ],
        "openings": [placement.as_dict() for placement in placements],
        "backend_requirements": {
            "contam": {
                "metric_inputs_ready": metric_geometry_ready,
                "missing_metric_opening_fields": missing_opening_fields,
                "missing_metric_wall_fields": missing_wall_fields,
                "prj_generation_implemented": False,
                "prj_generation_ready": False,
                "reason": (
                    "metric geometry is complete; CONTAM PRJ generation is the next gate"
                    if metric_geometry_ready
                    else "normalized placement is valid, but metric wall/opening geometry is incomplete"
                ),
            }
        },
    }
