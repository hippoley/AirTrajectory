// Genuine Pascal SceneGraph geometry renderer for the public Three.js studio.
// Reads local File objects only: no network upload of private homeowner coordinates.
export function loadPascalGraph(THREE, scene, graph) {
 if (!graph || !graph.nodes || !Array.isArray(graph.rootNodeIds)) throw Error('Pascal SceneGraph required');
 const nodes=Object.values(graph.nodes), zones=nodes.filter(n=>n.type==='zone'), walls=nodes.filter(n=>n.type==='wall'&&n.visible!==false);
 if(!zones.length||!walls.length)throw Error('Missing Pascal zones or walls');
 if(nodes.length>20000)throw Error('Scene exceeds 20,000 nodes');
 const group=new THREE.Group();group.name='Imported Pascal residence';scene.add(group);
 const openingsByWall=new Map();
 for(const node of nodes.filter(n=>['door','window'].includes(n.type)&&n.visible!==false)){
  const host=node.wallId||node.parentId;
  if(!host)continue;
  if(!openingsByWall.has(host))openingsByWall.set(host,[]);
  openingsByWall.get(host).push(node);
 }
 const xy=zones.flatMap(z=>z.polygon||[]);const center=[(Math.min(...xy.map(p=>p[0]))+Math.max(...xy.map(p=>p[0])))/2,(Math.min(...xy.map(p=>p[1]))+Math.max(...xy.map(p=>p[1])))/2];
 const pos=p=>[p[0]-center[0],p[1]-center[1]];
 const mesh=(w,h,d,color,x,y,z,root=group)=>{const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color,roughness:.8}));m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;root.add(m);return m};
 const floors=[];
 for(const z of zones){
  const points=(z.polygon||[]).map(p=>pos(p));if(points.length<3)continue;
  const shape=new THREE.Shape();shape.moveTo(points[0][0],-points[0][1]);points.slice(1).forEach(p=>shape.lineTo(p[0],-p[1]));
  const geometry=new THREE.ShapeGeometry(shape);const material=new THREE.MeshStandardMaterial({color:z.color||'#a98a65',side:THREE.DoubleSide,roughness:.94});
  const floor=new THREE.Mesh(geometry,material);floor.rotation.x=-Math.PI/2;floor.position.y=.025;floor.receiveShadow=true;group.add(floor);floors.push(floor);
 }
 // Build endpoint adjacency in the same world-space frame as the rendered walls.
 // Only seal a joint when the endpoint actually touches another wall centerline.
 const segmentData=walls.map(w=>{const a=pos(w.start),b=pos(w.end);
  return {id:w.id,a,b,dx:b[0]-a[0],dz:b[1]-a[1],length:Math.hypot(b[0]-a[0],b[1]-a[1]),thickness:Math.max(.06,Math.min(w.thickness||.12,.45))};
 }).filter(w=>w.length>.01);
 function sealedEnd(point,current){
  for(const other of segmentData){
   if(other.id===current.id)continue;
   const t=((point[0]-other.a[0])*other.dx+(point[1]-other.a[1])*other.dz)/(other.length*other.length);
   if(t<-.025/other.length||t>1+.025/other.length)continue;
   const q=[other.a[0]+t*other.dx,other.a[1]+t*other.dz];
   if(Math.hypot(point[0]-q[0],point[1]-q[1])>Math.min(.035,other.thickness*.35))continue;
   const cross=Math.abs(current.dx*other.dz-current.dz*other.dx)/(current.length*other.length);
   if(cross>.5)return Math.min(current.thickness,other.thickness)*.5;
  }
  return 0;
 }
 let openings=0;const wallMeshes=[];
 for(const wall of walls){
  const a=pos(wall.start),b=pos(wall.end);if(!a||!b)continue;
  const dx=b[0]-a[0],dz=b[1]-a[1],L=Math.hypot(dx,dz);if(L<.01)continue;
  const height=2.5,thick=Math.max(.06,Math.min(wall.thickness||.12,.45));
  const current=segmentData.find(w=>w.id===wall.id);
  const startCap=current?sealedEnd(a,current):0,endCap=current?sealedEnd(b,current):0;
  // Native opening positions use wall-local x coordinate, dimensions in metres.
  const holes=[...new Map([...(openingsByWall.get(wall.id)||[]),...(wall.children||[]).map(id=>graph.nodes[id]).filter(Boolean)].map(n=>[n.id,n])).values()].filter(n=>n&&['door','window'].includes(n.type)&&n.visible!==false)
    .map(n=>({lo:Math.max(0,n.position[0]-n.width/2),hi:Math.min(L,n.position[0]+n.width/2),bottom:n.type==='door'?0:Math.max(.6,n.position[1]-n.height/2),top:n.type==='door'?Math.min(height,n.height):Math.min(height,n.position[1]+n.height/2),type:n.type})).filter(h=>h.hi>h.lo);
  const boundaries=[0,L,...holes.flatMap(h=>[h.lo,h.hi])].sort((a,b)=>a-b).filter((v,i,arr)=>!i||v-arr[i-1]>.001);
  const addSection=(x0,x1,y0,y1,color)=>{if(x1-x0<.01||y1-y0<.01)return;
    const t=(x0+x1)/2/L,X=(a[0]+dx*t),Z=(a[1]+dz*t);
    const extraStart=x0<.001?startCap:0,extraEnd=x1>L-.001?endCap:0;
    // Extend solely solid ends into perpendicular touching walls; do not bridge openings.
    const m=mesh(x1-x0+extraStart+extraEnd,y1-y0,thick,color,
      X+(extraEnd-extraStart)*dx/(2*L),(y0+y1)/2,
      Z+(extraEnd-extraStart)*dz/(2*L));
    m.rotation.y=-Math.atan2(dz,dx);wallMeshes.push(m)};
  for(let i=1;i<boundaries.length;i++){
   const lo=boundaries[i-1],hi=boundaries[i],mid=(lo+hi)/2;
   const covering=holes.filter(h=>h.lo<=mid&&h.hi>=mid);
   if(!covering.length)addSection(lo,hi,0,height,'#e9e6df');
   else{let intervals=covering.map(h=>[h.bottom,h.top]).sort((a,b)=>a[0]-b[0]),cursor=0;
     for(const [y0,y1] of intervals){if(y0>cursor)addSection(lo,hi,cursor,y0,'#e9e6df');cursor=Math.max(cursor,y1)}
     if(cursor<height)addSection(lo,hi,cursor,height,'#e9e6df');
   }
  }
  for(const h of holes){
   openings++;
   const width=h.hi-h.lo,high=h.top-h.bottom;
   const t=(h.lo+h.hi)/2/L,X=a[0]+dx*t,Z=a[1]+dz*t;
   const angle=-Math.atan2(dz,dx),frameWidth=Math.min(.07,width*.08,high*.08);
   if(h.type==='window'){
    const glass=mesh(width,high,.022,'#8cbac9',X,(h.top+h.bottom)/2,Z);
    glass.material.transparent=true;glass.material.opacity=.27;glass.material.depthWrite=false;glass.rotation.y=angle;
    // Actual frame and sash members in the same wall coordinate frame.
    for(const side of [-1,1]){
     const edge=mesh(frameWidth,high,thick+.025,'#d7dee0',
       X+Math.cos(angle)*side*(width-frameWidth)/2,(h.top+h.bottom)/2,
       Z-Math.sin(angle)*side*(width-frameWidth)/2);
     edge.rotation.y=angle;
    }
    for(const y of [h.bottom+frameWidth/2,h.top-frameWidth/2]){
     const rail=mesh(width,frameWidth,thick+.025,'#d7dee0',X,y,Z);rail.rotation.y=angle;
    }
    const middle=mesh(Math.min(.035,frameWidth),high,.04,'#d7dee0',X,(h.top+h.bottom)/2,Z);middle.rotation.y=angle;
   }else if(h.type==='door'){
    // Show the door leaf in its native host opening rather than an unexplained wall gap.
    const door=mesh(Math.max(.05,width-.09),Math.max(.2,high-.07),Math.min(.048,thick*.6),'#a88968',X,h.bottom+high/2,Z);
    door.rotation.y=angle;door.userData.pascalOpeningType='door';
    const handle=mesh(.10,.035,.055,'#b3a992',
      X+Math.cos(angle)*width*.32,h.bottom+Math.min(1.02,high*.55),
      Z-Math.sin(angle)*width*.32);
    handle.rotation.y=angle;
   }
  }
 }
 const furniture=[];
 for(const n of nodes.filter(n=>n.type==='procedural-item'&&n.visible!==false)){
  const root=new THREE.Group(),[x,z]=pos([n.position[0],n.position[2]]);
  root.name=n.name||n.id;root.position.set(x,n.position[1]||0,z);root.rotation.y=n.rotation?.[1]||0;if(Array.isArray(n.scale)&&n.scale.length===3)root.scale.set(...n.scale);group.add(root);
  const slots=Object.fromEntries((n.recipe?.slots||[]).map(s=>[s.id,s.color||'#b7a797']));
  for(const part of n.recipe?.parts||[])for(const shape of part.shapes||[]){
   if(shape.primitive!=='box'||!Array.isArray(shape.size))continue;
   const [w,h,d]=shape.size;if(![w,h,d].every(v=>Number.isFinite(v)&&v>0&&v<10))continue;
   const [px,py,pz]=shape.position||[0,h/2,0];
   const piece=mesh(w,h,d,slots[shape.slot]||'#b8b0a1',px,py,pz,root);
   piece.userData.pascalMaterialSlot=shape.slot||null;
  }
  root.userData={id:n.id,type:'pascal',name:n.name||n.id,color:Object.values(slots)[0]||'#b7a797',paintSlot:(n.recipe?.slots||[])[0]?.id||null,rotation:root.rotation.y,scale:root.scale.x,pascalNode:n};furniture.push(root);
 }
 return {group,walls:wallMeshes,floors,furniture,stats:{rooms:zones.length,walls:walls.length,openings,furniture:furniture.length},center};
}
