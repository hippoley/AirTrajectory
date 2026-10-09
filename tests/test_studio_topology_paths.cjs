const assert=require('node:assert/strict');
const {discover}=require('../web/topology-path-explorer.js');
const base={outside_id:'OUTSIDE',rooms:[{id:'A'},{id:'B'}],walls:[
{id:'wA',source:'A',target:'OUTSIDE'},{id:'wB',source:'B',target:'OUTSIDE'},{id:'d',source:'A',target:'B'}],openings:[
{id:'W1',kind:'window',wall_id:'wA',source:'A',target:'OUTSIDE'},
{id:'W2',kind:'window',wall_id:'wB',source:'B',target:'OUTSIDE'},
{id:'D',kind:'door',wall_id:'d',source:'A',target:'B'}]};
let x=discover(base);
assert.equal(x.status,'TOPOLOGY_ONLY_NOT_AIRFLOW');
assert.equal(x.paths.length,1);
assert.deepEqual(x.paths[0].opening_ids,['W1','D','W2']);
const withoutDoor={...base,openings:base.openings.filter(o=>o.id!=='D')};
assert.equal(discover(withoutDoor).paths.length,0);
const renamed={...base,rooms:[{id:'KITCHEN'},{id:'HALL'}],walls:base.walls.map(w=>({...w,source:w.source==='A'?'KITCHEN':'HALL',target:w.target==='B'?'HALL':w.target})),openings:base.openings.map(o=>({...o,source:o.source==='A'?'KITCHEN':'HALL',target:o.target==='B'?'HALL':o.target}))};
assert.equal(discover(renamed).paths.length,1);
assert.equal(discover({...base,openings:[...base.openings,{id:'bad',kind:'window',wall_id:'wA',source:'B',target:'OUTSIDE'}]}).paths.length,1);
console.log('PASS topology path explorer: arbitrary names, door disconnection, host mismatch, evidence class');
