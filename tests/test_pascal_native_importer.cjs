const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {importScene,checkGraph}=require('../scripts/import-pascal-native-scene.cjs');
(async()=>{
 const graph={nodes:{site:{id:'site',type:'site',parentId:null,children:['wall']},wall:{id:'wall',type:'wall',parentId:'site',start:[0,0],end:[4,0]}},rootNodeIds:['site']};
 assert.equal(checkGraph(graph),2);
 assert.throws(()=>checkGraph({...graph,nodes:{...graph.nodes,wall:{...graph.nodes.wall,parentId:'missing'}}}),/Missing parent/);
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pascal-import-'));
 try{
  const f=path.join(dir,'graph.json');fs.writeFileSync(f,JSON.stringify(graph));
  const calls=[];
  const fetcher=async (url,opts={})=>{
   calls.push({url,method:opts.method||'GET'});
   if(calls.length===1)return {ok:false,status:404};
   if(calls.length===2)return {ok:true,json:async()=>({id:'residence-test'})};
   return {ok:true,json:async()=>({graph,version:1})};
  };
  const res=await importScene({source:f,id:'residence-test',fetcher});
  assert.equal(res.status,'NATIVE_SCENE_IMPORTED_AND_RELOADED');
  assert.equal(res.node_count,2);
  assert.match(res.editor_url,/\/scene\/residence-test$/);
  assert.deepEqual(calls.map(x=>x.method),['GET','POST','GET']);
  assert.equal(fs.readFileSync(f,'utf8'),JSON.stringify(graph));
  await assert.rejects(importScene({source:f,id:'residence-test',fetcher:async()=>({ok:true,status:200})}),/already exists/);
  await assert.rejects(importScene({source:f,id:'../unsafe',fetcher}),/safe --id/);
  console.log('PASS native Pascal persistence importer: no overwrite, id/geometry verified, source unchanged');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
