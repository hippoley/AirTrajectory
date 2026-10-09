/*
 * Adapted from RobinWeitzel/floor-planner src/core/geometry.ts
 * License: MIT (see upstream package.json). Preserve this notice.
 * https://github.com/RobinWeitzel/floor-planner
 * Changes: framework-free browser/Node module with nearest segment and snapping helpers.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.AirTrajectorySnapGeometry=api;
})(typeof globalThis==="object"?globalThis:null,function(){
  "use strict";
  function nearestPointOnSegment(point,start,end){
    const dx=end.x-start.x,dy=end.y-start.y,lenSq=dx*dx+dy*dy;
    if(!lenSq)return {x:start.x,y:start.y};
    let t=((point.x-start.x)*dx+(point.y-start.y)*dy)/lenSq;
    t=Math.max(0,Math.min(1,t));
    return {x:start.x+t*dx,y:start.y+t*dy};
  }
  function distanceToSegment(point,start,end){
    const q=nearestPointOnSegment(point,start,end);
    return Math.hypot(point.x-q.x,point.y-q.y);
  }
  function snapEndpoint(point,walls,tolerance=12){
    let best=null;
    for(const w of walls){
      for(const endpoint of [{x:+w.x1,y:+w.y1},{x:+w.x2,y:+w.y2}]){
        const distance=Math.hypot(point.x-endpoint.x,point.y-endpoint.y);
        if(distance<=tolerance&&(!best||distance<best.distance))best={...endpoint,distance,wall_id:w.id};
      }
    }
    return best||{...point,distance:null,wall_id:null};
  }
  return {nearestPointOnSegment,distanceToSegment,snapEndpoint};
});
