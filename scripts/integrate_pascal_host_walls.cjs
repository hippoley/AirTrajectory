'use strict';
/** Geometrically trim CAD wall candidates which duplicate native shared opening hosts.
 *  Mutation operates on a clone and preserves all genuine Pascal wallId references.
 *  Provisional geometry remains unapproved for physics.
 */
const fs=require('node:fs');
function integrate(scene,{tolerance=.09,maxAngle=2}={}){
 const graph=structuredClone(scene),nodes=graph.nodes,level=nodes.level_0,changes=[];
 const hosts=Object.entries(nodes).filter(([id,n])=>id.startsWith('wall_cad_consolidated_')&&n.type==='wall');
 const length=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
 for(const [id,n] of [...Object.entries(nodes)]){
  if(!id.startsWith('cad_wall_candidate_')||n.type!=='wall')continue;
  if(n.children?.length)throw Error('Cannot trim wall with children: '+id);
  const a=n.start,b=n.end,L=length(a,b);if(L<1e-8)continue;
  const ux=(b[0]-a[0])/L,uy=(b[1]-a[1])/L,cuts=[];
  for(const [hostId,h] of hosts){
   const [c,d]=[h.start,h.end],H=length(c,d);if(H<1e-8)continue;
   const cosine=Math.min(1,Math.abs(ux*(d[0]-c[0])/H+uy*(d[1]-c[1])/H));
   if(Math.acos(cosine)*180/Math.PI>maxAngle)continue;
   if(Math.max(...[c,d].map(p=>Math.abs((p[0]-a[0])*uy-(p[1]-a[1])*ux)))>tolerance)continue;
   const proj=p=>(p[0]-a[0])*ux+(p[1]-a[1])*uy;
   const low=Math.max(0,Math.min(proj(c),proj(d))),high=Math.min(L,Math.max(proj(c),proj(d)));
   if(high-low>.08)cuts.push([low,high,hostId]);
  }
  if(!cuts.length)continue;
  cuts.sort((a,b)=>a[0]-b[0]);const merged=[];
  for(const [start,end] of cuts){
   if(merged.length&&start<=merged.at(-1)[1]+1e-5)merged.at(-1)[1]=Math.max(merged.at(-1)[1],end);
   else merged.push([start,end]);
  }
  const remaining=[];let cursor=0;
  for(const [start,end] of merged){if(start-cursor>.06)remaining.push([cursor,start]);cursor=Math.max(cursor,end);}
  if(L-cursor>.06)remaining.push([cursor,L]);
  level.children.splice(level.children.indexOf(id),1);delete nodes[id];
  remaining.forEach(([start,end],i)=>{
   const key=id+'_remaining_'+String(i).padStart(2,'0');
   nodes[key]={...structuredClone(n),id:key,start:[+(a[0]+start*ux).toFixed(5),+(a[1]+start*uy).toFixed(5)],
    end:[+(a[0]+end*ux).toFixed(5),+(a[1]+end*uy).toFixed(5)],
    metadata:{...n.metadata,airtrajectory_trimmed_by_shared_host:'true'}};
   level.children.push(key);
  });
  changes.push({wall:id,remaining:remaining.length,hosts:[...new Set(cuts.map(c=>c[2]))]});
 }
 for(const [id,node] of Object.entries(nodes)){
  for(const child of node.children||[])if(!nodes[child]||nodes[child].parentId!==id)throw Error('Broken child '+id);
  if(['door','window'].includes(node.type)){
   const host=nodes[node.wallId];
   if(!host||node.parentId!==node.wallId||!host.children.includes(id))throw Error('Broken opening '+id);
  }
 }
 return {graph,audit:{trimmed_wall_candidates:changes.length,remaining_nodes:Object.keys(nodes).length,physics_authorized:false,changes}};
}
if(require.main===module){
 const [input,out,auditPath]=process.argv.slice(2);if(!input||!out||!auditPath)throw Error('Usage: node scripts/integrate_pascal_host_walls.cjs input.json output.json audit.json');
 const {graph,audit}=integrate(JSON.parse(fs.readFileSync(input,'utf8')));
 fs.writeFileSync(out,JSON.stringify(graph,null,2)+'\n');fs.writeFileSync(auditPath,JSON.stringify(audit,null,2)+'\n');
 console.log(JSON.stringify({trimmed_wall_candidates:audit.trimmed_wall_candidates,remaining_nodes:audit.remaining_nodes}));
}
module.exports={integrate};
