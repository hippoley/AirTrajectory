/* Native Pascal SceneGraph engineering readiness audit. Never infer physical adjacency. */
'use strict';
const {nodesOf}=require('../integrations/pascal-studio/pascal-scene-bridge.cjs');
function audit(scene){
 const nodes=nodesOf(scene),issues=[],ids=new Set(),count={};
 const push=(node,field,reason)=>issues.push({node_id:node.id,kind:node.type,field,reason});
 for(const n of nodes){
  if(!n||typeof n!=='object'||typeof n.id!=='string'||ids.has(n.id))throw Error('Invalid/duplicate native node ID');
  ids.add(n.id);count[n.type]=(count[n.type]||0)+1;
 }
 const rooms=nodes.filter(n=>n.type==='zone');
 const roomIds=new Set(rooms.map(n=>n.id));
 for(const z of rooms){
  if(z.spaceRole!=='room'&&z.metadata?.airtrajectory_space_role!=='room')push(z,'spaceRole','architectural room classification needs review');
  if(!Array.isArray(z.polygon)||z.polygon.length!==4||z.polygon.some(p=>!Array.isArray(p)||p.length!==2||p.some(v=>!Number.isFinite(v))))push(z,'polygon','LayoutContract v0.1 requires rectangular metric polygons');
  if(!(z.metadata?.airtrajectory_height_m>0))push(z,'metadata.airtrajectory_height_m','approved height missing');
  if(!(z.metadata?.airtrajectory_volume_m3>0))push(z,'metadata.airtrajectory_volume_m3','approved volume missing');
 }
 const walls=nodes.filter(n=>n.type==='wall'),wallMap=new Map(walls.map(w=>[w.id,w]));
 for(const w of walls){
  const m=w.metadata||{};
  if(!roomIds.has(m.airtrajectory_source_room))push(w,'metadata.airtrajectory_source_room','reviewed source zone missing');
  if(!roomIds.has(m.airtrajectory_target_room)&&m.airtrajectory_target_room!=='OUTSIDE')push(w,'metadata.airtrajectory_target_room','reviewed target zone/OUTSIDE missing');
 }
 for(const o of nodes.filter(n=>n.type==='door'||n.type==='window')){
  const host=wallMap.get(o.wallId);
  if(!host)push(o,'wallId','opening host missing');
  if(!(o.width>0&&o.height>0))push(o,'width/height','positive dimensions missing');
  if(!(typeof o.metadata?.airtrajectory_sill_height_m==='number'&&Number.isFinite(o.metadata.airtrajectory_sill_height_m)&&o.metadata.airtrajectory_sill_height_m>=0))push(o,'metadata.airtrajectory_sill_height_m','reviewed sill elevation missing');
  const offset=Array.isArray(o.position)?o.position[0]:undefined;
  const t=o.metadata?.airtrajectory_position_t;
  if(offset===undefined&&!(typeof t==='number'&&t>=0&&t<=1))push(o,'position','wall-local metric offset or reviewed normalized position missing');
  if(host&&typeof offset==='number'){
   const length=Math.hypot(host.end?.[0]-host.start?.[0],host.end?.[1]-host.start?.[1]);
   if(!Number.isFinite(offset)||offset<0||!Number.isFinite(length)||length<=0||offset>length)push(o,'position[0]','native wall-local offset outside wall bounds');
  }
 }
 return {schema_version:'0.1',status:issues.length?'PHYSICAL_REVIEW_REQUIRED':'ANNOTATIONS_READY_FOR_LAYOUT_VALIDATION',
   node_counts:count,node_count:nodes.length,issues:issues.sort((a,b)=>a.node_id.localeCompare(b.node_id)||a.field.localeCompare(b.field)),
   engineering_truth:false};
}
module.exports={audit};
if(require.main===module){
 const fs=require('node:fs'),crypto=require('node:crypto');
 const [source,dest]=process.argv.slice(2);
 if(!source||!dest)throw Error('Usage: node scripts/audit-pascal-native-scene.cjs scene.json review.json');
 const bytes=fs.readFileSync(source),output=audit(JSON.parse(bytes.toString('utf8')));
 output.source_sha256=crypto.createHash('sha256').update(bytes).digest('hex');
 fs.mkdirSync(require('node:path').dirname(dest),{recursive:true});
 fs.writeFileSync(dest,JSON.stringify(output,null,2)+'\n');
 console.log(JSON.stringify({status:output.status,issues:output.issues.length,source_sha256:output.source_sha256}));
}
