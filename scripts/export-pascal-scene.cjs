#!/usr/bin/env node
const fs=require('node:fs');
const crypto=require('node:crypto');
const path=require('node:path');
const {exportLayout}=require('../integrations/pascal-studio/pascal-scene-bridge.cjs');
const [src,out]=process.argv.slice(2);
if(!src||!out){console.error('Usage: node scripts/export-pascal-scene.cjs <pascal-scene.json> <layout-contract.json>');process.exit(2);}
try{
 const bytes=fs.readFileSync(src);
 const sha=crypto.createHash('sha256').update(bytes).digest('hex');
 const result=exportLayout(JSON.parse(bytes.toString('utf8')),{source_sha256:sha,topology_id:'pascal-'+sha.slice(0,16)});
 fs.mkdirSync(path.dirname(out),{recursive:true});
 fs.writeFileSync(out,JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({status:'LAYOUT_IMPORTED_NOT_PHYSICS_VERIFIED',rooms:result.rooms.length,walls:result.walls.length,openings:result.openings.length,source_sha256:sha,output:out}));
}catch(e){console.error('Pascal import BLOCKED:',e.message);process.exitCode=1;}
