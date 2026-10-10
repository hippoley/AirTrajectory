"""Group CAD visual opening hosts into longer native Pascal walls.
Provisional geometry only; physics authorization remains false.
"""
import copy,math
from collections import defaultdict

def consolidate(scene):
    graph=copy.deepcopy(scene)
    nodes=graph["nodes"];level=nodes["level_0"]
    grouped=defaultdict(list)
    for opening in nodes.values():
        if opening["type"] not in ("door","window"):continue
        host_id=opening.get("wallId","")
        if not host_id.startswith("wall_cad_opening_preview_"):continue
        host=nodes[host_id];a,b=host["start"],host["end"]
        dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy)
        ux,uy=dx/L,dy/L
        if ux<0 or (abs(ux)<1e-8 and uy<0):ux,uy=-ux,-uy
        key=(round(math.atan2(uy,ux)/.008),round((-uy*a[0]+ux*a[1])/.09))
        axis=lambda p:ux*p[0]+uy*p[1]
        start,end=sorted((axis(a),axis(b)))
        grouped[key].append((start,end,ux,uy,-uy*a[0]+ux*a[1],opening,host))
    audit=[];walls_added=0
    for key,items in sorted(grouped.items()):
        items.sort(key=lambda a:a[0]);clusters=[]
        for item in items:
            if not clusters or item[0]>clusters[-1][1]+.35:clusters.append(([item],item[1]))
            else:
                members,last=clusters[-1];members.append(item);clusters[-1]=(members,max(last,item[1]))
        for members,_ in clusters:
            ux,uy=members[0][2:4];offset=sum(m[4] for m in members)/len(members)
            lo=min(m[0] for m in members);hi=max(m[1] for m in members)
            ident=f"wall_cad_consolidated_{walls_added:03d}";walls_added+=1
            wall=dict(object="node",id=ident,type="wall",parentId="level_0",visible=True,
              metadata={"airtrajectory_status":"UNREVIEWED_CAD_CONTINUOUS_VISUAL_HOST",
                "airtrajectory_physics_authorized":"false"},children=[],thickness=.12,
              start=[round(ux*(lo-.24)-uy*offset,5),round(uy*(lo-.24)+ux*offset,5)],
              end=[round(ux*(hi+.24)-uy*offset,5),round(uy*(hi+.24)+ux*offset,5)],
              frontSide="unknown",backSide="unknown")
            nodes[ident]=wall;level["children"].append(ident)
            occupied=[]
            for _,_,_,_,_,opening,old in sorted(members,key=lambda m:(m[0]+m[1])/2):
                a,b=old["start"],old["end"];length=math.dist(a,b)
                center=[a[i]+(b[i]-a[i])*opening["position"][0]/length for i in (0,1)]
                pos=ux*center[0]+uy*center[1];left=pos-opening["width"]/2;right=pos+opening["width"]/2
                overlap=next(((x,y,t) for x,y,t in occupied if max(x,left)<min(y,right)-.07),None)
                if overlap:
                    opening["visible"]=False
                    opening["metadata"]["airtrajectory_status"]="BLOCKED_OVERLAPPING_CAD_OPENING"
                    audit.append({"id":opening["id"],"status":"BLOCKED_OVERLAP"})
                    continue
                opening["wallId"]=ident;opening["parentId"]=ident
                opening["position"][0]=round(pos-(lo-.24),5)
                opening["metadata"]["airtrajectory_status"]="UNREVIEWED_CAD_CONSOLIDATED_HOST"
                wall["children"].append(opening["id"]);old["children"].remove(opening["id"])
                occupied.append((left,right,opening["type"]))
                audit.append({"id":opening["id"],"status":"REHOSTED_VISUAL","host":ident})
            if not wall["children"]:
                level["children"].remove(ident);del nodes[ident]
    for key in list(nodes):
        n=nodes[key]
        if n["type"]=="wall" and key.startswith("wall_cad_opening_preview_") and not n["children"]:
            level["children"].remove(key);del nodes[key]
    return graph,{"status":"UNREVIEWED_VISUAL_ONLY","physics_authorized":False,
      "rehosted_openings":sum(x["status"]=="REHOSTED_VISUAL" for x in audit),
      "blocked_overlaps":sum(x["status"]=="BLOCKED_OVERLAP" for x in audit),
      "consolidated_hosts":sum(k.startswith("wall_cad_consolidated_") for k in nodes),"records":audit}
