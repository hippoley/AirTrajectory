/*
 Adapted from openPlan3D src/lib/utils/wallEditing.ts (MIT).
 Copyright (c) 2026 theLodgeStudio.
 Source: https://github.com/laanlabs/openPlan3D
 Adaptation: AirTrajectory LayoutContract's x1/y1/x2/y2 wall geometry.
*/
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.AirTrajectoryWallEditing=api;})(typeof globalThis==="object"?globalThis:null,function(){
"use strict";
function length(w){return Math.hypot(w.x2-w.x1,w.y2-w.y1);}
function endpoint(w,which){return which==="start"?{x:w.x1,y:w.y1}:{x:w.x2,y:w.y2};}
function connected(walls,p,exclude,tolerance=2){
 const result=[];
 for(const w of walls){if(w.id===exclude)continue;
  for(const which of ["start","end"]){const q=endpoint(w,which);if(Math.hypot(q.x-p.x,q.y-p.y)<tolerance)result.push({wallId:w.id,endpoint:which});}
 }
 return result;
}
function planResize(walls,id,newLength,fixed="start"){
 if(!Number.isFinite(newLength)||newLength<1)throw Error("Wall length must be at least 1");
 if(!["start","end"].includes(fixed))throw Error("Invalid fixed endpoint");
 const wall=walls.find(w=>w.id===id);if(!wall)throw Error("Unknown wall");
 const original=length(wall);if(!Number.isFinite(original)||original<1)throw Error("Invalid existing wall length");
 const move=fixed==="start"?"end":"start",anchor=endpoint(wall,fixed),old=endpoint(wall,move);
 const scale=newLength/original,target={x:anchor.x+(old.x-anchor.x)*scale,y:anchor.y+(old.y-anchor.y)*scale};
 const patches=new Map([[id,move==="start"?{x1:target.x,y1:target.y}:{x2:target.x,y2:target.y}]]);
 for(const joined of connected(walls,old,id)){
  patches.set(joined.wallId,joined.endpoint==="start"?{x1:target.x,y1:target.y}:{x2:target.x,y2:target.y});
 }
 const updated=walls.map(w=>({...w,...(patches.get(w.id)||{})}));
 for(const w of updated){
  if(![w.x1,w.y1,w.x2,w.y2].every(Number.isFinite)||length(w)<1)throw Error("Resize would collapse a connected wall");
 }
 return patches;
}
return {length,connected,planResize};
});
