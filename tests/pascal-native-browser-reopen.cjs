// Open the actual persisted Pascal scene route after restarting its production server.
// Navigation/render evidence only; this is NOT a browser-driven wall drawing test.
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const id=process.env.PASCAL_GATE_SCENE_ID;
 assert(id,'PASCAL_GATE_SCENE_ID required');
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader']});
 try{
   const page=await browser.newPage({viewport:{width:1440,height:900}});
   const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const response=await page.goto('http://127.0.0.1:3002/scene/'+encodeURIComponent(id),{waitUntil:'domcontentloaded',timeout:60000});
   assert(response&&response.ok(),'Pascal native scene route failed');
   await page.waitForTimeout(4000);
   const body=await page.locator('body').innerText();
   assert(!/scene not found|404: this page could not be found/i.test(body),'saved scene not found in native editor');
   const report={status:'NATIVE_SCENE_ROUTE_REOPENED',scene_id:id,url:page.url(),title:await page.title(),
     canvas_count:await page.locator('canvas').count(),runtime_errors:errors};
   fs.mkdirSync('artifacts/pascal-native',{recursive:true});
   await page.screenshot({path:'artifacts/pascal-native/reopened-native-scene.png',fullPage:true});
   fs.writeFileSync('artifacts/pascal-native/browser-reopen.json',JSON.stringify(report,null,2));
   assert(report.canvas_count>0,'native renderer did not mount');
   assert(!errors.some(e=>/TypeError|ReferenceError|uncaught/i.test(e)),'native page runtime errors');
   console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
