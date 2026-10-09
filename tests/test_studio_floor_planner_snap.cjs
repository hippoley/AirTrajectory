const assert=require('node:assert/strict');
const m=require('../web/vendor/floor-planner-snap.js');
assert.deepEqual(m.nearestPointOnSegment({x:5,y:10},{x:0,y:0},{x:10,y:0}),{x:5,y:0});
assert.deepEqual(m.nearestPointOnSegment({x:20,y:0},{x:0,y:0},{x:10,y:0}),{x:10,y:0});
assert.deepEqual(m.nearestPointOnSegment({x:5,y:5},{x:2,y:3},{x:2,y:3}),{x:2,y:3});
assert.equal(m.distanceToSegment({x:5,y:3},{x:0,y:0},{x:10,y:0}),3);
assert.deepEqual(m.snapEndpoint({x:2,y:1},[{id:'A',x1:0,y1:0,x2:100,y2:0}],5).wall_id,'A');
assert.equal(m.snapEndpoint({x:20,y:20},[],5).wall_id,null);
console.log('PASS floor-planner snapping geometry integration: 6 assertions');
