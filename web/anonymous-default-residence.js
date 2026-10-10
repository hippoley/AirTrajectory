// Clean fictional starter apartment. Not reconstructed from any private CAD.
// Orthogonal shared walls, four hosted openings, no duplicate wall fragments.
export function makeAnonymousDefaultGraph(){
 const nodes={},rootNodeIds=[];
 const zones=[
  ['living',[[0,0],[6,0],[6,4.1],[0,4.1]],'#bba989'],
  ['bedroom',[[6,0],[9.5,0],[9.5,4.1],[6,4.1]],'#bbb5a8'],
  ['kitchen',[[0,4.1],[3,4.1],[3,6.8],[0,6.8]],'#b2b8ae'],
  ['bathroom',[[3,4.1],[6,4.1],[6,6.8],[3,6.8]],'#b8b7b2']
 ];
 for(const [name,polygon,color] of zones){const id='zone-'+name;nodes[id]={id,type:'zone',name,polygon,color,visible:true};rootNodeIds.push(id)}
 const walls=[
  [[0,0],[9.5,0]],[[9.5,0],[9.5,4.1]],[[9.5,4.1],[6,4.1]],
  [[6,4.1],[6,6.8]],[[6,6.8],[0,6.8]],[[0,6.8],[0,0]],
  [[6,0],[6,4.1]],[[0,4.1],[6,4.1]],[[3,4.1],[3,6.8]]
 ];
 walls.forEach(([start,end],i)=>{const id='wall-'+i;nodes[id]={id,type:'wall',start,end,thickness:.14,visible:true,children:[]};rootNodeIds.push(id)});
 // Local along-wall offsets from the start node, y = opening center above floor.
 const openings=[
  [0,'window',2.9,1.55,2.4,1.35],
  [1,'window',1.75,1.55,1.65,1.25],
  [6,'door',2.1,1.05,.9,2.1],
  [7,'door',4.7,1.05,.82,2.1],
  [8,'door',1.4,1.05,.8,2.1],
  [4,'window',4.5,1.65,1.25,1.05]
 ];
 openings.forEach(([index,type,x,y,width,height],i)=>{const id='opening-'+i,wallId='wall-'+index;nodes[id]={id,type,wallId,parentId:wallId,position:[x,y,0],width,height,visible:true};nodes[wallId].children.push(id)});
 return {nodes,rootNodeIds};
}
