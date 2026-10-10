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
const starter=makeAnonymousDefaultGraph();
const shell=Object.values(starter.nodes).filter(n=>n.editorRole==='exterior');
assert.equal(shell.length,6,'six exterior segments in one authoritative shell');
for(let i=0;i<shell.length;i++){
 const a=starter.nodes['shell-'+i],b=starter.nodes['shell-'+((i+1)%shell.length)];
 assert.deepEqual(a.end,b.start,'shell edges form a closed polygon');
 assert.ok(starter.rootNodeIds.includes(a.id));
}
assert.equal(Object.values(starter.nodes).filter(n=>n.type==='zone').length,6);
const baseWalls=Object.values(starter.nodes).filter(n=>n.type==='wall');
assert.equal(baseWalls.length,12,'exactly six shell and six partition walls');
const openings=Object.values(starter.nodes).filter(n=>n.type==='door'||n.type==='window');
assert.equal(openings.length,9);
for(const n of openings){
 const wall=starter.nodes[n.wallId];assert.ok(wall&&wall.children.includes(n.id));
 const L=Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]);
 assert.ok(n.position[0]-n.width/2>=.05&&n.position[0]+n.width/2<=L-.05);
}
const normalizedStarter=normalizeWallGraph(starter);
assert.equal(Object.values(normalizedStarter.nodes).filter(n=>n.type==='door'||n.type==='window').length,9);
console.log('Single-topology default: shell closure, six zones, walls, opening host bounds PASS');
