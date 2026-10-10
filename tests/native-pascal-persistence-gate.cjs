#!/usr/bin/env node
// Real Pascal REST/SQLite save->process restart->reload integration evidence.
// Called in two separate processes on opposite sides of a production app restart.
'use strict';
const fs=require('node:fs');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const [phase,graphFile,evidenceDir]=process.argv.slice(2);
if(!['before','after'].includes(phase)||!graphFile||!evidenceDir)throw Error('Usage: node native-pascal-persistence-gate.cjs before|after native-graph.json evidence-dir');
const base=process.env.PASCAL_NATIVE_URL||'http://127.0.0.1:3002';
const sceneId=process.env.PASCAL_GATE_SCENE_ID||'airtrajectory-persistence-ci';
const sha=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const filename=evidenceDir+'/native-scene-before.json';
const project='airtrajectory-native-persistence-gate';
async function api(url,options){
 const resp=await fetch(base+url,options);
 const body=await resp.json().catch(()=>null);
 if(!resp.ok)throw Error(url+' HTTP '+resp.status+' '+JSON.stringify(body).slice(0,1000));
 return body;
}
function canonical(graph){
 assert(graph&&typeof graph==='object'&&graph.nodes&&typeof graph.nodes==='object','missing scene graph');
 const nodes=Object.fromEntries(Object.entries(graph.nodes).sort(([a],[b])=>a.localeCompare(b)).map(([id,n])=>{
   assert.equal(n.id,id,'node map key/id mismatch');
   return [id,{id:n.id,type:n.type,parentId:n.parentId??null,position:n.position??null,
      start:n.start??null,end:n.end??null,polygon:n.polygon??null,wallId:n.wallId??null,
      width:n.width??null,height:n.height??null,children:n.children??null}];
 }));
 const counts={}; for(const n of Object.values(nodes))counts[n.type]=(counts[n.type]||0)+1;
 assert((counts.wall||0)>=4&&(counts.window||0)>=1&&(counts.door||0)>=1&&(counts.zone||0)>=2,'template lacks walls/windows/doors/zones');
 return {nodes,rootNodeIds:graph.rootNodeIds,counts};
}
(async()=>{
 fs.mkdirSync(evidenceDir,{recursive:true});
 if(phase==='before'){
   const graph=JSON.parse(fs.readFileSync(graphFile,'utf8'));
   const expected=canonical(graph);
   // Unique ephemeral scene; collision is a hard failure, not destructive replacement.
   const created=await api('/api/scenes',{method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({id:sceneId,name:'AirTrajectory Persistence Gate',projectId:project,graph})});
   assert.equal(created.id,sceneId,'created scene ID mismatch');
   const loaded=await api('/api/scenes/'+encodeURIComponent(sceneId));
   assert.deepEqual(canonical(loaded.graph),expected,'saved graph differs on first GET');
   fs.writeFileSync(filename,JSON.stringify({scene_id:sceneId,version:loaded.version,
      graph_sha256:sha(expected),canonical:expected},null,2));
   console.log(JSON.stringify({status:'PERSISTED_PRE_RESTART',scene_id:sceneId,nodes:Object.keys(expected.nodes).length,graph_sha256:sha(expected)}));
 }else{
   const before=JSON.parse(fs.readFileSync(filename,'utf8'));
   assert.equal(before.scene_id,sceneId,'scene ID drift');
   const loaded=await api('/api/scenes/'+encodeURIComponent(sceneId));
   const actual=canonical(loaded.graph);
   assert.deepEqual(actual,before.canonical,'native node geometry/IDs drifted after process restart');
   assert.equal(sha(actual),before.graph_sha256,'canonical content hash mismatch');
   const receipt={status:'NATIVE_REST_SQLITE_RESTART_ROUNDTRIP_VERIFIED',
      scene_id:sceneId,node_count:Object.keys(actual.nodes).length,
      node_types:actual.counts,version_before:before.version,version_after:loaded.version,
      scene_graph_sha256:before.graph_sha256,backend:'Pascal native REST and SQLite',
      browser_draw_verified:false,container_restart_verified:false};
   fs.writeFileSync(evidenceDir+'/native-persistence-receipt.json',JSON.stringify(receipt,null,2));
   console.log(JSON.stringify(receipt));
 }
})().catch(e=>{console.error('PERSISTENCE_GATE_BLOCKED',e.stack||e);process.exitCode=1});
