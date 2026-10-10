// Browser-only original DXF loader. No CAD upload, no lossy guessed rooms.
// All real geometries are drawn on the XZ floor plane with their source layers.
const ACCEPTED=new Set(['LINE','LWPOLYLINE','POLYLINE','ARC','CIRCLE']);
const PALETTE={'J-隔墙':'#e5dcd1','J-窗':'#64c4e0','P-门':'#dbab76','P-门套':'#c89572','P-固定家具到顶':'#b7afc9','P-活动家具':'#91d2aa'};
function coords(ent){
 if(ent.type==='LINE'){
  const pts=ent.vertices||[];if(pts.length>=2)return [pts.map(p=>[p.x,p.y])];return [];
 }
 if(ent.type==='LWPOLYLINE'||ent.type==='POLYLINE'){
  const pts=(ent.vertices||[]).map(p=>[p.x,p.y]);
  if(pts.length<2)return [];if(ent.shape||ent.closed)pts.push([...pts[0]]);
  return [pts];
 }
 if(ent.type==='CIRCLE'||ent.type==='ARC'){
  const c=ent.center;if(!c)return [];const r=ent.radius;if(!Number.isFinite(r)||r<=0)return [];
  let a0=ent.type==='CIRCLE'?0:ent.startAngle, a1=ent.type==='CIRCLE'?360:ent.endAngle;
  if(!Number.isFinite(a0)||!Number.isFinite(a1))return [];
  // dxf-parser emits arc angles in degrees.
  if(a1<a0)a1+=360;
  const count=Math.max(8,Math.ceil((a1-a0)/8)),p=[];
  for(let i=0;i<=count;i++){const a=(a0+(a1-a0)*i/count)*Math.PI/180;p.push([c.x+Math.cos(a)*r,c.y+Math.sin(a)*r])}
  return [p];
 }
 return [];
}
export async function loadLocalDxf(THREE, scene, file){
 if(!file||!file.name.toLowerCase().endsWith('.dxf'))throw Error('请选择 DXF 文件');
 if(file.size>30000000)throw Error('DXF 超过浏览器导入上限 30MB');
 const {default:DxfParser}=await import('https://cdn.jsdelivr.net/npm/dxf-parser@1.1.2/+esm');
 const parser=new DxfParser(),doc=parser.parseSync(await file.text());
 const all=[],layers=new Map(),stats={};
 for(const ent of doc.entities||[]){
  if(!ACCEPTED.has(ent.type))continue;
  const polylines=coords(ent);if(!polylines.length)continue;
  const name=ent.layer||'0';
  if(!layers.has(name))layers.set(name,[]);
  for(const points of polylines){
   if(points.some(p=>!p.every(Number.isFinite)))continue;
   all.push(...points);layers.get(name).push(points);
  }
  stats[name]=(stats[name]||0)+1;
 }
 if(!all.length)throw Error('DXF 没有可读取的基础线条');
 const minX=Math.min(...all.map(p=>p[0])),maxX=Math.max(...all.map(p=>p[0]));
 const minY=Math.min(...all.map(p=>p[1])),maxY=Math.max(...all.map(p=>p[1]));
 // Original file is authored in millimetres (DXF INSUNITS=4); convert to metres.
 const units=doc.header?.$INSUNITS;
 const scale=units===4?.001:units===6?1:units===1?.0254:units===2?.3048:.001;
 const length=Math.max(maxX-minX,maxY-minY)*scale;
 if(length>3000||length<.01)throw Error('CAD 坐标尺寸异常，请检查 DXF 单位');
 const centerX=(minX+maxX)/2,centerY=(minY+maxY)/2;
 const group=new THREE.Group();group.name='PRIVATE DXF · native CAD layers';
 // Entire CAD is retained in its source dimensional proportions (no 6-room reconstruction).
 const materials=[],entries=[];
 try{
  for(const [name,paths] of layers){
   const positions=[];
   for(const path of paths)for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i];
    positions.push((a[0]-centerX)*scale,.10,-(a[1]-centerY)*scale,(b[0]-centerX)*scale,.10,-(b[1]-centerY)*scale);
   }
   if(!positions.length)continue;
   const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
   const material=new THREE.LineBasicMaterial({color:PALETTE[name]||'#8495a4',depthTest:false,transparent:true,opacity:.94});materials.push(material);
   const lines=new THREE.LineSegments(geo,material);lines.name=name;lines.renderOrder=10;group.add(lines);entries.push({name,object:lines,count:stats[name]||0,color:PALETTE[name]||'#8495a4'});
  }
  scene.add(group);
 }catch(e){group.traverse(o=>o.geometry?.dispose());materials.forEach(m=>m.dispose());throw e}
 return {group,entries,stats:{entities:doc.entities?.length||0,visible:entries.reduce((n,e)=>n+e.count,0),layers:entries.length,width:(maxX-minX)*scale,height:(maxY-minY)*scale,units},dispose(){
  scene.remove(group);group.traverse(o=>o.geometry?.dispose());materials.forEach(m=>m.dispose())
 }};
}
