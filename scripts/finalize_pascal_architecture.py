"""Remove rejected overlapping CAD door/window nodes and their orphan preview walls.
Preserve valid parent/host relationships; keep engineering authorization false.
"""
import copy

def finalize(graph):
 out=copy.deepcopy(graph);nodes=out["nodes"];level=nodes["level_0"]
 removed=[];blocked=[]
 for key,node in list(nodes.items()):
  if node.get("type") not in ("window","door"):continue
  if node.get("metadata",{}).get("airtrajectory_status")!="BLOCKED_OVERLAPPING_CAD_OPENING":continue
  host_id=node.get("wallId");host=nodes.get(host_id)
  if node.get("visible") is not False or not host or not host_id.startswith("wall_cad_opening_preview_") or host.get("children")!=[key] or node.get("parentId")!=host_id or host_id not in level["children"]:
   blocked.append(key);continue
  level["children"].remove(host_id);del nodes[key];del nodes[host_id]
  removed.append({"opening_id":key,"orphan_preview_wall":host_id})
 for key,node in nodes.items():
  parent=node.get("parentId")
  if parent is not None and parent not in nodes:raise ValueError("Broken parent "+key)
  for child in node.get("children",[]):
   if child not in nodes or nodes[child].get("parentId")!=key:raise ValueError("Broken child "+key)
  if node.get("type") in ("door","window"):
   host=nodes.get(node.get("wallId"))
   if not host or host.get("type")!="wall" or key not in host.get("children",[]):raise ValueError("Broken opening host "+key)
 return out,{"status":"VISUAL_PREVIEW_CLEANED_NOT_ENGINEERING_APPROVED","removed":removed,"blocked":blocked,"remaining_nodes":len(nodes),"physics_authorized":False}
