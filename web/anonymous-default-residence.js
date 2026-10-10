// Single authoritative, editable six-zone demonstration topology.
// All walls and openings are derived from these edges. No CAD candidate wall overlay.
export function makeAnonymousDefaultGraph(){
 const nodes={},rootNodeIds=[];
 const add=(node,root=true)=>{nodes[node.id]=node;if(root)rootNodeIds.push(node.id);return node};
 // Orthogonal L-shaped apartment in metres. The exterior is one closed cycle.
 const outline=[[0,0],[11.6,0],[11.6,7.6],[7.9,7.6],[7.9,9.3],[0,9.3]];
 const zones=[
  [[0,0],[4.1,0],[4.1,4.1],[0,4.1]],
  [[4.1,0],[8.1,0],[8.1,4.1],[4.1,4.1]],
  [[8.1,0],[11.6,0],[11.6,4.1],[8.1,4.1]],
  [[0,4.1],[3.1,4.1],[3.1,9.3],[0,9.3]],
  [[3.1,4.1],[7.9,4.1],[7.9,9.3],[3.1,9.3]],
  [[7.9,4.1],[11.6,4.1],[11.6,7.6],[7.9,7.6]]
 ];
 const colors=['#bbb3a7','#bcb9b0','#c0b5a8','#b5bcb5','#c6b8a6','#b7b5aa'];
 zones.forEach((polygon,i)=>add({id:'zone-'+i,type:'zone',polygon,color:colors[i],visible:true}));
 const edge=(id,start,end,role='interior')=>add({id,type:'wall',start,end,thickness:role==='exterior'?.16:.12,visible:true,editorRole:role,children:[]});
 for(let i=0;i<outline.length;i++)edge('shell-'+i,outline[i],outline[(i+1)%outline.length],'exterior');
 // Every partition terminates exactly on another structural edge.
 const partitions=[
  [[4.1,0],[4.1,4.1]],[[8.1,0],[8.1,4.1]],
  [[0,4.1],[11.6,4.1]],[[3.1,4.1],[3.1,9.3]],
  [[7.9,4.1],[7.9,7.6]]
 ];
 partitions.forEach(([a,b],i)=>edge('partition-'+i,a,b));
 const holes=[
  ['shell-0','window',2,1.5,2.3,1.3],
  ['shell-0','window',9.75,1.5,1.55,1.3],
  ['shell-2','window',1.8,1.5,1.7,1.3],
  ['shell-4','window',3.8,1.5,1.5,1.3],
  ['partition-0','door',2.05,1.05,.88,2.1],
  ['partition-1','door',2.05,1.05,.88,2.1],
  ['partition-2','door',2,1.05,.86,2.1],
  ['partition-2','door',5.65,1.05,.86,2.1],
  ['partition-2','door',9.65,1.05,.86,2.1],
  ['partition-3','door',1.85,1.05,.86,2.1],
  ['partition-4','door',1.75,1.05,.86,2.1],
  ['shell-1','door',5.7,1.05,.96,2.1]
 ];
 holes.forEach(([wallId,type,x,y,width,height],i)=>{
  const id='opening-'+i;
  const wall=nodes[wallId];if(!wall)throw Error('Opening host not found: '+wallId);
  const L=Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]);
  if(x-width/2<.05||x+width/2>L-.05)throw Error('Opening outside wall: '+wallId);
  add({id,type,visible:true,wallId,parentId:wallId,position:[x,y,0],width,height},false);
  wall.children.push(id);
 });
 return {nodes,rootNodeIds};
}
