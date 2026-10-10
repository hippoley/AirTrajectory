import assert from 'node:assert/strict';
import {extractArchitecturalSkeleton} from '../web/dxf-architecture-extract.js';
const doc={header:{$INSUNITS:4},entities:[
 {type:'LWPOLYLINE',layer:'J-隔墙',shape:true,vertices:[{x:1000,y:2000},{x:2000,y:2000},{x:2000,y:2200},{x:1000,y:2200}]},
 {type:'LINE',layer:'J-窗',vertices:[{x:1200,y:2200},{x:1700,y:2200}]},
 {type:'LINE',layer:'P-门',vertices:[{x:2000,y:2010},{x:2000,y:2100}]},
 {type:'LWPOLYLINE',layer:'P-门套',vertices:[{x:1900,y:2000},{x:2000,y:2000}]},
 {type:'TEXT',layer:'J-区域名称',text:'should never be exported'}]};
const result=extractArchitecturalSkeleton(doc);
assert.equal(result.geometry.wall.length,1);
assert.equal(result.geometry.window.length,1);
assert.equal(result.geometry.door.length,1);
assert.equal(result.geometry.doorFrame.length,1);
assert.equal(result.geometry.wall[0].closed,true);
assert.deepEqual(result.geometry.wall[0].points[0],[0,0]);
assert.deepEqual(result.geometry.window[0].points[0],[.2,.2]);
assert.deepEqual(result.bounds,{width:1,height:.2});
assert.ok(!JSON.stringify(result).includes('should never be exported'));
console.log('Anonymous DXF architecture skeleton: PASS');
