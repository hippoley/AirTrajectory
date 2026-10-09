/*
 * Room partition geometry for LayoutContract.
 * Based on openPlan3D's atomic edit/connected-wall model (MIT; see THIRD_PARTY_NOTICES.md).
 * No automatic engineering adjacency is inferred beyond the exact rectangular split below.
 */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.AirTrajectoryRoomPartition=api;})(typeof globalThis==="object"?globalThis:null,function(){
"use strict";
const EPS=1e-5;
function splitRectRoom(layout,roomId,axis="x",fraction=.5){
 if(!["x","y"].includes(axis)||!Number.isFinite(fraction)||fraction<.2||fraction>.8)throw Error("Unsupported room split");
 const room=layout.rooms.find(r=>r.id===roomId);
 if(!room||![room.x,room.y,room.w,room.h,room.volume_m3].every(Number.isFinite)||room.w<=0||room.h<=0||room.volume_m3<=0)throw Error("Missing valid room dimensions");
 const boundary=axis==="x"?room.x+room.w*fraction:room.y+room.h*fraction;
 const next=structuredClone(layout);
 const original=next.rooms.find(r=>r.id===roomId);
 const secondId=roomId+"-split-"+(next.rooms.length+1);
 if(next.rooms.some(r=>r.id===secondId))throw Error("Room ID collision");
 const added={...original,id:secondId,name:(original.name||roomId)+" B"};
 const a=axis==="x"?"w":"h",coord=axis==="x"?"x":"y";
 added[coord]=boundary;added[a]=original[a]*(1-fraction);added.volume_m3=original.volume_m3*(1-fraction);
 original[a]*=fraction;original.volume_m3*=fraction;original.name=(original.name||roomId)+" A";
 next.rooms.push(added);
 const openings=[];
 for(const wall of next.walls.slice()){
  if(wall.source!==roomId&&wall.target!==roomId)continue;
  const p1=axis==="x"?wall.x1:wall.y1,p2=axis==="x"?wall.x2:wall.y2;
  const lo=Math.min(p1,p2),hi=Math.max(p1,p2);
  if(lo<boundary-EPS&&hi>boundary+EPS){
   // A shared host crossing the cut is split exactly at the cut.
   const t=(boundary-p1)/(p2-p1);
   if(t<=EPS||t>=1-EPS)throw Error("Invalid cut parameter");
   const splitPoint={x:wall.x1+(wall.x2-wall.x1)*t,y:wall.y1+(wall.y2-wall.y1)*t};
   const extra={...wall,id:wall.id+"-part-"+secondId,x1:splitPoint.x,y1:splitPoint.y};
   if(next.walls.some(w=>w.id===extra.id))throw Error("Wall ID collision");
   wall.x2=splitPoint.x;wall.y2=splitPoint.y;
   const oldOpenings=next.openings.filter(o=>o.wall_id===wall.id);
   for(const o of oldOpenings){
    if(Math.abs(o.position_t-t)<EPS)throw Error("Opening intersects room split cut");
    if(o.position_t<t){o.position_t=o.position_t/t;}
    else {o.wall_id=extra.id;o.position_t=(o.position_t-t)/(1-t);}
   }
   next.walls.push(extra);
   for(const segment of [wall,extra]){
    const mid=(axis==="x"?(segment.x1+segment.x2):(segment.y1+segment.y2))/2;
    if(mid>boundary+EPS){if(segment.source===roomId)segment.source=secondId;if(segment.target===roomId)segment.target=secondId;}
   }
   openings.push(extra.id);
  }else{
   const middle=(p1+p2)/2;
   if(Math.abs(middle-boundary)<EPS)throw Error("Wall lies directly on split axis; manual review required");
   if(middle>boundary){if(wall.source===roomId)wall.source=secondId;if(wall.target===roomId)wall.target=secondId;}
  }
 }
 // Every opening must be attached to the updated host wall endpoints.
 for(const o of next.openings){
  const w=next.walls.find(w=>w.id===o.wall_id);
  if(!w)throw Error("Dangling opening after split");
  o.source=w.source;o.target=w.target;
 }
 // A new partition boundary is physical geometry, not an airflow opening.
 const partitionId="partition-"+secondId;
 if(next.walls.some(w=>w.id===partitionId))throw Error("Partition ID collision");
 if(axis==="x")next.walls.push({id:partitionId,kind:"internal",source:roomId,target:secondId,x1:boundary,y1:room.y,x2:boundary,y2:room.y+room.h});
 else next.walls.push({id:partitionId,kind:"internal",source:roomId,target:secondId,x1:room.x,y1:boundary,x2:room.x+room.w,y2:boundary});
 next.topology_id=String(next.topology_id||"layout")+".partition";
 return next;
}
return {splitRectRoom};
});