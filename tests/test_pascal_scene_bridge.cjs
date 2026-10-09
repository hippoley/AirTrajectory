const assert=require('node:assert/strict');
const {exportLayout}=require('../integrations/pascal-studio/pascal-scene-bridge.cjs');
const scene={nodes:{
zone_a:{id:'zone_a',type:'zone',spaceRole:'room',name:'Living',polygon:[[0,0],[4,0],[4,3],[0,3]],metadata:{airtrajectory_height_m:2.8,airtrajectory_volume_m3:33.6}},
zone_b:{id:'zone_b',type:'zone',spaceRole:'room',name:'Kitchen',polygon:[[4,0],[8,0],[8,3],[4,3]],metadata:{airtrajectory_height_m:2.8,airtrajectory_volume_m3:33.6}},
wall_outer:{id:'wall_outer',type:'wall',start:[0,0],end:[0,3],metadata:{airtrajectory_source_room:'zone_a',airtrajectory_target_room:'OUTSIDE'}},
wall_inner:{id:'wall_inner',type:'wall',start:[4,0],end:[4,3],metadata:{airtrajectory_source_room:'zone_a',airtrajectory_target_room:'zone_b'}},
window_1:{id:'window_1',type:'window',wallId:'wall_outer',width:1.2,height:1.1,metadata:{airtrajectory_position_t:0.25}},
door_1:{id:'door_1',type:'door',wallId:'wall_inner',width:.9,height:2,metadata:{airtrajectory_position_t:.6}}
}};
const sha='a'.repeat(64);
const out=exportLayout(scene,{source_sha256:sha});
assert.equal(out.rooms.length,2);
assert.equal(out.walls.length,2);
assert.equal(out.openings.length,2);
assert.equal(out.rooms[0].w,400);
assert.equal(out.openings[0].position_t,.25);
assert.equal(out.openings[1].target,'zone_b');
assert.equal(out.source_provenance.source_sha256,sha);
assert.throws(()=>exportLayout(scene,{source_sha256:'bad'}),/SHA-256/);
const corrupt=structuredClone(scene);delete corrupt.nodes.wall_inner.metadata.airtrajectory_target_room;
assert.throws(()=>exportLayout(corrupt,{source_sha256:sha}),/explicit verified/);
const curved=structuredClone(scene);curved.nodes.zone_a.polygon=[[0,0],[4,0],[4,2],[2,3],[0,3]];
assert.throws(()=>exportLayout(curved,{source_sha256:sha}),/not rectangular/);
const unhosted=structuredClone(scene);unhosted.nodes.window_1.wallId='missing';
assert.throws(()=>exportLayout(unhosted,{source_sha256:sha}),/wall host/);
const wrongPosition=structuredClone(scene);delete wrongPosition.nodes.window_1.metadata.airtrajectory_position_t;
assert.throws(()=>exportLayout(wrongPosition,{source_sha256:sha}),/verified normalized/);
console.log('PASS Pascal scene adapter: 2 rooms, host openings, dimensions, SHA provenance, fail-closed evidence');
