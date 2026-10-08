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
import hashlib
import json
from pathlib import Path
from typing import Any


def _optional_float(value: Any) -> float|None:
    return None if value is None else float(value)

from .topology import BuildingTopology, OpeningEdge, ZoneNode


_ALLOWED_OPENING_KINDS={"window","door","vent"}
_ALLOWED_WALL_KINDS={"exterior","internal"}
_ALLOWED_SOURCE_KINDS={"fixed-floorplan","imported-floorplan"}
_ALLOWED_IMPORT_STATES={"reserved","supported"}


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
    length_m: float|None
    azimuth_deg: float|None


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
    width_m: float|None
    height_m: float|None
    sill_height_m: float|None


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
    def from_file(cls,path: str|Path) -> "LayoutContract":
        payload=json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

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
                length_m=_optional_float(item.get("length_m")),
                azimuth_deg=_optional_float(item.get("azimuth_deg")),
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
                width_m=_optional_float(item.get("width_m")),
                height_m=_optional_float(item.get("height_m")),
                sill_height_m=_optional_float(item.get("sill_height_m")),
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
        if self.source_kind not in _ALLOWED_SOURCE_KINDS:
            raise ValueError(
                "unsupported source_kind; expected fixed-floorplan or imported-floorplan"
            )

        geometry_editable=self.capabilities.get("floorplan_geometry_editable")
        if not isinstance(geometry_editable,bool):
            raise ValueError("floorplan_geometry_editable must be boolean")
        if self.capabilities.get("opening_position_editable") is not True:
            raise ValueError(
                "layout contract must allow opening position edits"
            )
        import_state=self.capabilities.get("arbitrary_topology_import")
        if import_state not in _ALLOWED_IMPORT_STATES:
            raise ValueError(
                "arbitrary_topology_import must be reserved or supported"
            )
        if self.source_kind=="fixed-floorplan":
            if geometry_editable is not False:
                raise ValueError(
                    "fixed-floorplan contracts must keep floorplan geometry fixed"
                )
            if import_state!="reserved":
                raise ValueError(
                    "fixed-floorplan contracts must keep arbitrary import reserved"
                )
        else:
            if import_state!="supported":
                raise ValueError(
                    "imported-floorplan requires arbitrary_topology_import=supported"
                )
        if self.capabilities.get("contam_compiler") not in {"reserved","supported"}:
            raise ValueError(
                "contam_compiler must be reserved or supported"
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
            if wall.length_m is not None and wall.length_m<=0:
                raise ValueError(f"wall {wall.id} length_m must be positive")
            if wall.azimuth_deg is not None and not 0<=wall.azimuth_deg<360:
                raise ValueError(f"wall {wall.id} azimuth_deg must be in [0,360)")

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
            if opening.width_m is not None and opening.width_m<=0:
                raise ValueError(f"opening {opening.id} width_m must be positive")
            if opening.height_m is not None and opening.height_m<=0:
                raise ValueError(f"opening {opening.id} height_m must be positive")
            if opening.sill_height_m is not None and opening.sill_height_m<0:
                raise ValueError(f"opening {opening.id} sill_height_m must be non-negative")
            if wall.length_m is not None and opening.width_m is not None and opening.width_m>wall.length_m:
                raise ValueError(f"opening {opening.id} width_m exceeds wall length_m")
            if opening.width_m is not None and opening.height_m is not None:
                if opening.max_area_m2>opening.width_m*opening.height_m+1e-9:
                    raise ValueError(f"opening {opening.id} max_area_m2 exceeds physical opening area")

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

    def sha256(self) -> str:
        raw=json.dumps(
            self.web_snapshot(),
            sort_keys=True,
            separators=(",",":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def trajectory_context(
        self,
        *,
        topology_revision: int=0,
        opening_positions: dict[str,float]|None=None,
    ) -> dict[str,Any]:
        positions={
            opening.id:opening.position_t
            for opening in self.openings
        }
        if opening_positions:
            unknown=set(opening_positions)-set(positions)
            if unknown:
                raise ValueError(
                    "unknown opening positions: "
                    +",".join(sorted(unknown))
                )
            for opening_id,value in opening_positions.items():
                numeric=float(value)
                if not 0<=numeric<=1:
                    raise ValueError(
                        f"opening {opening_id} position must be between 0 and 1"
                    )
                positions[opening_id]=numeric

        return {
            "topology_id":self.topology_id,
            "layout_contract_sha256":self.sha256(),
            "source_kind":self.source_kind,
            "topology_revision":int(topology_revision),
            "capabilities":dict(self.capabilities),
            "opening_positions":positions,
        }

    def contam_compile_contract(
        self,
        *,
        opening_positions: dict[str,float]|None=None,
    ) -> dict[str,Any]:
        """Stable input seam for the future arbitrary topology -> CONTAM compiler.

        This seam is topology-source neutral. Downstream compiler readiness is
        reported separately from whether the layout was fixed or imported.
        """
        positions={
            opening.id:opening.position_t
            for opening in self.openings
        }
        if opening_positions:
            unknown=set(opening_positions)-set(positions)
            if unknown:
                raise ValueError(
                    "unknown opening positions: "
                    +",".join(sorted(unknown))
                )
            for opening_id,value in opening_positions.items():
                numeric=float(value)
                if not 0<=numeric<=1:
                    raise ValueError(
                        f"opening {opening_id} position must be between 0 and 1"
                    )
                positions[opening_id]=numeric

        return {
            "schema_version":"0.1",
            "status":"RESERVED",
            "compiler":"topology-to-contam",
            "topology_id":self.topology_id,
            "layout_contract_sha256":self.sha256(),
            "outside_id":self.outside_id,
            "zones":[
                {
                    "id":room.id,
                    "volume_m3":room.volume_m3,
                    "geometry":{
                        "x":room.x,
                        "y":room.y,
                        "w":room.w,
                        "h":room.h,
                    },
                }
                for room in self.rooms
            ],
            "walls":[wall.__dict__.copy() for wall in self.walls],
            "openings":[
                {
                    "id":opening.id,
                    "kind":opening.kind,
                    "wall_id":opening.wall_id,
                    "source":opening.source,
                    "target":opening.target,
                    "position_t":positions[opening.id],
                    "max_area_m2":opening.max_area_m2,
                    "controllable":opening.state_editable,
                }
                for opening in self.openings
            ],
            "reserved_outputs":{
                "prj_path":None,
                "zone_numbers":None,
                "opening_controls":None,
                "path_numbers":None,
            },
            "note":(
                "Contract only. Arbitrary topology -> CONTAM PRJ compilation "
                "is not claimed complete."
            ),
        }
