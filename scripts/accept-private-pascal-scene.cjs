#!/usr/bin/env node
/** Private-only genuine Pascal Editor browser acceptance (never prints geometry). */
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {importScene,checkGraph}=require('../scripts/import-pascal-native-scene.cjs');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
async function verify({sceneFile,base='http://127.0.0.1:3002',out='artifacts/private-pascal',sceneId}){
 const content=fs.readFileSync(sceneFile);
 const graph=JSON.parse(content);
 const count=checkGraph(graph), zones=Object.values(graph.nodes).filter(x=>x.type==='zone');
 assert(zones.length>=1,'Requires zone nodes');
 assert(Object.values(graph.nodes).every(x=>!['door','window'].includes(x.type))||process.env.ALLOW_UNREVIEWED_OPENINGS==='1',
    'Private unreconciled openings must not be presented as reviewed');
 const result=await importScene({source:sceneFile,id:sceneId,name:'Private residential native acceptance',url:base});
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader']});
 let report;
 try{
  const page=await browser.newPage({viewport:{width:1600,height:960}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e.message)));
  const res=await page.goto(result.editor_url,{waitUntil:'domcontentloaded',timeout:90000});
  assert(res?.ok(),'Native Pascal route rejected scene');
  await page.waitForTimeout(5000);
  const body=await page.locator('body').innerText();
  const canvasCount=await page.locator('canvas').count();
  const missing=/scene not found|404: this page could not be found/i.test(body);
  const response=await fetch(base.replace(/\/$/,'')+'/api/scenes/'+encodeURIComponent(sceneId));
  assert(response.ok,'Native API lost scene after browser reopened');
  const persisted=await response.json();
  const persistedZones=Object.values(persisted.graph.nodes).filter(n=>n.type==='zone');
  assert.equal(persistedZones.length,zones.length,'Native API room identity drift');
  for(const zone of zones){
   const saved=persisted.graph.nodes[zone.id];
   assert(saved&&saved.type==='zone','Native room missing: '+zone.id);
   assert.deepEqual(saved.polygon,zone.polygon,'Native room polygon changed: '+zone.id);
  }
  assert(!missing,'Native Editor displayed not-found');
  assert(canvasCount>0,'Native renderer canvas absent');
  // A hidden or zero-size canvas is not meaningful browser rendering evidence.
  const canvasBounds=await page.locator('canvas').evaluateAll(elements=>elements.map(el=>{
   const box=el.getBoundingClientRect(); const styles=getComputedStyle(el);
   return {width:box.width,height:box.height,visible:styles.visibility!=='hidden'&&styles.display!=='none'&&Number(styles.opacity)>0};
  }));
  assert(canvasBounds.some(box=>box.visible&&box.width>=160&&box.height>=120),
    'Native canvas mounted but was hidden or too small for a rendered scene');
  assert.equal(errors.length,0,'Browser runtime exceptions: '+errors.join(' | '));
  fs.mkdirSync(out,{recursive:true});
  const img=path.join(out,'native-private-residence.png');
  await page.screenshot({path:img,fullPage:true});
  report={status:'PRIVATE_PASCAL_NATIVE_SCENE_BROWSER_LOADED',scene_id:sceneId,scene_sha256:hash(content),
   total_native_nodes:count,verified_persisted_zones:zones.length,canvas_count:canvasCount,
   browser_errors:errors,canvas_bounds:canvasBounds,rendered_visual_accuracy_verified:false,
   wall_host_accuracy_verified:false,furniture_interaction_verified:false,
   private_artifact_screenshot:img};
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
 }finally{await browser.close()}
 return report;
}
if(require.main===module){
 const a=process.argv.slice(2),sceneFile=a[0];
 if(!sceneFile)throw Error('Usage: node scripts/accept-private-pascal-scene.cjs /private/graph.json [scene-id] [base-url]');
 const sceneId=a[1]||'private-residence-'+Date.now();
 verify({sceneFile,sceneId,base:a[2]||'http://127.0.0.1:3002'}).catch(e=>{console.error('PRIVATE_PASCAL_ACCEPTANCE_BLOCKED:',e.message);process.exitCode=1});
}
module.exports={verify};
