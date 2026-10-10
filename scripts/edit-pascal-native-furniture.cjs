#!/usr/bin/env node
/** Actual native Pascal procedural furniture move/paint + versioned persistence. */
'use strict';
const fs=require('node:fs');
function edit(graph,changes){
 const out=structuredClone(graph);
 for(const c of changes){
  const n=out.nodes[c.nodeId];
  if(n?.type!=='procedural-item')throw Error('Not native procedural furniture: '+c.nodeId);
  if(c.position!==undefined){
   if(!Array.isArray(c.position)||c.position.length!==3||!c.position.every(Number.isFinite)||c.position[1]!==0)throw Error('Bad floor position');
   n.position=[...c.position];
  }
  if(c.rotationY!==undefined){
   if(!Number.isFinite(c.rotationY))throw Error('Bad rotation');n.rotation=[0,c.rotationY,0];
  }
  if(c.slot!==undefined||c.color!==undefined){
   if(!/^#[0-9a-fA-F]{6}$/.test(c.color||''))throw Error('Bad color');
   const slot=n.recipe?.slots?.find(s=>s.id===c.slot);
   if(!slot)throw Error('Unknown Paint recipe slot '+c.slot);
   slot.color=c.color;
  }
 }
 for(const [id,n] of Object.entries(out.nodes)){
  if(n.parentId!=null&&!out.nodes[n.parentId])throw Error('Broken parent '+id);
  for(const kid of n.children||[])if(out.nodes[kid]?.parentId!==id)throw Error('Broken child '+id);
  if(['door','window'].includes(n.type)&&(!out.nodes[n.wallId]?.children?.includes(id)||n.parentId!==n.wallId))throw Error('Broken opening '+id);
  if(!changes.some(c=>c.nodeId===id)&&JSON.stringify(graph.nodes[id])!==JSON.stringify(n))throw Error('Unintended architecture mutation: '+id);
 }
 return out;
}
async function saveToPascal({baseUrl,sceneId,changes,fetcher=fetch}){
 const url=baseUrl.replace(/\/$/,'')+'/api/scenes/'+encodeURIComponent(sceneId);
 const read=await fetcher(url);if(!read.ok)throw Error('Native GET '+read.status);
 const current=await read.json();if(!Number.isInteger(current.version))throw Error('Scene missing native version');
 const updated=edit(current.graph,changes);
 const put=await fetcher(url,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':'"'+current.version+'"'},
  body:JSON.stringify({graph:updated,expectedVersion:current.version})});
 if(!put.ok)throw Error('Native optimistic-concurrency PUT '+put.status+': '+(await put.text()).slice(0,400));
 const verify=await fetcher(url);if(!verify.ok)throw Error('Native reload '+verify.status);
 const after=await verify.json();for(const c of changes){
  if(JSON.stringify(after.graph.nodes[c.nodeId])!==JSON.stringify(updated.nodes[c.nodeId]))throw Error('Native persistence drift: '+c.nodeId);
 }
 if(Object.keys(after.graph.nodes).length!==Object.keys(current.graph.nodes).length)throw Error('Node count changed');
 return {status:'NATIVE_FURNITURE_SAVED_AND_RELOADED',sceneId,previousVersion:current.version,newVersion:after.version,changedNodes:changes.map(c=>c.nodeId)};
}
if(require.main===module)(async()=>{
 const [mode,source,edits,destination]=process.argv.slice(2);
 if(!mode||!source||!edits||!destination)throw Error('Usage: node scripts/edit-pascal-native-furniture.cjs local scene.json edits.json new.json | native http://localhost:3002 edits.json scene-id');
 const changes=JSON.parse(fs.readFileSync(edits));
 if(!Array.isArray(changes)||!changes.length)throw Error('Empty furniture edits');
 if(mode==='local'){
  if(source===destination)throw Error('Do not overwrite source');
  const graph=edit(JSON.parse(fs.readFileSync(source)),changes);
  fs.writeFileSync(destination,JSON.stringify(graph,null,2)+'\n');
  console.log('NATIVE_FURNITURE_EDITED',changes.map(c=>c.nodeId).join(','));
 }else if(mode==='native')console.log(JSON.stringify(await saveToPascal({baseUrl:source,changes,sceneId:destination}),null,2));
 else throw Error('Unknown mode');
})().catch(e=>{console.error(e.message);process.exitCode=1});
module.exports={edit,saveToPascal};
