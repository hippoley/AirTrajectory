'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../scripts/accept-private-pascal-scene.cjs'),'utf8');
const launch=code.indexOf('await chromium.launch('),health=code.indexOf('const health=await fetch('),importAt=code.indexOf('result=await importScene(');
assert(launch>=0&&health>launch&&importAt>health,'browser and API readiness must precede first persistent scene write');
assert(code.includes('await browser.close(); throw error;'),'browser must close on native import preflight failure');
console.log('PASS: private Pascal native preflight orders browser and API checks before persistent import');
