"""Private DXF structural import/inspection for Pascal residential default.
Input CAD stays local; emits metadata and a structural preview, never uploads DXF.
Requires ezdxf. Do NOT mistake unreviewed CAD lines for valid airflow topology.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def inspect(path: Path) -> dict:
    import ezdxf
    data=path.read_bytes()
    doc=ezdxf.readfile(path)
    ms=doc.modelspace()
    unit=int(doc.header.get("$INSUNITS",0))
    if unit != 4:
        raise ValueError(f"Expected millimetre CAD ($INSUNITS=4); got {unit}. Review scale first.")
    room_labels=[]
    openings=[]
    wall_segments=[]
    for entity in ms:
        layer=entity.dxf.layer
        if layer=="J-区域名称" and entity.dxftype() in {"TEXT","MTEXT"}:
            name=entity.plain_text() if entity.dxftype()=="MTEXT" else entity.dxf.text
            pos=entity.dxf.insert
            room_labels.append({"name":name,"anchor_m":[round(pos.x/1000,4),round(pos.y/1000,4)]})
        if layer=="J-门窗标号" and entity.dxftype() in {"TEXT","MTEXT"}:
            name=entity.plain_text() if entity.dxftype()=="MTEXT" else entity.dxf.text
            pos=entity.dxf.insert
            openings.append({"drawing_label":name,"anchor_m":[round(pos.x/1000,4),round(pos.y/1000,4)],
                             "unverified_host":True})
        if layer=="J-隔墙" and entity.dxftype() in {"LINE","LWPOLYLINE"}:
            if entity.dxftype()=="LINE":
                pairs=[((entity.dxf.start.x,entity.dxf.start.y),(entity.dxf.end.x,entity.dxf.end.y))]
            else:
                points=list(entity.get_points("xy"))
                pairs=list(zip(points,points[1:]+(points[:1] if entity.closed else [])))
            for (x1,y1),(x2,y2) in pairs:
                if abs(x1-x2)+abs(y1-y2)>1e-6:
                    wall_segments.append([[round(x1/1000,5),round(y1/1000,5)],
                                          [round(x2/1000,5),round(y2/1000,5)]])
    if not room_labels or not wall_segments: raise ValueError("Missing room labels or structural wall layer")
    return {"schema_version":"1.0","status":"CAD_STRUCTURE_EXTRACTED_NOT_NATIVE_SCENE",
      "source_dxf_sha256":hashlib.sha256(data).hexdigest(),"units":"millimetres",
      "rooms":sorted(room_labels,key=lambda x:x["name"]),
      "openings":sorted(openings,key=lambda x:(x["drawing_label"],x["anchor_m"])),
      "structural_wall_segments_m":wall_segments,
      "entity_counts":dict(Counter(e.dxftype() for e in ms)),
      "limitations":["Room labels are anchors, NOT validated room polygons",
         "Wall polylines are drawing geometry, NOT an approved centreline topology",
         "Door/window label anchors are NOT reviewed wall attachment",
         "No implicit airflow adjacency, height, volume, or engineering truth"]}


def main():
    a=argparse.ArgumentParser()
    a.add_argument("dxf",type=Path)
    a.add_argument("--out",required=True,type=Path)
    args=a.parse_args()
    report=inspect(args.dxf)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","source_dxf_sha256","units")},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
