#!/usr/bin/env python3
"""Construct native Pascal wall nodes from CAD line-chain candidates.
Visual candidates only: wall thickness and wall hosts are NOT engineering approved.
"""
import argparse,hashlib,json,math
from pathlib import Path
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union

def build(scene,chains,*,min_length=.55,max_boundary_distance=.14,wall_thickness=.12):
    graph=json.loads(json.dumps(scene))
    nodes=graph['nodes']
    if 'level_0' not in nodes:raise ValueError('Native level missing')
    zones=[x for x in nodes.values() if x['type']=='zone']
    if not zones:raise ValueError('No rooms')
    boundary=unary_union([Polygon(z['polygon']).boundary for z in zones])
    new=[];rejected=0;seen=set()
    for chain in chains['chains']:
        p=chain['polyline_m']
        for a,b in zip(p,p[1:]):
            if len(a)!=2 or len(b)!=2:raise ValueError('Bad CAD point')
            dist=math.dist(a,b)
            if dist<min_length:rejected+=1;continue
            line=LineString([a,b])
            fraction=line.intersection(boundary.buffer(max_boundary_distance)).length/line.length
            if fraction<.8:rejected+=1;continue
            key=tuple(sorted((tuple(round(v,4) for v in a),tuple(round(v,4) for v in b))))
            if key in seen:continue
            seen.add(key)
            ident=f'cad_wall_candidate_{len(new):03d}'
            nodes[ident]={'object':'node','id':ident,'type':'wall','parentId':'level_0',
                'visible':True,'metadata':{'airtrajectory_status':'cad-unreviewed-wall-candidate',
                 'airtrajectory_source_chain':chain['candidate_id']},'children':[],
                'thickness':wall_thickness,'start':list(a),'end':list(b),
                'frontSide':'unknown','backSide':'unknown'}
            new.append(ident)
    if not new:raise ValueError('No near-perimeter wall candidate')
    nodes['level_0']['children'].extend(new)
    return graph,{'new_wall_candidates':len(new),'rejected_short_or_not_perimeter':rejected,
        'wall_thickness_default_m':wall_thickness,'status':'VISUAL_WALL_CANDIDATES_NOT_ENGINEERING_REVIEWED',
        'door_nodes':0,'window_nodes':0,'physics_authorized':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('scene',type=Path);p.add_argument('chains',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args(); scene=a.scene.read_bytes();walls=a.chains.read_bytes()
    graph,report=build(json.loads(scene),json.loads(walls))
    report.update({'source_native_sha256':hashlib.sha256(scene).hexdigest(),
                   'source_wall_chains_sha256':hashlib.sha256(walls).hexdigest()})
    a.out.write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
    a.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
