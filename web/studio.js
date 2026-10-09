(()=>{"use strict";
let doc=null,selected=null,history=[],future=[],drag=null;
const el=id=>document.getElementById(id),svg=el("plan"),NS="http://www.w3.org/2000/svg",clone=x=>structuredClone(x);
const find=()=>selected&&doc?.[selected.type+"s"]?.find(x=>x.id===selected.id);
function update(){if(!doc)return;el("summary").textContent=`${doc.rooms.length} rooms · ${doc.walls.length} walls · ${doc.openings.length} openings`;draw();fields();check();}
function checkpoint(){history.push(clone(doc));if(history.length>80)history.shift();future=[];}
function edit(fn){checkpoint();try{fn();update();}catch(e){doc=history.pop();update();alert(e.message);}}
function load(x){if(!x||x.schema_version!=="0.1"||!Array.isArray(x.rooms)||!Array.isArray(x.walls)||!Array.isArray(x.openings))throw Error("需要 LayoutContract v0.1 JSON");doc=clone(x);doc.source_kind="imported-floorplan";doc.capabilities={...(doc.capabilities||{}),floorplan_geometry_editable:true,opening_position_editable:true,opening_state_editable:true};selected=null;history=[];future=[];update();}
function point(w,t){return{x:+w.x1+(+w.x2-w.x1)*t,y:+w.y1+(+w.y2-w.y1)*t};}
function node(tag,attrs,parent=svg){const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.appendChild(n);return n;}
function pick(type,id){selected={type,id};draw();fields();}
function draw(){svg.replaceChildren();if(!doc)return;const b=doc.canvas||{width:1100,height:650};svg.setAttribute("viewBox",`0 0 ${b.width||1100} ${b.height||650}`);
for(const r of doc.rooms){const n=node("rect",{x:r.x,y:r.y,width:r.w,height:r.h,rx:3,class:"room"+(selected?.id===r.id?" active":"")});n.addEventListener("click",()=>pick("room",r.id));node("text",{x:+r.x+10,y:+r.y+24,class:"caption"}).textContent=r.name||r.id;}
for(const w of doc.walls){const n=node("line",{x1:w.x1,y1:w.y1,x2:w.x2,y2:w.y2,class:"wall",stroke:selected?.id===w.id?"#65e4ba":undefined});n.addEventListener("click",()=>pick("wall",w.id));}
for(const o of doc.openings){const w=doc.walls.find(w=>w.id===o.wall_id);if(!w)continue;const p=point(w,Math.max(0,Math.min(1,+o.position_t)));const length=Math.hypot(w.x2-w.x1,w.y2-w.y1)||1,dx=11*(w.x2-w.x1)/length,dy=11*(w.y2-w.y1)/length;
const n=node("line",{x1:p.x-dx,y1:p.y-dy,x2:p.x+dx,y2:p.y+dy,class:"opening"+(o.kind==="door"?" door":"")+(selected?.id===o.id?" active":"")});
n.addEventListener("pointerdown",e=>{e.stopPropagation();pick("opening",o.id);drag={id:o.id,wall:w,start:clone(doc)};svg.setPointerCapture(e.pointerId);});n.addEventListener("click",e=>{e.stopPropagation();pick("opening",o.id);});}
}
function coords(e){const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}
svg.addEventListener("pointermove",e=>{if(!drag)return;const p=coords(e),w=drag.wall,vx=w.x2-w.x1,vy=w.y2-w.y1,den=vx*vx+vy*vy;if(!den)return;const projection=AirTrajectoryWallGeometry.projectOntoWall(p,w,0.05,0.95);if(!projection)return;const t=projection.position;doc.openings.find(x=>x.id===drag.id).position_t=+t.toFixed(4);draw();});
svg.addEventListener("pointerup",()=>{if(!drag)return;history.push(drag.start);future=[];drag=null;update();});
function fields(){const f=el("fields");f.replaceChildren();const x=find();el("selected-title").textContent=x?`${selected.type.toUpperCase()} / ${x.id}`:"选择对象查看属性";if(!x)return;
const keys=selected.type==="room"?["name","x","y","w","h","volume_m3"]:selected.type==="wall"?["source","target","kind","x1","y1","x2","y2"]:["kind","wall_id","position_t","initial_open_pct","max_area_m2","width_m","height_m"];
for(const k of keys){const label=document.createElement("label");label.textContent=k;const input=document.createElement("input");input.value=x[k]??"";input.addEventListener("change",()=>{const next=input.value;edit(()=>{if(k==="id")throw Error("ID must remain stable");if(next===""){delete x[k];return;}x[k]=typeof x[k]==="number"?Number(next):next;if(k==="wall_id"){const w=doc.walls.find(w=>w.id===next);if(!w)throw Error("unknown wall");x.source=w.source;x.target=w.target;}if(k==="position_t"&&(x[k]<0||x[k]>1))throw Error("position_t must be 0..1");});});label.append(input);f.append(label);}
}
function check(){if(!doc)return;const issues=[],roomIDs=new Set(doc.rooms.map(x=>x.id)),wallIDs=new Set(doc.walls.map(x=>x.id)),outside=doc.outside_id||"OUTSIDE";
for(const group of ["rooms","walls","openings"]){const ids=doc[group].map(x=>x.id);if(new Set(ids).size!==ids.length)issues.push("duplicate IDs in "+group);}
for(const r of doc.rooms){if(!(+r.w>0&&+r.h>0&&+r.volume_m3>0))issues.push("room "+r.id+" requires positive geometry and volume");}
for(const w of doc.walls){if(!roomIDs.has(w.source)&&w.source!==outside)issues.push("wall "+w.id+" unknown source");if(!roomIDs.has(w.target)&&w.target!==outside)issues.push("wall "+w.id+" unknown target");if(w.source===w.target)issues.push("wall "+w.id+" has same endpoints");}
for(const o of doc.openings){const w=doc.walls.find(w=>w.id===o.wall_id);if(!w)issues.push("opening "+o.id+" unknown wall");else if(o.source!==w.source||o.target!==w.target)issues.push("opening "+o.id+" mismatched wall endpoints");if(!(o.position_t>=0&&o.position_t<=1))issues.push("opening "+o.id+" out of wall");if(!(o.max_area_m2>0))issues.push("opening "+o.id+" missing positive area");}
el("report").textContent=issues.length?issues.join("\n"):"拓扑基本检查通过（不代表工程物理就绪）";el("status").textContent=issues.length?`${issues.length} geometry issues · Not physics-ready`:"Layout edit valid · Not physics-ready";el("status").className=issues.length?"warning":"status";
}
el("load-demo").onclick=async()=>{try{load(await (await fetch("./data/home_topology.fixed.json")).json());}catch(e){alert(e.message);}};
el("file").onchange=async e=>{try{load(JSON.parse(await e.target.files[0].text()));}catch(err){alert(err.message);}};
el("export").onclick=()=>{if(!doc)return;const blob=new Blob([JSON.stringify(doc,null,2)+"\n"],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="airtrajectory-layout.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
el("undo").onclick=()=>{if(!history.length)return;future.push(clone(doc));doc=history.pop();selected=null;update();};
el("redo").onclick=()=>{if(!future.length)return;history.push(clone(doc));doc=future.pop();selected=null;update();};
el("add-room").onclick=()=>{if(!doc)return;edit(()=>{const id="room-"+Date.now();doc.rooms.push({id,name:"NEW ROOM",x:120,y:90,w:230,h:170,volume_m3:30});selected={type:"room",id};});};
el("add-wall").onclick=()=>{if(!doc||!doc.rooms.length)return;
const source=selected?.type==="room"?selected.id:doc.rooms[0].id;
const choice=prompt("连接到哪个房间 ID？输入 OUTSIDE 代表外墙",doc.outside_id||"OUTSIDE");
if(choice===null)return;
const target=choice.trim();
if(target===source||!(target===(doc.outside_id||"OUTSIDE")||doc.rooms.some(r=>r.id===target))){alert("连接必须指向不同的已存在空间或 OUTSIDE");return;}
edit(()=>{const room=doc.rooms.find(r=>r.id===source),id="wall-"+Date.now();
const from=AirTrajectorySnapGeometry.snapEndpoint({x:room.x+room.w,y:room.y+25},doc.walls,15);
const to=AirTrajectorySnapGeometry.snapEndpoint({x:room.x+room.w,y:room.y+room.h-25},doc.walls,15);
doc.walls.push({id,kind:target===(doc.outside_id||"OUTSIDE")?"exterior":"internal",source,target,
x1:from.x,y1:from.y,x2:to.x,y2:to.y});
selected={type:"wall",id};});};
function addOpening(kind){if(!doc)return;const w=selected?.type==="wall"?find():doc.walls[0];if(!w)return;edit(()=>{const id=kind+"-"+Date.now();doc.openings.push({id,kind,wall_id:w.id,source:w.source,target:w.target,position_t:.5,initial_open_pct:0,max_area_m2:kind==="window"?1.2:1.8,render_side:"imported",position_editable:true,state_editable:true});selected={type:"opening",id};});}
el("add-window").onclick=()=>addOpening("window");el("add-door").onclick=()=>addOpening("door");
el("remove").onclick=()=>{if(!doc||!selected)return;const x=find();if(!x)return;edit(()=>{if(selected.type==="wall"&&doc.openings.some(o=>o.wall_id===x.id))throw Error("先删除所在墙的开口");if(selected.type==="room"&&doc.walls.some(w=>w.source===x.id||w.target===x.id))throw Error("先处理该房间连接的墙");doc[selected.type+"s"]=doc[selected.type+"s"].filter(a=>a.id!==x.id);selected=null;});};
window.AirTrajectoryStudio={
  getLayout:()=>doc?clone(doc):null,
  getSelection:()=>selected?{...selected}:null,
  select:pick,
  apply:edit,
  refresh:update,
  getSelected:find,
  addWallBetween:(start,end,source,target)=>{
    if(!doc||!doc.rooms.some(r=>r.id===source)||!(target===(doc.outside_id||"OUTSIDE")||doc.rooms.some(r=>r.id===target)))throw Error("invalid room connectivity");
    if(source===target||Math.hypot(end.x-start.x,end.y-start.y)<8)throw Error("wall is too short");
    edit(()=>{const id="wall-"+Date.now();doc.walls.push({id,kind:target===(doc.outside_id||"OUTSIDE")?"exterior":"internal",source,target,x1:start.x,y1:start.y,x2:end.x,y2:end.y});selected={type:"wall",id};});
  }
};
el("load-demo").click();
})();