#!/usr/bin/env node
/**
 * Import an existing Pascal SceneGraph to Pascal's NATIVE /api/scenes store.
 * No parallel editor, no custom renderer, no writes to the supplied graph.
 * Usage: node scripts/import-pascal-native-scene.cjs scene.json --url http://127.0.0.1:3002 --id my-private-scene
 */
'use strict';
const fs=require('node:fs');
const crypto=require('node:crypto');
const {URL}=require('node:url');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function checkGraph(graph){
 if(!graph||typeof graph!=='object'||Array.isArray(graph))throw Error('Native SceneGraph object required');
 if(!graph.nodes||typeof graph.nodes!=='object'||Array.isArray(graph.nodes)||!Array.isArray(graph.rootNodeIds))throw Error('Need native nodes map and rootNodeIds array');
 const ids=Object.keys(graph.nodes);
 if(!ids.length||new Set(ids).size!==ids.length)throw Error('Empty or duplicate node IDs');
 for(const [id,node] of Object.entries(graph.nodes)){
  if(!node||node.id!==id||typeof node.type!=='string'||!node.type)throw Error('Invalid native node '+id);
  if(node.parentId!=null&&!Object.hasOwn(graph.nodes,node.parentId))throw Error('Missing parent for '+id);
  if(node.children&&(!Array.isArray(node.children)||node.children.some(child=>!Object.hasOwn(graph.nodes,child))))throw Error('Missing child for '+id);
 }
 if(new Set(graph.rootNodeIds).size!==graph.rootNodeIds.length)throw Error('Duplicate root node IDs');
 if(graph.rootNodeIds.some(id=>!Object.hasOwn(graph.nodes,id)))throw Error('Missing root node');
 for(const root of graph.rootNodeIds)if(graph.nodes[root].parentId!=null)throw Error('Root must have no parent: '+root);
 for(const [id,node] of Object.entries(graph.nodes)){
  const children=node.children||[];
  if(new Set(children).size!==children.length)throw Error('Duplicate children on '+id);
  for(const child of children){
   if(graph.nodes[child].parentId!==id)throw Error('Parent-child mismatch: '+id+' -> '+child);
  }
  if(node.parentId!=null&&!((graph.nodes[node.parentId].children||[]).includes(id)))throw Error('Child-parent mismatch: '+id);
 }
 for(const id of ids){
  const visited=new Set();let cursor=id;
  while(cursor!=null){
   if(visited.has(cursor))throw Error('Cycle detected at '+cursor);
   visited.add(cursor);cursor=graph.nodes[cursor].parentId??null;
  }
  if(!graph.rootNodeIds.includes([...visited].at(-1)))throw Error('Orphan hierarchy for '+id);
 }
 return ids.length;
}
async function importScene({source,url='http://127.0.0.1:3002',id,name='AirTrajectory Residence',projectId='airtrajectory',fetcher=fetch}){
 if(!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(id||''))throw Error('Explicit safe --id required (1-64 chars)');
 const endpoint=new URL(url);
 if(!['http:','https:'].includes(endpoint.protocol))throw Error('Only HTTP(S) supported');
 const sourceBytes=fs.readFileSync(source);
 const graph=JSON.parse(sourceBytes.toString('utf8'));
 const count=checkGraph(graph);
 const base=endpoint.href.replace(/\/$/,'');
 const existing=await fetcher(base+'/api/scenes/'+encodeURIComponent(id));
 if(existing.ok)throw Error('Native scene ID already exists: '+id+'; refusing destructive overwrite');
 if(existing.status!==404)throw Error('Preflight GET returned '+existing.status+' (expected 404)');
 const created=await fetcher(base+'/api/scenes',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id,name,projectId,graph})});
 if(!created.ok)throw Error('Native POST failed '+created.status+': '+(await created.text()).slice(0,700));
 const info=await created.json();
 if(info.id!==id)throw Error('Created ID mismatch');
 const reopened=await fetcher(base+'/api/scenes/'+encodeURIComponent(id));
 if(!reopened.ok)throw Error('Native GET after save failed: '+reopened.status);
 const saved=await reopened.json();
 if(!saved.graph||!saved.graph.nodes)throw Error('Native server did not return graph');
 // Pascal may migrate schema; preserving node geometry/ID still is mandatory.
 if(Object.keys(saved.graph.nodes).length!==count)throw Error('Native store node count changed');
 for(const [nodeId,node] of Object.entries(graph.nodes)){
  const stored=saved.graph.nodes[nodeId];
  if(!stored||stored.type!==node.type)throw Error('Native node identity drift: '+nodeId);
  for(const field of ['start','end','position','polygon','wallId','width','height']){
   if(Object.hasOwn(node,field)&&JSON.stringify(node[field])!==JSON.stringify(stored[field]))throw Error('Native geometry drift: '+nodeId+'.'+field);
  }
 }
 const result={status:'NATIVE_SCENE_IMPORTED_AND_RELOADED',scene_id:id,scene_name:name,
  source_sha256:sha(sourceBytes),node_count:count,saved_version:saved.version,
  editor_url:base+'/scene/'+encodeURIComponent(id),source_file_mutated:false,
  full_editor_interaction_tested:false,real_contam_tested:false};
 return result;
}
if(require.main===module){
 const args=process.argv.slice(2),source=args.shift(),options={source};
 for(let i=0;i<args.length;i+=2){
  const key=args[i],value=args[i+1];
  if(!['--url','--id','--name','--project-id'].includes(key)||!value)throw Error('Unknown or missing flag '+key);
  options[{'--url':'url','--id':'id','--name':'name','--project-id':'projectId'}[key]]=value;
 }
 if(!source)throw Error('Usage: node scripts/import-pascal-native-scene.cjs scene.json --id unique-id [--url ...]');
 importScene(options).then(v=>console.log(JSON.stringify(v,null,2))).catch(e=>{console.error('NATIVE_IMPORT_BLOCKED:',e.message);process.exitCode=1});
}
module.exports={importScene,checkGraph};
