const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process');
const source='tests/fixtures/pascal-scene-two-rooms.json';
const bytes=fs.readFileSync(source),hash=crypto.createHash('sha256').update(bytes).digest('hex');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'pascal-sidecar-'));
try{
 const input=JSON.parse(bytes);
 for(const n of Object.values(input.nodes)){
  delete n.spaceRole;
  n.metadata={};
 }
 const nativeFile=path.join(tmp,'scene.json'),sideFile=path.join(tmp,'side.json'),outFile=path.join(tmp,'layout.json');
 fs.writeFileSync(nativeFile,JSON.stringify(input));
 const sceneSha=crypto.createHash('sha256').update(fs.readFileSync(nativeFile)).digest('hex');
 const side={schema_version:'1.0',source_scene_sha256:sceneSha,topology_id:'sidecar-fixture-v1',
  evidence_level:'illustrative',nodes:{
   zone_a:{spaceRole:'room',height_m:2.8,volume_m3:33.6},
   zone_b:{spaceRole:'room',height_m:2.8,volume_m3:33.6},
   wall_outer:{source_room:'zone_a',target_room:'OUTSIDE'},
   wall_inner:{source_room:'zone_a',target_room:'zone_b'},
   window_1:{sill_height_m:.9,position_t:.25},
   door_1:{sill_height_m:0,position_t:.6}
  }};
 const cmd=()=>cp.spawnSync('node',['scripts/bind-pascal-physical-sidecar.cjs',nativeFile,sideFile,outFile],{encoding:'utf8'});
 fs.writeFileSync(sideFile,JSON.stringify(side));
 let res=cmd();assert.equal(res.status,0,res.stderr);
 const layout=JSON.parse(fs.readFileSync(outFile));
 assert.equal(layout.rooms.length,2);
 assert.equal(layout.openings.length,2);
 assert.equal(layout.compiler_contract.engineering_authorized,false);
 assert.equal(layout.source_provenance.source_sha256,sceneSha);
 assert.deepEqual(JSON.parse(fs.readFileSync(nativeFile)),input);
 const wrong={...side,source_scene_sha256:'f'.repeat(64)};
 fs.writeFileSync(sideFile,JSON.stringify(wrong));
 res=cmd();assert.notEqual(res.status,0);
 assert.match(res.stderr,/SHA-256 mismatch/);
 fs.writeFileSync(sideFile,JSON.stringify({...side,nodes:{...side.nodes,missing:{height_m:2}}}));
 res=cmd();assert.notEqual(res.status,0);
 assert.match(res.stderr,/missing native ID/);
 fs.writeFileSync(sideFile,JSON.stringify({...side,evidence_level:'engineering-reviewed'}));
 res=cmd();assert.notEqual(res.status,0);
 assert.match(res.stderr,/review attestation incomplete/);
 console.log('PASS physical sidecar immutable native source, checksum-bound, fail-closed metadata');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
