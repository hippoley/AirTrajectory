// 2D-first linework noding: intersections become real shared wall vertices
// before the editor SceneGraph is extruded into 3D. Pure JS, no Three dependency.
const EPS=1e-6;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const point=(a,b,t)=>[+(a[0]+(b[0]-a[0])*t).toFixed(6),+(a[1]+(b[1]-a[1])*t).toFixed(6)];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1];
const cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
export function nodeFloorplanSegments(lines,openings=[]){
 const segments=lines.map(line=>{
  const v=[line.end[0]-line.start[0],line.end[1]-line.start[1]],L=Math.hypot(...v);
  if(L<EPS)throw Error('Zero-length floorplan line: '+line.id);
  return {...line,v,L,cut:[0,1],doors:openings.filter(o=>o.wallId===line.id)};
 });
 // Every centerline intersection belongs to both wall edges, not two floating boxes.
 for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
  const a=segments[i],b=segments[j],q=[b.start[0]-a.start[0],b.start[1]-a.start[1]];
  const den=cross(a.v,b.v);if(Math.abs(den)<EPS)continue;
  const t=cross(q,b.v)/den,u=cross(q,a.v)/den;
  if(t>=-EPS&&t<=1+EPS&&u>=-EPS&&u<=1+EPS){
   if(t>EPS&&t<1-EPS)a.cut.push(t);
   if(u>EPS&&u<1-EPS)b.cut.push(u);
  }
 }
 const out=[],mapped=[];
 for(const line of segments){
  const cuts=[...new Set(line.cut.map(t=>clamp(t,0,1).toFixed(6)))].map(Number).sort((a,b)=>a-b);
  for(let i=1;i<cuts.length;i++){
   const t0=cuts[i-1],t1=cuts[i];if((t1-t0)*line.L<.01)continue;
   const id=line.id+'-part-'+(i-1);
   out.push({id,type:'wall',start:point(line.start,line.end,t0),end:point(line.start,line.end,t1),thickness:line.thickness,editorRole:line.editorRole,visible:true,children:[]});
  }
  // Place windows and doors using their true 2D positions on original 2D lines.
  for(const o of line.doors){
   const center=o.offset,lo=center-o.width/2,hi=center+o.width/2;
   if(lo<0||hi>line.L)throw Error('Opening outside 2D wall: '+o.id);
   // Prevent noding *through* an aperture. Such a plan must be corrected upstream.
   for(const t of cuts.slice(1,-1))if(t*line.L>lo+EPS&&t*line.L<hi-EPS)
    throw Error('2D wall intersection crosses an opening: '+o.id);
   const target=out.find(w=>w.id.startsWith(line.id+'-part-')&&
     dot([w.start[0]-line.start[0],w.start[1]-line.start[1]],line.v)/(line.L*line.L)*line.L<=lo+EPS&&
     dot([w.end[0]-line.start[0],w.end[1]-line.start[1]],line.v)/(line.L*line.L)*line.L>=hi-EPS);
   if(!target)throw Error('Opening spans split wall: '+o.id);
   const startOffset=dot([target.start[0]-line.start[0],target.start[1]-line.start[1]],line.v)/line.L;
   mapped.push({id:o.id,type:o.type,wallId:target.id,parentId:target.id,position:[+(center-startOffset).toFixed(6),o.y,0],width:o.width,height:o.height,visible:true});
   target.children.push(o.id);
  }
 }
 return {walls:out,openings:mapped};
}
