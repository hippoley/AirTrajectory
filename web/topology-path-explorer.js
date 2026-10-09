/* AirTrajectory topology-only path explorer. No airflow direction or physics claimed. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.AirTrajectoryPathExplorer=api;})(typeof globalThis==="object"?globalThis:null,function(){
"use strict";
function discover(layout){
 if(!layout||!Array.isArray(layout.rooms)||!Array.isArray(layout.openings)||!Array.isArray(layout.walls))throw Error("invalid layout");
 const outside=layout.outside_id||"OUTSIDE",rooms=new Set(layout.rooms.map(r=>r.id));
 const walls=new Map(layout.walls.map(w=>[w.id,w]));
 const neighbors=new Map([...rooms].map(r=>[r,[]])),outsideWindows=[];
 for(const opening of layout.openings){
  const w=walls.get(opening.wall_id);
  if(!w||w.source!==opening.source||w.target!==opening.target)continue;
  if(opening.kind==="window"&&[opening.source,opening.target].includes(outside)){
   const room=opening.source===outside?opening.target:opening.source;
   if(rooms.has(room))outsideWindows.push({id:opening.id,room});
  }
  if(opening.kind==="door"&&rooms.has(opening.source)&&rooms.has(opening.target)){
   neighbors.get(opening.source).push({to:opening.target,via:opening.id});
   neighbors.get(opening.target).push({to:opening.source,via:opening.id});
  }
 }
 outsideWindows.sort((a,b)=>a.id.localeCompare(b.id));
 for(const arr of neighbors.values())arr.sort((a,b)=>a.via.localeCompare(b.via));
 const paths=[];
 for(let i=0;i<outsideWindows.length;i++)for(let j=i+1;j<outsideWindows.length;j++){
  const start=outsideWindows[i],end=outsideWindows[j],queue=[{room:start.room,rooms:[start.room],doors:[]}],seen=new Set([start.room]);
  let found=null;
  while(queue.length){
   const curr=queue.shift();
   if(curr.room===end.room){found=curr;break;}
   for(const edge of neighbors.get(curr.room)||[]){
    if(seen.has(edge.to))continue;
    seen.add(edge.to);queue.push({room:edge.to,rooms:[...curr.rooms,edge.to],doors:[...curr.doors,edge.via]});
   }
  }
  if(found)paths.push({entry_window:start.id,exit_window:end.id,rooms:found.rooms,doors:found.doors,opening_ids:[start.id,...found.doors,end.id],evidence_class:"TOPOLOGY_ONLY_UNDIRECTED"});
 }
 return {status:"TOPOLOGY_ONLY_NOT_AIRFLOW",rooms:rooms.size,exterior_windows:outsideWindows.length,internal_door_edges:[...neighbors.values()].reduce((a,v)=>a+v.length,0)/2,paths};
}
return {discover};
});