const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-webgpu','--use-gl=angle','--use-angle=swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const bad=[];
  page.on('pageerror',e=>bad.push(e.message));
  const response=await page.goto(process.env.PASCAL_NATIVE_URL||'http://127.0.0.1:3002/',{waitUntil:'domcontentloaded',timeout:60000});
  assert(response?.ok(),'native app failed HTTP navigation');
  await page.locator('body').waitFor();
  await page.waitForTimeout(5000);
  const text=await page.locator('body').innerText();
  for(const label of ['Scene','Build','Paint','Items']) assert(text.includes(label),'upstream editor missing tab '+label);
  fs.mkdirSync('artifacts/pascal-native',{recursive:true});
  await page.screenshot({path:'artifacts/pascal-native/full-editor.png',fullPage:true});
  const report={url:page.url(),title:await page.title(),tabs:['Scene','Build','Paint','Items'],canvas_count:await page.locator('canvas').count(),runtime_errors:bad.slice(0,10)};
  fs.writeFileSync('artifacts/pascal-native/browser-smoke.json',JSON.stringify(report,null,2));
  assert(report.canvas_count>0,'No native 2D/3D rendering canvas mounted');
  assert(!bad.some(x=>/uncaught|TypeError|ReferenceError/i.test(x)),'Uncaught JavaScript runtime error');
  console.log('PASS authentic Pascal editor browser shell',JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
