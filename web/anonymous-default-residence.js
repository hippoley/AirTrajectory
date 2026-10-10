// Simplified geometry based on the six actual room footprints in the source plan.
// Deliberately keeps the irregular L-shaped living room and the real room adjacency.
// Clean wall preview only: selected long wall chains, not every tiny CAD fragment.
export function makeAnonymousDefaultGraph(){
 const zones=[[[-1.29,4.07],[0.27,4.07],[0.27,1.29],[-0.42,1.23],[-0.47,1.92],[-0.47,1.23],[-1.16,1.23],[-1.29,1.29]],[[-2.38,-0.05],[-0.6,0.01],[-0.6,-0.69],[-0.55,0.01],[0.15,0.01],[0.15,-0.1],[0.27,-0.11],[0.27,-3.41],[-0.27,-3.41],[-0.27,-3.61],[0.35,-3.61],[0.35,-5.48],[-2.3,-5.48],[-2.38,-3.61],[-1.69,-3.61],[-1.69,-3.41],[-2.38,-3.41]],[[-3.95,1.17],[-3.35,1.23],[-3.39,2.29],[-3.95,2.29],[-3.95,4.65],[-1.41,4.65],[-1.41,1.29],[-2.02,1.29],[-2.02,1.17],[-1.75,1.17],[-1.69,0.94],[-2.34,0.94],[-1.69,0.89],[-1.75,0.07],[-2.5,0.07],[-2.5,-4],[-5.69,-4],[-5.69,0.35],[-4.07,0.35],[-4.07,-0.05],[-3.61,-0.05],[-3.61,0.07],[-3.95,0.07]],[[-4.07,1.29],[-4.07,0.47],[-5.69,0.47],[-5.69,4.07],[-5.21,4.07],[-5.21,4.31],[-5.69,4.31],[-5.69,4.73],[-4.07,4.73],[-4.07,2.04],[-3.41,2.04],[-3.98,2.04],[-3.41,1.99],[-3.47,1.29]],[[4.3,1.29],[4.3,5.5],[6.06,5.5],[6.06,4.27],[5.59,4.27],[5.59,4.07],[6.06,4.07],[6.06,1.29]],[[4.17,-5.48],[0.47,-5.48],[0.47,-3.61],[0.94,-3.61],[0.94,-3.41],[0.47,-3.41],[0.47,0.01],[0.17,0.12],[0.12,0.01],[-0.58,0.01],[-0.58,0.12],[-1.63,0.07],[-1.63,1.17],[0.47,1.17],[0.47,4.07],[0.94,4.07],[0.94,4.27],[0.47,4.27],[0.47,5.5],[4.15,5.5],[4.15,1.17],[6.06,1.17],[6.06,-0.65],[6.16,-0.65],[6.06,-3.41],[4.17,-3.41]]];
 const wallCandidates=[{"original":1,"pts":[2.814,14.995,2.814,19.35]},{"original":5,"pts":[2.814,20.12,2.814,23.07]},{"original":8,"pts":[4.429,23.735,4.429,21.306]},{"original":11,"pts":[5.999,18.95,5.999,15.59]},{"original":17,"pts":[7.094,23.07,7.094,20.29]},{"original":19,"pts":[8.774,18.89,8.774,15.59]},{"original":22,"pts":[8.854,15.39,8.854,13.52]},{"original":23,"pts":[8.974,15.59,8.974,19.01]},{"original":27,"pts":[12.654,20.17,14.564,20.17]},{"original":34,"pts":[6.478,13.52,12.178,13.52]},{"original":35,"pts":[2.849,14.917,6.449,14.917]},{"original":36,"pts":[12.414,15.523,15.044,15.523]},{"original":39,"pts":[6.839,23.136,8.954,23.136]},{"original":40,"pts":[4.069,23.649,6.969,23.649]},{"original":42,"pts":[9.384,24.5,14.244,24.5]},{"original":43,"pts":[14.664,16.91,14.664,18.855]},{"original":44,"pts":[14.564,22.84,14.564,24.93]},{"original":45,"pts":[12.747,13.185,12.747,15.579]},{"original":46,"pts":[12.654,20.54,12.654,23.4]},{"original":61,"pts":[14.564,22.84,14.564,20.29]}];
 const hosted=[[42,"window",1.875,1.5,2.79,1.2],[35,"window",1.35,1.5,1.74,1.2],[34,"door",1.257,1.05,1.554,2.1],[40,"window",1.45,1.5,1.94,1.2],[39,"window",1.058,1.5,1.155,1.2],[36,"window",1.315,1.5,1.67,1.2],[46,"door",1.43,1.05,1.9,2.1],[45,"window",1.197,1.5,1.434,1.2],[43,"door",0.973,1.05,0.985,2.1],[44,"door",1.045,1.05,1.13,2.1]];
 const names=['bath-west','bed-east','bed-west','bath-inner','kitchen','living-dining'];
 const colors=['#bcb9b2','#c1b7a8','#b7b6ae','#aeb8b8','#b9b2a6','#c4b8a5'];
 const nodes={},rootNodeIds=[];
 zones.forEach((polygon,i)=>{const id='zone-'+i;nodes[id]={id,type:'zone',name:names[i],polygon,color:colors[i],visible:true};rootNodeIds.push(id)});
 const hostMap={};
 wallCandidates.forEach(({original,pts},i)=>{
  const id='wall-'+i;hostMap[original]=id;
  nodes[id]={id,type:'wall',start:[+(pts[0]-8.5).toFixed(3),+(pts[1]-19).toFixed(3)],end:[+(pts[2]-8.5).toFixed(3),+(pts[3]-19).toFixed(3)],thickness:.14,visible:true,children:[]};
  rootNodeIds.push(id);
 });
 hosted.forEach(([host,type,x,y,width,height],i)=>{
  const wallId=hostMap[host];if(!wallId)return;
  const id='opening-'+i;
  nodes[id]={id,type,wallId,parentId:wallId,position:[x,y,0],width,height,visible:true};
  nodes[wallId].children.push(id);
 });
 return {nodes,rootNodeIds};
}
