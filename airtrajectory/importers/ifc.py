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


def _volume_from_property_sets(
    psets: dict[str, Any],
    *,
    volume_unit_scale: float=1.0,
) -> tuple[float, str]:
    """Resolve one positive space volume from IFC quantities/properties.

    Preference order:
    1. standard/common quantity names NetVolume / GrossVolume;
    2. a unique positive property named Volume.

    Multiple conflicting fallback values fail closed instead of selecting one.
    """
    preferred=[]
    fallback=[]
    for set_name, values in (psets or {}).items():
        if not isinstance(values,dict):
            continue
        for key in ("NetVolume","GrossVolume"):
            value=values.get(key)
            if isinstance(value,(int,float)) and value>0:
                preferred.append((float(value)*volume_unit_scale,f"{set_name}.{key}"))
        value=values.get("Volume")
        if isinstance(value,(int,float)) and value>0:
            fallback.append((float(value)*volume_unit_scale,f"{set_name}.Volume"))

    if preferred:
        # NetVolume/GrossVolume may both exist. Prefer first deterministic name.
        preferred.sort(key=lambda item:item[1])
        return preferred[0]

    unique={round(value,12) for value,_ in fallback}
    if len(unique)==1 and fallback:
        fallback.sort(key=lambda item:item[1])
        return fallback[0]
    if len(unique)>1:
        raise ValueError("space has conflicting positive Volume properties")
    raise ValueError("space missing usable volume quantity/property")


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
        import ifcopenshell.util.unit
    except ImportError as exc:
        raise RuntimeError(
            "IFC import requires optional dependency ifcopenshell"
        ) from exc

    model=ifcopenshell.open(str(path))
    settings=ifcopenshell.geom.settings()
    length_unit_scale=ifcopenshell.util.unit.calculate_unit_scale(
        model,"LENGTHUNIT"
    )
    try:
        volume_unit_scale=ifcopenshell.util.unit.calculate_unit_scale(
            model,"VOLUMEUNIT"
        )
    except Exception:
        volume_unit_scale=length_unit_scale**3

    def bbox(entity):
        shape=ifcopenshell.geom.create_shape(settings,entity)
        verts=list(shape.geometry.verts)
        if not verts:
            raise ValueError(f"{entity.GlobalId} has no geometry")
        xs=verts[0::3]; ys=verts[1::3]
        return min(xs),min(ys),max(xs),max(ys)

    def volume(space):
        # Real IFC2X3/Revit exports commonly place space volume in ordinary
        # property sets rather than Qto_SpaceBaseQuantities. Read all psets,
        # prefer standard quantity names, then accept one unambiguous positive
        # property named Volume while preserving its source path.
        psets=ifcopenshell.util.element.get_psets(space)
        try:
            value,source=_volume_from_property_sets(
                psets,
                volume_unit_scale=volume_unit_scale,
            )
            return value,source
        except ValueError as exc:
            raise ValueError(
                f"IfcSpace {space.GlobalId} {exc}"
            ) from exc

    spaces=[]
    for s in model.by_type("IfcSpace"):
        x1,y1,x2,y2=bbox(s)
        volume_m3,volume_source=volume(s)
        spaces.append({
            "id":s.GlobalId,
            "name":s.Name or s.GlobalId,
            "x":x1,"y":y1,"w":x2-x1,"h":y2-y1,
            "volume_m3":volume_m3,
            "volume_source":volume_source,
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
    # IFC-native host boundary cross-reference. This is a review candidate,
    # not an inferred direct opening-space connection.
    host_spaces = {}
    for rel in model.by_type("IfcRelSpaceBoundary"):
        elem = getattr(rel, "RelatedBuildingElement", None)
        space = getattr(rel, "RelatingSpace", None)
        host_id = getattr(elem, "GlobalId", None)
        space_id = getattr(space, "GlobalId", None)
        if host_id and space_id:
            host_spaces.setdefault(str(host_id), set()).add(str(space_id))

    for kind,ifc_type in (("door","IfcDoor"),("window","IfcWindow")):
        for elem in model.by_type(ifc_type):
            adj=sorted(adjacency.get(elem.GlobalId) or [])
            if len(adj) not in {1,2}:
                raise ValueError(
                    f"{ifc_type} {elem.GlobalId} lacks unambiguous "
                    "IfcRelSpaceBoundary adjacency"
                )
            width=float(getattr(elem,"OverallWidth",0) or 0)*length_unit_scale
            height=float(getattr(elem,"OverallHeight",0) or 0)*length_unit_scale
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
        "source_units":{
            "length_to_m":length_unit_scale,
            "volume_to_m3":volume_unit_scale,
            "geometry_output":"SI_METERS",
        },
        "spaces":spaces,
        "openings":opening_rows,
    }


def _resolve_control_scope(
    openings: list[dict[str, Any]],
    requested_scope: set[str]|None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    known={str(row["id"]) for row in openings}
    if requested_scope is None:
        selected=list(openings)
        return selected,{
            "mode":"ALL_OPENINGS",
            "requested_opening_ids":None,
            "resolved_opening_ids":sorted(known),
        },[]

    requested={str(value) for value in requested_scope}
    selected=[row for row in openings if str(row["id"]) in requested]
    missing=sorted(requested-known)
    blockers=[
        {"entity_id":opening_id,"reason":"UNKNOWN_CONTROL_OPENING"}
        for opening_id in missing
    ]
    return selected,{
        "mode":"DECLARED_SUBSET",
        "requested_opening_ids":sorted(requested),
        "resolved_opening_ids":sorted(str(row["id"]) for row in selected),
    },blockers


def inspect_ifc_control_readiness(
    path: str|Path,
    *,
    controlled_opening_ids: set[str]|None=None,
) -> dict[str, Any]:
    """Inspect a real IFC file and collect control-readiness blockers.

    Unlike `import_ifc()`, this function is diagnostic: missing geometry,
    volume, dimensions, or adjacency is accumulated instead of stopping at the
    first failure.
    """
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import ifcopenshell.util.element
        import ifcopenshell.util.unit
    except ImportError as exc:
        raise RuntimeError(
            "IFC inspection requires optional dependency ifcopenshell"
        ) from exc

    path=Path(path)
    model=ifcopenshell.open(str(path))
    settings=ifcopenshell.geom.settings()
    length_unit_scale=ifcopenshell.util.unit.calculate_unit_scale(
        model,"LENGTHUNIT"
    )
    try:
        volume_unit_scale=ifcopenshell.util.unit.calculate_unit_scale(
            model,"VOLUMEUNIT"
        )
    except Exception:
        volume_unit_scale=length_unit_scale**3
    blockers=[]
    spaces=[]
    openings=[]
    requested_scope=(
        {str(value) for value in controlled_opening_ids}
        if controlled_opening_ids is not None
        else None
    )

    def try_bbox(entity, *, record_blocker: bool=True):
        try:
            shape=ifcopenshell.geom.create_shape(settings,entity)
            verts=list(shape.geometry.verts)
            if not verts:
                raise ValueError("no geometry vertices")
            xs=verts[0::3]; ys=verts[1::3]
            return min(xs),min(ys),max(xs),max(ys)
        except Exception as exc:
            if record_blocker:
                blockers.append({
                    "entity_id":getattr(entity,"GlobalId","<entity>"),
                    "reason":"GEOMETRY_UNAVAILABLE",
                    "detail":str(exc),
                })
            return None

    for space in model.by_type("IfcSpace"):
        gid=space.GlobalId
        box=try_bbox(space)
        try:
            volume_m3,volume_source=_volume_from_property_sets(
                ifcopenshell.util.element.get_psets(space),
                volume_unit_scale=volume_unit_scale,
            )
        except ValueError as exc:
            blockers.append({
                "entity_id":gid,
                "reason":"MISSING_VOLUME_M3",
                "detail":str(exc),
            })
            volume_m3=None
            volume_source=None
        row={
            "id":gid,
            "name":space.Name or gid,
            "volume_m3":volume_m3,
            "volume_source":volume_source,
        }
        if box is not None:
            x1,y1,x2,y2=box
            row.update({"x":x1,"y":y1,"w":x2-x1,"h":y2-y1})
        else:
            row.update({"x":None,"y":None,"w":None,"h":None})
        spaces.append(row)

    adjacency={}
    for rel in model.by_type("IfcRelSpaceBoundary"):
        elem=getattr(rel,"RelatedBuildingElement",None)
        space=getattr(rel,"RelatingSpace",None)
        if elem is None or space is None:
            continue
        if elem.is_a() not in {"IfcDoor","IfcWindow"}:
            continue
        adjacency.setdefault(elem.GlobalId,set()).add(space.GlobalId)

    host_spaces = {}
    for relation in model.by_type("IfcRelSpaceBoundary"):
        related = getattr(relation, "RelatedBuildingElement", None)
        room = getattr(relation, "RelatingSpace", None)
        host_id = getattr(related, "GlobalId", None)
        space_id = getattr(room, "GlobalId", None)
        if host_id and space_id:
            host_spaces.setdefault(str(host_id), set()).add(str(space_id))

    for kind,ifc_type in (("door","IfcDoor"),("window","IfcWindow")):
        for elem in model.by_type(ifc_type):
            gid=elem.GlobalId
            adj=sorted(adjacency.get(gid) or [])
            in_scope=requested_scope is None or gid in requested_scope
            if in_scope and len(adj) not in {1,2}:
                blockers.append({
                    "entity_id":gid,
                    "reason":"AMBIGUOUS_SPACE_ADJACENCY",
                    "detail":{"adjacent_spaces":adj},
                })
            width=float(getattr(elem,"OverallWidth",0) or 0)*length_unit_scale
            height=float(getattr(elem,"OverallHeight",0) or 0)*length_unit_scale
            if in_scope and width<=0:
                blockers.append({"entity_id":gid,"reason":"MISSING_WIDTH_M"})
            if in_scope and height<=0:
                blockers.append({"entity_id":gid,"reason":"MISSING_HEIGHT_M"})
            box=try_bbox(elem,record_blocker=in_scope)
            # Reuse native IFC void/fill relationships to expose independent
            # host-element evidence for ambiguous space boundaries. These
            # references are diagnostic only: host walls do not establish
            # which side of the wall connects to each zone.
            host_ids=[]
            try:
                for fill in getattr(elem, "FillsVoids", ()) or ():
                    void=getattr(fill, "RelatingOpeningElement", None)
                    for rel in getattr(void, "VoidsElements", ()) or ():
                        host=getattr(rel, "RelatingBuildingElement", None)
                        host_id=getattr(host, "GlobalId", None)
                        if host_id:
                            host_ids.append(str(host_id))
            except (AttributeError, TypeError):
                pass
            host_ids=sorted(set(host_ids))
            host_candidates=sorted(set().union(*(host_spaces.get(h, set()) for h in host_ids)))
            # Plan-view geometry can provide a second, weak proximity hint,
            # but bounding box intersection must never approve adjacency.
            geometric_candidates=[]
            if box is not None:
                bx1,by1,bx2,by2=box
                for space_row in spaces:
                    if any(space_row.get(k) is None for k in ("x","y","w","h")):
                        continue
                    sx1,sy1=space_row["x"],space_row["y"]
                    sx2,sy2=sx1+space_row["w"],sy1+space_row["h"]
                    if bx1 <= sx2 and bx2 >= sx1 and by1 <= sy2 and by2 >= sy1:
                        geometric_candidates.append(space_row["id"])
            geometric_candidates=sorted(set(geometric_candidates))

            row={
                "id":gid,
                "kind":kind,
                "adjacent_spaces":adj,
                "ifc_host_element_ids":host_ids,
                "host_boundary_space_candidates":host_candidates,
                "bbox_intersection_space_candidates":geometric_candidates,
                "host_evidence_level":"IFC_REL_FILLS_VOIDS_DIAGNOSTIC_ONLY",
                "width_m":width if width>0 else None,
                "height_m":height if height>0 else None,
                "in_control_scope":in_scope,
            }
            if box is not None:
                x1,y1,x2,y2=box
                row.update({"x1":x1,"y1":y1,"x2":x2,"y2":y2})
            else:
                row.update({"x1":None,"y1":None,"x2":None,"y2":None})
            openings.append(row)

    # Reuse normalized-semantic checks so diagnostic and import paths share the
    # same blocker vocabulary. Deduplicate exact blocker identities/reasons.
    scoped_openings,scope_meta,scope_blockers=_resolve_control_scope(
        openings,
        requested_scope,
    )
    normalized=assess_ifc_semantics({
        "spaces":spaces,
        "openings":scoped_openings,
    })
    blockers.extend(normalized["blockers"])
    blockers.extend(scope_blockers)
    dedup={}
    for blocker in blockers:
        key=(str(blocker.get("entity_id")),str(blocker.get("reason")))
        dedup.setdefault(key,blocker)
    blockers=list(dedup.values())

    mapped_doors=sum(
        1 for row in openings
        if row["kind"]=="door" and len(row["adjacent_spaces"]) in {1,2}
    )
    mapped_windows=sum(
        1 for row in openings
        if row["kind"]=="window" and len(row["adjacent_spaces"]) in {1,2}
    )

    return {
        "schema_version":"0.1",
        "status":"READY" if not blockers else "BLOCKED",
        "source":{
            "format":"IFC",
            "path":str(path),
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "schema":str(getattr(model,"schema","")),
            "units":{
                "length_to_m":length_unit_scale,
                "volume_to_m3":volume_unit_scale,
                "geometry_output":"SI_METERS",
            },
        },
        "space_count":len(spaces),
        "door_count":len(model.by_type("IfcDoor")),
        "window_count":len(model.by_type("IfcWindow")),
        "space_boundary_count":len(model.by_type("IfcRelSpaceBoundary")),
        "opening_count":len(openings),
        "control_scope":scope_meta,
        "opening_boundary_coverage":{
            "doors_total":len(model.by_type("IfcDoor")),
            "doors_mapped":mapped_doors,
            "windows_total":len(model.by_type("IfcWindow")),
            "windows_mapped":mapped_windows,
        },
        "blockers":blockers,
        "semantics":{
            "topology_id":"ifc:"+path.stem,
            "spaces":spaces,
            "openings":openings,
        },
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
