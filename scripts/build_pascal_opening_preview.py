#!/usr/bin/env python3
"""Convert CAD opening candidates to native Pascal VISUAL drafts, never physics-authorized."""
import copy,json,math,argparse
from pathlib import Path
def build(scene,evidence):
 graph=copy.deepcopy(scene);nodes=graph['nodes'];zones=[n for n in nodes.values() if n['type']=='zone']
 segments={(s['handle'],s['layer']):s for s in evidence['all_geometry_segments']}
 records=[]
 for i,item in enumerate(evidence['openings']):
  choices=[]
  for span in item['possible_opening_spans']:
   s=segments.get((span['segment_handle'],span['layer']))
   if not s:continue
   a,b=s['a'],s['b'];L=math.dist(a,b)
   if not .5<=L<=3.5:continue
   v=[(b[j]-a[j])/L for j in (0,1)]
   for z in zones:
    polygon=z['polygon']
    for p,q in zip(polygon,polygon[1:]+polygon[:1]):
     E=math.dist(p,q)
     if E<.45:continue
     cross=abs(v[0]*(q[1]-p[1])-v[1]*(q[0]-p[0]))/E
     if cross>.012:continue
     offset=max(abs((t[0]-p[0])*(q[1]-p[1])-(t[1]-p[1])*(q[0]-p[0]))/E for t in (a,b))
     if offset>.16:continue
     proj=lambda t:sum((t[j]-p[j])*(q[j]-p[j]) for j in (0,1))/E
     if min(proj(a),proj(b))<-.08 or max(proj(a),proj(b))>E+.08:continue
     choices.append((round(offset,4),z['id'],s['handle'],s['layer'],a,b,L,v))
  row={'index':i,'label':item['label'],'status':'BLOCKED_NO_BOUNDARY_EVIDENCE'}
  if choices:
   choices.sort(key=lambda v:(v[0],v[1],v[2]));offset,zone_id,handle,layer,a,b,L,v=choices[0]
   kind='window' if layer=='J-窗' else 'door'
   wid=f'wall_cad_preview_{i:02d}';nid=f'{kind}_cad_preview_{i:02d}';margin=.24
   wall={'object':'node','id':wid,'type':'wall','parentId':'level_0','visible':True,
    'metadata':{'airtrajectory_status':'UNREVIEWED_VIRTUAL_VISUAL_HOST','airtrajectory_source_handle':handle,'airtrajectory_room_candidate':zone_id},
    'children':[nid],'thickness':.12,
    'start':[round(a[j]-margin*v[j],5) for j in (0,1)],
    'end':[round(b[j]+margin*v[j],5) for j in (0,1)],'frontSide':'unknown','backSide':'unknown'}
   node={'object':'node','id':nid,'type':kind,'parentId':wid,'wallId':wid,'visible':True,
    'metadata':{'airtrajectory_status':'UNREVIEWED_VISUAL_OPENING','airtrajectory_cad_label':item['label'],'airtrajectory_dimensions_unverified':'true'},
    'position':[round(margin+L/2,5),1.5 if kind=='window' else 1.05,0],
    'rotation':[0,0,0],'width':round(L,5),'height':1.2 if kind=='window' else 2.1,
    'frameThickness':.05,'frameDepth':.07}
   if kind=='window':
    node.update(columnRatios=[1],rowRatios=[1],columnDividerThickness=.03,rowDividerThickness=.03,sill=True,sillDepth=.08,sillThickness=.03)
   else:
    node.update(threshold=True,thresholdHeight=.02,hingesSide='left',swingDirection='inward',
     segments=[{'type':'panel','heightRatio':1,'columnRatios':[1],'dividerThickness':.03,'panelDepth':.01,'panelInset':.04}],
     handle=True,handleHeight=1.05,handleSide='right',contentPadding=[.04,.04],doorCloser=False,panicBar=False,panicBarHeight=1.)
   nodes[wid]=wall;nodes[nid]=node;graph['nodes']['level_0']['children'].append(wid)
   row.update(status='NATIVE_VISUAL_PREVIEW_UNREVIEWED',wall_id=wid,node_id=nid,width_candidate_m=round(L,5),boundary_offset_m=offset,kind=kind)
  records.append(row)
 return graph,{'status':'NATIVE_VISUAL_PREVIEW_NOT_ENGINEERING','native_opening_count':sum(r['status'].startswith('NATIVE') for r in records),
  'native_door_count':sum(r.get('kind')=='door' for r in records),
  'native_window_count':sum(r.get('kind')=='window' for r in records),
  'engineered_host_walls':0,'physics_authorized':False,'records':records}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('scene');p.add_argument('evidence');p.add_argument('--output',required=True);p.add_argument('--audit',required=True);a=p.parse_args()
 graph,report=build(json.loads(Path(a.scene).read_text()),json.loads(Path(a.evidence).read_text()))
 Path(a.output).write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
 Path(a.audit).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
