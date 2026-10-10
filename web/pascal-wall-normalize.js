// Merge overlapping/co-linear Pascal walls without losing hosted openings.
// Coordinates are metres in the source two-dimensional floor-plan frame.
const EPS=0.015;
const near=(a,b,e=EPS)=>Math.abs(a-b)<=e;
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1];
export function normalizeWallGraph(graph){
 const originals=Object.values(graph.nodes).filter(n=>n.type==='wall'&&n.visible!==false&&Array.isArray(n.start)&&Array.isArray(n.end));
 const other=Object.fromEntries(Object.entries(graph.nodes).filter(([,n])=>n.type!=='wall'&&!['door','window'].includes(n.type)));
 const openings=Object.values(graph.nodes).filter(n=>['door','window'].includes(n.type)&&n.visible!==false);
 const descriptors=[];
 for(const w of originals){
  const dx=w.end[0]-w.start[0],dy=w.end[1]-w.start[1],len=Math.hypot(dx,dy);
  if(len<EPS)continue;
  let u=[dx/len,dy/len];
  if(u[0]<-1e-8||(near(u[0],0,1e-8)&&u[1]<0))u=[-u[0],-u[1]];
  const v=[-u[1],u[0]],offset=dot(w.start,v);
  const a=dot(w.start,u),b=dot(w.end,u);
  descriptors.push({w,u,v,offset,start:Math.min(a,b),end:Math.max(a,b),len,forward:dot([dx,dy],u)>0});
 }
 // Do not combine different structural thicknesses, directions, or parallel-offset walls.
 const buckets=[];
 for(const d of descriptors){
  let bucket=buckets.find(b=>near(dot(b.u,d.u),1,1e-5)&&near(b.offset,d.offset)&&near(b.thickness,d.w.thickness||.12,.005));
  if(!bucket){bucket={u:d.u,v:d.v,offset:d.offset,thickness:d.w.thickness||.12,items:[]};buckets.push(bucket)}
  bucket.items.push(d);
 }
 const newNodes={...other},roots=graph.rootNodeIds.filter(id=>newNodes[id]),hostMap={};
 let count=0;
 for(const bucket of buckets){
  bucket.items.sort((a,b)=>a.start-b.start);
  const components=[];
  for(const d of bucket.items){
   let c=components[components.length-1];
   if(!c||d.start>c.end+EPS){c={start:d.start,end:d.end,items:[]};components.push(c)}
   else c.end=Math.max(c.end,d.end);
   c.items.push(d);
  }
  for(const c of components){
   const id='normalized-wall-'+count++;
   const point=t=>[+(bucket.u[0]*t+bucket.v[0]*bucket.offset).toFixed(6),+(bucket.u[1]*t+bucket.v[1]*bucket.offset).toFixed(6)];
   const wall={id,type:'wall',start:point(c.start),end:point(c.end),thickness:bucket.thickness,visible:true,children:[]};
   newNodes[id]=wall;roots.push(id);
   for(const d of c.items)hostMap[d.w.id]={id,start:c.start,sourceStart:d.forward?d.start:d.end,sign:d.forward?1:-1};
  }
 }
 const duplicate=new Set(),rejected=[];
 for(const opening of openings){
  const mapped=hostMap[opening.wallId||opening.parentId];
  if(!mapped||!Array.isArray(opening.position)||!Number.isFinite(opening.width)){rejected.push(opening.id);continue}
  const x=mapped.sourceStart+mapped.sign*opening.position[0]-mapped.start;
  const key=[mapped.id,opening.type,x.toFixed(3),opening.position[1]?.toFixed(3),opening.width.toFixed(3),opening.height?.toFixed(3)].join('|');
  if(duplicate.has(key))continue;
  duplicate.add(key);
  newNodes[opening.id]={...opening,wallId:mapped.id,parentId:mapped.id,position:[x,opening.position[1],opening.position[2]||0]};
  newNodes[mapped.id].children.push(opening.id);
 }
 return {...graph,nodes:newNodes,rootNodeIds:roots,normalization:{sourceWalls:originals.length,renderWalls:count,droppedOpenings:rejected}};
}
