'use client';
import { useEffect, useState } from 'react';
import { Editor, useScene } from '@pascal-app/editor';
import { builtinPlugin } from '@pascal-app/nodes';
import { nodeRegistry, registerNode, type AnyNodeDefinition } from '@pascal-app/core';
let registered=false;
function setup(){
  if(registered)return;
  registered=true;
  for(const raw of builtinPlugin.nodes??[]){
    const def=raw as AnyNodeDefinition;
    if(!nodeRegistry.has(def.kind))registerNode(def);
  }
}
export default function Home(){
  const [ready,setReady]=useState(false);
  useEffect(()=>{setup();setReady(true);},[]);
  function exportRawScene(){
    const nodes=useScene.getState().nodes;
    if(!nodes||Object.keys(nodes).length===0){window.alert('场景没有节点');return;}
    const blob=new Blob([JSON.stringify({nodes},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download='pascal-native-scene.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <main style={{height:'100vh',display:'flex',flexDirection:'column'}}>
    <header style={{height:52,display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 20px'}}>
      <strong>AirTrajectory × Pascal · 3D Studio</strong>
      <button onClick={exportRawScene} style={{padding:8,background:"#c6f4da",border:0,borderRadius:7,cursor:"pointer"}}>导出原生场景 JSON</button>
      <a href="https://github.com/hippoley/AirTrajectory" style={{color:'#7ce4c4'}}>AirTrajectory</a>
    </header>
    <div style={{flex:1,minHeight:0}}>{ready?<Editor projectId="airtrajectory-local" layoutVersion="v2" />:<p>Initializing Pascal…</p>}</div>
    <footer style={{padding:8,fontSize:12}}>Experimental Pascal host. Scene-to-LayoutContract bridge and engineering verification are pending.</footer>
  </main>;
}
