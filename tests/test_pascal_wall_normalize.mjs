import assert from 'node:assert/strict';
import {normalizeWallGraph} from '../web/pascal-wall-normalize.js';
const scene={rootNodeIds:['room','a','b','reverse','perp'],nodes:{
 room:{id:'room',type:'zone',polygon:[[0,0],[8,0],[8,4],[0,4]]},
 a:{id:'a',type:'wall',start:[0,0],end:[4,0],thickness:.12,children:['win']},
 b:{id:'b',type:'wall',start:[2,0],end:[6,0],thickness:.12,children:[]},
 reverse:{id:'reverse',type:'wall',start:[8,0],end:[6,0],thickness:.12,children:['door']},
 perp:{id:'perp',type:'wall',start:[4,0],end:[4,4],thickness:.12,children:[]},
 win:{id:'win',type:'window',wallId:'a',position:[1.5,1.4,0],width:1.2,height:1.1},
 door:{id:'door',type:'door',wallId:'reverse',position:[1,1,0],width:.85,height:2},
}};
const normalized=normalizeWallGraph(scene);
const walls=Object.values(normalized.nodes).filter(n=>n.type==='wall');
assert.equal(walls.length,2,'overlapping and adjacent straight segments become one, perpendicular stays separate');
const long=walls.find(w=>Math.abs(w.end[0]-w.start[0])>7.9);
assert.ok(long,'merged wall spans full 8m');
assert.equal(normalized.nodes.win.wallId,long.id);
assert.equal(normalized.nodes.door.wallId,long.id);
assert.ok(Math.abs(normalized.nodes.win.position[0]-1.5)<.001);
assert.ok(Math.abs(normalized.nodes.door.position[0]-7)<.001,'reversed hosted wall remaps offset');
assert.ok(scene.nodes.a && scene.nodes.b,'source graph remains unmodified');
const again=normalizeWallGraph(normalized);
assert.equal(Object.values(again.nodes).filter(n=>n.type==='wall').length,2);
assert.equal(again.nodes.win.position[0],normalized.nodes.win.position[0]);
console.log('Wall collinearity, overlap, perpendicular isolation, host-offset, reversal and idempotence: PASS');

import {makeAnonymousDefaultGraph} from '../web/anonymous-default-residence.js';
import {nodeFloorplanSegments} from '../web/floorplan-to-scene.js';
const starter=makeAnonymousDefaultGraph();
assert.equal(starter.floorplanDerived,true);
assert.equal(Object.values(starter.nodes).filter(n=>n.type==='zone').length,6);
const walls2=Object.values(starter.nodes).filter(n=>n.type==='wall');
const openings2=Object.values(starter.nodes).filter(n=>['door','window'].includes(n.type));
assert.equal(openings2.length,12);
for(const o of openings2){
 const wall=starter.nodes[o.wallId];assert.ok(wall&&wall.children.includes(o.id));
 const L=Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]);
 assert.ok(o.position[0]-o.width/2>=-.00001&&o.position[0]+o.width/2<=L+.00001);
}
assert.ok(walls2.length>11,'junctions split lines before 3D extrusion');
const isolated=nodeFloorplanSegments([
 {id:'horizontal',start:[0,0],end:[8,0],thickness:.12},
 {id:'vertical',start:[3,0],end:[3,3],thickness:.12}],
 [{id:'window',wallId:'horizontal',type:'window',offset:6,y:1.5,width:1.2,height:1.1}]);
assert.equal(isolated.walls.length,3,'split T junction into two aligned sections and a vertical section');
assert.equal(isolated.openings.length,1);
assert.ok(Math.abs(isolated.openings[0].position[0]-3)<.00001,'opening offset follows its split host');
assert.deepEqual(isolated.walls.find(w=>w.id==='horizontal-part-0').end, isolated.walls.find(w=>w.id==='vertical-part-0').start);
assert.throws(()=>nodeFloorplanSegments([
 {id:'a',start:[0,0],end:[8,0]},{id:'b',start:[3,0],end:[3,3]}],
 [{id:'invalid',wallId:'a',type:'door',offset:3,y:1,width:1,height:2}]),/crosses an opening/);
console.log('2D floorplan intersections, opening rehosting, 3D topology handoff: PASS');
