#!/usr/bin/env node
/* Attach reviewed engineering data to a COPY of Pascal SceneGraph.
 * The original scene bytes and node content are never modified.
 * Example/design assumptions MUST NOT authorize engineering runtime.
 */
'use strict';
const fs=require('node:fs');
const crypto=require('node:crypto');
const path=require('node:path');
const {exportLayout,nodesOf}=require('../integrations/pascal-studio/pascal-scene-bridge.cjs');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const [source,sidecarFile,output]=process.argv.slice(2);
if(!source||!sidecarFile||!output){console.error('Usage: node scripts/bind-pascal-physical-sidecar.cjs scene.json reviewed-sidecar.json layout.json');process.exit(2);}
try{
 const original=fs.readFileSync(source),originalHash=digest(original),raw=JSON.parse(original.toString('utf8'));
 const side=JSON.parse(fs.readFileSync(sidecarFile,'utf8'));
 if(side.schema_version!=='1.0'||side.source_scene_sha256!==originalHash)throw Error('sidecar scene SHA-256 mismatch');
 if(!['illustrative','engineering-reviewed'].includes(side.evidence_level))throw Error('unsupported evidence_level');
 if(side.evidence_level==='engineering-reviewed'&&(!side.review?.reviewer_id||!side.review?.reviewed_at||!side.review?.evidence_reference))throw Error('review attestation incomplete');
 const declarations=side.nodes;
 if(!declarations||typeof declarations!=='object'||Array.isArray(declarations))throw Error('sidecar nodes must be an object');
 const graph=structuredClone(raw);
 const rawNodes=graph.nodes||graph.state?.nodes;
 if(!rawNodes||Array.isArray(rawNodes))throw Error('native scene must contain a keyed node map');
 const nativeIds=new Set(nodesOf(raw).map(n=>n.id));
 for(const [id,fields] of Object.entries(declarations)){
  if(!nativeIds.has(id)||!rawNodes[id])throw Error('sidecar references missing native ID: '+id);
  const node=rawNodes[id];
  if(!['zone','wall','window','door'].includes(node.type))throw Error('unsupported annotated node kind: '+id);
  const allowed=node.type==='zone'?['spaceRole','height_m','volume_m3']:
   node.type==='wall'?['source_room','target_room']:
   ['sill_height_m','position_t'];
  if(!fields||typeof fields!=='object'||Array.isArray(fields)||Object.keys(fields).some(k=>!allowed.includes(k)))throw Error('invalid physical fields for '+id);
  node.metadata={...(node.metadata||{})};
  const map={height_m:'airtrajectory_height_m',volume_m3:'airtrajectory_volume_m3',
   source_room:'airtrajectory_source_room',target_room:'airtrajectory_target_room',
   sill_height_m:'airtrajectory_sill_height_m',position_t:'airtrajectory_position_t'};
  for(const [key,value] of Object.entries(fields)){
   if(key==='spaceRole')node.spaceRole=value;
   else{
    const k=map[key];
    if(Object.hasOwn(node.metadata,k)&&node.metadata[k]!==value)throw Error('native metadata conflicts with sidecar: '+id+'/'+k);
    node.metadata[k]=value;
   }
  }
 }
 const result=exportLayout(graph,{source_sha256:originalHash,topology_id:side.topology_id});
 result.source_provenance.physical_sidecar_sha256=digest(fs.readFileSync(sidecarFile));
 result.source_provenance.physical_evidence_level=side.evidence_level;
 result.source_provenance.physical_review_reference=side.review?.evidence_reference||null;
 result.compiler_contract.engineering_authorized=false;
 result.compiler_contract.note='Sidecar only supplies declared metadata; model calibration and real engineering runtime require independent authorization.';
 fs.mkdirSync(path.dirname(output),{recursive:true});
 fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
 if(digest(fs.readFileSync(source))!==originalHash)throw Error('source scene unexpectedly modified');
 console.log(JSON.stringify({status:'SIDECAR_BOUND_NOT_ENGINEERING_AUTHORIZED',source_sha256:originalHash,sidecar_sha256:result.source_provenance.physical_sidecar_sha256,rooms:result.rooms.length,walls:result.walls.length,openings:result.openings.length}));
}catch(e){console.error('SIDECAR_BIND_BLOCKED:',e.message);process.exitCode=1;}
