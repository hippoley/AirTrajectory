(()=>{
"use strict";
const api=window.AirTrajectoryStudio,svg=document.getElementById("plan"),stage=document.getElementById("stage");
if(!api||!svg||!stage)return;
let mode="select",zoom=1,drawStart=null,preview=null,panStart=null,anchor=null;
const el=id=>document.getElementById(id);
const info=el("tool-hint");
const hints={select:"选择对象来编辑。拖动黄色窗户或蓝色房门可沿墙改变位置。",wall:"在画布上点击墙体起点，再点击终点，创建新的墙段。按 Esc 取消。",pan:"拖动画布以观察户型。按 V 返回选择。"};
const modeButtons=[...document.querySelectorAll("[data-mode]")];
function setMode(next){
 mode=next;drawStart=null;if(preview){preview.remove();preview=null;}
 modeButtons.forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));
 el("mode-label").textContent=({select:"选择模式",wall:"画墙模式",pan:"平移模式"})[mode];
 info.textContent=hints[mode];
 svg.style.cursor=mode==="pan"?"grab":mode==="wall"?"crosshair":"default";
}
modeButtons.forEach(b=>b.addEventListener("click",()=>setMode(b.dataset.mode)));
function toWorld(e){const c=svg.createSVGPoint();c.x=e.clientX;c.y=e.clientY;return c.matrixTransform(svg.getScreenCTM().inverse());}
function snap(p){
 const layout=api.getLayout();
 if(!layout)return p;
 const snapped=window.AirTrajectorySnapGeometry.snapEndpoint(p,layout.walls,17);
 const grid=n=>Math.round(n/20)*20;
 return snapped.wall_id?{x:snapped.x,y:snapped.y}:{x:grid(p.x),y:grid(p.y)};
}
function mark(x,y){const n=document.createElementNS("http://www.w3.org/2000/svg","circle");n.setAttribute("cx",x);n.setAttribute("cy",y);n.setAttribute("r",8);n.setAttribute("fill","#94ffd7");n.setAttribute("stroke","#12372d");n.setAttribute("stroke-width",2);n.setAttribute("pointer-events","none");svg.append(n);return n;}
function selectionSource(p){const layout=api.getLayout();if(!layout)return null;const s=api.getSelection();
 if(s?.type==="room"&&layout.rooms.some(r=>r.id===s.id))return s.id;
 const room=layout.rooms.find(r=>p.x>=r.x&&p.x<=r.x+r.w&&p.y>=r.y&&p.y<=r.y+r.h);
 return room?.id||layout.rooms[0]?.id||null;
}
svg.addEventListener("click",e=>{
 if(mode!=="wall"||!api.getLayout())return;
 // Capture click events above the editor scene in draw mode.
 e.preventDefault();e.stopImmediatePropagation();
 const p=snap(toWorld(e));
 if(!drawStart){drawStart={p,source:selectionSource(p)};preview=mark(p.x,p.y);info.textContent="已设定起点；点击画布设置终点。Esc 取消。";return;}
 const start=drawStart;drawStart=null;if(preview){preview.remove();preview=null;}
 if(Math.hypot(start.p.x-p.x,start.p.y-p.y)<8){info.textContent="墙段太短，请重新画墙。";return;}
 const layout=api.getLayout();let target=layout.outside_id||"OUTSIDE";
 const hit=layout.rooms.find(r=>r.id!==start.source&&p.x>=r.x&&p.x<=r.x+r.w&&p.y>=r.y&&p.y<=r.y+r.h);
 if(hit)target=hit.id;
 try{api.addWallBetween(start.p,p,start.source,target);info.textContent="墙体已添加，结构连接已更新。继续点击可绘制下一段。";}catch(err){info.textContent=err.message;}
},true);
svg.addEventListener("pointerdown",e=>{if(mode!=="pan")return;panStart={x:e.clientX,y:e.clientY};anchor={x:svg.style.translate?parseFloat(svg.dataset.panX||"0"):0,y:parseFloat(svg.dataset.panY||"0")};svg.setPointerCapture(e.pointerId);});
svg.addEventListener("pointermove",e=>{if(mode==="pan"&&panStart){const x=anchor.x+e.clientX-panStart.x,y=anchor.y+e.clientY-panStart.y;svg.dataset.panX=x;svg.dataset.panY=y;applyView();}});
svg.addEventListener("pointerup",()=>{panStart=null;anchor=null;});
function applyView(){svg.style.transform=`translate(${Number(svg.dataset.panX||0)}px,${Number(svg.dataset.panY||0)}px) scale(${zoom})`;el("zoom-label").textContent=Math.round(zoom*100)+"%";}
el("zoom-in").onclick=()=>{zoom=Math.min(2.5,+(zoom+.15).toFixed(2));applyView();};
el("zoom-out").onclick=()=>{zoom=Math.max(.45,+(zoom-.15).toFixed(2));applyView();};
el("zoom-fit").onclick=()=>{zoom=1;svg.dataset.panX=0;svg.dataset.panY=0;applyView();};
function syncScene(){
 const root=el("scene-list"),layout=api.getLayout();if(!layout)return;
 root.replaceChildren();
 for(const [type,rows]of [["room",layout.rooms],["wall",layout.walls],["opening",layout.openings]]){
  for(const row of rows){
   const button=document.createElement("button");button.className="scene-entry"+(api.getSelection()?.id===row.id?" selected":"");
   const label=document.createElement("span");label.textContent=(type==="room"?"▣ ":type==="wall"?"╱ ":"◫ ")+(row.name||row.id);
   const tag=document.createElement("small");tag.textContent=type.toUpperCase();
   button.append(label,tag);button.onclick=()=>{setMode("select");api.select(type,row.id);syncScene();};
   root.append(button);
  }
 }
}
const original=api.refresh;api.refresh=()=>{original();syncScene();};
const observer=new MutationObserver(()=>syncScene());
observer.observe(el("summary"),{childList:true,characterData:true,subtree:true});
svg.addEventListener("click",()=>queueMicrotask(syncScene));
document.addEventListener("keydown",e=>{
 const typing=["INPUT","TEXTAREA"].includes(document.activeElement?.tagName);
 if(typing)return;
 if(e.key==="Escape"){setMode("select");return;}
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"){e.preventDefault();el(e.shiftKey?"redo":"undo").click();return;}
 if(e.key.toLowerCase()==="v")setMode("select");
 if(e.key.toLowerCase()==="w")setMode("wall");
 if(e.key.toLowerCase()==="h")setMode("pan");
 if(e.key==="Delete"||e.key==="Backspace")el("remove").click();
});
setMode("select");syncScene();
})();