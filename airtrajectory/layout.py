"""Layout/topology contract used by UI today and future physics compilers.

The current release intentionally keeps room/wall geometry fixed while allowing
windows and doors to slide along their declared wall and change opening state.

The important boundary is the contract itself:
- today's source_kind is fixed-floorplan;
- future arbitrary floorplan importers can emit the same schema;
- future CONTAM compilation should consume this contract, not web-only state.

This module does not implement an arbitrary floorplan editor or CONTAM compiler.
It validates the seam those components will use later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .topology import BuildingTopology, OpeningEdge, ZoneNode


_ALLOWED_OPENING_KINDS={"window","door","vent"}
_ALLOWED_WALL_KINDS={"exterior","internal"}


@dataclass(frozen=True)
class LayoutRoom:
    id: str
    name: str
    x: float
    y: float
    w: float
    h: float
    volume_m3: float


@dataclass(frozen=True)
class LayoutWall:
    id: str
    kind: str
    source: str
    target: str
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class LayoutOpening:
    id: str
    kind: str
    wall_id: str
    source: str
    target: str
    position_t: float
    initial_open_pct: float
    max_area_m2: float
    render_side: str
    position_editable: bool
    state_editable: bool


@dataclass(frozen=True)
class LayoutContract:
    schema_version: str
    topology_id: str
    source_kind: str
    outside_id: str
    capabilities: dict[str,Any]
    rooms: tuple[LayoutRoom,...]
    walls: tuple[LayoutWall,...]
    openings: tuple[LayoutOpening,...]
    compiler_contract: dict[str,Any]

    @classmethod
    def from_dict(cls,payload: dict[str,Any]) -> "LayoutContract":
        if not isinstance(payload,dict):
            raise ValueError("layout contract must be an object")

        rooms=tuple(
            LayoutRoom(
                id=str(item["id"]),
                name=str(item.get("name") or item["id"]),
                x=float(item["x"]),
                y=float(item["y"]),
                w=float(item["w"]),
                h=float(item["h"]),
                volume_m3=float(item["volume_m3"]),
            )
            for item in payload.get("rooms") or []
        )
        walls=tuple(
            LayoutWall(
                id=str(item["id"]),
                kind=str(item["kind"]),
                source=str(item["source"]),
                target=str(item["target"]),
                x1=float(item["x1"]),
                y1=float(item["y1"]),
                x2=float(item["x2"]),
                y2=float(item["y2"]),
            )
            for item in payload.get("walls") or []
        )
        openings=tuple(
            LayoutOpening(
                id=str(item["id"]),
                kind=str(item["kind"]),
                wall_id=str(item["wall_id"]),
                source=str(item["source"]),
                target=str(item["target"]),
                position_t=float(item["position_t"]),
                initial_open_pct=float(item["initial_open_pct"]),
                max_area_m2=float(item["max_area_m2"]),
                render_side=str(item.get("render_side") or ""),
                position_editable=item.get("position_editable") is True,
                state_editable=item.get("state_editable") is True,
            )
            for item in payload.get("openings") or []
        )
        contract=cls(
            schema_version=str(payload.get("schema_version") or ""),
            topology_id=str(payload.get("topology_id") or ""),
            source_kind=str(payload.get("source_kind") or ""),
            outside_id=str(payload.get("outside_id") or "OUTSIDE"),
            capabilities=dict(payload.get("capabilities") or {}),
            rooms=rooms,
            walls=walls,
            openings=openings,
            compiler_contract=dict(payload.get("compiler_contract") or {}),
        )
        contract.validate()
        return contract

    def validate(self) -> None:
        if self.schema_version!="0.1":
            raise ValueError("unsupported layout schema_version")
        if not self.topology_id:
            raise ValueError("layout topology_id is required")
        if self.source_kind!="fixed-floorplan":
            raise ValueError(
                "current runtime accepts source_kind=fixed-floorplan only; "
                "future topology sources are reserved"
            )

        if self.capabilities.get("floorplan_geometry_editable") is not False:
            raise ValueError(
                "current layout contract must keep floorplan geometry fixed"
            )
        if self.capabilities.get("opening_position_editable") is not True:
            raise ValueError(
                "current layout contract must allow opening position edits"
            )
        if self.capabilities.get("arbitrary_topology_import")!="reserved":
            raise ValueError(
                "arbitrary_topology_import must remain reserved in current schema"
            )
        if self.capabilities.get("contam_compiler")!="reserved":
            raise ValueError(
                "contam_compiler must remain reserved in current schema"
            )

        if not self.rooms:
            raise ValueError("layout requires at least one room")
        room_ids=[room.id for room in self.rooms]
        if len(room_ids)!=len(set(room_ids)):
            raise ValueError("room ids must be unique")
        for room in self.rooms:
            if room.w<=0 or room.h<=0 or room.volume_m3<=0:
                raise ValueError(f"room {room.id} geometry/volume must be positive")

        wall_ids=[wall.id for wall in self.walls]
        if len(wall_ids)!=len(set(wall_ids)):
            raise ValueError("wall ids must be unique")
        valid_nodes=set(room_ids)|{self.outside_id}
        for wall in self.walls:
            if wall.kind not in _ALLOWED_WALL_KINDS:
                raise ValueError(f"wall {wall.id} has unsupported kind")
            if wall.source not in valid_nodes or wall.target not in valid_nodes:
                raise ValueError(f"wall {wall.id} references unknown node")
            if wall.source==wall.target:
                raise ValueError(f"wall {wall.id} cannot connect a node to itself")
            if wall.x1==wall.x2 and wall.y1==wall.y2:
                raise ValueError(f"wall {wall.id} has zero length")
            if wall.kind=="exterior" and self.outside_id not in (wall.source,wall.target):
                raise ValueError(f"exterior wall {wall.id} must touch OUTSIDE")
            if wall.kind=="internal" and self.outside_id in (wall.source,wall.target):
                raise ValueError(f"internal wall {wall.id} cannot touch OUTSIDE")

        wall_map={wall.id:wall for wall in self.walls}
        opening_ids=[opening.id for opening in self.openings]
        if len(opening_ids)!=len(set(opening_ids)):
            raise ValueError("opening ids must be unique")
        for opening in self.openings:
            if opening.kind not in _ALLOWED_OPENING_KINDS:
                raise ValueError(f"opening {opening.id} has unsupported kind")
            wall=wall_map.get(opening.wall_id)
            if wall is None:
                raise ValueError(
                    f"opening {opening.id} references unknown wall {opening.wall_id}"
                )
            if {opening.source,opening.target}!={wall.source,wall.target}:
                raise ValueError(
                    f"opening {opening.id} endpoints do not match wall {wall.id}"
                )
            if not 0<=opening.position_t<=1:
                raise ValueError(
                    f"opening {opening.id} position_t must be between 0 and 1"
                )
            if not 0<=opening.initial_open_pct<=100:
                raise ValueError(
                    f"opening {opening.id} initial_open_pct must be 0..100"
                )
            if opening.max_area_m2<=0:
                raise ValueError(
                    f"opening {opening.id} max_area_m2 must be positive"
                )
            if not opening.position_editable:
                raise ValueError(
                    f"current product contract expects opening {opening.id} to be movable"
                )

        building=self.to_building_topology()
        building.validate()

    def to_building_topology(self) -> BuildingTopology:
        return BuildingTopology(
            zones={
                room.id:ZoneNode(
                    id=room.id,
                    volume_m3=room.volume_m3,
                )
                for room in self.rooms
            },
            openings={
                opening.id:OpeningEdge(
                    id=opening.id,
                    source=opening.source,
                    target=opening.target,
                    kind=opening.kind,
                    max_area_m2=opening.max_area_m2,
                    controllable=opening.state_editable,
                )
                for opening in self.openings
            },
            outside_id=self.outside_id,
        )

    def web_snapshot(self) -> dict[str,Any]:
        return {
            "schema_version":self.schema_version,
            "topology_id":self.topology_id,
            "source_kind":self.source_kind,
            "outside_id":self.outside_id,
            "capabilities":dict(self.capabilities),
            "rooms":[room.__dict__.copy() for room in self.rooms],
            "walls":[wall.__dict__.copy() for wall in self.walls],
            "openings":[opening.__dict__.copy() for opening in self.openings],
            "compiler_contract":dict(self.compiler_contract),
        }
