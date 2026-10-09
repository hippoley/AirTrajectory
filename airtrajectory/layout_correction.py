"""Fail-closed correction operations for imported canonical layouts.

Corrections are explicit, replayable operations. They never infer geometry or
silently overwrite an original IFC source. Output remains LayoutContract v0.1.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from .layout import LayoutContract


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def correct_layout(layout: LayoutContract, operations: list[Mapping[str, Any]]) -> LayoutContract:
    if layout.source_kind != "imported-floorplan":
        raise ValueError("corrections require imported-floorplan; fixed demo is immutable")
    data={
        "schema_version":layout.schema_version,
        "topology_id":layout.topology_id,
        "source_kind":layout.source_kind,
        "outside_id":layout.outside_id,
        "capabilities":deepcopy(layout.capabilities),
        "source_provenance":deepcopy(layout.source_provenance),
        "rooms":[asdict(x) for x in layout.rooms],
        "walls":[asdict(x) for x in layout.walls],
        "openings":[asdict(x) for x in layout.openings],
        "compiler_contract":deepcopy(layout.compiler_contract),
    }
    if not data["capabilities"]["floorplan_geometry_editable"]:
        raise ValueError("imported layout has locked geometry")
    allowed={
        "rename_room", "move_opening", "resize_opening", "rewire_wall",
        "add_opening", "remove_opening", "set_room_volume",
        "move_wall", "rename_opening",
    }
    for op in operations:
        name=op.get("op")
        if name not in allowed:
            raise ValueError(f"unsupported correction: {name}")
        collection="rooms" if name in {"rename_room","set_room_volume"} else "walls" if name in {"rewire_wall","move_wall"} else "openings"
        ident=str(op.get("id") or "")
        matches=[row for row in data[collection] if row["id"]==ident]
        if name=="add_opening":
            if any(row["id"]==ident for row in data["openings"]):
                raise ValueError("duplicate opening id")
            wall=next((w for w in data["walls"] if w["id"]==op.get("wall_id")),None)
            if wall is None:
                raise ValueError("unknown wall")
            data["openings"].append({
                "id":ident,"kind":op["kind"],"wall_id":wall["id"],
                "source":wall["source"],"target":wall["target"],
                "position_t":float(op.get("position_t",0.5)),
                "initial_open_pct":float(op.get("initial_open_pct",0)),
                "max_area_m2":float(op["max_area_m2"]),
                "render_side":op.get("render_side","imported"),
                "position_editable":True,"state_editable":True,
                "width_m":op.get("width_m"),"height_m":op.get("height_m"),
                "sill_height_m":op.get("sill_height_m"),
            })
        else:
            if len(matches)!=1:
                raise ValueError(f"unknown {collection} id: {ident}")
            item=matches[0]
            if name=="rename_room":
                item["name"]=str(op["name"])
            elif name=="set_room_volume":
                item["volume_m3"]=float(op["volume_m3"])
            elif name=="move_opening":
                item["position_t"]=float(op["position_t"])
            elif name=="resize_opening":
                for field in ("width_m","height_m","sill_height_m","max_area_m2"):
                    if field in op:
                        item[field]=float(op[field])
            elif name=="remove_opening":
                data["openings"].remove(item)
            elif name=="rename_opening":
                new_id=str(op["new_id"])
                if any(o["id"]==new_id for o in data["openings"]):
                    raise ValueError("duplicate opening id")
                item["id"]=new_id
            elif name=="move_wall":
                for field in ("x1","y1","x2","y2","length_m","azimuth_deg"):
                    if field in op:
                        item[field]=float(op[field])
            elif name=="rewire_wall":
                item["source"]=str(op["source"])
                item["target"]=str(op["target"])
                item["kind"]=str(op["kind"])
                for opening in data["openings"]:
                    if opening["wall_id"]==ident:
                        opening["source"]=item["source"]
                        opening["target"]=item["target"]
        # Validate EVERY atomic edit before committing it.
        LayoutContract.from_dict(data)
    data["source_provenance"]["correction"]={
        "operations_sha256":_digest(operations),
        "count":len(operations),
        "base_source_sha256":layout.source_provenance["source_sha256"],
    }
    return LayoutContract.from_dict(data)
