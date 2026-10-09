/*
 * Adapted from openPlan3D src/lib/utils/wallProjection.ts.
 * Copyright (c) 2026 theLodgeStudio. MIT License.
 * Upstream: https://github.com/laanlabs/openPlan3D
 * Changes: dependency-free browser/Node API and AirTrajectory wall coordinates.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(root)root.AirTrajectoryWallGeometry=api;
})(typeof globalThis==="object"?globalThis:null,function(){
  "use strict";
  function roots(coeff,lo,hi){
    const scale=Math.max(...coeff.map(Math.abs));
    if(!scale)return [];
    const c=coeff.map(v=>v/scale);
    while(c.length>1&&Math.abs(c[0])<1e-14)c.shift();
    if(c.length===1)return [];
    const evaluate=t=>c.reduce((v,x)=>v*t+x,0);
    const derivative=c.slice(0,-1).map((v,i)=>v*(c.length-1-i));
    const knots=[lo,...roots(derivative,lo,hi),hi];
    const result=knots.filter(t=>Math.abs(evaluate(t))<1e-12);
    for(let i=1;i<knots.length;i++){
      let a=knots[i-1],b=knots[i],fa=evaluate(a);
      if(fa*evaluate(b)>=0)continue;
      for(let step=0;step<60;step++){
        const mid=(a+b)/2,fm=evaluate(mid);
        if(fa*fm<=0)b=mid;else{a=mid;fa=fm;}
      }
      result.push((a+b)/2);
    }
    return [...new Set(result)].sort((a,b)=>a-b);
  }
  function projectOntoWall(point,wall,min=0,max=1){
    if(!point||!wall||!(min>=0&&max<=1&&min<=max))return null;
    const start={x:Number(wall.x1),y:Number(wall.y1)};
    const end={x:Number(wall.x2),y:Number(wall.y2)};
    const control=wall.curvePoint||{x:(start.x+end.x)/2,y:(start.y+end.y)/2};
    const a={x:start.x-2*control.x+end.x,y:start.y-2*control.y+end.y};
    const b={x:2*(control.x-start.x),y:2*(control.y-start.y)};
    const d={x:start.x-point.x,y:start.y-point.y};
    if(![a.x,a.y,b.x,b.y,d.x,d.y].every(Number.isFinite)||Math.hypot(a.x,a.y,b.x,b.y)<1)return null;
    const dot=(u,v)=>u.x*v.x+u.y*v.y;
    const candidates=[min,max,...roots([2*dot(a,a),3*dot(a,b),dot(b,b)+2*dot(a,d),dot(b,d)],min,max)];
    let result=null;
    for(const t of candidates){
      const distance=Math.hypot(a.x*t*t+b.x*t+d.x,a.y*t*t+b.y*t+d.y);
      if(!result||distance<result.distance)result={position:t,distance};
    }
    return result;
  }
  return {projectOntoWall};
});
