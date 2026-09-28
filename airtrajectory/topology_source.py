"""Topology source contract for UI, simulation and future CONTAM compilation.

The current product intentionally ships a fixed floor plan with movable windows
and doors. The fixed layout is data, not a hard-coded architectural assumption.

Future providers can replace the manifest source without changing downstream
consumers:
- arbitrary JSON topology
- 2D/CAD-derived topology
- 3D scene-derived topology

This module does not claim arbitrary topology -> CONTAM PRJ compilation exists
yet. It exposes a stable compile contract containing the geometry/connectivity
CONTAM will eventually consume.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from .topology import BuildingTopology, OpeningEdge, ZoneNode


DEFAULT_FIXED_TOPOLOGY_PATH=(
    Path(__file__).resolve().parents[1]
    /"web"/"data"/"home_topology.fixed.json"
)


def _canonical_sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class TopologyManifest:
    payload: Dict[str, Any]
    source_path: str | None=None

    @classmethod
    def from_file(cls,path: str|Path):
        p=Path(path)
        payload=json.loads(p.read_text(encoding="utf-8"))
        model=cls(payload=payload,source_path=str(p))
        model.validate()
        return model

    @property
    def topology_id(self) -> str:
        return str(self.payload["topology_id"])

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.payload)

    @property
    def edit_policy(self) -> dict:
        return dict(self.payload.get("edit_policy") or {})

    def validate(self) -> None:
        p=self.payload
        if not isinstance(p,dict):
            raise ValueError("topology manifest must be an object")
        if str(p.get("schema_version") or "")!="0.1":
            raise ValueError("unsupported topology manifest schema")
        if not str(p.get("topology_id") or "").strip():
            raise ValueError("topology_id is required")

        policy=p.get("edit_policy")
        if not isinstance(policy,dict):
            raise ValueError("edit_policy is required")
        expected={
            "layout_mutable":False,
            "room_geometry_mutable":False,
            "wall_geometry_mutable":False,
            "opening_position_mutable":True,
            "opening_state_mutable":True,
        }
        for key,value in expected.items():
            if policy.get(key) is not value:
                raise ValueError(
                    f"current fixed-topology provider requires {key}={value}"
                )

        rooms=p.get("rooms")
        walls=p.get("walls")
        openings=p.get("openings")
        if not isinstance(rooms,list) or not rooms:
            raise ValueError("topology requires rooms")
        if not isinstance(walls,list) or not walls:
            raise ValueError("topology requires walls")
        if not isinstance(openings,list) or not openings:
            raise ValueError("topology requires openings")

        room_ids=[str(r.get("id") or "") for r in rooms if isinstance(r,dict)]
        if len(room_ids)!=len(set(room_ids)) or any(not x for x in room_ids):
            raise ValueError("room ids must be unique and non-empty")

        wall_map={}
        for wall in walls:
            if not isinstance(wall,dict):
                raise ValueError("wall must be an object")
            wid=str(wall.get("id") or "")
            if not wid or wid in wall_map:
                raise ValueError("wall ids must be unique and non-empty")
            seg=wall.get("segment")
            if not isinstance(seg,dict):
                raise ValueError(f"wall {wid} requires segment")
            for key in ("x1","y1","x2","y2"):
                if not isinstance(seg.get(key),(int,float)):
                    raise ValueError(f"wall {wid} segment.{key} must be numeric")
            if seg["x1"]==seg["x2"] and seg["y1"]==seg["y2"]:
                raise ValueError(f"wall {wid} segment cannot have zero length")
            wall_map[wid]=wall

        valid_nodes=set(room_ids)|{"OUTSIDE"}
        opening_ids=set()
        for opening in openings:
            if not isinstance(opening,dict):
                raise ValueError("opening must be an object")
            oid=str(opening.get("id") or "")
            if not oid or oid in opening_ids:
                raise ValueError("opening ids must be unique and non-empty")
            opening_ids.add(oid)
            if opening.get("kind") not in ("window","door","vent"):
                raise ValueError(f"opening {oid} kind is unsupported")
            if opening.get("wall_id") not in wall_map:
                raise ValueError(f"opening {oid} references unknown wall")
            if opening.get("source") not in valid_nodes:
                raise ValueError(f"opening {oid} source is unknown")
            if opening.get("target") not in valid_nodes:
                raise ValueError(f"opening {oid} target is unknown")
            t=opening.get("position_on_wall")
            if not isinstance(t,(int,float)) or not 0 <= float(t) <= 1:
                raise ValueError(
                    f"opening {oid} position_on_wall must be within [0,1]"
                )
            area=opening.get("max_area_m2")
            if not isinstance(area,(int,float)) or float(area)<=0:
                raise ValueError(f"opening {oid} max_area_m2 must be positive")

        # Reuse the runtime topology validation for connectivity semantics.
        self.to_building_topology()

    def to_building_topology(self) -> BuildingTopology:
        rooms=self.payload.get("rooms") or []
        openings=self.payload.get("openings") or []
        zones=[
            ZoneNode(
                str(room["id"]),
                float(room["volume_m3"]),
                str(room.get("kind") or "room"),
            )
            for room in rooms
        ]
        edges=[
            OpeningEdge(
                str(opening["id"]),
                str(opening["source"]),
                str(opening["target"]),
                str(opening["kind"]),
                float(opening["max_area_m2"]),
                bool(opening.get("controllable",True)),
            )
            for opening in openings
        ]
        return BuildingTopology.from_parts(zones,edges)

    def opening_positions(self) -> dict[str,float]:
        return {
            str(opening["id"]):float(opening["position_on_wall"])
            for opening in self.payload["openings"]
        }

    def with_opening_positions(
        self,
        positions: dict[str,float],
    ) -> "TopologyManifest":
        """Return a new manifest with only opening positions changed.

        Room/wall geometry and connectivity are intentionally immutable in the
        current provider.
        """
        unknown=set(positions)-{
            str(o["id"]) for o in self.payload["openings"]
        }
        if unknown:
            raise ValueError(
                "unknown opening positions: "+",".join(sorted(unknown))
            )

        clone=json.loads(json.dumps(self.payload))
        for opening in clone["openings"]:
            oid=str(opening["id"])
            if oid not in positions:
                continue
            value=float(positions[oid])
            if not 0 <= value <= 1:
                raise ValueError(
                    f"opening {oid} position_on_wall must be within [0,1]"
                )
            opening["position_on_wall"]=value

        result=TopologyManifest(
            clone,
            source_path=self.source_path,
        )
        result.validate()
        return result

    def trajectory_context(self) -> dict:
        return {
            "topology_id":self.topology_id,
            "topology_manifest_sha256":self.sha256,
            "topology_provider":str(
                self.payload.get("provider") or "unknown"
            ),
            "edit_policy":self.edit_policy,
            "opening_positions":self.opening_positions(),
        }

    def contam_compile_contract(self) -> dict:
        """Return the stable input contract for the future PRJ compiler.

        This is deliberately not a PRJ file and not evidence that automatic
        CONTAM topology compilation is complete.
        """
        return {
            "schema_version":"0.1",
            "status":"RESERVED",
            "compiler":"topology-to-contam",
            "topology_id":self.topology_id,
            "topology_manifest_sha256":self.sha256,
            "outside_id":"OUTSIDE",
            "zones":[
                {
                    "id":str(room["id"]),
                    "volume_m3":float(room["volume_m3"]),
                    "geometry":dict(room["geometry"]),
                }
                for room in self.payload["rooms"]
            ],
            "walls":[
                {
                    "id":str(wall["id"]),
                    "kind":str(wall.get("kind") or "unknown"),
                    "segment":dict(wall["segment"]),
                }
                for wall in self.payload["walls"]
            ],
            "openings":[
                {
                    "id":str(opening["id"]),
                    "kind":str(opening["kind"]),
                    "source":str(opening["source"]),
                    "target":str(opening["target"]),
                    "wall_id":str(opening["wall_id"]),
                    "position_on_wall":float(
                        opening["position_on_wall"]
                    ),
                    "max_area_m2":float(opening["max_area_m2"]),
                    "controllable":bool(
                        opening.get("controllable",True)
                    ),
                }
                for opening in self.payload["openings"]
            ],
            "reserved_outputs":{
                "prj_path":None,
                "zone_numbers":None,
                "opening_controls":None,
                "path_numbers":None,
            },
            "note":(
                "Contract only. Arbitrary topology -> CONTAM PRJ compilation "
                "is intentionally not claimed complete yet."
            ),
        }


def load_fixed_topology(
    path: str|Path=DEFAULT_FIXED_TOPOLOGY_PATH,
) -> TopologyManifest:
    return TopologyManifest.from_file(path)
