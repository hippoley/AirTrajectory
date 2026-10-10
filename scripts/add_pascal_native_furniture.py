#!/usr/bin/env python3
"""Add editable native Pascal procedural-item furniture to local residential SceneGraph."""
import argparse, json
from pathlib import Path
from shapely.geometry import Polygon, Point, box

SPECS={
 '客餐厅':[('沙发',1.9,.8,.72,'#99aaa9'),('茶几',.95,.55,.4,'#a78668'),('餐桌',1.5,.85,.76,'#ae936e')],
 '主卧':[('双人床',1.75,2,.53,'#d3baac'),('床头柜',.48,.42,.5,'#9c8168')],
 '儿童房':[('单人床',1,1.9,.49,'#b9c7d9'),('书桌',1.1,.55,.75,'#be9879')],
 '厨房':[('岛台',.9,.6,.86,'#dfd4ca')],
 '公卫':[('洗手台',.55,.43,.8,'#e4e4e0')],
 '主卫':[('洗手台',.65,.45,.8,'#e4e4e0')]}
def build(data):
 graph=json.loads(json.dumps(data));nodes=graph['nodes'];level=nodes['level_0'];created=[];placed=[]
 for zone in [n for n in nodes.values() if n['type']=='zone']:
  poly=Polygon(zone['polygon']);minx,miny,maxx,maxy=poly.bounds
  candidates=[poly.representative_point()]+[Point(minx+(maxx-minx)*u,miny+(maxy-miny)*v) for u,v in [(0.3,0.36),(0.7,0.65),(0.3,0.7),(0.7,0.33),(0.5,0.5)]]
  for label,w,d,h,color in SPECS.get(zone['name'],[]):
   selected=None
   for p in candidates:
    foot=box(p.x-w/2,p.y-d/2,p.x+w/2,p.y+d/2)
    if poly.buffer(-.06).contains(foot) and not any(foot.buffer(.15).intersects(other) for other in placed):
     selected=p;placed.append(foot);break
   if selected is None:continue
   ident=f'procedural-item_residence_{len(created):03d}'
   nodes[ident]={'object':'node','id':ident,'type':'procedural-item','name':label,'parentId':'level_0','visible':True,
    'metadata':{'airtrajectory_status':'visual-layout-unreviewed','airtrajectory_zone_id':zone['id']},
    'recipe':{'version':1,'name':label,'description':'Native editable primitive furniture','surfaces':[],
     'parameters':[],'slots':[{'id':'body','label':'Body','color':color}],
     'parts':[{'id':'body','count':1,'shapes':[{'id':'box','primitive':'box','slot':'body','size':[w,h,d],'position':[0,h/2,0]}]}],
     'constraints':[]},
    'parameters':{},'slots':{},'position':[round(selected.x,5),0,round(selected.y,5)],
    'rotation':[0,0,0],'children':[],'attachments':{}}
   level['children'].append(ident);created.append(ident)
 return graph,{'native_procedural_furniture':len(created),'ids':created,'collision_checked_at_placement':True,'interactive_drag_tested':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--audit',required=True,type=Path);a=p.parse_args()
 graph,report=build(json.loads(a.input.read_text()))
 a.output.write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
 a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False))
