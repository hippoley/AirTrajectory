const assert=require('node:assert/strict');
const {splitRectRoom}=require('../web/vendor/room-partition.js');
const base={schema_version:'0.1',topology_id:'test',outside_id:'OUTSIDE',rooms:[
{id:'A',name:'Alpha',x:0,y:0,w:100,h:100,volume_m3:50},
{id:'B',name:'Beta',x:100,y:0,w:100,h:100,volume_m3:50}],
walls:[
{id:'top',kind:'exterior',source:'A',target:'OUTSIDE',x1:0,y1:0,x2:100,y2:0},
{id:'right',kind:'internal',source:'A',target:'B',x1:100,y1:0,x2:100,y2:100}],
openings:[
{id:'W1',kind:'window',wall_id:'top',source:'A',target:'OUTSIDE',position_t:.75},
{id:'D1',kind:'door',wall_id:'right',source:'A',target:'B',position_t:.5}]};
const original=JSON.stringify(base);
const result=splitRectRoom(base,'A');
assert.equal(result.rooms.length,3);
assert.equal(result.rooms[0].volume_m3,25);
assert.equal(result.rooms[2].volume_m3,25);
assert.equal(result.walls.length,4);
assert.equal(result.openings.find(x=>x.id==='W1').wall_id,'top-part-A-split-3');
assert.equal(result.openings.find(x=>x.id==='D1').source,'A-split-3');
assert.equal(result.openings.find(x=>x.id==='W1').position_t,.5);
assert.equal(result.walls.find(w=>w.id==='partition-A-split-3').target,'A-split-3');
assert.equal(JSON.stringify(base),original);
assert.throws(()=>splitRectRoom(base,'A','z'),/Unsupported/);
assert.throws(()=>splitRectRoom(base,'A','x',0),/Unsupported/);
const obstruction=structuredClone(base);obstruction.openings[0].position_t=.5;
assert.throws(()=>splitRectRoom(obstruction,'A'),/Opening intersects/);
console.log('PASS room partition: wall segmentation, opening remap, room volume, immutability and fail-closed cases');
