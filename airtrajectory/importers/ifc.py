"""Strict IFC -> LayoutContract adapter.

The adapter intentionally fails closed. It consumes IFC semantics already
present in the file and never lets missing adjacency/volume/geometry become
invented engineering truth.

The public helper `layout_from_ifc_semantics()` is dependency-free and tested.
`extract_ifc_semantics()` uses IfcOpenShell when installed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from ..layout import LayoutContract


@dataclass(frozen=True)
class IfcImportBlocker:
    entity_id: str
    reason: str


def _room_box(item: dict[str, Any]) -> dict[str, Any]:
    required=("id","name","x","y","w","h","volume_m3")
    missing=[k for k in required if item.get(k) is None]
    if missing:
        raise ValueError("IFC space missing fields: "+",".join(missing))
    return {
        "id":str(item["id"]),
        "name":str(item["name"]),
        "x":float(item["x"]),
        "y":float(item["y"]),
        "w":float(item["w"]),
        "h":float(item["h"]),
        "volume_m3":float(item["volume_m3"]),
    }


def assess_ifc_semantics(semantics: dict[str, Any]) -> dict[str, Any]:
    """Return machine-readable blockers before LayoutContract construction."""
    blockers=[]
    spaces=semantics.get("spaces") or []
    if not spaces:
        blockers.append({"entity_id":"<model>","reason":"NO_IFCSPACE"})
    room_ids=set()
    for item in spaces:
        entity_id=str(item.get("id") or "<space>")
        room_ids.add(entity_id)
        for key in ("id","x","y","w","h","volume_m3"):
            if item.get(key) is None:
                blockers.append({"entity_id":entity_id,"reason":"MISSING_"+key.upper()})
        if item.get("volume_m3") is not None and float(item["volume_m3"])<=0:
            blockers.append({"entity_id":entity_id,"reason":"NONPOSITIVE_VOLUME"})

    for item in semantics.get("openings") or []:
        entity_id=str(item.get("id") or "<opening>")
        adjacent=[str(x) for x in (item.get("adjacent_spaces") or [])]
        if len(adjacent) not in {1,2}:
            blockers.append({"entity_id":entity_id,"reason":"AMBIGUOUS_SPACE_ADJACENCY"})
        unknown=sorted(set(adjacent)-room_ids)
        if unknown:
            blockers.append({
                "entity_id":entity_id,
                "reason":"UNKNOWN_ADJACENT_SPACE",
                "detail":unknown,
            })
        for key in ("width_m","height_m"):
            value=item.get(key)
            if value is None or float(value)<=0:
                blockers.append({"entity_id":entity_id,"reason":"MISSING_"+key.upper()})
        for key in ("x1","y1","x2","y2"):
            if item.get(key) is None:
                blockers.append({"entity_id":entity_id,"reason":"MISSING_PROJECTED_"+key.upper()})

    return {
        "schema_version":"0.1",
        "status":"READY" if not blockers else "BLOCKED",
        "space_count":len(spaces),
        "opening_count":len(semantics.get("openings") or []),
        "blockers":blockers,
    }


def layout_from_ifc_semantics(
    semantics: dict[str, Any],
    *,
    source_sha256: str,
    importer_version: str="0.1",
) -> LayoutContract:
    """Build LayoutContract from strict normalized IFC semantics.

    Required semantics:
      spaces: [{id,name,x,y,w,h,volume_m3}]
      openings: [{id,kind,adjacent_spaces,width_m,height_m,x1,y1,x2,y2}]

    An opening with one adjacent space is exterior; two is internal.
    More/zero spaces are rejected.
    """
    readiness=assess_ifc_semantics(semantics)
    if readiness["status"]!="READY":
        first=readiness["blockers"][0]
        raise ValueError(
            "IFC semantics blocked: "
            + first["reason"]
            + " @ "
            + first["entity_id"]
        )
    spaces=[_room_box(x) for x in semantics.get("spaces") or []]
    room_ids={x["id"] for x in spaces}

    walls=[]
    openings=[]
    for raw in semantics.get("openings") or []:
        oid=str(raw.get("id") or "")
        kind=str(raw.get("kind") or "").lower()
        if kind not in {"window","door"}:
            raise ValueError(f"IFC opening {oid} has unsupported kind")
        adjacent=[str(x) for x in (raw.get("adjacent_spaces") or [])]
        if len(adjacent) not in {1,2}:
            raise ValueError(
                f"IFC opening {oid} requires one or two adjacent spaces"
            )
        unknown=set(adjacent)-room_ids
        if unknown:
            raise ValueError(
                f"IFC opening {oid} references unknown spaces: "
                + ",".join(sorted(unknown))
            )
        width=float(raw.get("width_m") or 0)
        height=float(raw.get("height_m") or 0)
        if width<=0 or height<=0:
            raise ValueError(f"IFC opening {oid} requires width_m/height_m")
        for key in ("x1","y1","x2","y2"):
            if raw.get(key) is None:
                raise ValueError(f"IFC opening {oid} missing projected {key}")
        source=adjacent[0]
        target=adjacent[1] if len(adjacent)==2 else "OUTSIDE"
        wall_id="ifc-boundary:"+oid
        walls.append({
            "id":wall_id,
            "kind":"internal" if len(adjacent)==2 else "exterior",
            "source":source,
            "target":target,
            "x1":float(raw["x1"]),
            "y1":float(raw["y1"]),
            "x2":float(raw["x2"]),
            "y2":float(raw["y2"]),
        })
        openings.append({
            "id":oid,
            "kind":kind,
            "wall_id":wall_id,
            "source":source,
            "target":target,
            "position_t":0.5,
            "initial_open_pct":0,
            "max_area_m2":width*height,
            "render_side":"ifc",
            "position_editable":True,
            "state_editable":True,
            "width_m":width,
            "height_m":height,
            "sill_height_m":raw.get("sill_height_m"),
        })

    payload={
        "schema_version":"0.1",
        "topology_id":str(semantics.get("topology_id") or "ifc-import"),
        "source_kind":"imported-floorplan",
        "outside_id":"OUTSIDE",
        "capabilities":{
            "floorplan_geometry_editable":True,
            "opening_position_editable":True,
            "opening_state_editable":True,
            "arbitrary_topology_import":"supported",
            "contam_compiler":"reserved",
        },
        "source_provenance":{
            "format":"IFC",
            "source_sha256":source_sha256,
            "importer":{"id":"airtrajectory-ifc","version":importer_version},
            "geometry_fidelity":"bbox-and-boundary-projection",
        },
        "rooms":spaces,
        "walls":walls,
        "openings":openings,
        "compiler_contract":{
            "current_consumers":["trajectory-context","spatial-compile"],
            "reserved_consumers":["engineering-contam-compiler"],
        },
    }
    return LayoutContract.from_dict(payload)


def extract_ifc_semantics(path: str|Path) -> dict[str, Any]:
    """Extract strict semantics with IfcOpenShell.

    Current v0.1 deliberately requires:
    - IfcSpace quantity volume;
    - geometric bounding box for each space;
    - IfcRelSpaceBoundary directly relating each IfcDoor/IfcWindow to 1-2 spaces;
    - positive OverallWidth / OverallHeight;
    - geometric bounding box for each opening.

    Files that do not encode these facts are rejected instead of guessed.
    """
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import ifcopenshell.util.element
    except ImportError as exc:
        raise RuntimeError(
            "IFC import requires optional dependency ifcopenshell"
        ) from exc

    model=ifcopenshell.open(str(path))
    settings=ifcopenshell.geom.settings()

    def bbox(entity):
        shape=ifcopenshell.geom.create_shape(settings,entity)
        verts=list(shape.geometry.verts)
        if not verts:
            raise ValueError(f"{entity.GlobalId} has no geometry")
        xs=verts[0::3]; ys=verts[1::3]
        return min(xs),min(ys),max(xs),max(ys)

    def volume(space):
        psets=ifcopenshell.util.element.get_psets(space,qtos_only=True)
        for name in ("Qto_SpaceBaseQuantities","BaseQuantities"):
            q=psets.get(name) or {}
            for key in ("NetVolume","GrossVolume"):
                value=q.get(key)
                if isinstance(value,(int,float)) and value>0:
                    return float(value)
        raise ValueError(f"IfcSpace {space.GlobalId} missing volume quantity")

    spaces=[]
    for s in model.by_type("IfcSpace"):
        x1,y1,x2,y2=bbox(s)
        spaces.append({
            "id":s.GlobalId,
            "name":s.Name or s.GlobalId,
            "x":x1,"y":y1,"w":x2-x1,"h":y2-y1,
            "volume_m3":volume(s),
        })

    adjacency={}
    for rel in model.by_type("IfcRelSpaceBoundary"):
        elem=getattr(rel,"RelatedBuildingElement",None)
        space=getattr(rel,"RelatingSpace",None)
        if elem is None or space is None:
            continue
        if elem.is_a() not in {"IfcDoor","IfcWindow"}:
            continue
        adjacency.setdefault(elem.GlobalId,set()).add(space.GlobalId)

    opening_rows=[]
    for kind,ifc_type in (("door","IfcDoor"),("window","IfcWindow")):
        for elem in model.by_type(ifc_type):
            adj=sorted(adjacency.get(elem.GlobalId) or [])
            if len(adj) not in {1,2}:
                raise ValueError(
                    f"{ifc_type} {elem.GlobalId} lacks unambiguous "
                    "IfcRelSpaceBoundary adjacency"
                )
            width=float(getattr(elem,"OverallWidth",0) or 0)
            height=float(getattr(elem,"OverallHeight",0) or 0)
            if width<=0 or height<=0:
                raise ValueError(
                    f"{ifc_type} {elem.GlobalId} missing OverallWidth/OverallHeight"
                )
            x1,y1,x2,y2=bbox(elem)
            opening_rows.append({
                "id":elem.GlobalId,
                "kind":kind,
                "adjacent_spaces":adj,
                "width_m":width,
                "height_m":height,
                "x1":x1,"y1":y1,"x2":x2,"y2":y2,
            })

    return {
        "topology_id":"ifc:"+Path(path).stem,
        "spaces":spaces,
        "openings":opening_rows,
    }


def import_ifc(path: str|Path, *, importer_version: str="0.1") -> LayoutContract:
    path=Path(path)
    source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    semantics=extract_ifc_semantics(path)
    return layout_from_ifc_semantics(
        semantics,
        source_sha256=source_hash,
        importer_version=importer_version,
    )
