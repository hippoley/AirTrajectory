// De-identified geometric approximation derived from the supplied floor plan.
// No original DXF, annotations, names, identifying labels, CAD headers or metadata.
// Original CAD remains available through private browser-only DXF import.
const outlines=[
[[-1.29,4.07],[.27,4.07],[.27,1.29],[-.42,1.23],[-.47,1.92],[-.47,1.23],[-1.16,1.23],[-1.29,1.29]],
[[-2.38,-.05],[-.6,.01],[-.6,-.69],[-.55,.01],[.15,.01],[.15,-.1],[.27,-.11],[.27,-3.41],[-.27,-3.41],[-.27,-3.61],[.35,-3.61],[.35,-5.48],[-2.3,-5.48],[-2.38,-3.61],[-1.69,-3.61],[-1.69,-3.41],[-2.38,-3.41]],
[[-3.95,1.17],[-3.35,1.23],[-3.39,2.29],[-3.95,2.29],[-3.95,4.65],[-1.41,4.65],[-1.41,1.29],[-2.02,1.29],[-2.02,1.17],[-1.75,1.17],[-1.69,.94],[-2.34,.94],[-1.69,.89],[-1.75,.07],[-2.5,.07],[-2.5,-4],[-5.69,-4],[-5.69,.35],[-4.07,.35],[-4.07,-.05],[-3.61,-.05],[-3.61,.07],[-3.95,.07]],
[[-4.07,1.29],[-4.07,.47],[-5.69,.47],[-5.69,4.07],[-5.21,4.07],[-5.21,4.31],[-5.69,4.31],[-5.69,4.73],[-4.07,4.73],[-4.07,2.04],[-3.41,2.04],[-3.98,2.04],[-3.41,1.99],[-3.47,1.29]],
[[4.3,1.29],[4.3,5.5],[6.06,5.5],[6.06,4.27],[5.59,4.27],[5.59,4.07],[6.06,4.07],[6.06,1.29]],
[[4.17,-5.48],[.47,-5.48],[.47,-3.61],[.94,-3.61],[.94,-3.41],[.47,-3.41],[.47,.01],[.17,.12],[.12,.01],[-.58,.01],[-.58,.12],[-1.63,.07],[-1.63,1.17],[.47,1.17],[.47,4.07],[.94,4.07],[.94,4.27],[.47,4.27],[.47,5.5],[4.15,5.5],[4.15,1.17],[6.06,1.17],[6.06,-.65],[6.16,-.65],[6.06,-3.41],[4.17,-3.41]]
];
export function makeAnonymousDefaultGraph(){
 const nodes={},rootNodeIds=[],seen=new Set();let wi=0;
 outlines.forEach((polygon,i)=>{
  const zid='zone-'+(i+1);
  nodes[zid]={id:zid,type:'zone',polygon,visible:true,color:['#b4ad9e','#b9afa3','#b5a58d','#b7b3a9','#a9b5ab','#c0ae91'][i]};
  rootNodeIds.push(zid);
  polygon.forEach((a,k)=>{
   const b=polygon[(k+1)%polygon.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]);
   if(len<.14)return;
   const p=[a[0].toFixed(2),a[1].toFixed(2)].join(','),q=[b[0].toFixed(2),b[1].toFixed(2)].join(',');
   const key=[p,q].sort().join('|');
   if(seen.has(key))return;seen.add(key);
   const id='wall-'+(++wi);
   nodes[id]={id,type:'wall',start:a,end:b,thickness:.12,visible:true,children:[]};
   rootNodeIds.push(id);
  });
 });
 return {nodes,rootNodeIds};
}
