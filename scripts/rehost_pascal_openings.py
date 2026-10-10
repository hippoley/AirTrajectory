#!/usr/bin/env python3
"""Move Pascal Door/Window from provisional visual hosts to real surveyed wall
candidates ONLY when complete opening fits one collinear wall. No engineering
authorization is inferred from geometric proximity.
"""
import copy,json,math,argparse
from pathlib import Path
def projection(p,a,b):
 dx=b[0]-a[0];dy=b[1]-a[1];length=math.hypot(dx,dy)
 if length<1e-8:return None
 return ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length,abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/length,length
def rehost(scene,tolerance=.045,clearance=.04,max_angle=2):
 graph=copy.deepcopy(scene);nodes=graph['nodes']
 walls={key:node for key,node in nodes.items() if node.get('type')=='wall' and key.startswith('cad_wall_candidate_')}
 records=[]
 for key,opening in list(nodes.items()):
  old_id=opening.get('wallId','')
  if opening.get('type') not in ('door','window') or not old_id.startswith('wall_cad_opening_preview_'):continue
  old=nodes[old_id];a,b=old['start'],old['end'];L=math.dist(a,b)
  unit=[(b[i]-a[i])/L for i in (0,1)]
  center=[a[i]+unit[i]*opening['position'][0] for i in (0,1)]
  half=opening['width']/2
  ends=[[center[i]+sign*unit[i]*half for i in (0,1)] for sign in (-1,1)]
  choices=[]
  for wall_id,wall in walls.items():
   x,y=wall['start'],wall['end']
   projections=[projection(p,x,y) for p in ends]
   if any(p is None for p in projections):continue
   direction=[(y[i]-x[i])/projections[0][2] for i in (0,1)]
   cosine=min(1,abs(sum(direction[i]*unit[i] for i in (0,1))))
   if math.degrees(math.acos(cosine))>max_angle:continue
   if any(p[1]>tolerance for p in projections):continue
   low,high=sorted(p[0] for p in projections)
   if low<clearance or high>projections[0][2]-clearance:continue
   choices.append((wall_id,(low+high)/2))
  row={'opening_id':key,'previous_host_id':old_id,'full_width_matching_wall_count':len(choices)}
  if len(choices)==1:
   wall_id,offset=choices[0]
   wall=nodes[wall_id];wall.setdefault('children',[]).append(key)
   opening['parentId']=wall_id;opening['wallId']=wall_id
   opening['position'][0]=round(offset,6)
   opening.setdefault('metadata',{})['airtrajectory_status']='CAD_HOST_MATCHED_BUT_ENGINEERING_UNREVIEWED'
   assert old['children']==[key],'Provisional host has other children'
   graph['nodes']['level_0']['children'].remove(old_id);del nodes[old_id]
   row.update(status='MIGRATED_GEOMETRICALLY_UNREVIEWED',new_host_id=wall_id)
  else:row['status']='BLOCKED_NO_UNIQUE_REAL_WALL_FIT'
  records.append(row)
 transferred=sum(x['status'].startswith('MIGRATED') for x in records)
 return graph,{'status':'CAD_REHOSTING_NOT_PHYSICS_APPROVED','transferred':transferred,'blocked':len(records)-transferred,'openings':records}
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--audit',required=True,type=Path)
 a=p.parse_args();graph,audit=rehost(json.loads(a.source.read_text(encoding='utf8')))
 a.output.write_text(json.dumps(graph,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 a.audit.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 print('MIGRATED',audit['transferred'],'BLOCKED',audit['blocked'])
if __name__=='__main__':main()
