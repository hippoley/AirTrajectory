// Extract 2D architectural skeleton directly from an uploaded DXF document.
// Raw architectural outlines are evidence, not yet inferred wall centre-lines.
const LAYERS={'J-隔墙':'wall','J-窗':'window','P-门':'door','P-门套':'doorFrame'};
function points(entity){
 if(entity.type==='LINE')return (entity.vertices||[]).map(p=>[p.x,p.y]);
 if(entity.type==='LWPOLYLINE'||entity.type==='POLYLINE')return (entity.vertices||[]).map(p=>[p.x,p.y]);
 if(entity.type==='ARC'){
  const c=entity.center,r=entity.radius;if(!c||!(r>0))return [];
  let a=entity.startAngle,b=entity.endAngle;
  if(b<a)b+=360;
  const n=Math.max(6,Math.ceil((b-a)/6)),p=[];
  for(let i=0;i<=n;i++){const t=(a+(b-a)*i/n)*Math.PI/180;p.push([c.x+Math.cos(t)*r,c.y+Math.sin(t)*r])}
  return p;
 }
 return [];
}
export function extractArchitecturalSkeleton(doc){
 const raw={wall:[],window:[],door:[],doorFrame:[]},all=[];
 for(const e of doc.entities||[]){
  const group=LAYERS[e.layer];if(!group)continue;
  const p=points(e);if(p.length<2||!p.every(a=>a.every(Number.isFinite)))continue;
  const closed=!!(e.shape||e.closed||e.type==='LWPOLYLINE'&&Math.hypot(p[0][0]-p[p.length-1][0],p[0][1]-p[p.length-1][1])<.001);
  raw[group].push({id:group+'-'+raw[group].length,points:p,closed,kind:e.type});all.push(...p);
 }
 if(!all.length)throw Error('No architectural lines found in DXF');
 const minX=Math.min(...all.map(p=>p[0])),minY=Math.min(...all.map(p=>p[1]));
 const maxX=Math.max(...all.map(p=>p[0])),maxY=Math.max(...all.map(p=>p[1]));
 const units=doc.header?.$INSUNITS;
 const scale=units===4?.001:units===6?1:units===1?.0254:units===2?.3048:.001;
 const geometry={};
 for(const [kind,entries] of Object.entries(raw))geometry[kind]=entries.map(e=>({
  ...e,points:e.points.map(p=>[+((p[0]-minX)*scale).toFixed(4),+((p[1]-minY)*scale).toFixed(4)])
 }));
 return {version:1,units:'m',origin:'local-anonymous',geometry,
  bounds:{width:+((maxX-minX)*scale).toFixed(4),height:+((maxY-minY)*scale).toFixed(4)}};
}
