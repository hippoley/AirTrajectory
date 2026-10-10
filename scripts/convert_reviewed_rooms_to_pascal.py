#!/usr/bin/env python3
"""Convert local CAD room polygons into Pascal-native zone scene; privacy safe."""
import argparse,hashlib,json,math
from pathlib import Path

def convert(src):
 rooms=src.get("rooms",[])
 if not rooms or len({r["name"] for r in rooms})!=len(rooms): raise ValueError("Missing or duplicate rooms")
 points=[]
 for r in rooms:
  p=r["polygon_outer_ring_m"]
  if len(p)<3 or any(len(x)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in x) for x in p) or r.get("hole_count",0): raise ValueError("Invalid/holed polygon")
  area=abs(sum(x[0]*y[1]-y[0]*x[1] for x,y in zip(p,p[1:]+p[:1]))/2)
  if area<.1: raise ValueError("Degenerate room")
  points.extend(p)
 xs=[p[0] for p in points];ys=[p[1] for p in points];x0,x1=min(xs)-2,max(xs)+2;y0,y1=min(ys)-2,max(ys)+2
 nodes={
 "site_private":{"object":"node","id":"site_private","type":"site","parentId":None,"visible":True,"metadata":{},"polygon":{"type":"polygon","points":[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]},"children":["building_private"]},
 "building_private":{"object":"node","id":"building_private","type":"building","parentId":"site_private","visible":True,"metadata":{},"position":[0,0,0],"rotation":[0,0,0],"children":["level_0"]}}
 keys=[]
 for i,r in enumerate(rooms):
  key=f"zone_private_{i:02d}"; keys.append(key)
  nodes[key]={"object":"node","id":key,"type":"zone","parentId":"level_0","visible":True,"metadata":{"airtrajectory_geometry_review_required":"true"},"name":r["name"],"color":["#9ad0c3","#e8bf8c","#aec8ed","#d3c0e3","#b8d89e","#f0b0a1"][i%6],"polygon":r["polygon_outer_ring_m"]}
 nodes["level_0"]={"object":"node","id":"level_0","type":"level","parentId":"building_private","visible":True,"metadata":{"airtrajectory_height_unverified":"true"},"level":0,"height":2.7,"children":keys}
 return {"nodes":nodes,"rootNodeIds":["site_private"]}

def main():
 p=argparse.ArgumentParser();p.add_argument("rooms",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
 graph=convert(json.loads(a.rooms.read_text(encoding="utf8")))
 a.output.write_text(json.dumps(graph,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print("ROOMS_ONLY_ARCHITECTURAL_REVIEW_REQUIRED",len(graph["nodes"])-3,"rooms; no unverified walls, openings, or physics")
if __name__=="__main__": main()
