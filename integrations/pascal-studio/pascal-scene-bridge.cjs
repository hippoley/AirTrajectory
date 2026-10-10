/*
 * Pascal (pascalorg/editor MIT) SceneNodes -> AirTrajectory LayoutContract v0.1.
 * Schema mapping is based on native ZoneNode, WallNode, WindowNode and DoorNode.
 * Explicit metadata is required for physical zone adjacency; never infer airflow
 * connectivity from visual closeness, facing, or topological direction.
 */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.AirTrajectoryPascalBridge=api;})(typeof globalThis==="object"?globalThis:null,function(){
"use strict";
const hex64=x=>typeof x==="string"&&/^[0-9a-f]{64}$/i.test(x);
const positive=x=>typeof x==="number"&&Number.isFinite(x)&&x>0;
function nodesOf(scene){
 const raw=scene?.nodes||scene?.state?.nodes||scene;
 if(!raw||typeof raw!=="object"||Array.isArray(raw))throw Error("Pascal SceneNodes record required");
 return Object.values(raw);
}
function exportLayout(scene,options={}){
 const nodes=nodesOf(scene),byId=new Map();
 for(const n of nodes){if(!n||typeof n!=="object"||typeof n.id!=="string"||byId.has(n.id))throw Error("Invalid/duplicate Pascal node ID");byId.set(n.id,n);}
 if(!hex64(options.source_sha256))throw Error("Require SHA-256 of the original exported Pascal scene");
 const zones=nodes.filter(n=>n.type==="zone"&&n.spaceRole==="room");
 if(!zones.length)throw Error("No architectural room zones; cannot infer from visible floor mesh");
 const rooms=zones.map(n=>{
  const coords=n.polygon;
  if(!Array.isArray(coords)||coords.length<3||coords.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)))throw Error("Zone "+n.id+" has invalid polygon");
  // Rectangular contract only; nonrectangular zones require explicit conversion approval.
  const xs=[...new Set(coords.map(p=>p[0]))].sort((a,b)=>a-b),ys=[...new Set(coords.map(p=>p[1]))].sort((a,b)=>a-b);
  if(xs.length!==2||ys.length!==2||coords.length!==4)throw Error("Zone "+n.id+" not rectangular; geometry adapter required");
  const w=xs[1]-xs[0],h=ys[1]-ys[0];
  const height=n.metadata?.airtrajectory_height_m,volume=n.metadata?.airtrajectory_volume_m3;
  if(!positive(height)||!positive(volume)||!positive(w)||!positive(h))throw Error("Zone "+n.id+" lacks approved metric height/volume");
  return {id:n.id,name:n.name||n.id,x:Math.min(...xs)*100,y:Math.min(...ys)*100,w:w*100,h:h*100,volume_m3:volume};
 });
 const roomIds=new Set(rooms.map(r=>r.id)),outside="OUTSIDE";
 const walls=nodes.filter(n=>n.type==="wall").map(n=>{
  if(!Array.isArray(n.start)||!Array.isArray(n.end)||n.start.length!==2||n.end.length!==2||![...n.start,...n.end].every(Number.isFinite))throw Error("Wall "+n.id+" has invalid endpoints");
  const meta=n.metadata||{},source=meta.airtrajectory_source_room,target=meta.airtrajectory_target_room;
  if(!roomIds.has(source)||!(roomIds.has(target)||target===outside)||source===target)throw Error("Wall "+n.id+" needs explicit verified source/target rooms");
  const distance=Math.hypot(n.end[0]-n.start[0],n.end[1]-n.start[1]);
  if(!positive(distance))throw Error("Wall "+n.id+" has zero length");
  return {id:n.id,kind:target===outside?"exterior":"internal",source,target,x1:n.start[0]*100,y1:n.start[1]*100,x2:n.end[0]*100,y2:n.end[1]*100,length_m:distance,azimuth_deg:(Math.atan2(n.end[1]-n.start[1],n.end[0]-n.start[0])*180/Math.PI+360)%360};
 });
 const wallById=new Map(walls.map(w=>[w.id,w]));
 const openings=nodes.filter(n=>n.type==="window"||n.type==="door").map(n=>{
  const host=wallById.get(n.wallId);
  if(!host)throw Error("Opening "+n.id+" has no supported wall host");
  const meta=n.metadata||{};
  if(!positive(n.width)||!positive(n.height))throw Error("Opening "+n.id+" requires physical width and height");
  // Pascal wall children are face-local. Exact normalized t requires explicit
  // semantic export, rather than guessing from the node's 3D position tuple.
  const t=meta.airtrajectory_position_t;
  const sill=meta.airtrajectory_sill_height_m;
  if(typeof sill!=="number"||!Number.isFinite(sill)||sill<0)throw Error("Opening "+n.id+" needs verified sill height in metres");
  if(typeof t!=="number"||!Number.isFinite(t)||t<0||t>1)throw Error("Opening "+n.id+" needs verified normalized wall position");
  if(n.type==="window"&&host.target!==outside)throw Error("Exterior window "+n.id+" hosted on interior wall");
  return {id:n.id,kind:n.type,wall_id:host.id,source:host.source,target:host.target,position_t:t,initial_open_pct:0,
   max_area_m2:n.width*n.height,width_m:n.width,height_m:n.height,sill_height_m:sill,render_side:"imported",position_editable:true,state_editable:true};
 });
 const result={schema_version:"0.1",topology_id:options.topology_id||"pascal-import-v1",source_kind:"imported-floorplan",
  outside_id:outside,source_provenance:{format:"Pascal SceneNodes",source_sha256:options.source_sha256,importer:"airtrajectory-pascal-scene-bridge-v0.1"},
  capabilities:{floorplan_geometry_editable:true,opening_position_editable:true,opening_state_editable:true,arbitrary_topology_import:"supported",contam_compiler:"reserved"},
  canvas:{width:1100,height:650},rooms,walls,openings,compiler_contract:{current_consumers:["web-ui","trajectory-context"],reserved_consumers:["contam-layout-compiler"],note:"Visual scene imported with explicit geometry/adjacency evidence; no engineering solver authorization."}};
 return result;
}
return {exportLayout,nodesOf};
});